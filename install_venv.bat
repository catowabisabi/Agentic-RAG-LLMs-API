@echo off
REM ===============================
REM Project venv setup (Python 3.11 + uv)
REM ===============================

cd /d %~dp0

echo [1/6] Checking uv...
where uv >nul 2>&1
if errorlevel 1 (
    echo uv not found, installing...
    pip install -U uv
)

echo [2/6] Installing Python 3.11 via uv...
uv python install 3.11

echo [3/6] Creating venv with Python 3.11...
uv venv venv --python 3.11

echo [4/6] Activating venv...
call venv\Scripts\activate

echo [5/6] Upgrading pip...
uv pip install -U pip

echo [6/6] Installing requirements.txt...
uv pip install -r docker\requirements.txt

echo.
echo ===============================
echo DONE ✅
python --version
echo ===============================
pause
