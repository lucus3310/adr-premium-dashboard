@echo off
title ADR/GDR 盤中即時更新監控器
echo ===================================================
echo   ADR/GDR 盤中即時更新監控器
echo ===================================================
echo.
python monitor.py
if %errorlevel% neq 0 (
    echo.
    echo [錯誤] 監控程式已中斷或無法啟動。
    echo 請確保您已安裝 Python 並且 yfinance, pandas 等套件正常運作。
    pause
)
