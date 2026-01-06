# Tasks: FYERS Live Market Data → Google Sheets Automation

## References

- [Original Specification](../trading-feeder.md) - Project overview and requirements
- [Product Requirements Document](./prd-fyers-live-sheet.md) - Detailed PRD with functional requirements

---

## Relevant Files

- `src/config.py` - Environment variable loading and configuration constants
- `src/auth/fyers_auth.py` - FYERS authentication with TOTP and token management
- `src/auth/test_fyers_auth.py` - Unit tests for FYERS authentication
- `src/sheets/sheets_client.py` - Google Sheets read/write operations
- `src/sheets/test_sheets_client.py` - Unit tests for Sheets client
- `src/market/websocket_client.py` - WebSocket connection and subscription management
- `src/market/test_websocket_client.py` - Unit tests for WebSocket client
- `src/market/data_normalizer.py` - Raw data to output schema transformation
- `src/market/test_data_normalizer.py` - Unit tests for data normalizer
- `src/scheduler/market_hours.py` - Market hours controller with start/stop logic
- `src/scheduler/test_market_hours.py` - Unit tests for market hours controller
- `src/notifications/telegram.py` - Telegram bot notification sender
- `src/notifications/test_telegram.py` - Unit tests for Telegram notifications
- `src/main.py` - Application entry point and orchestration
- `Dockerfile` - Container definition
- `.env.example` - Environment variable template
- `requirements.txt` - Python dependencies
- `README.md` - Setup and deployment documentation

### Notes

- Unit tests should be placed alongside the code files they are testing.
- Use `pytest` to run tests. Running without a path executes all tests.
- Use `pytest --cov=src` for coverage reports.

## Instructions for Completing Tasks

**IMPORTANT:** As you complete each task, check it off by changing `- [ ]` to `- [x]`.

Update the file after completing each sub-task, not just after completing an entire parent task.

---

## Tasks

- [x] 1.0 Project Setup & Configuration
  - [x] 1.1 Create project directory structure (`src/`, `src/auth/`, `src/sheets/`, `src/market/`, `src/scheduler/`, `src/notifications/`)
  - [x] 1.2 Create `requirements.txt` with dependencies: `fyers-apiv3`, `pyotp`, `gspread`, `google-auth`, `websocket-client`, `python-telegram-bot`, `schedule`, `python-dotenv`, `pytest`, `pytest-cov`
  - [x] 1.3 Create `.env.example` with all required environment variables documented
  - [x] 1.4 Create `src/config.py` to load and validate environment variables using `python-dotenv`
  - [x] 1.5 Create `src/__init__.py` and module `__init__.py` files

- [x] 2.0 FYERS Authentication Module (TOTP + Token Management)
  - [x] 2.1 Create `src/auth/fyers_auth.py` with `FyersAuthenticator` class
  - [x] 2.2 Implement TOTP generation using `pyotp` and stored secret
  - [x] 2.3 Implement programmatic login flow using `fyers-apiv3` SDK
  - [x] 2.4 Implement token persistence (save access token to file/memory)
  - [x] 2.5 Implement token refresh/re-authentication logic when token expires
  - [x] 2.6 Implement retry logic (up to 3 attempts) with exponential backoff
  - [x] 2.7 Add error callback hook for notification on auth failure
  - [x] 2.8 Write unit tests in `src/auth/test_fyers_auth.py`

- [x] 3.0 Google Sheets Integration Module (Read Config & Write Data)
  - [x] 3.1 Create `src/sheets/sheets_client.py` with `SheetsClient` class
  - [x] 3.2 Implement service account authentication using `gspread` + `google-auth`
  - [x] 3.3 Implement `read_config()` to fetch enabled instruments from Config sheet
  - [x] 3.4 Implement `write_live_data()` to batch update Live Data sheet
  - [x] 3.5 Implement retry logic (3 attempts) with exponential backoff for writes
  - [x] 3.6 Implement rate limiting to respect Google Sheets API quotas
  - [x] 3.7 Add error callback hook for notification on persistent write failures
  - [x] 3.8 Write unit tests in `src/sheets/test_sheets_client.py`

- [x] 4.0 WebSocket Market Data Streaming Module
  - [x] 4.1 Create `src/market/websocket_client.py` with `MarketDataClient` class
  - [x] 4.2 Implement WebSocket connection to FYERS streaming API
  - [x] 4.3 Implement batch subscription for instruments (respect API limits)
  - [x] 4.4 Implement message handler callback for incoming market data
  - [x] 4.5 Implement auto-reconnect logic on disconnection
  - [x] 4.6 Implement resubscribe logic after reconnection
  - [x] 4.7 Add connection state tracking (connected/disconnected/reconnecting)
  - [x] 4.8 Add error callback hook for notification on connection failures
  - [x] 4.9 Write unit tests in `src/market/test_websocket_client.py`

- [x] 5.0 Data Normalization & Metrics Calculation
  - [x] 5.1 Create `src/market/data_normalizer.py` with `DataNormalizer` class
  - [x] 5.2 Define output schema matching PRD data fields (LTP, Open, High, Low, etc.)
  - [x] 5.3 Implement transformation from FYERS raw format to output schema
  - [x] 5.4 Implement Change (₹) calculation: `LTP - Previous Close`
  - [x] 5.5 Implement Change (%) calculation: `((LTP - Previous Close) / Previous Close) * 100`
  - [x] 5.6 Implement timestamp formatting for Last Updated field
  - [x] 5.7 Handle missing/null fields gracefully with defaults
  - [x] 5.8 Write unit tests in `src/market/test_data_normalizer.py`

- [x] 6.0 Market Hours Controller (Auto Start/Stop)
  - [x] 6.1 Create `src/scheduler/market_hours.py` with `MarketHoursController` class
  - [x] 6.2 Implement `is_market_open()` check using configured start/end times
  - [x] 6.3 Implement timezone handling using `Asia/Kolkata`
  - [x] 6.4 Implement `wait_for_market_open()` that sleeps until 09:15 IST
  - [x] 6.5 Implement `wait_for_market_close()` that triggers stop at 15:30 IST
  - [x] 6.6 Implement weekday check (skip Saturday/Sunday)
  - [x] 6.7 Implement main loop: sleep → start → run → stop → repeat
  - [x] 6.8 Write unit tests in `src/scheduler/test_market_hours.py`

- [x] 7.0 Telegram Notification Module (Error Alerts)
  - [x] 7.1 Create `src/notifications/telegram.py` with `TelegramNotifier` class
  - [x] 7.2 Implement `send_alert(error_type, message, timestamp)` method
  - [x] 7.3 Format alert messages with error type, description, and IST timestamp
  - [x] 7.4 Implement retry logic for failed Telegram API calls
  - [x] 7.5 Handle missing bot token gracefully (log warning, disable notifications)
  - [x] 7.6 Write unit tests in `src/notifications/test_telegram.py`

- [x] 8.0 Main Application Orchestration & Error Handling
  - [x] 8.1 Create `src/main.py` as the application entry point
  - [x] 8.2 Initialize all modules: config, auth, sheets, websocket, scheduler, telegram
  - [x] 8.3 Wire up error callbacks from all modules to Telegram notifier
  - [x] 8.4 Implement main orchestration loop:
    - [x] 8.4.1 Wait for market open
    - [x] 8.4.2 Authenticate with FYERS
    - [x] 8.4.3 Read instrument config from Sheets
    - [x] 8.4.4 Connect WebSocket and subscribe to instruments
    - [x] 8.4.5 On data received: normalize → write to Sheets
    - [x] 8.4.6 At market close: disconnect and wait for next day
  - [x] 8.5 Implement graceful shutdown on SIGTERM/SIGINT
  - [x] 8.6 Add comprehensive logging to stdout (Docker logs)

- [x] 9.0 Docker Containerization & Deployment Setup
  - [x] 9.1 Create `Dockerfile` with Python 3.11-slim base image
  - [x] 9.2 Configure non-root user in container
  - [x] 9.3 Copy source code and install dependencies
  - [x] 9.4 Set `CMD` to run `python src/main.py`
  - [x] 9.5 Create `README.md` with:
    - [x] 9.5.1 Project overview and features
    - [x] 9.5.2 Prerequisites (Docker, FYERS account, Google service account)
    - [x] 9.5.3 Environment variable setup instructions
    - [x] 9.5.4 Google Sheets template setup instructions
    - [x] 9.5.5 Telegram bot setup instructions
    - [x] 9.5.6 Docker build and run commands
    - [x] 9.5.7 Troubleshooting common issues
  - [x] 9.6 Test Docker build locally
  - [x] 9.7 Test end-to-end workflow in container

- [ ] 10.0 Feature: 52-Week Data Implementation
  - [x] 10.1 Create QuoteClient for REST API calls
  - [ ] 10.2 Fetch 52W High/Low at startup for all symbols
  - [ ] 10.3 Merge 52W data with live WebSocket stream
  - [ ] 10.4 Verify 52W High/Low in Google Sheets
