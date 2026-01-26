#!/bin/bash
# 清理和標準化 tmux session

echo "🧹 清理 tmux session..."

# 殺掉重複的 windows，保留編號較小的
echo "🗑️ 移除重複 windows..."
tmux kill-window -t agentic_rag:4 2>/dev/null  # 重複的 testing_terminal
tmux kill-window -t agentic_rag:6 2>/dev/null  # 重複的 ui_terminal  
tmux kill-window -t agentic_rag:5 2>/dev/null  # api_terminal-

# 重命名確保名稱正確
echo "📝 標準化 window 名稱..."
tmux rename-window -t agentic_rag:0 'main'
tmux rename-window -t agentic_rag:1 'testing_terminal' 2>/dev/null
tmux rename-window -t agentic_rag:2 'api_terminal' 2>/dev/null
tmux rename-window -t agentic_rag:3 'ui_terminal' 2>/dev/null

echo "✅ 清理後的 windows:"
tmux list-windows -t agentic_rag

echo ""
echo "🚀 在 window 2 (api_terminal) 啟動服務..."
tmux send-keys -t agentic_rag:2 'C-c' Enter
sleep 1
tmux send-keys -t agentic_rag:2 'python3 main.py --ui' Enter

echo ""
echo "📱 等待 10 秒後檢查服務狀態..."
sleep 10

echo "📊 window 2 (api_terminal) 輸出:"
tmux capture-pane -t agentic_rag:2 -p | tail -10

echo ""
echo "💡 記住：使用 window 編號比較可靠:"
echo "   tmux send-keys -t agentic_rag:2 'command' Enter  # api_terminal"
echo "   tmux capture-pane -t agentic_rag:2 -p | tail -10"