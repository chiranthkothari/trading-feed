import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, date, time
import pytz
from src.scheduler.market_hours import MarketHoursController
from src.config import Config

# Mock Config if needed, but defaults are usually fine
@pytest.fixture
def scheduler():
    with patch("src.scheduler.market_hours.Config.MARKET_START", "09:15"), \
         patch("src.scheduler.market_hours.Config.MARKET_END", "15:30"), \
         patch("src.scheduler.market_hours.Config.TIMEZONE", "Asia/Kolkata"):
        return MarketHoursController()

def test_is_market_open_weekday_business_hours(scheduler):
    # Mon, 10:00 AM -> Open
    with patch.object(scheduler, 'get_current_time') as mock_time:
        mock_time.return_value = datetime(2023, 11, 20, 10, 0) # Mon
        # Ensure it has weekday() method if we mocked a datetime object?
        # Standard datetime has it.
        # But we need to ensure tz aware if code expects it...
        # Code does: now.weekday(), now.time().
        
        assert scheduler.is_market_open() is True

def test_is_market_open_weekday_pre_market(scheduler):
    # Mon, 08:00 AM -> Closed
    with patch.object(scheduler, 'get_current_time') as mock_time:
        mock_time.return_value = datetime(2023, 11, 20, 8, 0)
        assert scheduler.is_market_open() is False

def test_is_market_open_weekday_post_market(scheduler):
    # Mon, 16:00 PM -> Closed
    with patch.object(scheduler, 'get_current_time') as mock_time:
        tz = pytz.timezone("Asia/Kolkata")
        mock_time.return_value = tz.localize(datetime(2023, 11, 20, 16, 0))
        assert scheduler.is_market_open() is False

def test_is_market_open_weekend(scheduler):
    # Sat -> Closed
    with patch.object(scheduler, 'get_current_time') as mock_time:
        tz = pytz.timezone("Asia/Kolkata")
        mock_time.return_value = tz.localize(datetime(2023, 11, 18, 10, 0)) # Sat
        assert scheduler.is_market_open() is False

def test_wait_for_market_open_sleeps_correctly(scheduler):
    # Current: Mon 08:15. Open: 09:15.
    # Should sleep 1 hour (3600s)
    
    with patch.object(scheduler, 'get_current_time') as mock_time:
        tz = pytz.timezone("Asia/Kolkata")
        start_time = tz.localize(datetime(2023, 11, 20, 8, 15))
        mock_time.return_value = start_time
    
        with patch("time.sleep") as mock_sleep:
            # We must break the loop. 
            # The code: if sleep_seconds > 0: sleep... return
            # So if we set up time such that it sleeps once, it returns!
            
            scheduler.wait_for_market_open()
            
            # 09:15 - 08:15 = 1 hour = 3600s
            # Allow small float diff
            args, _ = mock_sleep.call_args
            assert 3590 < args[0] < 3610

def test_wait_for_market_open_handles_post_market_same_day(scheduler):
    # Current: Mon 16:00. Next Open: Tue 09:15.
    # Mon 16:00 to Tue 09:15 = 8h + 9h15 = 17h15m = ~62100s
    
    with patch.object(scheduler, 'get_current_time') as mock_time:
        start_time = datetime(2023, 11, 20, 16, 0, tzinfo=pytz.timezone("Asia/Kolkata"))
        mock_time.return_value = start_time
        
        with patch("time.sleep") as mock_sleep:
            scheduler.wait_for_market_open()
            # Verify approximate seconds (> 10 hours)
            args, _ = mock_sleep.call_args
            assert args[0] > 36000

def test_wait_for_market_open_handles_weekend(scheduler):
    # Current: Sat 10:00. Next Open: Mon 09:15.
    # Sat 10 to Mon 09:15 = ~47h
    
    with patch.object(scheduler, 'get_current_time') as mock_time:
        start_time = datetime(2023, 11, 18, 10, 0, tzinfo=pytz.timezone("Asia/Kolkata"))
        mock_time.return_value = start_time
        
        with patch("time.sleep") as mock_sleep:
            scheduler.wait_for_market_open()
            args, _ = mock_sleep.call_args
            assert args[0] > 100000 # 47h is ~170k seconds
