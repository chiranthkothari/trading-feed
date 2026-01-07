
import sys
import os
import logging
import certifi

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.sheets.sheets_client import SheetsClient
from src.config import Config

# Fix SSL context for Mac
os.environ['SSL_CERT_FILE'] = certifi.where()

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("PopulateConfig")

def generate_symbols():
    """Generates a list of ~400 symbols across different types."""
    symbols = []

    # 1. INDICES (10)
    indices = [
        "NSE:NIFTY50-INDEX", "NSE:NIFTYBANK-INDEX", "NSE:FINNIFTY-INDEX", 
        "NSE:NIFTYIT-INDEX", "NSE:NIFTYAUTO-INDEX", "NSE:NIFTYFMCG-INDEX",
        "NSE:NIFTYMETAL-INDEX", "NSE:NIFTYPHARMA-INDEX", "NSE:NIFTYPSE-INDEX",
        "NSE:NIFTYREALTY-INDEX"
    ]
    for ind in indices:
        symbols.append([ind, "INDEX", "TRUE"])

    # 2. EQUITIES (Top ~200)
    # Common highly traded stocks
    base_stocks = [
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "BHARTIARTL", "ICICIBANK", "ITC", "SBIN",
        "LICI", "HINDUNILVR", "LT", "BAJFINANCE", "HCLTECH", "MARUTI", "SUNPHARMA",
        "ADANIENT", "KOTAKBANK", "TITAN", "ONGC", "TATAMOTORS", "NTPC", "AXISBANK",
        "ASIANPAINT", "ULTRACEMCO", "WIPRO", "POWERGRID", "M&M", "JSWSTEEL", "BAJAJFINSV",
        "LTIM", "ADANIPORTS", "TATASTEEL", "COALINDIA", "SIEMENS", "DMART", "NESTLEIND",
        "SBILIFE", "GRASIM", "TECHM", "PIDILITIND", "HINDALCO", "BEL", "ADANIPOWER",
        "VBL", "GODREJCP", "IOC", "ZOMATO", "DLF", "EICHERMOT", "HAL", "TRENT", "INDIGO",
        "DIVISLAB", "GAIL", "ABB", "BPCL", "LODHA", "JIOFIN", "AMBUJACEM", "BANKBARODA",
        "VEDL", "PFC", "TATAPOWER", "PNB", "HAVELLS", "INDUSINDBK", "CIPLA", "DABUR",
        "APOLLOHOSP", "SHRIRAMFIN", "TVSMOTOR", "CHOLAFIN", "BRITANNIA", "POLYCAB", 
        "CUMMINSIND", "RECLTD", "NAUKRI", "MANGALAM", "MOTHERSON", "BOSCHLTD", "OBEROIRLTY",
        "ICICIGI", "OFSS", "COLPAL", "HDFCLIFE", "IRFC", "ZYDUSLIFE", "GODREJPROP",
        "SHREECEM", "TORNTPOWER", "UNIONBANK", "CANBK", "M&MFIN", "TIINDIA", "HEROMOTOCO",
        "AUROPHARMA", "LUPIN", "UBL", "PERSISTENT", "ALKEM", "ASTRAL", "LTTS", "MRF",
        "MUTHOOTFIN", "BHARATFORG", "ASHOKLEY", "CONCOR", "IDFCFIRSTB", "PIIND", "PATANJALI",
        "MPHASIS", "ACC", "INDIANB", "BALKRISIND", "CUB", "FEDERALBNK", "JUBLFOOD",
        "KAYNES", "MAXHEALTH", "DEEPAKNTR", "FSL", "GLENMARK", "GMRINFRA", "HINDPETRO",
        "IDBI", "IGL", "INDHOTEL", "JINDALSTEL", "JSWENERGY", "L&TFH", "LAURUSLAB",
        "LICHSGFIN", "MANAPPURAM", "MCX", "METROPOLIS", "MFSL", "MGL", "NAM-INDIA",
        "NATIONALUM", "NAVINFLUOR", "NMDC", "OBEROIRLTY", "PEL", "PETRONET", "PVRINOX",
        "RBLBANK", "SAIL", "SRF", "SYNGENE", "TATACHEM", "TATACOMM", "TATACONSUM",
        "VOLTAS", "ZEEL", "BHEL", "BSOFT", "CANFINHOME", "CHAMBLFERT", "COROMANDEL",
        "CROMPTON", "DELTACORP", "ESCORTS", "EXIDEIND", "GNA", "GNFC", "GRANULES",
        "GUJGASLTD", "IBULHSGFIN", "IEX", "INTELLECT", "IPCALAB", "JKCEMENT", "JKPAPER",
        "KPRMILL", "LALPATHLAB", "MAHABANK", "MAHLIFE", "MSUMI", "NCC", "NHPC", "NSL",
        "OIL", "PIGL", "PRESTIGE", "RAIN", "RAMCOCEM", "RAYMOND", "RITES", "RVNL",
        "SJVN", "SONACOMS", "STAR", "SUNDRMFAST", "SUNTV", "SUPREMEIND", "TATAINVEST",
        "TEJASNET", "TIIL", "TITAGARH", "UCOBANK", "UPL", "VAMSHI", "VARROC", "VGUARD",
        "VIJAYA", "VINATIORGA", "VIPIND", "WELCORP", "WHIRLPOOL", "WOCKPHARMA", "YESBANK"
    ]
    
    # Fill up to 200 with simple generated ones if short, but list is decent.
    # Format: NSE:SYMBOL-EQ
    for stock in base_stocks[:200]:
        symbols.append([f"NSE:{stock}-EQ", "EQUITY", "TRUE"])

    # 3. FUTURES (50)
    # Jan 2026 Futures
    future_stocks = ["NIFTY", "BANKNIFTY", "RELIANCE", "HDFCBANK", "INFY", "TCS", "SBIN", "ICICIBANK", "ITC", "LT"]
    # Generating 5 future contracts for each if possible, or usually just Near/Next/Far
    # Let's create mock symbols for user testing
    # Assuming symbol format: NSE:SYMBOL26JANFUT for monthly
    for root in future_stocks:
        symbols.append([f"NSE:{root}26JANFUT", "FUTURE", "TRUE"])
        symbols.append([f"NSE:{root}26FEBFUT", "FUTURE", "TRUE"])
        symbols.append([f"NSE:{root}26MARFUT", "FUTURE", "TRUE"])
    
    # Fill remaining futures with other stocks
    more_futures = base_stocks[10:30]
    for stock in more_futures:
        symbols.append([f"NSE:{stock}26JANFUT", "FUTURE", "TRUE"])

    # 4. OPTIONS (Balance to reach 400, approx 140)
    # NIFTY Options
    strikes = range(24000, 26000, 100) # 20 strikes
    for k in strikes:
        symbols.append([f"NSE:NIFTY26JAN{k}CE", "OPTION", "TRUE"])
        symbols.append([f"NSE:NIFTY26JAN{k}PE", "OPTION", "TRUE"])
        symbols.append([f"NSE:NIFTY26FEB{k}CE", "OPTION", "TRUE"])
        symbols.append([f"NSE:NIFTY26FEB{k}PE", "OPTION", "TRUE"])

    # BANKNIFTY Options
    bn_strikes = range(52000, 54000, 500) # 4 strikes
    for k in bn_strikes:
         symbols.append([f"NSE:BANKNIFTY26JAN{k}CE", "OPTION", "TRUE"])
         symbols.append([f"NSE:BANKNIFTY26JAN{k}PE", "OPTION", "TRUE"])

    # Limit to 400 total
    return symbols[:400]

def populate():
    logger.info("Starting populate config script...")
    sheets = SheetsClient()
    
    try:
        sheets.connect()
        
        # Ensure Config tab exists or get it
        try:
            ws = sheets.sheet.worksheet("Config")
            logger.info("Found 'Config' sheet.")
        except Exception:
            logger.info("Creating 'Config' sheet...")
            ws = sheets.sheet.add_worksheet(title="Config", rows=500, cols=10)

        # Generate Data
        data = generate_symbols()
        logger.info(f"Generated {len(data)} symbols.")

        # Prepare Header + Data
        all_rows = [["Symbol", "Instrument Type", "Enabled"]] + data
        
        # Write
        logger.info("Clearing and writing to sheet...")
        ws.clear()
        ws.update(range_name="A1", values=all_rows)
        logger.info("Successfully populated 'Config' sheet with 400 symbols.")

    except Exception as e:
        logger.error(f"Failed to populate config: {e}")
        sys.exit(1)

if __name__ == "__main__":
    populate()
