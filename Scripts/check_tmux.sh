#!/bin/bash
# 檢查和修復 tmux windows

echo "🔍 檢查 tmux session 狀態..."

# 檢查 session 是否存在
if ! tmux has-session -t agentic_rag 2>/dev/null; then
    echo "❌ agentic_rag session 不存在"
    exit 1
fi

echo "📋 當前 windows:"
tmux list-windows -t agentic_rag

echo ""
echo "🔧 建立標準 windows (如果不存在)..."

# 檢查並建立標準 windows
if ! tmux list-windows -t agentic_rag | grep -q "testing_terminal"; then
    echo "➕ 建立 testing_terminal"
    tmux new-window -t agentic_rag -n 'testing_terminal' -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
fi

if ! tmux list-windows -t agentic_rag | grep -q "api_terminal"; then
    echo "➕ 建立 api_terminal"  
    tmux new-window -t agentic_rag -n 'api_terminal' -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
fi

if ! tmux list-windows -t agentic_rag | grep -q "ui_terminal"; then
    echo "➕ 建立 ui_terminal"
    tmux new-window -t agentic_rag -n 'ui_terminal' -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'  
fi

echo ""
echo "✅ 修復後的 windows:"
tmux list-windows -t agentic_rag

echo ""
echo "🚀 在 api_terminal 中啟動服務..."
tmux send-keys -t agentic_rag:api_terminal 'C-c' Enter  # 中斷現有進程
sleep 1
tmux send-keys -t agentic_rag:api_terminal 'python3 main.py --ui' Enter

echo ""
echo "📱 等待 8 秒後檢查服務狀態..."
sleep 8

echo "📊 api_terminal 最近輸出:"
tmux capture-pane -t agentic_rag:api_terminal -p | tail -10