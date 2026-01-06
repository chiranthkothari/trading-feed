import logging
import time
import sys
import signal
import threading
import base64
import json
import os
import certifi
from src.config import Config
from src.auth.fyers_auth import FyersAuthenticator
from src.sheets.sheets_client import SheetsClient
from src.market.websocket_client import MarketDataClient
from src.market.data_normalizer import DataNormalizer
from src.notifications.telegram import TelegramNotifier
from src.market.quote_client import QuoteClient

# Fix SSL context for Mac
os.environ['SSL_CERT_FILE'] = certifi.where()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("TestFeed")

# Sample Symbols to Add
SAMPLE_SYMBOLS = [
    ["NSE:SBIN-EQ", "EQUITY", "TRUE"],
    ["NSE:RELIANCE-EQ", "EQUITY", "TRUE"],
    ["NSE:HDFCBANK-EQ", "EQUITY", "TRUE"],
    ["NSE:INFY-EQ", "EQUITY", "TRUE"],
    ["NSE:TCS-EQ", "EQUITY", "TRUE"],
    ["NSE:NIFTY50-INDEX", "INDEX", "TRUE"],
    ["NSE:NIFTYBANK-INDEX", "INDEX", "TRUE"],
    # Assuming valid Jan 2026 Future Symbol. If invalid, API will just return error or no data for it.
    ["NSE:NIFTY26JANFUT", "FUTURE", "TRUE"],
    ["NSE:NIFTY26JAN25000CE", "OPTION", "TRUE"]
]

class TestFeeder:
    def __init__(self):
        self.stop_event = threading.Event()
        self.market_data_buffer = {} 
        self.buffer_lock = threading.Lock()
        
        self.notifier = TelegramNotifier()
        self.auth = FyersAuthenticator() # No error callback for test
        self.sheets = SheetsClient()
        self.ws_client = None
        self.quote_client = None
        self.symbol_metadata = {}

    def setup_config_sheet(self):
        """Populates the Config sheet with sample data."""
        logger.info("Populating 'Config' sheet with sample symbols...")
        try:
            self.sheets.connect()
            
            # Ensure Config tab exists
            try:
                ws = self.sheets.sheet.worksheet("Config")
            except Exception:
                logger.info("'Config' tab not found. Creating it...")
                ws = self.sheets.sheet.add_worksheet(title="Config", rows=100, cols=10)

            # Ensure Live Data tab exists
            live_headers = [
                "Symbol", "Date", "Prev Close", "Open", "High", "Low", "LTP", 
                "Volume", "Value", "Chg", "Chg%", "Bid", "Ask", 
                "52W H", "52W L", "Updated At"
            ]
            try:
                live_ws = self.sheets.sheet.worksheet("Live Data")
                # Update headers if needed, but primarily ensure sheet exists.
                live_ws.update(range_name="A1", values=[live_headers])
            except Exception:
                logger.info("'Live Data' tab not found. Creating it...")
                live_ws = self.sheets.sheet.add_worksheet(title="Live Data", rows=1000, cols=20)
                live_ws.update(range_name="A1", values=[live_headers])

            # Clear and write header + data
            ws.clear()
            ws.update(range_name="A1", values=[["Symbol", "Instrument Type", "Enabled"]] + SAMPLE_SYMBOLS)
            logger.info("Config sheet updated successfully.")
        except Exception as e:
            logger.error(f"Failed to update Config sheet: {e}")
            sys.exit(1)

    def on_market_data(self, message):
        # logger.debug(f"DEBUG RAW MSG: {message}") 
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
        except Exception as e:
            logger.error(f"Error processing tick: {e}")

    def on_ws_error(self, code, message):
        logger.error(f"WS Error [{code}]: {message}")

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

    def run(self):
        # 1. Setup Sheet
        self.setup_config_sheet()

        # 2. Auth
        logger.info("Authenticating with FYERS...")
        access_token = self.auth.authenticate()
        if not access_token:
            logger.error("Authentication failed.")
            return

        # 3. Read Config
        instruments = self.sheets.read_config()
        symbols = [inst['Symbol'] for inst in instruments]
        logger.info(f"Loaded {len(symbols)} instruments for testing.")

        # Determine App ID (Critical for both Quotes and WS)
        extracted_app_id = self.get_app_id_from_token(access_token)
        if extracted_app_id:
            logger.info(f"Detected App ID from token: {extracted_app_id}")
            app_id_to_use = extracted_app_id
        else:
            logger.warning("Could not extract App ID. Fallback to Config.")
            app_id_to_use = Config.FYERS_APP_ID

        # 3.5 Fetch 52-Week Data (Quotes)
        logger.info("Fetching 52-Week High/Low data via Quote API...")
        try:
            self.quote_client = QuoteClient(access_token, app_id=app_id_to_use)
            self.symbol_metadata = self.quote_client.get_52_week_data(symbols)
            if not self.symbol_metadata:
                 logger.warning("No 52-week data fetched. Columns will be 0.")
        except Exception as e:
            logger.error(f"Failed to init QuoteClient or fetch data: {e}")

        # 4. Connect WS
        ws_token = f"{app_id_to_use}:{access_token}" if ":" not in access_token else access_token
            
        self.ws_client = MarketDataClient(
            access_token=ws_token,
            on_message=self.on_market_data,
            on_error=self.on_ws_error
        )
        self.ws_client.connect()
        time.sleep(2)
        
        if self.ws_client.is_connected:
            self.ws_client.subscribe(symbols)
            logger.info("Subscribed to symbols. Streaming data... (Press Ctrl+C to stop)")
        else:
            logger.error("WS Connection failed.")
            return

        # 5. Loop
        try:
            while True:
                # User requested slower updates (3s+ latency) to avoid throttling
                time.sleep(4)
                with self.buffer_lock:
                    # Rows are already enriched in on_market_data
                    rows = list(self.market_data_buffer.values())
                
                if rows:
                    # Rows are already enriched in on_market_data with quotes
                    
                    # Force Update Timestamp for Liveness (Index 15) -> REMOVED
                    # This ensures "Updated At" changes every cycle even if no new ticks arrive
                    # from datetime import datetime
                    # current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    # for row in rows:
                    #     if len(row) > 15:
                    #          row[15] = current_time_str

                    logger.info(f"Writing {len(rows)} rows to Live Data sheet...")
                    self.sheets.write_live_data(rows)
                else:
                    logger.info("No data received yet...")

        except KeyboardInterrupt:
            logger.info("Stopping test...")
            if self.ws_client:
                self.ws_client.unsubscribe(symbols)

if __name__ == "__main__":
    TestFeeder().run()
