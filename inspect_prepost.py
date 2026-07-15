import yfinance as yf

def inspect_extended_hours(symbol):
    print(f"=== Inspecting {symbol} ===")
    try:
        t = yf.Ticker(symbol)
        
        # 1. Print fast_info keys and values
        print("--- fast_info ---")
        for k, v in t.fast_info.items():
            print(f"  {k}: {v}")
            
        # 2. Print specific keys from info
        print("--- info (selected keys) ---")
        info = t.info
        keys_to_check = [
            "regularMarketPrice", "preMarketPrice", "postMarketPrice", 
            "currentPrice", "bid", "ask", "regularMarketPreviousClose",
            "marketState", "regularMarketTime", "preMarketTime", "postMarketTime"
        ]
        for k in keys_to_check:
            if k in info:
                print(f"  {k}: {info[k]}")
            else:
                print(f"  {k}: Not found")
                
    except Exception as e:
        print(f"Error: {e}")

inspect_extended_hours("TSM")
inspect_extended_hours("BABA")
