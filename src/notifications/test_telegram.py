import pytest
from unittest.mock import MagicMock, patch
from src.notifications.telegram import TelegramNotifier
from src.config import Config

@pytest.fixture
def mock_config():
    Config.TELEGRAM_BOT_TOKEN = "test_token"
    Config.TELEGRAM_CHAT_ID = "123456"

@pytest.fixture
def notifier(mock_config):
    return TelegramNotifier()

def test_init_disabled_if_no_token():
    Config.TELEGRAM_BOT_TOKEN = None
    notifier = TelegramNotifier()
    assert notifier.enabled is False

def test_send_message_success(notifier):
    with patch("src.notifications.telegram.requests.post") as mock_post:
        mock_post.return_value.status_code = 200
        
        notifier.send_message("Hello")
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs["json"]["text"] == "Hello"
        assert kwargs["json"]["chat_id"] == "123456"

def test_send_message_retries_failure(notifier):
    with patch("src.notifications.telegram.requests.post") as mock_post:
        mock_post.side_effect = Exception("Network Error")
        
        with patch("time.sleep"): # Skip sleep
            notifier.send_message("Test", retries=2)
        
        assert mock_post.call_count == 2

def test_send_alert_formatting(notifier):
    with patch.object(notifier, 'send_message') as mock_send:
        notifier.send_alert("CRITICAL", "Something broke", timestamp="2023-01-01 10:00:00")
        
        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert "🚨 **[CRITICAL]**" in msg
        assert "_Time: 2023-01-01 10:00:00_" in msg
        assert "Something broke" in msg

def test_send_alert_auto_timestamp(notifier):
    with patch.object(notifier, 'send_message') as mock_send:
        notifier.send_alert("INFO", "Test")
        msg = mock_send.call_args[0][0]
        # Check if timestamp is present (current year)
        import datetime
        current_year = str(datetime.datetime.now().year)
        assert f"Time: {current_year}" in msg
