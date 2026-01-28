#!/bin/bash
# 直接在 api_terminal 中啟動服務

echo "🚀 啟動 Agentic RAG 服務 (API + UI)..."

# 檢查是否有 agentic_rag session，如果沒有就建立
if ! tmux has-session -t agentic_rag 2>/dev/null; then
    echo "🆕 建立 agentic_rag session..."
    tmux new-session -d -s agentic_rag -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
    tmux new-window -t agentic_rag -n 'testing_terminal' -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
    tmux new-window -t agentic_rag -n 'api_terminal' -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
    tmux new-window -t agentic_rag -n 'ui_terminal' -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
fi

# 在 api_terminal 中啟動服務
echo "📡 啟動服務在 api_terminal..."
tmux send-keys -t agentic_rag:api_terminal 'C-c' Enter  # 先中斷任何現有進程
sleep 1
tmux send-keys -t agentic_rag:api_terminal 'conda activate agentic' Enter
tmux send-keys -t agentic_rag:api_terminal 'python main.py --ui' Enter

echo "✅ 服務已啟動！"
echo "📡 API: http://localhost:1130"  
echo "🌐 UI: http://localhost:1131"
echo "🔐 Login: guest / beourguest"
echo ""
echo "💡 使用以下指令查看:"
echo "   tmux capture-pane -t agentic_rag:api_terminal -p | tail -10"