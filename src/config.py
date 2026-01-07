import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # FYERS Credentials
    FYERS_APP_ID = os.getenv("FYERS_APP_ID")
    FYERS_SECRET_KEY = os.getenv("FYERS_SECRET_KEY")
    FYERS_REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI")
    FYERS_USER_ID = os.getenv("FYERS_USER_ID")
    FYERS_PIN = os.getenv("FYERS_PIN")
    FYERS_TOTP_SECRET = os.getenv("FYERS_TOTP_SECRET")

    # Google Sheets Configuration
    GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
    GOOGLE_SERVICE_ACCOUNT_JSON_PATH = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_PATH", "service_account.json")

    # Market Hours (only used for scheduling, logic handles types)
    MARKET_START = os.getenv("MARKET_START", "09:15")
    MARKET_END = os.getenv("MARKET_END", "15:30")
    TIMEZONE = os.getenv("TIMEZONE", "Asia/Kolkata")

    # Telegram Notifications
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
    
    # App Settings
    CONFIG_REFRESH_INTERVAL = int(os.getenv("CONFIG_REFRESH_INTERVAL", 300))

    @classmethod
    def validate(cls):
        """Validates that all required environment variables are set."""
        required_vars = [
            "FYERS_APP_ID", "FYERS_SECRET_KEY", "FYERS_REDIRECT_URI",
            "FYERS_USER_ID", "FYERS_PIN", "FYERS_TOTP_SECRET",
            "GOOGLE_SHEET_ID", "GOOGLE_SERVICE_ACCOUNT_JSON_PATH"
        ]
        
        missing = [var for var in required_vars if not getattr(cls, var)]
        
        if missing:
            raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")
        return True

# Validate on import (optional, but good for fail-fast)
# Config.validate()
