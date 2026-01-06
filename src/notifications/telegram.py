import logging
import requests
import time
from datetime import datetime
import pytz
from src.config import Config

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.bot_token = Config.TELEGRAM_BOT_TOKEN
        self.chat_id = Config.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            logger.warning("Telegram Bot Token or Chat ID missing. Notifications disabled.")

    def send_message(self, text, retries=3):
        """
        Sends a plain text message to the configured chat ID.
        """
        if not self.enabled:
            return

        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }

        for attempt in range(1, retries + 1):
            try:
                response = requests.post(self.base_url, json=payload, timeout=10)
                response.raise_for_status()
                logger.debug("Telegram notification sent successfully.")
                return
            except Exception as e:
                logger.error(f"Failed to send Telegram message (Attempt {attempt}): {e}")
                if attempt < retries:
                    time.sleep(2)
                else:
                    logger.error("Max retries reached for Telegram notification.")

    def send_alert(self, error_type, message, timestamp=None):
        """
        Formats and sends a critical alert.
        Format:
        🚨 **[ERROR_TYPE]**
        _Time: YYYY-MM-DD HH:MM:SS IST_
        
        Message content...
        """
        if not self.enabled:
            return

        if timestamp is None:
            tz = pytz.timezone(Config.TIMEZONE)
            timestamp = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')

        formatted_text = (
            f"🚨 **[{error_type}]**\n"
            f"_Time: {timestamp}_\n\n"
            f"{message}"
        )
        
        self.send_message(formatted_text)
