import yfinance as yf
import pandas as pd
import json
import os
import numpy as np
import datetime
import sys
import urllib.request

# Config dict containing all metadata
STOCKS_CONFIG = {
    "tsmc": {
        "name": "台積電 (TSMC)",
        "local_ticker": "2330.TW",
        "local_currency": "TWD",
        "dr_listings": {
            "us": {
                "name": "美股 ADR (TSM)",
                "ticker": "TSM",
                "currency": "USD",
                "fx_ticker": "USDTWD=X",
                "ratio": 5.0,
                "csv_name": "tsmc_premium.csv"
            }
        }
    },
    "skhynix": {
        "name": "SK海力士 (SK Hynix)",
        "local_ticker": "000660.KS",
        "local_currency": "KRW",
        "dr_listings": {
            "us": {
                "name": "美股 ADR (SKHY)",
                "ticker": "SKHY",
                "currency": "USD",
                "fx_ticker": "USDKRW=X",
                "ratio": 0.1,
                "csv_name": "skhynix_premium_us.csv"
            },
            "gdr": {
                "name": "德股 GDR (HY9H.F)",
                "ticker": "HY9H.F",
                "currency": "EUR",
                "fx_ticker": "EURKRW=X",
                "ratio": 1.0,
                "csv_name": "skhynix_premium_gdr.csv"
            },
            "binance": {
                "name": "幣安永續合約 (SKHYUSDT)",
                "ticker": "SKHYUSDT",
                "currency": "USDT",
                "fx_ticker": "1.0",
                "ratio": 0.1,
                "csv_name": "skhynix_binance_premium.csv",
                "override_local_ticker": "SKHYNIXUSDT",
                "override_local_currency": "USDT"
            }
        }
    },
    "samsung": {
        "name": "三星電子 (Samsung)",
        "local_ticker": "005930.KS",
        "local_currency": "KRW",
        "dr_listings": {
            "gdr": {
                "name": "英股 GDR (SMSN.IL)",
                "ticker": "SMSN.IL",
                "currency": "USD",
                "fx_ticker": "USDKRW=X",
                "ratio": 25.0,
                "csv_name": "samsung_premium_gdr.csv"
            }
        }
    },
    "asml": {
        "name": "艾司摩爾 (ASML)",
        "local_ticker": "ASML.AS",
        "local_currency": "EUR",
        "dr_listings": {
            "us": {
                "name": "美股 ADR (ASML)",
                "ticker": "ASML",
                "currency": "USD",
                "fx_ticker": "USDEUR=X",
                "ratio": 1.0,
                "csv_name": "asml_premium.csv"
            }
        }
    },
    "alibaba": {
        "name": "阿里巴巴 (Alibaba)",
        "local_ticker": "9988.HK",
        "local_currency": "HKD",
        "dr_listings": {
            "us": {
                "name": "美股 ADR (BABA)",
                "ticker": "BABA",
                "currency": "USD",
                "fx_ticker": "USDHKD=X",
                "ratio": 8.0,
                "csv_name": "alibaba_premium.csv"
            }
        }
    },
    "tencent": {
        "name": "騰訊控股 (Tencent)",
        "local_ticker": "0700.HK",
        "local_currency": "HKD",
        "dr_listings": {
            "us": {
                "name": "美股 OTC ADR (TCEHY)",
                "ticker": "TCEHY",
                "currency": "USD",
                "fx_ticker": "USDHKD=X",
                "ratio": 1.0,
                "csv_name": "tencent_premium.csv"
            }
        }
    }
}

def get_binance_futures_price(symbol):
    """
    Fetches the live ticker price of a Binance Futures symbol.
    """
    url = f"https://fapi.binance.com/fapi/v1/ticker/price?symbol={symbol}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return float(data['price'])
    except Exception as e:
        print(f"Error fetching Binance live price for {symbol}: {e}")
        return None

def get_binance_klines(symbol, interval="1d", limit=1000, time_format="%Y-%m-%d"):
    """
    Fetches historical close prices for a Binance Futures symbol.
    Returns a DataFrame with a DatetimeIndex (date-only, no time component).
    """
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            if not data:
                return pd.DataFrame(columns=["Close"])
            records = []
            for item in data:
                # Convert ms timestamp to UTC date string
                dt = datetime.datetime.fromtimestamp(item[0] / 1000.0, tz=datetime.timezone.utc)
                date_str = dt.strftime(time_format)
                close_price = float(item[4])
                records.append((date_str, close_price))
            df = pd.DataFrame(records, columns=["Date", "Close"])
            # Normalize index to date-only (same as Yahoo Finance output)
            df["Date"] = pd.to_datetime(df["Date"]).dt.normalize()
            df = df.set_index("Date")
            df = df[~df.index.duplicated(keep="last")]
            return df
    except Exception as e:
        print(f"Error fetching Binance klines for {symbol}: {e}")
        return pd.DataFrame(columns=["Close"])
def get_binance_15m_premium(dr_symbol, local_symbol, ratio, limit=192):
    """
    Fetches 15-minute klines for both dr and local Binance Futures symbols,
    aligns them by timestamp, calculates premium, and returns a list of records.
    limit=192 covers the last 48 hours (192 x 15min = 48h).
    Time labels are expressed in UTC+8 for readability.
    """
    url_dr = f"https://fapi.binance.com/fapi/v1/klines?symbol={dr_symbol}&interval=15m&limit={limit}"
    url_local = f"https://fapi.binance.com/fapi/v1/klines?symbol={local_symbol}&interval=15m&limit={limit}"
    try:
        req_dr = urllib.request.Request(url_dr, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_dr, timeout=10) as r:
            data_dr = json.loads(r.read().decode())

        req_local = urllib.request.Request(url_local, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_local, timeout=10) as r:
            data_local = json.loads(r.read().decode())

        # Build timestamp -> close price dicts
        dr_prices = {item[0]: float(item[4]) for item in data_dr}
        local_prices = {item[0]: float(item[4]) for item in data_local}

        # Join on common timestamps
        common_ts = sorted(set(dr_prices.keys()) & set(local_prices.keys()))
        records = []
        for ts in common_ts:
            dt_utc = datetime.datetime.fromtimestamp(ts / 1000.0, tz=datetime.timezone.utc)
            dt_local = dt_utc + datetime.timedelta(hours=8)  # Convert to UTC+8
            time_str = dt_local.strftime("%m-%d %H:%M")
            price_dr = dr_prices[ts]
            price_local = local_prices[ts]
            premium = ((price_dr / ratio) / price_local - 1) * 100
            records.append({
                "time": time_str,
                "local": round(price_local, 4),
                "adr": round(price_dr, 4),
                "premium": round(premium, 4)
            })
        print(f"  Binance 15m premium: fetched {len(records)} candles for {dr_symbol}/{local_symbol}")
        return records
    except Exception as e:
        print(f"Error fetching Binance 15m premium for {dr_symbol}/{local_symbol}: {e}")
        return []

def get_binance_1m_premium(dr_symbol, local_symbol, ratio, limit=60):
    """
    Fetches 1-minute klines for both dr and local Binance Futures symbols,
    aligns them by timestamp, calculates premium, and returns a list of records.
    limit=60 covers the last 60 minutes.
    Time labels are expressed in UTC+8 for readability (HH:MM:SS format to match server.py).
    """
    url_dr = f"https://fapi.binance.com/fapi/v1/klines?symbol={dr_symbol}&interval=1m&limit={limit}"
    url_local = f"https://fapi.binance.com/fapi/v1/klines?symbol={local_symbol}&interval=1m&limit={limit}"
    try:
        req_dr = urllib.request.Request(url_dr, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_dr, timeout=10) as r:
            data_dr = json.loads(r.read().decode())

        req_local = urllib.request.Request(url_local, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_local, timeout=10) as r:
            data_local = json.loads(r.read().decode())

        # Build timestamp -> close price dicts
        dr_prices = {item[0]: float(item[4]) for item in data_dr}
        local_prices = {item[0]: float(item[4]) for item in data_local}

        # Join on common timestamps
        common_ts = sorted(set(dr_prices.keys()) & set(local_prices.keys()))
        records = []
        for ts in common_ts:
            dt_utc = datetime.datetime.fromtimestamp(ts / 1000.0, tz=datetime.timezone.utc)
            dt_local = dt_utc + datetime.timedelta(hours=8)  # Convert to UTC+8
            time_str = dt_local.strftime("%H:%M:%S")
            price_dr = dr_prices[ts]
            price_local = local_prices[ts]
            premium = ((price_dr / ratio) / price_local - 1) * 100
            records.append({
                "time": time_str,
                "local": round(price_local, 4),
                "adr": round(price_dr, 4),
                "premium": round(premium, 4)
            })
        print(f"  Binance 1m premium: fetched {len(records)} candles for {dr_symbol}/{local_symbol}")
        return records
    except Exception as e:
        print(f"Error fetching Binance 1m premium for {dr_symbol}/{local_symbol}: {e}")
        return []

def get_live_price(symbol, ticker_obj):
    """
    Fetches real-time / intraday price including pre-market and post-market sessions.
    """
    if symbol.endswith("USDT"):
        return get_binance_futures_price(symbol)
        
    try:
        info = ticker_obj.info
        market_state = info.get("marketState")
        
        # Check for Pre-market price
        if market_state == "PRE" and info.get("preMarketPrice") is not None:
            return float(info["preMarketPrice"])
        # Check for Post-market price
        elif market_state == "POST" and info.get("postMarketPrice") is not None:
            return float(info["postMarketPrice"])
            
        # Standard active session price
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is not None:
            return float(price)
            
        # Fast fallback
        return float(ticker_obj.fast_info.get("last_price"))
    except Exception:
        try:
            return float(ticker_obj.fast_info.get("last_price"))
        except Exception:
            return None

def calculate_stats(df, col):
    if df.empty:
        return {"mean": 0, "median": 0, "min": 0, "max": 0, "std": 0, "latest": 0}
    
    clean_series = df[col].replace([np.inf, -np.inf], np.nan).dropna()
    if clean_series.empty:
        return {"mean": 0, "median": 0, "min": 0, "max": 0, "std": 0, "latest": 0}
        
    return {
        "mean": round(float(clean_series.mean()), 4),
        "median": round(float(clean_series.median()), 4),
        "min": round(float(clean_series.min()), 4),
        "max": round(float(clean_series.max()), 4),
        "std": round(float(clean_series.std()), 4),
        "latest": round(float(clean_series.iloc[-1]), 4)
    }

def format_history(df):
    records = []
    for date_val, row in df.iterrows():
        date_str = date_val.strftime("%Y-%m-%d")
        
        def sanitize(val):
            return None if pd.isna(val) or np.isinf(val) else round(float(val), 4)
            
        record = {
            "date": date_str,
            "local": sanitize(row["local_close"]),
            "adr": sanitize(row["dr_close"]),
            "fx": sanitize(row["fx_close"]),
            "equiv": sanitize(row["dr_equiv"]),
            "premium": sanitize(row["premium_pct"])
        }
        records.append(record)
    return records

def fetch_data():
    period = "5y"
    series_data = {}
    
    print("=== Step 1: Downloading raw data from Yahoo Finance & Binance ===")
    
    downloaded_tickers = {}
    downloaded_data = {}
    
    # Gather all unique tickers
    unique_tickers = set()
    for stock_key, stock_info in STOCKS_CONFIG.items():
        unique_tickers.add(stock_info["local_ticker"])
        for dr_key, dr_info in stock_info["dr_listings"].items():
            unique_tickers.add(dr_info["ticker"])
            unique_tickers.add(dr_info["fx_ticker"])
            if "override_local_ticker" in dr_info:
                unique_tickers.add(dr_info["override_local_ticker"])
            
    # Download all unique tickers
    for t in sorted(unique_tickers):
        if t == "1.0":
            continue
        print(f"Downloading {t}...")
        try:
            if t.endswith("USDT"):
                # Download Binance Futures klines (returns DataFrame directly)
                df = get_binance_klines(t)
                if df.empty:
                    print(f"Warning: No Binance data returned for {t}")
                downloaded_tickers[t] = None  # No yfinance Ticker object for Binance
            else:
                # Download Yahoo Finance history
                ticker = yf.Ticker(t)
                df = ticker.history(period=period)
                downloaded_tickers[t] = ticker
                if df.empty:
                    print(f"Warning: No data returned for {t}")
                    df = pd.DataFrame(columns=["Close"])
                else:
                    # Normalize to date-only index (no time/timezone)
                    df.index = pd.to_datetime(df.index.date)
                    df = df[["Close"]]
            
            downloaded_data[t] = df
        except Exception as e:
            print(f"Error downloading {t}: {e}")
            downloaded_data[t] = pd.DataFrame(columns=["Close"])

    print("\n=== Step 2: Processing stock series with Live/Extended Hours Prices ===")
    
    for stock_key, stock_info in STOCKS_CONFIG.items():
        local_t_default = stock_info["local_ticker"]
        
        for dr_key, dr_info in stock_info["dr_listings"].items():
            dr_t = dr_info["ticker"]
            fx_t = dr_info["fx_ticker"]
            ratio = dr_info["ratio"]
            csv_name = dr_info["csv_name"]
            local_t = dr_info.get("override_local_ticker", local_t_default)
            
            print(f"Processing {stock_info['name']} -> {dr_info['name']}...")
            
            dr_df = downloaded_data[dr_t].rename(columns={"Close": "dr_close"})
            local_df = downloaded_data[local_t].rename(columns={"Close": "local_close"})
            
            if fx_t == "1.0":
                fx_df = pd.DataFrame(1.0, index=dr_df.index, columns=["fx_close"])
            else:
                fx_df = downloaded_data[fx_t].rename(columns={"Close": "fx_close"})
            
            # Merge datasets (outer join to keep all dates)
            merged = dr_df.join([local_df, fx_df], how="outer")
            
            # Get live active prices (use Binance live for USDT pairs, yfinance for others)
            live_dr = get_live_price(dr_t, downloaded_tickers.get(dr_t))
            live_local = get_live_price(local_t, downloaded_tickers.get(local_t))
            
            if fx_t == "1.0":
                live_fx = 1.0
            else:
                live_fx = get_live_price(fx_t, downloaded_tickers.get(fx_t))
            
            # Merge live points into today's date slot
            today_dt = pd.to_datetime(datetime.date.today())
            latest_date = merged.index[-1] if not merged.empty else today_dt
            
            # Append today if new day, else update last row
            if today_dt > latest_date:
                merged.loc[today_dt] = np.nan
                latest_date = today_dt
                
            if live_dr is not None:
                merged.loc[latest_date, "dr_close"] = live_dr
            if live_local is not None:
                merged.loc[latest_date, "local_close"] = live_local
            if live_fx is not None:
                merged.loc[latest_date, "fx_close"] = live_fx
            
            # Forward fill and clean
            merged = merged.ffill()
            merged = merged.dropna(subset=["dr_close", "local_close", "fx_close"])
            
            # Calculations
            merged["dr_equiv"] = merged["dr_close"] * merged["fx_close"]
            merged["local_equiv"] = merged["local_close"] * ratio
            merged["premium_pct"] = (merged["dr_equiv"] / merged["local_equiv"] - 1) * 100
            
            # Save to individual CSV
            merged.to_csv(csv_name)
            print(f"  Saved CSV to {csv_name} (rows: {len(merged)})")
            
            # Compute stats and format history
            series_key = f"{stock_key}_{dr_key}"
            series_data[series_key] = {
                "stats": calculate_stats(merged, "premium_pct"),
                "history": format_history(merged)
            }

    # --- Fetch Binance 15m intraday premium (48h window, auto-refreshes every run) ---
    print("\nFetching Binance 15m intraday premium for skhynix_binance...")
    records_15m = get_binance_15m_premium("SKHYUSDT", "SKHYNIXUSDT", ratio=0.1, limit=192)
    if records_15m and "skhynix_binance" in series_data:
        series_data["skhynix_binance"]["intraday_15m"] = records_15m

    # --- Fetch Binance 1m intraday premium (last 60 minutes, auto-refreshes every run) ---
    print("\nFetching Binance 1m intraday premium for skhynix_binance...")
    records_1m = get_binance_1m_premium("SKHYUSDT", "SKHYNIXUSDT", ratio=0.1, limit=60)
    if records_1m and "skhynix_binance" in series_data:
        series_data["skhynix_binance"]["intraday_1m"] = records_1m

    print("\n=== Step 3: Compiling Master JSON outputs ===")

    master_output = {
        "metadata": STOCKS_CONFIG,
        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "series": series_data
    }

    # Preserve intraday_1m AND merge history from existing data.json.
    # Critical: if Binance API is unreachable (GitHub Actions cloud),
    # the new history would be empty/short. We merge so no historical rows are lost.
    try:
        json_path = "data.json"
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f_old:
                old_data = json.load(f_old)

            if "series" in old_data and "skhynix_binance" in old_data["series"]:
                old_binance = old_data["series"]["skhynix_binance"]

                if "skhynix_binance" in master_output["series"]:
                    new_binance = master_output["series"]["skhynix_binance"]

                    # --- Preserve/Merge intraday_1m ---
                    if "intraday_1m" not in new_binance or not new_binance["intraday_1m"]:
                        if "intraday_1m" in old_binance:
                            new_binance["intraday_1m"] = old_binance["intraday_1m"]

                    # --- Merge history: old rows + new rows, new wins on same date ---
                    old_history = old_binance.get("history", [])
                    new_history = new_binance.get("history", [])

                    if old_history:
                        history_map = {r["date"]: r for r in old_history}
                        for r in new_history:
                            history_map[r["date"]] = r  # new data overwrites same date
                        merged_history = sorted(history_map.values(), key=lambda x: x["date"])
                        new_binance["history"] = merged_history

                        # Re-compute stats from merged history
                        prems = [r["premium"] for r in merged_history if r.get("premium") is not None]
                        if prems:
                            new_binance["stats"] = {
                                "mean": round(float(np.mean(prems)), 4),
                                "median": round(float(np.median(prems)), 4),
                                "min": round(float(np.min(prems)), 4),
                                "max": round(float(np.max(prems)), 4),
                                "std": round(float(np.std(prems)), 4),
                                "latest": round(float(prems[-1]), 4)
                            }
                        print(f"  skhynix_binance history merged: {len(old_history)} old + {len(new_history)} new -> {len(merged_history)} total rows")

    except Exception as e:
        print(f"Error preserving/merging skhynix_binance data: {e}")

    # Save to data.json
    json_path = "data.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(master_output, f, ensure_ascii=False, indent=2)
    print(f"Saved {json_path}")

    # Save to data.js
    js_path = "data.js"
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("window.HISTORICAL_DATA = " + json.dumps(master_output, ensure_ascii=False, indent=2) + ";")
    print(f"Saved {js_path}")

    print("\nData update process complete!")

if __name__ == "__main__":
    fetch_data()
