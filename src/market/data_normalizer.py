import logging
from datetime import datetime
import time

logger = logging.getLogger(__name__)

class DataNormalizer:
    @staticmethod
    def normalize_market_data(raw_data):
        """
        Normalizes raw FYERS WebSocket data into a format suitable for Google Sheets.
        
        Expected Input (raw_data): Dict or Object with keys like:
        - symbol
        - ltp
        - open_price
        - high_price
        - low_price
        - prev_close_price
        - vol_traded_today (Volume)
        - last_traded_time (Epoch)
        
        Expected Output: List representing a row in Sheets (or Dict for mapping).
        PRD Columns:
        0. Symbol
        1. Date
        2. Prev Close
        3. Open
        4. High
        5. Low
        6. LTP
        7. Volume
        8. Traded Value (Calculated/Raw)
        9. Change (Rs)
        10. Change (%)
        11. Bid
        12. Ask
        13. 52W High
        14. 52W Low
        15. Updated At
        """
        try:
            # Handle potential list input (batch) - though usually we process one tick at a time
            # If raw_data is a list, we might need to loop. Assuming single dict here.
            
            if not isinstance(raw_data, dict):
                logger.warning(f"Invalid data format received: {type(raw_data)}")
                return None

            symbol = raw_data.get("symbol", "")
            if not symbol:
                return None

            # Extract basic fields with defaults
            ltp = raw_data.get("ltp", 0)
            open_price = raw_data.get("open_price", 0)
            high_price = raw_data.get("high_price", 0)
            low_price = raw_data.get("low_price", 0)
            prev_close = raw_data.get("prev_close_price", 0)
            volume = raw_data.get("vol_traded_today", 0)
            
            # Traded Value (Turnover)
            # Try standard keys 'val_traded' or 'value'
            traded_value = raw_data.get("val_traded", raw_data.get("value", 0))
            
            # If 0, try to calculate: Volume * AvgPrice (if available)
            if traded_value == 0 and volume > 0:
                 avg_price = raw_data.get("avg_trade_price", 0)
                 if avg_price > 0:
                     traded_value = volume * avg_price
                 else:
                     # Fallback: Approximate using LTP (Inaccurate but better than 0 for visual)
                     traded_value = volume * ltp
            
            # Bid/Ask
            # V3 often gives 'bid_price' and 'ask_price' in full mode
            bid = raw_data.get("bid_price", 0)
            ask = raw_data.get("ask_price", 0)
            
            # 52W High/Low - usually in meta or depth, maybe not in simple tick?
            # If missing, use 0.
            fifty_two_high = 0 # raw_data.get("upper_circuit", 0) # Placeholder
            fifty_two_low = 0 # raw_data.get("lower_circuit", 0) # Placeholder
            
            # Timestamp
            raw_time = raw_data.get("last_traded_time", time.time())
            try:
                last_traded_time = float(raw_time)
                # Check if ms (13 digits) or sec (10 digits)
                if last_traded_time > 10**11: # 10^11 covers all reasonable MS timestamps
                    last_traded_time = last_traded_time / 1000
                
                dt_object = datetime.fromtimestamp(last_traded_time)
                # updated_at = dt_object.strftime('%Y-%m-%d %H:%M:%S') # Old behavior: Trade Time
                date_str = dt_object.strftime('%Y-%m-%d')
            except ValueError:
                # Fallback if casting fails
                # updated_at = str(raw_time)
                date_str = datetime.now().strftime('%Y-%m-%d')
            
            # Change: User wants to see liveness. "Updated At" should be System Time (Fetch Time)
            updated_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Calculations
            change_rs = 0
            change_pct = 0.0
            
            if prev_close > 0:
                change_rs = ltp - prev_close
                change_pct = (change_rs / prev_close) * 100
            
            # Create Row List (Order matters for Sheets!)
            row = [
                symbol,          # 0
                date_str,        # 1
                prev_close,      # 2
                open_price,      # 3
                high_price,      # 4
                low_price,       # 5
                ltp,             # 6
                volume,          # 7
                traded_value,    # 8
                round(change_rs, 2), # 9
                round(change_pct, 2),# 10
                bid,             # 11
                ask,             # 12
                fifty_two_high,  # 13
                fifty_two_low,   # 14
                updated_at       # 15
            ]
            
            return row

        except Exception as e:
            logger.error(f"Error normalizing data: {e} | Data: {raw_data}")
            return None
