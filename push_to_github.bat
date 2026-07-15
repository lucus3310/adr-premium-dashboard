@echo off
chcp 65001 >nul
echo ===================================================
echo             GitHub 專案推送自動化助手
echo ===================================================
echo.

:: 1. Check if git is installed
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [錯誤] 找不到 git 指令，請確認已成功安裝 Git！
    pause
    exit /b
)

:: 2. Configure default git identity if not set
for /f "tokens=*" %%i in ('git config --global user.email 2^>nul') do set GIT_EMAIL=%%i
if "%GIT_EMAIL%"=="" (
    echo 偵測到尚未設定 Git 身分，正在為您設定...
    git config --global user.email "lucus3310@users.noreply.github.com"
    git config --global user.name "lucus3310"
)

:: 3. Initialize git if not done
if not exist .git (
    echo 正在初始化 Git 儲存庫...
    git init -b main
    git remote add origin https://github.com/lucus3310/adr-premium-dashboard.git
) else (
    :: Ensure remote is set correctly
    git remote get-url origin >nul 2>nul
    if %errorlevel% neq 0 (
        git remote add origin https://github.com/lucus3310/adr-premium-dashboard.git
    )
)

:: 4. Pull latest remote changes (merge ours for auto-generated data files)
echo 正在從 GitHub 拉取最新版本...
git fetch origin main >nul 2>nul
if %errorlevel% equ 0 (
    git merge origin/main --strategy-option=ours --no-commit -q >nul 2>nul
    if %errorlevel% equ 0 (
        echo [OK] 已成功合併遠端版本
    ) else (
        echo [OK] 無需合併（本地已是最新）
    )
)

:: 5. Regenerate data to ensure freshness
echo 正在重新生成最新數據...
python data_fetcher.py
if %errorlevel% neq 0 (
    echo [警告] data_fetcher.py 執行失敗，將使用現有數據繼續推送
)

:: 6. Add and commit files
echo 正在新增檔案與建立提交...
git add -A
git commit -m "Manual update: refresh all data and code [skip ci]"

:: 7. Push to GitHub
echo.
echo 正在推送至 GitHub (如果跳出網頁請點選授權/登入)...
echo.
git push origin main

if %errorlevel% equ 0 (
    echo.
    echo ===================================================
    echo [成功] 專案已順利上傳至 GitHub！
    echo GitHub Pages 將在數分鐘內自動更新。
    echo ===================================================
) else (
    echo.
    echo [失敗] 推送失敗。請確認網路連線與 GitHub 帳號設定。
)
echo.
pause
