@echo off
cd /d "%~dp0"
echo.
echo  ==========================================
echo   Accounting DB Viewer
echo   http://localhost:8765
echo  ==========================================
echo.

:: Try to find python in the conda env
set PYTHON=python

:: Check if uvicorn is available
%PYTHON% -c "import uvicorn" 2>nul
if errorlevel 1 (
    echo [INFO] Installing dependencies...
    %PYTHON% -m pip install fastapi uvicorn --quiet
)

echo [INFO] Starting server at http://localhost:8765
echo [INFO] Press Ctrl+C to stop
echo.

:: Open browser after short delay
start "" cmd /c "timeout /t 2 /nobreak >nul && start http://localhost:8765"

%PYTHON% server.py

pause
