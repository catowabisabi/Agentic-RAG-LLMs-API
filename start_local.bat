@echo off
title Agentic RAG - Local Development
color 0A

echo.
echo ============================================================
echo   Agentic RAG - Local Development Server
echo ============================================================
echo.

:: Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    pause
    exit /b 1
)

:: Check if .env exists
if not exist "config\.env" (
    echo [WARNING] config\.env not found, copying from .env.example...
    copy "config\.env.example" "config\.env" >nul
    echo Please edit config\.env with your API keys
    pause
)

:: Check if node_modules exists for UI
if not exist "ui\node_modules" (
    echo [INFO] Installing UI dependencies...
    cd ui
    call npm install
    cd ..
)

:: Kill existing processes on ports 1130 and 1131
echo [INFO] Checking for existing processes...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :1130 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :1131 ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1
timeout /t 1 /nobreak >nul

echo.
echo [1] Starting API Server on port 1130...
echo [2] Starting UI Server on port 1131...
echo.
echo Press Ctrl+C to stop all servers
echo.

:: Start API in background
start /B cmd /c "python main.py 2>&1 | findstr /v /c:\"^\""

:: Wait for API to start
timeout /t 3 /nobreak >nul

:: Start UI
cd ui
call npm run dev

pause
