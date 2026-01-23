# RAG Demo 整合與擴充規劃 (Planning)

基於 `all-agentic-architectures-main` 存儲庫中的代理架構模式，以及建立即時生產級 API 服務的需求，本文件詳細規劃了 `rag-demo` 的未來發展藍圖。

## 概要

我們將打造一個現代化的 RAG 系統，該系統不僅擁有強大的後端推理能力（透過 LangGraph 整合多種代理模式），還具備可擴展的 API 服務架構（FastAPI + WebSocket + 任務佇列）。

---

## 1. 系統架構設計

### 整體架構圖
```mermaid
graph TD
    Client[客戶端 Web/Mobile] <-->|WebSocket / REST| Gateway[FastAPI Server]
    Gateway -->|HTTP POST| TaskQueue[任務隊列 (Redis/BackgroundTasks)]
    TaskQueue --> Worker[Agent Worker]
    Worker -->|Invoke| LangGraphApp[LangGraph 應用]
    
    subgraph "LangGraph Agent 核心"
    LangGraphApp --> Planner[規劃器 (Planning)]
    Planner --> Router{路由 (Router/Meta)}
    
    Router -->|一般查詢| RAG[RAG 檢索增強]
    Router -->|複雜推理| ReAct[ReAct 推理引擎]
    Router -->|多角觀點| Ensemble[多觀點集成]
    
    RAG & ReAct & Ensemble --> Critic[自我反思 Critic]
    Critic -->|通過| FinalAnswer[最終回答]
    Critic -->|未通過| Refiner[優化器] --> Router
    end
    
    Worker -->|Save| DB[(資料庫 / 向量庫)]
    Worker -->|Stream| PubSub[Redis Pub/Sub]
    PubSub --> Gateway
```

### API 服務層功能
- **FastAPI 整合**: 
    - `POST /query`: 非同步接收使用者請求，回傳 `task_id`。
    - `GET /status/{task_id}`: 輪詢任務狀態與結果。
    - `POST /feedback`: 收集使用者對回答的滿意度 (RLHF data)。
- **即時通訊 (WebSocket)**: 
    - `/ws/chat/{client_id}`: 全雙工通訊，支援從 Agent 逐字串流 (Streaming) 回傳 Token 給前端，提供更好的 UX。
- **背景任務**: 使用 `BackgroundTasks` 或 `Celery/Redis` 處理長運行 Agent 流程，避免阻塞 API 線程。

---

## 2. 代理架構整合 (Agentic Patterns)

這裡列出 `all-agentic-architectures-main` 中可用的 17 種模式，並說明如何應用於本專案。

### 核心增強 (高優先級)
這些模式能直接解決 RAG 常見的準確度與邏輯問題。

1.  **Reflection (01_reflection.ipynb) - 自我反思**:
    *   **應用**: 在生成回答後加入「Critic Node」，檢查是否有幻覺、是否回答了用戶問題。
    *   **優勢**: 將單次生成變為 `生成 -> 檢查 -> 修改` 的循環，大幅提升準確度。

2.  **Tool Use (02_tool_use.ipynb) - 工具使用**:
    *   **應用**: 賦予 Agent 除了 `retriever` 之外的工具，例如 `WebSearch` (補足最新資訊)、`Calculator` (處理財報數據)。

3.  **ReAct (03_ReAct.ipynb) - 推理與行動**:
    *   **應用**: 允許 Agent 進行多步檢索。例如：「先查 A 公司的產品，再查 B 公司的產品，最後比較差異」。

4.  **Planning (04_planning.ipynb) - 規劃**:
    *   **應用**: 針對複雜查詢，先生成一個「執行計畫」(Plan)，再按步驟執行。
    *   **場景**: "幫我寫一份關於 LangGraph 的導入計畫書，需包含安裝、優缺點和範例程式碼"。

5.  **Multi-Agent (05_multi_agent.ipynb) - 多代理協作**:
    *   **應用**: 專職分工。`Researcher` 負責廣泛搜索，`Writer` 負責統整撰寫，`Editor` 負責格式審查。

6.  **Episodic Memory (08_episodic_with_semantic.ipynb) - 情節記憶**:
    *   **應用**: 讓 Agent 記住使用者過去的對話與偏好（例如：「依據我上次提到的專案背景...」）。這需要升級 Vector Store 來存儲對話片段。

### 進階推理 (中優先級)
用於處理模糊或高度複雜的問題。

7.  **Meta Controller (11_meta_controller.ipynb) - 元控制**:
    *   **應用**: 當系統有多個特定領域的 Agent (如 HR Agent, Tech Support Agent) 時，由 Meta Controller 決定派發給誰。

8.  **Ensemble (13_ensemble.ipynb) - 集成**:
    *   **應用**: 對於關鍵問題，同時讓三個不同的 Prompt/Model 生成回答，再由投票機制選出最佳解。

9.  **Tree of Thoughts (09_tree_of_thoughts.ipynb) - 思維樹**:
    *   **應用**: 探索多種可能的解決路徑，並進行前瞻性評估，選擇最佳路徑繼續。適合策略性問題。

10. **Graph (12_graph.ipynb)**:
    *   **應用**: 我們目前的 LangGraph 本身就是此模式的實踐，將 Agent 流程定義為圖結構。

11. **Dry Run (14_dry_run.ipynb) - 試運行**:
    *   **應用**: 如果 Agent 生成程式碼，先在沙盒環境執行一次確認無誤，再回傳給使用者。

### 實驗性與輔助 (低優先級/特定場景)

12. **PEV (06_PEV.ipynb) - Plan, Execute, Verify**: 類似 Planning + Code Execution 的組合。
13. **Blackboard (07_blackboard.ipynb)**: 多個 Agent 共享一個黑板狀態，適合複雜協作場景，暫時可用 Shared Graph State 取代。
14. **Mental Loop (10_mental_loop.ipynb)**: 簡單的內部獨白循環，可被 Reflection 涵蓋。
15. **RLHF (15_RLHF.ipynb)**: 從人類回饋中學習。這需要建立資料收集 pipeline (透過 API 的 `/feedback` 端點)。
16. **Cellular Automata (16_cellular_automata.ipynb)**: 較為學術的自組織模式，目前 RAG 應用場景較少。
17. **Reflexive Metacognitive (17_reflexive_metacognitive.ipynb)**: Agent 動態修改自己的系統提示詞與策略，屬於高階的自我進化。

---

## 3. 開發路線圖 (Roadmap)

### Phase 1: 基礎建設與 API 化 (Current)
- [ ] 建立 `api_server.py` (FastAPI)
- [ ] 實作基本的 `invocations` 端點 (POST /query)
- [ ] 整合 `BackgroundTasks` 進行非阻塞處理
- [ ] 建立基本的 WebSocket 端點用於串流測試

### Phase 2: 增強 Agent 核心 (Robustness)
- [ ] 實作 **Reflection (01)**: 加入 Quality Check 循環
- [ ] 實作 **ReAct (03)**: 升級 Retriever 節點支援多步查詢
- [ ] 實作 **Memory (08)**: 整合 ConversationMemory 到 VectorDB

### Phase 3: 進階功能與優化 (Intelligence)
- [ ] 實作 **Planning (04)**: 為長查詢加入規劃步驟
- [ ] 擴充 **Router (11)**: 分流不同類型的問題
- [ ] 完善 **Streaming**: 透過 WebSocket 串流 Graph 的中間狀態與 Token

### Phase 4: 生產環境準備
- [ ] 加入任務隊列 (Redis/Dramatiq)
- [ ] 加入使用者認證與 Rate Limiting
- [ ] Docker 化部署

---

## 結論
此架構規劃將 RAG Demo 從一個簡單的腳本轉變為一個全功能的 AI 應用平台。透過整合 LangGraph 的強大編排能力與 FastAPI 的高效服務，我們能提供既準確又具備即時互動能力的系統。
