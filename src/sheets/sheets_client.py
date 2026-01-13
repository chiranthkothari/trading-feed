import gspread
import logging
import time
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError
from src.config import Config

logger = logging.getLogger(__name__)

class SheetsClient:
    def __init__(self, on_error=None):
        self.config_sheet_name = "Config"
        self.live_data_sheet_name = "Live Data"
        self.client = None
        self.sheet = None
        self.on_error = on_error
        self.scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]

    def connect(self):
        """Authenticates with Google Sheets API."""
        try:
            creds = Credentials.from_service_account_file(
                Config.GOOGLE_SERVICE_ACCOUNT_JSON_PATH, 
                scopes=self.scopes
            )
            self.client = gspread.authorize(creds)
            self.sheet = self.client.open_by_key(Config.GOOGLE_SHEET_ID)
            logger.info("Connected to Google Sheets successfully.")
            return True
        except Exception as e:
            msg = f"Failed to connect to Google Sheets: {e}"
            logger.error(msg)
            if self.on_error: self.on_error("SHEETS_CONN_ERROR", msg)
            raise

    def read_config(self):
        """
        Reads the 'Config' sheet and returns a list of enabled instruments.
        Expected columns: Symbol, Instrument Type, Enabled
        Returns: List of dicts [{'symbol': '...', 'type': '...'}, ...]
        """
        try:
            worksheet = self.sheet.worksheet(self.config_sheet_name)
            records = worksheet.get_all_records()
            
            enabled_instruments = [
                row for row in records 
                if str(row.get("Enabled", "")).upper() == "TRUE"
            ]
            logger.info(f"Loaded {len(enabled_instruments)} enabled instruments from config.")
            return enabled_instruments
        except Exception as e:
            logger.error(f"Failed to read config sheet: {e}")
            raise

    def write_live_data(self, data, retries=3):
        """
        Writes a batch of data to the 'Live Data' sheet.
        data: List of lists (rows) to append/update.
        Strategy: Clear sheet content (except header) and rewrite? 
                  Or update in place?
        For a live dashboard, 'update in place' usually implies mapping symbols to rows.
        However, clearing and writing fresh sorted data is simpler and robuster for keeping list clean.
        
        Let's implement: Clear all rows > 1, then batch update.
        """
        for attempt in range(1, retries + 1):
            try:
                worksheet = self.sheet.worksheet(self.live_data_sheet_name)
                
                # We assume data matches the header columns order defined in PRD
                # Row 1 is header.
                
                # Check if we have data
                if not data:
                    return

                # Option 1: Append (if historical). 
                # Option 2: Overwrite (Live View). THIS IS A LIVE FEEDER.
                # To reduce API calls:
                # 1. Clear range A2:Z1000
                # 2. Update range A2
                
                # Note: clearing entire sheet can flicker. 
                # Better optimization: Update specific range if size constant. 
                # But simple reliable approach first:
                
                # Define range to update
                num_rows = len(data)
                num_cols = len(data[0]) if num_rows > 0 else 0
                
                # Helper to convert explicit values to batch update
                # gspread update method
                
                end_col_letter = chr(64 + num_cols) # Simple A-Z mapper (works for < 26 cols)
                # PRD has ~15 cols. So 'O'.
                
                cell_range = f"A2:{end_col_letter}{num_rows + 1}"
                
                worksheet.update(values=data, range_name=cell_range)
                
                # Clear stale rows beyond the current data
                # Start clearing from the row after the last data row
                clear_start_row = num_rows + 2
                # We want to clear everything below. A safe large range is usually enough, 
                # or we can just clear a reasonable chunk. 
                # Better: Clear from start_row to end of sheet. 
                # 'A{row}:Z' implies to the end of sheet in gspread if supported, or we pick a large number.
                # Let's use a large number (e.g., 2000) to be safe for this use case.
                clear_range = f"A{clear_start_row}:Z2000"
                worksheet.batch_clear([clear_range])
                
                logger.debug(f"Updated {num_rows} rows and cleared stale data starting from row {clear_start_row}.")
                return

            except APIError as e:
                # Rate limit handling (Quota exceeded)
                if e.response.status_code == 429:
                    logger.warning(f"Rate limit exceeded (429). Retrying in {2**attempt}s...")
                    time.sleep(2 ** attempt)
                else:
                    logger.error(f"Google Sheets API Error: {e}")
                    if self.on_error: self.on_error("SHEETS_API_ERROR", str(e))
                    raise
            except Exception as e:
                logger.error(f"Write failed: {e}")
                if attempt == retries:
                     if self.on_error: self.on_error("SHEETS_WRITE_ERROR", str(e))
                     raise
                time.sleep(2 ** attempt)
