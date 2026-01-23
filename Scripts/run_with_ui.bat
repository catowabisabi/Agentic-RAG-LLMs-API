@echo off
echo ============================================================
echo Starting Agentic RAG System with UI
echo ============================================================
echo.
echo API Server: http://localhost:1130
echo UI Server:  http://localhost:1131
echo Login: guest / beourguest
echo.
echo ============================================================

cd /d %~dp0\..
python main.py --ui
