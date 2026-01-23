@echo off
echo Installing UI dependencies...
cd /d %~dp0\..\ui
npm install

echo.
echo Done! Run 'run_with_ui.bat' to start the system.
