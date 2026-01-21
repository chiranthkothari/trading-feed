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

    def get_updates(self, offset=None):
        """
        Fetches new messages from the bot.
        """
        if not self.enabled:
            return []
        
        url = f"https://api.telegram.org/bot{self.bot_token}/getUpdates"
        params = {"timeout": 10}
        if offset:
            params["offset"] = offset
            
        try:
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            if data.get("ok"):
                return data.get("result", [])
        except Exception as e:
            logger.error(f"Failed to get Telegram updates: {e}")
        return []

    def wait_for_response(self, timeout=300):
        """
        Polls for a response from the admin chat ID.
        Returns the text of the message if received, else None.
        """
        if not self.enabled:
            return None
            
        logger.info(f"Waiting for Telegram response (Timeout: {timeout}s)...")
        start_time = time.time()
        
        # Get current offset to ignore old messages
        updates = self.get_updates()
        if updates:
            last_update_id = updates[-1]["update_id"]
            current_offset = last_update_id + 1
        else:
            current_offset = None
            
        while time.time() - start_time < timeout:
            updates = self.get_updates(offset=current_offset)
            
            for update in updates:
                # Update offset for next poll
                current_offset = update["update_id"] + 1
                
                message = update.get("message", {})
                chat_id = str(message.get("chat", {}).get("id"))
                text = message.get("text")
                
                # Check if message is from our configured admin
                if chat_id == str(self.chat_id) and text:
                    logger.info("Received response from user.")
                    return text
            
            time.sleep(2)
            
        logger.warning("Telegram wait timeout expired.")
        return None
