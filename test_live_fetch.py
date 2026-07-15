import yfinance as yf
import time
import datetime

tickers = [
    "TSM", "2330.TW", "USDTWD=X",
    "SKHY", "000660.KS", "USDKRW=X",
    "HY9H.F", "EURKRW=X",
    "SMSN.IL", "005930.KS",
    "ASML", "ASML.AS", "USDEUR=X",
    "BABA", "9988.HK", "USDHKD=X",
    "TCEHY", "0700.HK"
]

def get_live_price(symbol, ticker_obj):
    try:
        info = ticker_obj.info
        market_state = info.get("marketState")
        if market_state == "PRE" and info.get("preMarketPrice") is not None:
            return float(info["preMarketPrice"]), "PRE"
        elif market_state == "POST" and info.get("postMarketPrice") is not None:
            return float(info["postMarketPrice"]), "POST"
        
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is not None:
            return float(price), "REGULAR"
            
        return float(ticker_obj.fast_info.get("last_price")), "FAST_INFO"
    except Exception:
        try:
            return float(ticker_obj.fast_info.get("last_price")), "FAST_INFO_FALLBACK"
        except Exception:
            return None, "ERROR"

start_time = time.time()
print("Starting sequential live price fetch...")

for symbol in tickers:
    t_start = time.time()
    t = yf.Ticker(symbol)
    price, state = get_live_price(symbol, t)
    t_end = time.time()
    print(f"Ticker: {symbol:10} | Price: {str(price):10} | State: {state:15} | Time: {t_end - t_start:.2f}s")

end_time = time.time()
print(f"Total time elapsed: {end_time - start_time:.2f}s")
