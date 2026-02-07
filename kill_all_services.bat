@echo off
echo ====================================
echo 停止所有 Agentic RAG 相關服務
echo ====================================

echo.
echo [1] 停止所有 Python 程序...
taskkill /f /im python.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ Python 程序已停止
) else (
    echo - 沒有 Python 程序在執行
)

echo.
echo [2] 停止所有 Node.js 程序...
taskkill /f /im node.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ Node.js 程序已停止
) else (
    echo - 沒有 Node.js 程序在執行
)

echo.
echo [3] 停止所有 uvicorn 程序...
taskkill /f /im uvicorn.exe >nul 2>&1
if %errorlevel% equ 0 (
    echo ✓ uvicorn 程序已停止
) else (
    echo - 沒有 uvicorn 程序在執行
)

echo.
echo [4] 檢查 port 1130 (API) 和 1131 (UI)...
set "port1130="
set "port1131="

for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":1130"') do set "port1130=%%a"
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":1131"') do set "port1131=%%a"

if defined port1130 (
    echo - 強制停止 port 1130 程序: %port1130%
    taskkill /f /pid %port1130% >nul 2>&1
) else (
    echo ✓ Port 1130 已清空
)

if defined port1131 (
    echo - 強制停止 port 1131 程序: %port1131%
    taskkill /f /pid %port1131% >nul 2>&1
) else (
    echo ✓ Port 1131 已清空
)

echo.
echo [5] 最終檢查...
powershell -Command "Get-Process | Where-Object {$_.ProcessName -like '*python*' -or $_.ProcessName -like '*node*' -or $_.ProcessName -like '*uvicorn*'} | Select-Object ProcessName, Id"

echo.
echo ====================================
echo ✅ 清理完成！所有服務已停止
echo ====================================
echo.
echo 💡 如需重新啟動：
echo    - API 後端: start_api.bat
echo    - UI 前端: cd ui ^& npm run dev
echo.
pause