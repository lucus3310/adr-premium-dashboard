@echo off
title 海外存託憑證 (ADR/GDR) 網站 APP 啟動器
echo ===================================================
echo   海外存託憑證 (ADR/GDR) 網站 APP 啟動器
echo ===================================================
echo.
python server.py
if %errorlevel% neq 0 (
    echo.
    echo [錯誤] 網站 APP 伺服器啟動失敗。
    echo 請確保您已安裝 Python 並且網路環境與埠口 (8000) 正常。
    pause
)
