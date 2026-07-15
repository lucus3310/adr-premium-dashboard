import http.server
import socketserver
import threading
import time
import datetime
import webbrowser
import os
import sys
from data_fetcher import fetch_data, get_binance_futures_price
import json
import numpy as np

PORT = 8000
DIRECTORY = os.path.dirname(os.path.abspath(__file__))

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Set the directory to host files from
        super().__init__(*args, directory=DIRECTORY, **kwargs)

    def end_headers(self):
        # Disable caching for data files to guarantee real-time updates on refresh
        if self.path.endswith('.js') or self.path.endswith('.json') or 'data.js' in self.path:
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
        super().end_headers()

    def log_message(self, format, *args):
        # Suppress server request logging to keep console output clean for the user
        pass

def update_loop():
    interval_seconds = 300  # 5 minutes update interval
    
    # Initial data load at startup
    now = datetime.datetime.now()
    print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] 正在進行第一次數據初始化抓取...")
    try:
        fetch_data()
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 數據初始化載入成功！")
    except Exception as e:
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 數據初始化抓取錯誤: {e}", file=sys.stderr)

    while True:
        time.sleep(interval_seconds)
        now = datetime.datetime.now()
        print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] 正在背景更新最新股價數據...")
        try:
            fetch_data()
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 背景數據更新與溢價計算成功！")
        except Exception as e:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 背景數據更新出錯: {e}", file=sys.stderr)

def binance_update_loop():
    """
    Background loop that runs every 1 minute to fetch Binance perpetual prices
    and updates the 1-minute intraday dataset for real-time charting.
    """
    interval_seconds = 60  # 1 minute
    
    while True:
        price_local = get_binance_futures_price("SKHYNIXUSDT")
        price_dr = get_binance_futures_price("SKHYUSDT")
        
        if price_local is not None and price_dr is not None:
            now = datetime.datetime.now()
            time_str = now.strftime("%H:%M:%S")
            ratio = 0.1
            premium = ((price_dr / ratio) / price_local - 1) * 100
            
            try:
                json_path = "data.json"
                if os.path.exists(json_path):
                    with open(json_path, "r", encoding="utf-8") as f:
                        master_data = json.load(f)
                    
                    if "series" in master_data and "skhynix_binance" in master_data["series"]:
                        binance_series = master_data["series"]["skhynix_binance"]
                        if "intraday_1m" not in binance_series:
                            binance_series["intraday_1m"] = []
                        
                        # Append new 1m intraday price record
                        new_record = {
                            "time": time_str,
                            "local": price_local,
                            "adr": price_dr,
                            "premium": round(premium, 4)
                        }
                        binance_series["intraday_1m"].append(new_record)
                        
                        # Keep only the last 60 minutes of data
                        if len(binance_series["intraday_1m"]) > 60:
                            binance_series["intraday_1m"].pop(0)
                        
                        # Also update today's last daily history point
                        today_str = now.strftime("%Y-%m-%d")
                        history = binance_series.get("history", [])
                        if history:
                            if history[-1]["date"] == today_str:
                                history[-1]["local"] = price_local
                                history[-1]["adr"] = price_dr
                                history[-1]["equiv"] = price_dr
                                history[-1]["premium"] = round(premium, 4)
                            else:
                                history.append({
                                    "date": today_str,
                                    "local": price_local,
                                    "adr": price_dr,
                                    "fx": 1.0,
                                    "equiv": price_dr,
                                    "premium": round(premium, 4)
                                })
                        
                        # Re-calculate statistics including this new latest premium
                        prems = [item["premium"] for item in history]
                        if prems:
                            binance_series["stats"] = {
                                "mean": round(float(np.mean(prems)), 4),
                                "median": round(float(np.median(prems)), 4),
                                "min": round(float(np.min(prems)), 4),
                                "max": round(float(np.max(prems)), 4),
                                "std": round(float(np.std(prems)), 4),
                                "latest": round(premium, 4)
                            }
                        
                        # Update global last_updated time
                        master_data["last_updated"] = now.strftime("%Y-%m-%d %H:%M:%S")
                        
                        # Save back to data.json
                        with open(json_path, "w", encoding="utf-8") as f:
                            json.dump(master_data, f, ensure_ascii=False, indent=2)
                        
                        # Save back to data.js
                        js_path = "data.js"
                        with open(js_path, "w", encoding="utf-8") as f:
                            f.write("window.HISTORICAL_DATA = " + json.dumps(master_data, ensure_ascii=False, indent=2) + ";")
                        
                        print(f"[{time_str}] 幣安 1 分鐘即時數據更新成功！(Premium: {premium:.2f}%)")
            except Exception as e:
                print(f"Error updating Binance intraday data: {e}", file=sys.stderr)
        
        # Sleep for 1 minute before the next iteration
        time.sleep(interval_seconds)

def start_server():
    # 1. Start the background data monitoring loop thread
    update_thread = threading.Thread(target=update_loop, daemon=True)
    update_thread.start()

    # 2. Start the Binance-specific 1-minute real-time update loop thread
    binance_thread = threading.Thread(target=binance_update_loop, daemon=True)
    binance_thread.start()

    # 3. Setup and run TCP HTTP Server
    socketserver.TCPServer.allow_reuse_address = True
    
    preferred_ports = [8000, 8080, 8888, 9000, 9999, 0]
    httpd = None
    assigned_port = None
    
    for port in preferred_ports:
        try:
            # Bind to 0.0.0.0 to enable local network access (e.g. from iPhone)
            httpd = socketserver.TCPServer(("0.0.0.0", port), Handler)
            assigned_port = httpd.server_address[1]
            break
        except OSError:
            if port == 0:
                print("\n[錯誤] 無法取得任何可用的連接埠來啟動伺服器。")
                return
            print(f"連接埠 {port} 已被其它程式佔用，正在嘗試下一個...")
            continue
            
    if httpd is None:
        print("\n[錯誤] 伺服器啟動失敗。")
        return

    # Dynamically resolve local network IP for friendly mobile instructions
    import socket
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    print("=" * 60)
    print("        海外存託憑證 (ADR/GDR) 網站 APP 伺服器已啟動")
    print("=" * 60)
    print(f"  本機存取網址：http://127.0.0.1:{assigned_port}/")
    if local_ip != "127.0.0.1":
        print(f"  手機 (Wi-Fi) 存取網址：http://{local_ip}:{assigned_port}/")
    print("  功能與使用指引：")
    print(f"    - 程式已將數據與網頁託管於本機連接埠 {assigned_port}。")
    print("    - 背景更新執行緒每 5 分鐘會自動重新抓取盤中數據。")
    print("    - 幣安永續合約價格每 1 分鐘會自動於背景抓取並記錄。")
    print("    - 手機與電腦需連線至同一個 Wi-Fi 即可直接存取。")
    print("    - 請保持此命令提示字元視窗開啟，關閉本視窗即可關閉伺服器。")
    print("=" * 60)

    # 4. Automatically launch browser after 1.5 seconds delay
    def launch_browser():
        time.sleep(1.5)
        print("正在為您開啟瀏覽器加載網站 App...")
        webbrowser.open(f"http://127.0.0.1:{assigned_port}/")
    
    browser_thread = threading.Thread(target=launch_browser, daemon=True)
    browser_thread.start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n伺服器已安全停止。感謝使用！")
    finally:
        if httpd:
            httpd.server_close()

if __name__ == "__main__":
    start_server()
