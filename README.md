# FYERS Live Market Data → Google Sheets Automation

A Python-based automated trading feeder that streams live market data from FYERS API to Google Sheets in real-time. Designed to run in Docker

## Features

- **Live Streaming**: Updates up to 400 instruments in near real-time (4s latency to respect rate limits).
- **52-Week High/Low**: Automatically fetches 1 year of historical data at startup to calculate and display valid 52W High/Low values (hybrid approach).
- **Liveness Indicator**: The "Updated At" column automatically refreshes every 4s (System Time) to show the feeder is active, even if prices are static.
- **Automated**: Auto-starts at 09:15 IST and stops at 15:30 IST.
- **Resilient**: Auto-reconnects on network failure, refreshes auth tokens daily using a persistent refresh token.
- **Configurable**: Manage instrument list directly from Google Sheets (`Config` tab).
- **Notifications**: Telegram alerts for critical errors (Auth failure, API limits, Crashes).
- **Secure**: Uses environment variables and non-root Docker container.

## Prerequisites

1. **FYERS Account**: API V3 App created (App ID, Secret, Redirect URI).
2. **Google Cloud Project**:
   - Enable "Google Sheets API" and "Google Drive API".
   - Create Service Account and download JSON key.
3. **Telegram Bot**:
   - Create a bot via @BotFather.
   - Get your Chat ID.
4. **Google Sheet**:
   - Create a new Sheet.
   - Share it with the Service Account email (Editor access).
   - Create two tabs: `Config` and `Live Data`.

### Sheet Structure
- **Config Tab**:
  - Columns: `Symbol` (A), `Instrument Type` (B), `Enabled` (C).
  - Example: `NSE:SBIN-EQ`, `EQUITY`, `TRUE`.
- **Live Data Tab**:
  - Columns: `Symbol`, `Date`, `Prev Close`, `Open`, `High`, `Low`, `LTP`, `Volume`, `Traded Value`, `Change (Rs)`, `Change (%)`, `Bid`, `Ask`, `52W High`, `52W Low`, `Updated At`.

## Setup Guide

### 1. Environment Variables
Create a `.env` file in the root directory (copy from `.env.example`):

```bash
cp .env.example .env
```

Fill in the required details:
```ini
FYERS_APP_ID=your_app_id
FYERS_SECRET_KEY=your_secret
FYERS_USER_ID=your_fyers_id
FYERS_PIN=your_pin
FYERS_TOTP_SECRET=your_totp_secret
GOOGLE_SHEET_ID=your_sheet_id
GOOGLE_SERVICE_ACCOUNT_JSON_PATH=service_account.json
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

### 2. Service Account Key
Place your `service_account.json` in the root directory.

### 3. Refresh Token
Create a `refresh_token.json` file in the root directory with your initial refresh token (obtained via login flow or creating a token manually). The app will update this file automatically.
Format:
```json
{"refresh_token": "your_initial_refresh_token"}
```

### 4. Local Run (Testing)
```bash
# Install dependencies
pip install -r requirements.txt

# Run
python -m src.main
```

### 5. Docker Deployment
Build the image:
```bash
docker build -t trading-feeder .
```

Run the container:
```bash
docker run -d \
  --name trading-feeder \
  --restart unless-stopped \
  --env-file .env \
  -v $(pwd)/service_account.json:/app/service_account.json \
  -v $(pwd)/access_token.json:/app/access_token.json \
  -v $(pwd)/refresh_token.json:/app/refresh_token.json \
  -v $(pwd)/logs:/app/logs \
  trading-feeder
```
*Note: We mount `access_token.json` AND `refresh_token.json` to persist authentication across container restarts.*

## Troubleshooting

- **Logs**: `docker logs -f trading-feeder`
- **Auth Error**: Ensure `refresh_token.json` is valid and TOTP secret is correct.
- **52W Data 0?**: Check logs to see if History API fetch failed at startup.
- **Values not updating**: Check `Config` sheet has `TRUE` for instruments.
- **Telegram silent**: Check Chat ID and Bot Token.
