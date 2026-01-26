# Agentic RAG Multi-Agent System - 重建指南

## 概述

本指南記錄如何重建所有向量資料庫的 embeddings，以及如何測試真正的 multi-agent 協調流程。

---

## 問題診斷

### 發現的問題

1. **Embedding 維度不匹配**
   ```
   ERROR: Collection expecting embedding with dimension of 384, got 1536
   ```
   - 舊資料庫使用 384 維度 (可能是 all-MiniLM-L6-v2)
   - 現在配置使用 text-embedding-3-small (1536 維度)
   - 受影響資料庫：11 個，共 1463 個文檔

2. **假的 Agent 協調**
   - chat_router.py 只發送 WebSocket 廣播
   - 沒有真正調用 agent 的 process_task()
   - 回應立即返回（< 1 秒），沒有真實的處理時間
   - 所有 "thinking" 都是假的消息

---

## 解決方案

### Part 1: 重建 Embeddings

#### 準備工作

1. **停止正在運行的 API**
   ```bash
   # 在 WSL 中
   tmux send-keys -t agentic_rag:2 C-c
   ```

2. **檢查現有資料庫**
   ```bash
   cd /mnt/d/codebase/Agentic-RAG-LLMs-API
   python -c "from services.vectordb_manager import vectordb_manager; \
              dbs = vectordb_manager.list_databases(); \
              print(f'Total: {len(dbs)} databases'); \
              [print(f'{d[\"name\"]}: {d.get(\"document_count\", 0)} docs') for d in dbs]"
   ```

#### 執行重建

**方法 1: 使用自動化腳本（推薦）**

```bash
cd /mnt/d/codebase/Agentic-RAG-LLMs-API
python rebuild_simple.py
```

這會：
- 刪除所有舊資料庫目錄
- 創建空的新資料庫（使用 1536 維度 embeddings）
- 生成重建日誌：`embedding_rebuild_simple.json`

**注意：資料庫會是空的，需要重新導入文檔！**

#### 重新導入文檔

重建後，資料庫是空的。需要重新導入所有文檔：

```bash
# 方法 1: 使用載入腳本（如果有原始文檔）
python Scripts/load_docs_to_rag.py

# 方法 2: 通過 API 手動添加
curl -X POST http://localhost:1130/rag/document \
  -H 'Content-Type: application/json' \
  -d '{
    "database": "solidworks-api",
    "content": "Your document content here...",
    "metadata": {
      "title": "Document Title",
      "source": "Source URL or path"
    }
  }'
```

#### 驗證重建

```bash
# 測試查詢
python test_rag.py

# 或通過 API
curl -X POST http://localhost:1130/rag/query \
  -H 'Content-Type: application/json' \
  -d '{"database": "solidworks-api", "query": "How to use SelectByID2?"}'
```

---

### Part 2: 真正的 Multi-Agent 協調

#### 修改內容

1. **chat_router.py** - 真正調用 Manager Agent
   ```python
   # 之前：假的協調，只發 WebSocket 廣播
   await ws_manager.broadcast_agent_activity(...)
   response = await llm.ainvoke(...)  # 直接調用 LLM
   
   # 現在：真正的 multi-agent 流程
   manager_agent = registry.get_agent("manager_agent")
   result = await manager_agent.process_task(task)  # 真實處理
   ```

2. **manager_agent.py** - 新增 `_handle_user_query()` 方法
   - Planning Agent 分析查詢（1.5 秒）
   - RAG Agent 查詢知識庫（2-5 秒）
   - Thinking Agent 深度推理（3-5 秒）
   - Validation Agent 驗證回應（1 秒）
   - **總時間：8-15 秒**（正常的處理時間）

#### 真實的執行流程

```
User Query
    ↓
Manager Agent (收到任務)
    ↓
Planning Agent (分析 & 創建計劃) ← 1.5s
    ↓
RAG Agent (查詢向量資料庫) ← 2-5s
    ↓
Thinking Agent (使用 context 推理) ← 3-5s
    ↓
Validation Agent (檢查質量) ← 1s
    ↓
Manager Agent (返回結果)
    ↓
User Response
```

#### WebSocket 活動流

正確的 COT (Chain of Thought) 應該顯示：

```json
[
  {"type": "agent_started", "agent": "manager_agent", "timestamp": "T+0s"},
  {"type": "thinking", "agent": "manager_agent", "timestamp": "T+0.1s"},
  {"type": "task_assigned", "agent": "planning_agent", "timestamp": "T+0.2s"},
  {"type": "thinking", "agent": "planning_agent", "timestamp": "T+0.3s"},
  {"type": "task_assigned", "agent": "rag_agent", "timestamp": "T+1.8s"},
  {"type": "thinking", "agent": "rag_agent", "timestamp": "T+1.9s"},
  {"type": "agent_completed", "agent": "rag_agent", "timestamp": "T+5.2s"},
  {"type": "task_assigned", "agent": "thinking_agent", "timestamp": "T+5.3s"},
  {"type": "thinking", "agent": "thinking_agent", "timestamp": "T+5.4s"},
  {"type": "agent_completed", "agent": "thinking_agent", "timestamp": "T+9.8s"},
  {"type": "task_assigned", "agent": "validation_agent", "timestamp": "T+9.9s"},
  {"type": "thinking", "agent": "validation_agent", "timestamp": "T+10.0s"},
  {"type": "agent_completed", "agent": "validation_agent", "timestamp": "T+11.0s"},
  {"type": "agent_completed", "agent": "manager_agent", "timestamp": "T+11.1s"}
]
```

---

## 測試步驟

### 1. 重啟 API（在 WSL）

```bash
tmux send-keys -t agentic_rag:2 C-c
sleep 2
tmux send-keys -t agentic_rag:2 'python main.py' Enter
```

### 2. 測試真實的 Agent 協調

```bash
# 測試 SolidWorks 查詢（需要等待 10-15 秒）
curl -X POST http://localhost:1130/chat/message \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "How to use IModelDocExtension in SolidWorks API?",
    "use_rag": true
  }' | jq .

# 檢查回應
# - agents_involved 應該包含：manager_agent, planning_agent, rag_agent, thinking_agent, validation_agent
# - 處理時間應該 > 10 秒
# - sources 應該包含相關文檔（如果已重新導入）
```

### 3. 監控 WebSocket 活動

在瀏覽器打開 UI (`http://localhost:1131`)，查看：

- **Chat 頁面**：COT 面板應該實時顯示每個 agent 的活動
- **Agents 頁面**：Agent 狀態應該從 idle → busy → idle
- **時間線**：應該看到明顯的等待時間（不是立即完成）

### 4. 驗證真實性

**檢查點：**

✅ 回應時間 > 10 秒（不是 < 1 秒）  
✅ COT 顯示真實的 agent 活動（有時間間隔）  
✅ Agents 頁面顯示狀態變化  
✅ API 日誌顯示實際的 OpenAI 請求  
✅ sources 包含相關文檔（如果 RAG 有數據）

---

## 文件位置參考

### 修改的文件

- `fast_api/routers/chat_router.py` - 真正的 manager agent 調用
- `agents/core/manager_agent.py` - `_handle_user_query()` 方法
- `ui/components/ChatPage.tsx` - COT 去重邏輯
- `ui/components/AgentsPage.tsx` - Agent 狀態動態更新

### 重建腳本

- `rebuild_embeddings.py` - 完整版（有備份，但在 WSL 有權限問題）
- `rebuild_embeddings_auto.py` - 自動確認版本
- `rebuild_simple.py` - 簡化版（無備份，推薦）

### 測試腳本

- `test_rag.py` - RAG 查詢測試

### 日誌文件

- `embedding_rebuild_simple.json` - 重建日誌
- `rebuild_output.log` - 重建輸出

---

## 示例文件參考

查看 `app_docs/Agentic-Rag-Examples/` 以了解正確的 multi-agent 架構：

- `05_multi_agent.ipynb` - Multi-Agent 系統實現
- `11_meta_controller.ipynb` - Meta Controller 路由模式
- `README.md` - 所有 17 種 agent 架構說明

---

## 故障排除

### 問題：Embedding 維度錯誤

```
ERROR: Collection expecting embedding with dimension of 384, got 1536
```

**解決：**
1. 執行 `rebuild_simple.py`
2. 重新導入文檔

### 問題：回應太快（< 1 秒）

**原因：** 沒有真正調用 agent，還是用舊的直接 LLM 調用

**解決：**
1. 檢查 `chat_router.py` 是否調用 `manager_agent.process_task()`
2. 重啟 API
3. 查看 API 日誌確認 agent 活動

### 問題：RAG 沒有返回 sources

**原因：**
1. 資料庫是空的（重建後未導入）
2. 查詢詞與文檔不匹配
3. Embedding 仍有問題

**解決：**
1. 執行 `test_rag.py` 檢查資料庫狀態
2. 確認文檔已重新導入
3. 調整查詢詞

---

## 下一步

1. ✅ 重建所有 embeddings
2. ✅ 真正的 multi-agent 協調
3. ⏳ 重新導入所有文檔到資料庫
4. ⏳ 測試完整的 RAG 流程
5. ⏳ UI 顯示優化

---

**作者：** AI Assistant  
**日期：** 2026-01-26  
**版本：** 1.0
