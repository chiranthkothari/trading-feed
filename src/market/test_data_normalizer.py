import pytest
from datetime import datetime
import time
from src.market.data_normalizer import DataNormalizer

def test_normalize_valid_full_data():
    raw = {
        "symbol": "NSE:RELIANCE-EQ",
        "ltp": 2500.0,
        "open_price": 2480.0,
        "high_price": 2510.0,
        "low_price": 2475.0,
        "prev_close_price": 2450.0,
        "vol_traded_today": 100000,
        "bid_price": 2499.0,
        "ask_price": 2501.0,
        "last_traded_time": 1700000000 # 2023-11-14 ...
    }
    
    row = DataNormalizer.normalize_market_data(raw)
    
    assert row is not None
    assert row[0] == "NSE:RELIANCE-EQ" # Symbol
    assert row[6] == 2500.0 # LTP
    
    # Check Calculations
    # Change = 2500 - 2450 = 50.0
    # % = 50 / 2450 * 100 = 2.04%
    assert row[9] == 50.0
    assert row[10] == 2.04
    
    # Check Timestamp
    # 1700000000 -> 2023-11-14 ...
    assert "2023-11-15" in row[15] or "2023-11-14" in row[15] # Timezone dependent roughly, exact check below
    # Using datetime.fromtimestamp in code uses local timezone. 
    # Let's just verify format roughly matches YYYY-MM-DD
    assert len(row[15].split(" ")) == 2 # "YYYY-MM-DD HH:MM:SS"

def test_normalize_missing_fields_defaults():
    raw = {"symbol": "NSE:TCS-EQ"} # Minimal
    row = DataNormalizer.normalize_market_data(raw)
    
    assert row is not None
    assert row[0] == "NSE:TCS-EQ"
    assert row[6] == 0 # LTP Default
    assert row[9] == 0 # Change Rs
    assert row[10] == 0.0 # Change %

def test_normalize_invalid_input():
    assert DataNormalizer.normalize_market_data(None) is None
    assert DataNormalizer.normalize_market_data([]) is None
    assert DataNormalizer.normalize_market_data({"no_symbol": 1}) is None

def test_normalize_ms_timestamp():
    # 13 digit timestamp (ms)
    ts_ms = 1700000000000
    raw = {
        "symbol": "TEST",
        "last_traded_time": ts_ms
    }
    row = DataNormalizer.normalize_market_data(raw)
    assert row is not None
    # Should handle it without crash and format correctly
    # 2023...
    assert row[15].startswith("2023-")

def test_normalize_prev_close_zero():
    # division by zero protection
    raw = {
        "symbol": "TEST",
        "ltp": 100,
        "prev_close_price": 0
    }
    row = DataNormalizer.normalize_market_data(raw)
    assert row[10] == 0.0 # Change % should be 0, not Inf/Error
