import logging
import requests
import time
from datetime import datetime, timedelta
from src.config import Config

logger = logging.getLogger(__name__)

class QuoteClient:
    def __init__(self, access_token, app_id):
        """
        :param access_token: Valid FYERS access token
        :param app_id: The App ID to prefix (e.g. "8090G65TJW" or "8090G65TJW-100")
        """
        self.access_token = access_token
        self.app_id = app_id
        # Note: History API uses a different base URL structure usually, but api-t1 works for data
        self.history_url = "https://api-t1.fyers.in/data/history"

    def get_52_week_data(self, symbols):
        """
        Fetches 52-Week High and Low for the given symbols using History API.
        This is resource intensive (1 call per symbol).
        """
        if not symbols:
            return {}
        
        results = {}
        headers = {
            "Authorization": f"{self.app_id}:{self.access_token}"
        }
        
        # Date Range: Last 365 days
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        range_to = end_date.strftime("%Y-%m-%d")
        range_from = start_date.strftime("%Y-%m-%d")

        logger.info(f"Fetching History (1Y) for {len(symbols)} symbols to calculate 52W H/L...")

        for symbol in symbols:
            retries = 3
            backoff = 2
            
            for attempt in range(retries):
                try:
                    # API Params: symbol, resolution=D, date_format=1, range_from, range_to
                    params = {
                        "symbol": symbol,
                        "resolution": "D",
                        "date_format": "1",
                        "range_from": range_from,
                        "range_to": range_to,
                        "cont_flag": "1"
                    }
                    
                    res = requests.get(self.history_url, headers=headers, params=params)
                    data = res.json()
                    
                    if data.get("s") == "ok" and data.get("candles"):
                        # Candles format: [timestamp, open, high, low, close, volume]
                        # Index 2 = High, Index 3 = Low
                        candles = data["candles"]
                        # Just to be safe, filter invalid candles
                        valid_candles = [c for c in candles if len(c) > 3]
                        if valid_candles:
                            highs = [c[2] for c in valid_candles]
                            lows = [c[3] for c in valid_candles]
                            results[symbol] = {
                                "52h": max(highs) if highs else 0,
                                "52l": min(lows) if lows else 0
                            }
                        else:
                             results[symbol] = {"52h": 0, "52l": 0}
                        break # Success, move to next symbol

                    elif data.get("s") == "error":
                        msg = data.get("message", "").lower()
                        if "limit reached" in msg:
                            logger.warning(f"Rate limit hit for {symbol}. Retrying in {backoff}s...")
                            time.sleep(backoff)
                            backoff *= 2 # Exponential backoff
                            continue # Retry
                        else:
                            logger.warning(f"History fetch failed for {symbol}: {data.get('message')}")
                            results[symbol] = {"52h": 0, "52l": 0}
                            break # Non-retryable error
                    else:
                        # Unknown state
                        results[symbol] = {"52h": 0, "52l": 0}
                        break

                except Exception as e:
                    logger.error(f"Error calculating 52W for {symbol}: {e}")
                    results[symbol] = {"52h": 0, "52l": 0}
                    break
            
            # Rate limit protection (sleep between symbols)
            time.sleep(0.5) # slowed down from 0.1 to 0.5 to prevent hitting limit


        return results

    def test_depth(self, symbol):
        # ... removed or kept only for debug ...
        pass
