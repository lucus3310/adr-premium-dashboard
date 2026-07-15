import time
import datetime
import sys
from data_fetcher import fetch_data

def run_loop():
    print("=" * 60)
    print("   海外存託憑證 (ADR/GDR) 盤中即時更新監控器")
    print("=" * 60)
    print(" 說明：此監控器將每 5 分鐘自動執行一次數據更新。")
    print("       更新完成後，您只需在瀏覽器中重新整理 (按 F5) index.html 即可看到最新溢價。")
    print(" 提示：")
    print("   - 亞洲市場開盤時間：台北/香港約 09:00 - 16:00")
    print("   - 歐洲市場開盤時間：歐洲中部約 15:00 - 23:30 (台北時間)")
    print("   - 美國市場開盤時間：美東約 21:30 - 04:00 (台北時間)")
    print("   - 按下 Ctrl + C 可隨時停止此監控器。")
    print("=" * 60)

    interval_seconds = 300  # 5 minutes

    while True:
        now = datetime.datetime.now()
        print(f"\n[{now.strftime('%Y-%m-%d %H:%M:%S')}] 正在啟動數據抓取引擎...")
        
        try:
            fetch_data()
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 數據更新與折溢價計算成功！")
        except Exception as e:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] 執行出錯: {e}", file=sys.stderr)
        
        next_run = datetime.datetime.now() + datetime.timedelta(seconds=interval_seconds)
        print(f"下次執行時間：{next_run.strftime('%H:%M:%S')} (將在 5 分鐘後自動執行)")
        print("等待中...", end="", flush=True)
        
        # Sleep in smaller increments to allow clean exit on Ctrl+C in Windows
        try:
            for _ in range(interval_seconds):
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n監控已停止。感謝使用！")
            break

if __name__ == "__main__":
    run_loop()
