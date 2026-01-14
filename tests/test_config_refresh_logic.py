
import unittest
from unittest.mock import MagicMock, patch
import time
import sys
import os

# Mock the modules before importing TradingFeederApp
sys.modules['src.notifications.telegram'] = MagicMock()
sys.modules['src.scheduler.market_hours'] = MagicMock()
sys.modules['src.auth.fyers_auth'] = MagicMock()
sys.modules['src.sheets.sheets_client'] = MagicMock()
sys.modules['src.market.websocket_client'] = MagicMock()
sys.modules['src.market.data_normalizer'] = MagicMock()
sys.modules['src.market.quote_client'] = MagicMock()

from src.main import TradingFeederApp
from src.config import Config

class TestConfigRefresh(unittest.TestCase):
    def setUp(self):
        Config.CONFIG_REFRESH_INTERVAL = 0 # Force refresh
        self.app = TradingFeederApp()
        self.app.sheets = MagicMock()
        self.app.ws_client = MagicMock()
        self.app.ws_client.is_connected = True
        self.app.instruments = [{'Symbol': 'A'}, {'Symbol': 'B'}]
        self.app.last_config_refresh_time = 0

    def test_reordering(self):
        # New order: B, A
        self.app.sheets.read_config.return_value = [{'Symbol': 'B'}, {'Symbol': 'A'}]
        
        with patch('src.main.logger') as mock_logger:
            self.app.refresh_config_if_needed()
            mock_logger.info.assert_any_call("Config reordering detected.")
            self.assertEqual(self.app.symbol_rank['B'], 0)
            self.assertEqual(self.app.symbol_rank['A'], 1)

    def test_addition_removal(self):
        # New symbols: B, C (A removed, C added)
        self.app.sheets.read_config.return_value = [{'Symbol': 'B'}, {'Symbol': 'C'}]
        
        with patch('src.main.logger') as mock_logger:
            self.app.refresh_config_if_needed()
            mock_logger.info.assert_any_call("Config changes detected! Added: 1, Removed: 1")
            self.app.ws_client.unsubscribe.assert_called_with(['A'])
            self.app.ws_client.subscribe.assert_called_with(['C'])

if __name__ == '__main__':
    unittest.main()
