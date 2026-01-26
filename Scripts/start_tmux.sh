#!/bin/bash
# tmux 啟動腳本 - 在已設置好的 WSL 環境中使用

cd /mnt/d/codebase/Agentic-RAG-LLMs-API

# 檢查是否已在 tmux session 中
if [ -n "$TMUX" ]; then
    echo "🔄 已在 tmux 中，切換到 agentic_rag session..."
    if tmux has-session -t agentic_rag 2>/dev/null; then
        tmux switch-client -t agentic_rag
    else
        echo "🆕 建立 agentic_rag session..."
        # 建立標準化 windows
        tmux new-session -d -s agentic_rag -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
        tmux new-window -t agentic_rag -n 'testing_terminal' -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
        tmux new-window -t agentic_rag -n 'api_terminal' -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
        tmux new-window -t agentic_rag -n 'ui_terminal' -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
        
        # 切換到新建立的 session
        tmux switch-client -t agentic_rag
    fi
else
    # 不在 tmux 中，正常 attach
    if tmux has-session -t agentic_rag 2>/dev/null; then
        echo "🔄 連接到現有 tmux session..."
        tmux attach-session -t agentic_rag
    else
        echo "🆕 建立新 tmux session..."
        
        # 建立主 session
        tmux new-session -d -s agentic_rag -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
        
        # 建立標準化 windows
        tmux new-window -t agentic_rag -n 'testing_terminal' -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
        tmux new-window -t agentic_rag -n 'api_terminal' -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
        tmux new-window -t agentic_rag -n 'ui_terminal' -c '/mnt/d/codebase/Agentic-RAG-LLMs-API'
        
        # 連接到 session
        tmux attach-session -t agentic_rag
    fi
fi

# 如果成功切換/連接，在 api_terminal 中啟動服務
echo "🚀 在 api_terminal 中啟動服務..."