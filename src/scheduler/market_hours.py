import logging
import time
import pytz
from datetime import datetime, timedelta, time as dt_time
from src.config import Config

logger = logging.getLogger(__name__)

class MarketHoursController:
    def __init__(self):
        self.tz = pytz.timezone(Config.TIMEZONE)
        self.start_time = self._parse_time(Config.MARKET_START)
        self.end_time = self._parse_time(Config.MARKET_END)

    def _parse_time(self, time_str):
        """Parses HH:MM string into datetime.time object."""
        try:
            h, m = map(int, time_str.split(':'))
            return dt_time(h, m)
        except ValueError:
            logger.error(f"Invalid time format: {time_str}. Defaulting to 09:15/15:30")
            return dt_time(9, 15)

    def get_current_time(self):
        """Returns current time in configured timezone."""
        return datetime.now(self.tz)

    def is_market_open(self):
        """
        Checks if the market is currently open.
        Conditions:
        1. Weekday (Mon=0 to Fri=4)
        2. Time between START and END
        """
        now = self.get_current_time()
        
        # 1. Weekday check (Skip Sat=5, Sun=6)
        if now.weekday() >= 5:
            return False
            
        # 2. Time check
        current_time = now.time()
        return self.start_time <= current_time <= self.end_time

    def is_holiday(self):
        """Placeholder for holiday check."""
        # Future: Check against a list of dates
        return False

    def wait_for_market_open(self):
        """
        Calculates seconds until next market open and sleeps.
        Handles weekends and same-day post-market scenarios.
        """
        while True:
            now = self.get_current_time()
            target_date = now.date()
            
            # Check if today is weekend
            # If Sat(5), add 2 days -> Mon
            # If Sun(6), add 1 day -> Mon
            if now.weekday() == 5:
                target_date += timedelta(days=2)
            elif now.weekday() == 6:
                target_date += timedelta(days=1)
            
            # Construct target datetime
            target_dt = self.tz.localize(datetime.combine(target_date, self.start_time))
            
            # If target is in the past (e.g. today is Mon, 10 AM, Start is 09:15)
            # wait... this method is "wait_for_market_open".
            # If market IS open, we shouldn't wait? Or we wait for TOMORROW's open?
            # Usage pattern: 
            # if is_market_open(): run()
            # else: wait_for_market_open()
            
            # So if we are here, we assume we need to wait for a FUTURE start time.
            if target_dt <= now:
                # Target is passed for today. Move to next day.
                target_date += timedelta(days=1)
                # Re-check weekend for next day
                if target_date.weekday() == 5: # Sat
                    target_date += timedelta(days=2) # -> Mon
                elif target_date.weekday() == 6: # Sun
                    target_date += timedelta(days=1) # -> Mon
                
                target_dt = self.tz.localize(datetime.combine(target_date, self.start_time))
            
            # Calculate sleep duration
            sleep_seconds = (target_dt - now).total_seconds()
            
            if sleep_seconds > 0:
                hours = sleep_seconds / 3600
                logger.info(f"Market Closed. Sleeping for {sleep_seconds:.0f}s ({hours:.1f} hours) until {target_dt}")
                time.sleep(sleep_seconds)
                return # Woke up!
            
            # Safety loop
            time.sleep(1)

    def wait_for_market_close(self):
        """
        Sleeping until market close time today.
        Assumes called when market is OPEN.
        """
        now = self.get_current_time()
        target_dt = self.tz.localize(datetime.combine(now.date(), self.end_time))
        
        sleep_seconds = (target_dt - now).total_seconds()
        
        if sleep_seconds > 0:
            logger.info(f"Market Open. Running logic... (Main loop should handle this, helper just returns/logs?)")
            # Actually, this method might be used for "Sleep until close" if the main loop just fires and waits?
            # But we need to STREAM data. So we CANNOT sleep here.
            # Usually, we don't 'wait' for close in the main thread if we are streaming.
            # The streaming happens in a loop or callback.
            # The Main Orchestrator Check:
            # while is_market_open():
            #    ... process ...
            #    time.sleep(n)
            
            # So this helper might just be useful for "seconds_until_close".
            pass
        return sleep_seconds
