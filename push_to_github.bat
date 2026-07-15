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
git config --global user.email >nul 2>nul
if %errorlevel% neq 0 (
    echo 偵測到尚未設定 Git 身分，正在為您設定預設身分...
    git config --global user.email "lucus3310@example.com"
    git config --global user.name "lucus3310"
)

:: 3. Initialize git if not done
if not exist .git (
    echo 正在初始化 Git 儲存庫...
    git init -b main
)

:: 4. Add remote repository
echo 正在設定 GitHub 遠端連結...
git remote remove origin >nul 2>nul
git remote add origin https://github.com/lucus3310/adr-premium-dashboard.git

:: 5. Add and commit files
echo 正在新增檔案與建立提交...
git add .
git commit -m "Initial commit for serverless dashboard"

:: 6. Push to GitHub
echo.
echo 正在推送至 GitHub (如果跳出網頁請點選授權/登入)...
echo.
git push -u origin main --force

if %errorlevel% equ 0 (
    echo.
    echo ===================================================
    echo [成功] 專案已順利上傳至 GitHub！
    echo ===================================================
) else (
    echo.
    echo [失敗] 推送失敗。請確認：
    echo 1. 您已在 GitHub 網頁上建立了名為 "adr-premium-dashboard" 的專案庫。
    echo 2. 您的 GitHub 帳號名稱確為 "lucus3310"。
)
echo.
pause
