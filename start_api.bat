@echo off
title Agentic RAG - API Only
color 0B

echo.
echo ============================================================
echo   Agentic RAG API Server
echo ============================================================
echo.

:: Check if .env exists
if not exist "config\.env" (
    echo [WARNING] config\.env not found, copying from .env.example...
    copy "config\.env.example" "config\.env" >nul
    echo Please edit config\.env with your API keys before continuing.
    pause
)

echo Starting API Server on http://localhost:1130
echo.
echo API Endpoints:
echo   - Health Check: GET  /health
echo   - Chat:         POST /api/agent/chat
echo   - Query:        POST /api/agent/query  
echo   - VectorDB:     POST /api/vectordb/*
echo   - WebSocket:    WS   /ws/{client_id}
echo.
echo Press Ctrl+C to stop
echo.

python main.py
