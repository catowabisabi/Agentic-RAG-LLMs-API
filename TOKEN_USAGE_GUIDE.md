# Token 使用追蹤

查看後端日誌中的這些關鍵詞來判斷是否在消耗 token：

## ✅ 不消耗 Token 的操作
- `EventBus broadcast loop started` - 心跳開始
- `event_type: heartbeat` - 心跳發送
- `Client connected:` - 客戶端連接
- `WebSocket connected` - WS 連接
- `Agent registered:` - Agent 註冊

## ⚠️ 消耗 Token 的操作
- `[Entry] Intent:` - **分類器被調用** (小量 token)
- `[Manager] Handling user query:` - **Manager 開始處理** (開始計費)
- `Calling LLM` - **調用 LLM** (主要消耗)
- `[ReAct] Think:` - **ReAct 推理** (消耗 token)
- `[RAG] Querying` - **RAG 搜尋** (如果啟用)

## 💰 Token 消耗估算
- WebSocket 心跳: **0 tokens**
- 簡單分類: ~100-200 tokens
- ReAct 推理 (3 iterations): ~1000-2000 tokens
- RAG + 回答: ~500-1500 tokens

## 🛡️ 如何避免浪費 Token
1. 不發送消息時，系統完全不消耗 token
2. 心跳只是狀態同步，不調用 AI
3. 如果看到日誌中沒有 `Calling LLM`，就沒有消耗 token
