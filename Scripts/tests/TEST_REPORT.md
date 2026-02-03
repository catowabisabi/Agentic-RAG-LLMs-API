# RAG 系統測試報告

## 1. 健康檢查: ✓ 200

## 2. 數據庫列表: ✓ 200
總共 12 個數據庫
- ✓ agentic-rag-docs: 32 文檔
- ✓ solidworks: 154 文檔
- ✓ agentic-example: 172 文檔
- ✓ programming: 142 文檔
- ✓ agentic-examples: 172 文檔
- ✓ hosting-docs: 24 文檔

**有效知識庫**: ['agentic-rag-docs', 'solidworks', 'agentic-example', 'programming', 'agentic-examples', 'hosting-docs']

## 3. Agent 列表: ✓ 200
總共 16 個 agents 運行中

## 4. RAG 數據庫查詢 (agentic-rag-docs): ✓ 200
返回 3 條結果
  - 結果1: # Agentic RAG LLMs API - Project Structure

## Overview

This is a multi-agent RAG (Retrieval-Augmented Generation) system built with:
- **LangGraph** for agent orchestration
- **LangChain** for LLM i...
  - 結果2: # LangGraph RAG Demo

A demonstration of building a Retrieval-Augmented Generation (RAG) system using LangGraph for stateful agent workflows.

## Features

- **Stateful RAG Agent**: Uses LangGraph for...

## 5. 智能多庫查詢: ✓ 200
- 查詢模式: multi
- 結果總數: 9
- 搜索數據庫: ['agentic-rag-docs', 'solidworks', 'programming', 'agentic-examples', 'hosting-docs']

## 6. 簡單對話 (無 RAG): ✓ 200
回應: 你好！我是你的AI助手，可以幫你回答問題和聊天。有什麼我可以幫你解答的嗎？...

## 7. RAG 增強對話: ✓ 200
回應: 這個 RAG 系統具備以下功能：

1. **API 服務**：
   - 非同步接收使用者請求 (`POST /query`)。
   - 查詢任務狀態 (`GET /status/{task_id}`)。
   - 收集使用者滿意度反饋 (`POST /feedback`)。

2. **即時通訊**：
   - 支援全雙工通訊的 WebSocket 端點，用於逐字串流回傳。

3. **任務處理**：
   - 使用任務佇列 (Redis/BackgroundTasks) 處理長運行的 Agent 流程。

4. **增強推理能力**：
   - 自我反思 (Reflection) 檢查回答準確性。
   - 多步檢索 (ReAct) 支援複雜查詢。
   - 規劃 (Planning) 生成執行計畫。

5. **多代理協作**：
   - 專職分工的多代理系統。

6. **情節記憶**：
   - 記住使用者過去的對話與偏好。

這些功能共同提升了系統的準確性、靈活性和用戶體驗。...
涉及 Agents: ['entry_classifier', 'manager_agent', 'rag_agent']
來源數量: 10

---
## 總結
- API 服務: ✓ 運行中
- 有效知識庫: 6 個
- 知識庫列表: agentic-rag-docs, solidworks, agentic-example, programming, agentic-examples, hosting-docs
- 測試完成