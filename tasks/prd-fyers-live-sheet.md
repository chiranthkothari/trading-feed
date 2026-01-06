# PRD: FYERS Live Market Data → Google Sheets Automation

## 1. Introduction/Overview

This project delivers a **fully automated live market-data pipeline** that streams real-time stock data from the FYERS brokerage API to Google Sheets. It is designed for an **individual trader** who wants to monitor up to 400 instruments (Equity, F&O, Indices) with near-real-time updates (~3–4 second latency) during Indian market hours.

**Problem Solved:** Manual market data tracking is tedious and error-prone. This system automates the entire workflow—authentication, data streaming, and sheet updates—so the trader can focus on analysis rather than data collection.

---

## 2. Goals

| # | Goal | Measurable Outcome |
|---|------|-------------------|
| G1 | Automate FYERS authentication with TOTP | System logs in without manual intervention |
| G2 | Stream live data for up to 400 symbols | All enabled instruments receive updates |
| G3 | Update Google Sheets with ~3–4s latency | Timestamps reflect real-time updates |
| G4 | Operate autonomously during market hours | No manual start/stop required |
| G5 | Resume gracefully after restarts | Preserve data rows and continue updating |
| G6 | Alert on critical failures via Telegram | User receives push notification on errors |

---

## 3. User Stories

| ID | As a... | I want to... | So that... |
|----|---------|--------------|------------|
| US1 | Trader | See live LTP, bid/ask, and volume in Google Sheets | I can make informed trading decisions |
| US2 | Trader | Configure which instruments to track via a sheet | I don't need to edit code to add/remove symbols |
| US3 | Trader | Have the system start/stop automatically with market hours | I don't need to manually manage the service |
| US4 | Trader | Receive a Telegram alert when the system fails | I know immediately if data is stale |
| US5 | Trader | Have data persist across restarts | I don't lose intraday data if the container restarts |

---

## 4. Functional Requirements

### 4.1 Authentication Module
1. **FR-AUTH-01:** The system must authenticate with FYERS API using app credentials and TOTP-based 2FA.
2. **FR-AUTH-02:** The system must generate OTP programmatically using `pyotp` and the stored TOTP secret.
3. **FR-AUTH-03:** The system must persist access tokens and refresh them when expired.
4. **FR-AUTH-04:** The system must retry authentication up to 3 times on failure before alerting.

### 4.2 Market Data Module
5. **FR-DATA-01:** The system must connect to FYERS WebSocket API for streaming market data.
6. **FR-DATA-02:** The system must subscribe to instruments in batches (respecting API limits).
7. **FR-DATA-03:** The system must handle WebSocket disconnections with auto-reconnect and resubscribe logic.
8. **FR-DATA-04:** The system must normalize incoming data to match the required output fields.

### 4.3 Required Data Fields
9. **FR-DATA-05:** Each instrument row must include the following fields:
   - Date
   - Previous Close
   - Open
   - High
   - Low
   - LTP (Last Traded Price)
   - Volume
   - Traded Value
   - Change (Rs.)
   - Change (%)
   - Bid Price
   - Offer Price
   - 52-Week High
   - 52-Week Low
   - Last Updated Timestamp

### 4.4 Google Sheets Module
10. **FR-SHEET-01:** The system must read instrument configuration from a "Config" sheet.
11. **FR-SHEET-02:** Only rows with `Enabled = TRUE` must be subscribed and tracked.
12. **FR-SHEET-03:** The system must write live data to a "Live Data" sheet.
13. **FR-SHEET-04:** The system must use batch writes to minimize API calls and respect rate limits.
14. **FR-SHEET-05:** The system must retry failed writes up to 3 times with exponential backoff.

### 4.5 Market Hours Controller
15. **FR-TIME-01:** The system must start streaming at **09:15 IST** on trading days.
16. **FR-TIME-02:** The system must stop streaming at **15:30 IST**.
17. **FR-TIME-03:** The system must sleep outside market hours and auto-resume the next trading day.
18. **FR-TIME-04:** The system must use the `Asia/Kolkata` timezone for all time calculations.

### 4.6 Error Handling & Notifications
19. **FR-ERR-01:** The system must log all errors to stdout/stderr (Docker logs).
20. **FR-ERR-02:** The system must send a Telegram push notification for critical failures:
    - Authentication failure after retries
    - WebSocket connection failure after retries
    - Google Sheets write failure after retries
21. **FR-ERR-03:** Telegram alerts must include: error type, timestamp, and brief description.

### 4.7 Data Persistence
22. **FR-PERSIST-01:** The system must preserve live data rows in Google Sheets across restarts.
23. **FR-PERSIST-02:** On restart, the system must resume updating existing rows (not clear and recreate).

---

## 5. Non-Goals (Out of Scope)

| What | Why |
|------|-----|
| Order placement | This is a data monitoring tool only |
| Historical data storage | No database; Sheets is ephemeral live view |
| Strategy execution | No algorithmic trading logic |
| Multi-user authentication | Single personal trader use case |
| Web dashboard UI | Google Sheets serves as the interface |

---

## 6. Design Considerations

### 6.1 Google Sheets Schema

**Config Sheet:**
| Column | Description |
|--------|-------------|
| Symbol | FYERS format symbol (e.g., `NSE:RELIANCE-EQ`) |
| Instrument Type | Equity / F&O / Index |
| Enabled | TRUE / FALSE |

**Live Data Sheet:**
| Column | Description |
|--------|-------------|
| Symbol | Instrument identifier |
| Date | Trading date |
| Prev Close | Previous day's closing price |
| Open | Day's opening price |
| High | Day's high |
| Low | Day's low |
| LTP | Last traded price |
| Volume | Total volume traded |
| Traded Value | Total value traded |
| Change (₹) | Absolute change from prev close |
| Change (%) | Percentage change |
| Bid | Best bid price |
| Ask | Best offer price |
| 52W High | 52-week high |
| 52W Low | 52-week low |
| Updated At | Last update timestamp |

---

## 7. Technical Considerations

### 7.1 Technology Stack
- **Language:** Python 3.11+
- **Libraries:**
  - `fyers-apiv3` – FYERS API client
  - `pyotp` – TOTP generation
  - `gspread` + `google-auth` – Google Sheets API
  - `python-telegram-bot` or `requests` – Telegram notifications
  - `websocket-client` – WebSocket handling
  - `schedule` or `APScheduler` – Market hours automation

### 7.2 Environment Variables
```
# FYERS Credentials
FYERS_APP_ID
FYERS_SECRET_KEY
FYERS_REDIRECT_URI
FYERS_USER_ID
FYERS_PIN
FYERS_TOTP_SECRET

# Google Sheets
GOOGLE_SHEET_ID
GOOGLE_SERVICE_ACCOUNT_JSON_PATH

# Market Hours
MARKET_START=09:15
MARKET_END=15:30
TIMEZONE=Asia/Kolkata

# Telegram Notifications
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```

### 7.3 Docker
- Base image: `python:3.11-slim`
- Run as non-root user
- Restart policy: `unless-stopped`
- Command: `docker run -d --env-file .env --restart unless-stopped fyers-live-sheet`

### 7.4 Deployment
- Target: Oracle Cloud VM (Always Free tier)
- Prerequisites: Docker runtime installed
- Designed for unattended 24/7 operation

---

## 8. Success Metrics

| Metric | Target |
|--------|--------|
| Data latency | ≤ 4 seconds from market feed to Sheets |
| Uptime during market hours | 99%+ (excluding FYERS API outages) |
| Authentication success rate | 100% with valid credentials |
| Alert delivery | Telegram notification within 30s of critical error |
| Symbols tracked | Up to 400 instruments |

---

## 9. Deliverables

| Deliverable | Description |
|-------------|-------------|
| `src/` | Python codebase with modular architecture |
| `Dockerfile` | Production-ready container definition |
| `.env.example` | Template for environment variables |
| `README.md` | Setup and deployment instructions |
| `sheets-template.md` | Google Sheets schema documentation |

---

## 10. Open Questions

1. **Holiday Calendar:** Should the system skip Indian market holidays automatically, or is weekday-only logic sufficient for now?
2. **Rate Limiting:** What are the exact FYERS WebSocket subscription limits per connection?
3. **Telegram Bot Setup:** Does the user already have a Telegram bot, or should setup instructions be included?

---

## 11. Security Considerations

- ✅ No secrets hardcoded in source code
- ✅ Google service account scoped to single spreadsheet
- ✅ Access tokens never logged
- ✅ Environment variables for all sensitive config
- ✅ Docker runs as non-root user
