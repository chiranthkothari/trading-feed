import logging
import time
import sys
import signal
import threading
import base64
import json
import os
from datetime import datetime
from src.config import Config
from src.auth.fyers_auth import FyersAuthenticator
from src.sheets.sheets_client import SheetsClient
from src.market.websocket_client import MarketDataClient
from src.market.data_normalizer import DataNormalizer
from src.scheduler.market_hours import MarketHoursController
from src.notifications.telegram import TelegramNotifier
from src.market.quote_client import QuoteClient

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("Main")

class TradingFeederApp:
    def __init__(self):
        self.stop_event = threading.Event()
        self.market_data_buffer = {} # Key: Symbol, Value: Row List
        self.buffer_lock = threading.Lock()
        self.instruments = [] # List of config dicts
        self.symbol_metadata = {} # 52W Data cache
        
        # Initialize Modules
        self.notifier = TelegramNotifier()
        self.market_hours = MarketHoursController()
        
        self.auth = FyersAuthenticator(on_error=self.notifier.send_alert)
        self.sheets = SheetsClient(on_error=self.notifier.send_alert)
        self.ws_client = None
        self.quote_client = None

        # Config Refresh
        self.last_config_refresh_time = time.time()
        self.config_refresh_interval = 300 # 5 Minutes

    def handle_shutdown(self, signum, frame):
        logger.info("Shutdown signal received. Exiting...")
        self.stop_event.set()
        if self.ws_client:
            try:
                self.ws_client.unsubscribe(list(self.market_data_buffer.keys()))
            except:
                pass
        sys.exit(0)

    def on_market_data(self, message):
        """Callback for WebSocket data."""
        try:
            # Normalize
            normalized_row = DataNormalizer.normalize_market_data(message)
            if normalized_row:
                symbol = normalized_row[0]
                
                # ENRICH IMMEDIATELY (Prevent flicker)
                # Apply 52W data if available
                meta = self.symbol_metadata.get(symbol, {})
                if meta and len(normalized_row) > 14:
                     normalized_row[13] = meta.get("52h", 0)
                     normalized_row[14] = meta.get("52l", 0)

                with self.buffer_lock:
                    self.market_data_buffer[symbol] = normalized_row
            else:
                pass 
        except Exception as e:
            logger.error(f"Error processing tick: {e}")

    def on_ws_error(self, code, message):
        """Callback for WebSocket errors."""
        logger.error(f"WS Error [{code}]: {message}")
        # Only alert on critical errors, not benign disconnects if reconnect is handled
        if code not in [-100, -200]: # Example benign codes, tune as needed
            self.notifier.send_alert(f"WS Error {code}", str(message))

    def get_app_id_from_token(self, token):
        try:
            if "." not in token: return None
            # JWT is header.payload.signature
            payload_part = token.split('.')[1]
            # Add padding if needed
            payload_part += '=' * (-len(payload_part) % 4)
            decoded = base64.b64decode(payload_part)
            data = json.loads(decoded)
            return data.get("app_id")
        except Exception as e:
            logger.error(f"Failed to extract App ID from token: {e}")
            return None
            return None

    def refresh_config_if_needed(self):
        """Checks if config needs refresh and updates subscriptions."""
        if time.time() - self.last_config_refresh_time < self.config_refresh_interval:
            return

        logger.info("Checking for Config updates...")
        self.last_config_refresh_time = time.time()
        
        try:
            new_instruments = self.sheets.read_config()
            if not new_instruments:
                logger.warning("Config refresh returned empty. Ignoring.")
                return

            old_symbols = set(inst['Symbol'] for inst in self.instruments)
            new_symbols = set(inst['Symbol'] for inst in new_instruments)

            added = new_symbols - old_symbols
            removed = old_symbols - new_symbols

            if not added and not removed:
                logger.info("No config changes detected.")
                return

            logger.info(f"Config changes detected! Added: {len(added)}, Removed: {len(removed)}")

            # Update State
            self.instruments = new_instruments
            
            # Handle WebSocket Subscriptions
            if self.ws_client and self.ws_client.is_connected:
                if removed:
                    logger.info(f"Unsubscribing from {len(removed)} symbols...")
                    self.ws_client.unsubscribe(list(removed))
                    # Clean buffer
                    with self.buffer_lock:
                        for sym in removed:
                            self.market_data_buffer.pop(sym, None)
                
                if added:
                    logger.info(f"Subscribing to {len(added)} new symbols...")
                    self.ws_client.subscribe(list(added))
                    
                    # Fetch 52W for new symbols
                    if self.quote_client:
                        try:
                            logger.info("Fetching 52W data for new symbols...")
                            new_meta = self.quote_client.get_52_week_data(list(added))
                            self.symbol_metadata.update(new_meta)
                        except Exception as e:
                            logger.error(f"Failed to fetch 52W for new symbols: {e}")

        except Exception as e:
            logger.error(f"Config refresh failed: {e}")

    def run(self):
        logger.info("Starting Trading Feeder Application...")
        
        try:
            Config.validate()
        except Exception as e:
            self.notifier.send_alert("STARTUP_ERROR", f"Config validation failed: {e}")
            sys.exit(1)

        # Initial Connect to Sheets to check config presence
        try:
            self.sheets.connect()
        except Exception:
             sys.exit(1)

        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        self.notifier.send_alert("INFO", "Trading Feeder Started.")
        
        # Main Loop
        while not self.stop_event.is_set():
            try:
                # 1. Market Hours Check
                if not self.market_hours.is_market_open():
                    logger.info("Market is closed. Waiting for open...")
                    
                    if self.ws_client and self.ws_client.is_connected:
                         logger.info("Disconnecting WebSocket for market close.")
                         # In fyers api v3, we assume cleanup happens or we just let loop idle
                         pass 
                         
                    self.market_hours.wait_for_market_open()
                    logger.info("Waking up! Market should be opening soon.")
                    continue

                # 2. Authentication
                logger.info("Authenticating with FYERS...")
                access_token = self.auth.authenticate()
                if not access_token:
                    logger.error("Authentication failed. Retrying in 60s...")
                    time.sleep(60)
                    continue

                # 3. Read Config
                self.instruments = self.sheets.read_config()
                if not self.instruments:
                    logger.warning("No enabled instruments found in Config sheet.")
                    time.sleep(60)
                    continue
                
                symbols_to_subscribe = [inst['Symbol'] for inst in self.instruments]
                logger.info(f"Targeting {len(symbols_to_subscribe)} instruments.")
                
                # Determine App ID
                extracted_app_id = self.get_app_id_from_token(access_token)
                if extracted_app_id:
                    logger.info(f"Detected App ID from token: {extracted_app_id}")
                    app_id_to_use = extracted_app_id
                else:
                    logger.warning("Could not extract App ID. Fallback to Config.")
                    app_id_to_use = Config.FYERS_APP_ID

                # 3.5 Fetch 52-Week Data (History API)
                logger.info("Fetching 52-Week High/Low data via History API...")
                try:
                    self.quote_client = QuoteClient(access_token, app_id=app_id_to_use)
                    self.symbol_metadata = self.quote_client.get_52_week_data(symbols_to_subscribe)
                    if not self.symbol_metadata:
                        logger.warning("No 52-week data fetched. Columns will be 0.")
                except Exception as e:
                    logger.error(f"Failed to fetch 52-week data: {e}")

                # 4. WebSocket Setup
                ws_token = f"{app_id_to_use}:{access_token}" if ":" not in access_token else access_token

                self.ws_client = MarketDataClient(
                    access_token=ws_token,
                    on_message=self.on_market_data,
                    on_error=self.on_ws_error
                )
                self.ws_client.connect()
                
                # Wait a bit for connection
                time.sleep(2) 
                
                if self.ws_client.is_connected:
                    self.ws_client.subscribe(symbols_to_subscribe)
                    logger.info("Subscribed to instruments.")
                else:
                    logger.error("WS Connect failed. Retrying loop.")
                    time.sleep(5)
                    continue

                # 5. Runtime Loop (Streaming)
                logger.info("Entering streaming loop...")
                
                # We use a simple sleep loop corresponding to the update interval
                # write_interval = 4 (from User request)
                
                while self.market_hours.is_market_open() and not self.stop_event.is_set():
                    # Check for Config Refresh
                    self.refresh_config_if_needed()

                    time.sleep(4) # Rate limit protection (4s latency)
                    
                    with self.buffer_lock:
                        rows = list(self.market_data_buffer.values())
                    
                    if rows:
                        # Force Update Timestamp for Liveness (Index 15) -> REMOVED to fix market close bug
                        # We only want to update if data actually changes.
                        # current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        # for row in rows:
                        #     if len(row) > 15:
                        #         row[15] = current_time_str
                        
                        logger.info(f"Writing {len(rows)} rows to Live Data sheet...")
                        self.sheets.write_live_data(rows)
                    else:
                        logger.debug("No data to write.")

            except Exception as e:
                logger.critical(f"Critical Main Loop Failure: {e}", exc_info=True)
                self.notifier.send_alert("CRITICAL_FAILURE", f"Main loop crashed: {e}")
                time.sleep(10) # Avoid rapid crash loops

if __name__ == "__main__":
    app = TradingFeederApp()
    app.run()
