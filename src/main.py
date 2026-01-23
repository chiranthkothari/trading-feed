import logging
import time
import socket
import sys

# Set global timeout to prevent hangs (e.g. infinite API calls)
socket.setdefaulttimeout(60)
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
        self.last_update_times = {} # Key: Symbol, Value: timestamp (for staleness detection)
        self.symbol_rank = {} # Key: Symbol, Value: Index (from Config sheet)
        
        # Initialize Modules
        self.notifier = TelegramNotifier()
        self.market_hours = MarketHoursController()
        
        self.auth = FyersAuthenticator(on_error=self.notifier.send_alert)
        self.sheets = SheetsClient(on_error=self.notifier.send_alert)
        self.ws_client = None
        self.quote_client = None

        # Config Refresh
        self.last_config_refresh_time = time.time()
        self.config_refresh_interval = Config.CONFIG_REFRESH_INTERVAL

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
        """Callback for WebSocket data. Handles both single and batch messages."""
        try:
            # Handle batch messages (list of ticks from SDK)
            if isinstance(message, list):
                for tick in message:
                    self._process_single_tick(tick)
                return
            
            # Handle single tick
            self._process_single_tick(message)
            
        except Exception as e:
            logger.error(f"Error processing tick batch: {e}")

    def _merge_row_data(self, existing_row, new_row):
        """
        Merge new row with existing, preserving non-zero values for critical fields.
        This prevents partial ticks (with zeros) from overwriting good data.
        """
        merged = new_row[:]
        
        # Fields that should never be zero in valid market data
        # Indices: 2=prev_close, 3=open, 4=high, 5=low
        # We preserve these from existing if new value is 0
        preserve_if_zero_indices = [2, 3, 4, 5]
        
        for idx in preserve_if_zero_indices:
            if idx < len(merged) and idx < len(existing_row):
                if merged[idx] == 0 and existing_row[idx] != 0:
                    merged[idx] = existing_row[idx]
                    logger.debug(f"Preserved existing value for index {idx}: {existing_row[idx]}")
        
        # Recalculate change values if we preserved prev_close
        if merged[2] != new_row[2] and merged[2] > 0 and merged[6] > 0:
            ltp = merged[6]
            prev_close = merged[2]
            change_rs = ltp - prev_close
            change_pct = (change_rs / prev_close) * 100
            merged[9] = round(change_rs, 2)
            merged[10] = round(change_pct, 2)
        
        return merged

    def _process_single_tick(self, tick):
        """Process a single tick message with validation and smart merging."""
        try:
            # Validate tick before processing
            if not DataNormalizer.is_valid_tick(tick):
                logger.debug(f"Ignoring invalid tick: {tick.get('symbol', 'UNKNOWN') if isinstance(tick, dict) else 'non-dict'}")
                return
            
            # Normalize
            normalized_row = DataNormalizer.normalize_market_data(tick)
            if not normalized_row:
                return
                
            symbol = normalized_row[0]
            
            # Check if this symbol is still active in our config
            if symbol not in self.symbol_rank:
                return

            # ENRICH IMMEDIATELY (Prevent flicker)
            # Apply 52W data if available
            meta = self.symbol_metadata.get(symbol, {})
            
            # Dynamic update of 52W High/Low
            ltp = normalized_row[6]
            if ltp > 0:
                current_52h = meta.get("52h", 0)
                current_52l = meta.get("52l", 0)
                
                updated = False
                if ltp > current_52h:
                    meta["52h"] = ltp
                    updated = True
                
                if current_52l == 0 or ltp < current_52l:
                    meta["52l"] = ltp
                    updated = True
                
                if updated:
                    # self.symbol_metadata stores reference to 'meta', so it updates globally
                    pass

            if meta and len(normalized_row) > 14:
                 normalized_row[13] = meta.get("52h", 0)
                 normalized_row[14] = meta.get("52l", 0)

            with self.buffer_lock:
                # Smart merge: preserve good values if new tick has zeros
                existing_row = self.market_data_buffer.get(symbol)
                if existing_row:
                    normalized_row = self._merge_row_data(existing_row, normalized_row)
                
                self.market_data_buffer[symbol] = normalized_row
                self.last_update_times[symbol] = time.time()
                
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

        logger.info(f"Checking for Config updates (Internal: {self.config_refresh_interval}s)...")
        
        try:
            new_instruments = self.sheets.read_config()
            # Mark that we successfully checked
            self.last_config_refresh_time = time.time()
            
            if not new_instruments:
                logger.warning("Config refresh returned empty. Ignoring.")
                return

            old_symbols_list = [inst['Symbol'] for inst in self.instruments]
            new_symbols_list = [inst['Symbol'] for inst in new_instruments]
            
            old_symbols_set = set(old_symbols_list)
            new_symbols_set = set(new_symbols_list)

            added = new_symbols_set - old_symbols_set
            removed = old_symbols_set - new_symbols_set
            reordered = (not added and not removed and old_symbols_list != new_symbols_list)

            if not added and not removed and not reordered:
                logger.debug("No config changes detected.")
                return

            if reordered:
                logger.info("Config reordering detected.")
            else:
                logger.info(f"Config changes detected! Added: {len(added)}, Removed: {len(removed)}")

            # Update State
            self.instruments = new_instruments
            self.symbol_rank = {inst['Symbol']: i for i, inst in enumerate(self.instruments)}
            
            # Handle WebSocket Subscriptions
            if self.ws_client and self.ws_client.is_connected:
                if removed:
                    logger.info(f"Unsubscribing from {len(removed)} symbols: {list(removed)}")
                    self.ws_client.unsubscribe(list(removed))
                    # Clean buffer
                    with self.buffer_lock:
                        for sym in removed:
                            self.market_data_buffer.pop(sym, None)
                            self.last_update_times.pop(sym, None)
                            self.symbol_metadata.pop(sym, None)
                
                if added:
                    logger.info(f"Subscribing to {len(added)} new symbols: {list(added)}")
                    self.ws_client.subscribe(list(added))
                    
                    # Fetch 52W for new symbols
                    if self.quote_client:
                        try:
                            logger.info(f"Fetching 52W data for {len(added)} new symbols...")
                            new_meta = self.quote_client.get_52_week_data(list(added))
                            if new_meta:
                                self.symbol_metadata.update(new_meta)
                        except Exception as e:
                            logger.error(f"Failed to fetch 52W for new symbols: {e}")
            else:
                logger.warning("WS client not connected, skipping subscription update. Will be handled by main loop.")

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

                self.symbol_rank = {inst['Symbol']: i for i, inst in enumerate(self.instruments)}
                
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
                    
                    # Sort by symbol to ensure consistent row ordering (based on Config rank)
                    # Use a large number (9999) for symbols not found in rank to place them at the end
                    rows.sort(key=lambda x: self.symbol_rank.get(x[0], 9999) if x else 9999)
                    
                    # Staleness detection: warn about symbols not receiving updates
                    current_time = time.time()
                    stale_threshold = 60  # seconds
                    with self.buffer_lock:
                        stale_symbols = [
                            sym for sym, last_update in self.last_update_times.items()
                            if current_time - last_update > stale_threshold
                        ]
                    if stale_symbols:
                        logger.warning(f"Stale symbols (no updates for {stale_threshold}s): {stale_symbols}")
                        # Auto-resubscribe stale symbols
                        if self.ws_client and self.ws_client.is_connected:
                            logger.info(f"Re-subscribing to {len(stale_symbols)} stale symbols...")
                            try:
                                self.ws_client.subscribe(stale_symbols)
                                # Reset their update times to avoid immediate re-trigger
                                with self.buffer_lock:
                                    for sym in stale_symbols:
                                        self.last_update_times[sym] = time.time()
                            except Exception as e:
                                logger.error(f"Failed to re-subscribe stale symbols: {e}")
                    
                    if rows:
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
