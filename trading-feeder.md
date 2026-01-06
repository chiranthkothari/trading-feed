# FYERS Live Market Data → Google Sheets Automation (Python + Docker)

## 1. Overview
This project implements a fully automated live market-data pipeline that:
- Authenticates with FYERS API using TOTP (2FA)
- Streams near-real-time data (3–4s latency)
- Tracks up to 400 instruments (Equity + F&O)
- Uses Google Sheets as config + output
- Auto starts/stops during Indian market hours
- Runs inside Docker on Oracle Cloud VM

---

## 2. Functional Requirements
- Instruments: Equity, F&O, Indices
- Data mode: WebSocket streaming
- Scale: Up to 400 symbols
- Latency: ~3–4 seconds

---

## 3. Required Data Fields
Date  
Previous Close  
Open  
High  
Low  
LTP  
Volume  
Traded Value  
Change (Rs.)  
Change (%)  
Bid Price  
Offer Price  
52-Week High  
52-Week Low  
Last Updated Timestamp  

---

## 4. Architecture
Google Sheets (Config)  
↓  
Python Core Engine  
- FYERS Auth (TOTP)  
- WebSocket Market Feed  
- Data Normalizer  
- Metrics Calculator  
- Market Hours Controller  
- Google Sheets Writer  
↓  
Google Sheets (Live Data)

---

## 5. Authentication (FYERS + TOTP)
- Automated OTP generation using shared secret
- Programmatic login
- Token persistence and refresh

Libraries:
- pyotp
- requests
- fyers-apiv3

---

## 6. Google Sheets Design
Acts as:
- Instrument master
- Live monitoring dashboard

Only rows with Enabled = TRUE are tracked.

---

## 7. Market Data Strategy
- WebSocket-based streaming
- Batch subscriptions
- Auto reconnect & resubscribe

---

## 8. Market Hours Automation
- Start: 09:15 IST
- Stop: 15:30 IST
- Sleeps outside market hours
- Auto resumes next trading day

---

## 9. Error Handling
- Auth retry on failure
- WebSocket auto-reconnect
- Batch write retries for Sheets
- Container auto-restart

---

## 10. Environment Variables
FYERS_APP_ID  
FYERS_SECRET_KEY  
FYERS_REDIRECT_URI  
FYERS_USER_ID  
FYERS_PIN  
FYERS_TOTP_SECRET  

GOOGLE_SHEET_ID  
GOOGLE_SERVICE_ACCOUNT_JSON_PATH  

MARKET_START=09:15  
MARKET_END=15:30  
TIMEZONE=Asia/Kolkata  

---

## 11. Docker
- Python 3.11+
- Non-root user
- Minimal image

Run:
docker run -d --env-file .env --restart unless-stopped fyers-live-sheet

---

## 12. Deployment
- Oracle Cloud VM
- Docker runtime
- Designed for unattended execution

---

## 13. Security
- No secrets in code
- Service account restricted to one sheet
- Tokens never logged

---

## 14. Deliverables
- Python codebase
- Dockerfile
- .env.example
- README
- Google Sheet schema

---

## 15. Non-Goals
- No order placement
- No historical storage
- No strategy execution
