@echo off
title Agentic RAG - UI Only
color 0D

echo.
echo ============================================================
echo   Agentic RAG UI Server
echo ============================================================
echo.

:: Check if node_modules exists
if not exist "ui\node_modules" (
    echo [INFO] Installing UI dependencies...
    cd ui
    call npm install
    cd ..
)

echo Starting UI Server on http://localhost:1131
echo.
echo Make sure API is running on http://localhost:1130
echo.
echo Press Ctrl+C to stop
echo.

cd ui
call npm run dev
