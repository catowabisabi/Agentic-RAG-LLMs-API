# Agentic RAG API - MCP 服務指南
## Model Context Protocol (MCP) - 投資者技術說明

---

## 一、什麼是 MCP？

**Model Context Protocol (MCP)** 是 Anthropic 開發的開放標準，用於讓 AI 應用程式安全地連接外部工具和資料源。

### 核心價值

```
┌─────────────────────────────────────────────────────────────┐
│                    傳統 AI 應用                              │
│  ┌─────────┐                                                │
│  │   LLM   │ ←→ 只能使用訓練資料                            │
│  └─────────┘                                                │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    MCP 增強的 AI 應用                        │
│  ┌─────────┐     ┌───────────────────────────────────┐     │
│  │   LLM   │ ←→  │  MCP Server                       │     │
│  └─────────┘     │  ├── 網頁搜尋 (Brave)             │     │
│                  │  ├── 程式碼執行 (E2B)             │     │
│                  │  ├── 資料庫查詢 (Supabase)        │     │
│                  │  ├── 醫學文獻 (PubMed)            │     │
│                  │  ├── 自動化流程 (Zapier)          │     │
│                  │  └── 檔案管理 (File System)       │     │
│                  └───────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、我們的 MCP 服務一覽

### 2.1 Web Intelligence（網路智能）

| Provider | 功能 | 商業價值 |
|----------|------|----------|
| **Brave Search** | 隱私優先的網頁搜尋 | 即時資訊檢索，無需擔心使用者資料外洩 |
| **Firecrawl** | 網頁爬蟲與結構化提取 | 自動將任何網站轉換為結構化資料 |
| **Exa** | 語意搜尋引擎 | 比關鍵字搜尋更精準的 AI 驅動搜尋 |

**使用情境**：
- 市場競爭分析：自動追蹤競爭對手網站變化
- 輿情監控：即時搜尋品牌相關新聞
- 資料採集：將網頁內容自動轉換為結構化資料庫

### 2.2 Code Execution（程式碼執行）

| Provider | 功能 | 商業價值 |
|----------|------|----------|
| **E2B** | 雲端沙盒執行 | 安全執行用戶提供的程式碼 |

**使用情境**：
- 資料分析：用戶上傳 CSV，AI 自動撰寫 Python 分析程式碼並執行
- 教育平台：學生提交程式碼，AI 即時執行並給予回饋
- 自動化報告：定期執行資料處理腳本生成報告

### 2.3 Database Integration（資料庫整合）

| Provider | 功能 | 商業價值 |
|----------|------|----------|
| **Supabase** | PostgreSQL + Realtime | AI 直接查詢和修改業務資料庫 |

**使用情境**：
- 客服自動化：AI 直接查詢訂單狀態回覆客戶
- 銷售報告：自然語言查詢「上個月北區銷售額」
- 資料錄入：對話式資料輸入取代表單

### 2.4 Medical Intelligence（醫療智能）

| Service | 功能 | 商業價值 |
|---------|------|----------|
| **MedicalRAGService** | PubMed、PMC 文獻檢索 | 醫療文獻即時查詢 |

**使用情境**：
- 臨床決策支援：醫生查詢最新治療指南
- 藥物交互檢查：檢查多種藥物的相互作用
- 醫學教育：AI 助教回答醫學問題並附上文獻來源

### 2.5 Automation（自動化）

| Provider | 功能 | 商業價值 |
|----------|------|----------|
| **Zapier** | 5000+ 應用整合 | AI 觸發跨應用工作流程 |
| **GitHub** | 程式碼倉庫操作 | 自動化 DevOps 流程 |

**使用情境**：
- 銷售自動化：當 AI 判斷客戶有購買意願，自動在 CRM 建立機會
- 客戶通知：對話結束後自動發送跟進郵件
- 工單系統：AI 判斷問題類型後自動建立 Jira ticket

### 2.6 File & System Control（檔案與系統控制）

| Provider | 功能 | 商業價值 |
|----------|------|----------|
| **FileControl** | 讀寫 TXT/JSON/CSV/PDF | AI 處理本地文件 |
| **SystemCommand** | 執行系統指令 | 自動化系統維護 |

**使用情境**：
- 文件處理：上傳合約 PDF，AI 自動提取關鍵條款
- 報表生成：將分析結果匯出為 Excel
- 系統監控：定期檢查伺服器狀態

---

## 三、架構圖

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Client Applications                          │
│   (Claude Desktop / VS Code / Custom Apps / Web Interface)           │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ MCP Protocol (stdio / SSE)
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        MCP Server (Port 8001)                        │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                         Tools Layer                            │  │
│  │  • query_agents      • list_agents       • get_agent_status   │  │
│  │  • query_rag         • add_document      • interrupt_agent    │  │
│  │  • create_plan       • deep_think        • summarize          │  │
│  │  • translate         • calculate         • read_file          │  │
│  │  • write_file        • search_web        • execute_code       │  │
│  │  • query_database    • send_email        • search_pubmed      │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                      Providers Layer                           │  │
│  │  BraveSearch │ Firecrawl │ Exa │ E2B │ Supabase │ GitHub     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                      Services Layer                            │  │
│  │  MedicalRAG │ CodeExecution │ WebScraping │ Automation        │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Main API Server (Port 1130)                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    14 Multi-Agents                             │  │
│  │  Manager │ RAG │ Memory │ Planning │ Thinking │ Validation    │  │
│  │  Notes │ Roles │ Data │ Tool │ Summarize │ Translate │ Calc   │  │
│  │  CasualChat (with LangGraph)                                   │  │
│  └───────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                    Vector Database (ChromaDB)                  │  │
│  │  solidworks(296) │ agentic-example(172) │ agentic-rag-docs(32)│  │
│  │  medical │ personal-finance │ market-data │ trading DBs       │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 四、商業模式與變現路徑

### 4.1 SaaS 訂閱模式

| 方案 | 價格 | 包含功能 |
|------|------|----------|
| **Starter** | $99/月 | 基礎 RAG、5 個 Agents、1 個 VectorDB |
| **Professional** | $299/月 | 全部 Agents、10 個 VectorDB、MCP 工具 |
| **Enterprise** | 自訂 | 私有部署、無限 DB、專屬支援 |

### 4.2 按使用量計費

| 資源 | 單價 |
|------|------|
| API 呼叫 | $0.001/次 |
| Vector 儲存 | $0.01/MB/月 |
| MCP 工具呼叫 | $0.01/次 |

### 4.3 垂直產業解決方案

| 產業 | 解決方案 | 預估市場規模 |
|------|----------|--------------|
| 醫療 | Medical RAG + PubMed 整合 | 醫療 AI 市場 2027 年達 $67B |
| 金融 | 交易策略 + 市場數據分析 | 金融 AI 市場 2030 年達 $130B |
| 法律 | 合約分析 + 案例檢索 | 法律科技市場 2027 年達 $37B |
| 教育 | 程式碼執行 + 個人化學習 | EdTech 市場 2030 年達 $400B |

---

## 五、競爭優勢

### 5.1 技術差異化

| 特點 | 我們 | 競爭對手 |
|------|------|----------|
| Multi-Agent 架構 | ✅ 14 個專業 Agents | ❌ 單一 Agent |
| LangGraph 整合 | ✅ 自我修正迴圈 | ❌ 線性執行 |
| MCP 標準支援 | ✅ 完整實作 | ⚠️ 部分支援 |
| Vector DB 多租戶 | ✅ 每客戶獨立 DB | ❌ 共享 DB |
| 即時 WebSocket | ✅ 串流輸出 | ❌ 批次回應 |

### 5.2 開放生態

- **MCP 標準**：與 Claude Desktop、VS Code Copilot 等工具無縫整合
- **API First**：RESTful + WebSocket，任何客戶端都能接入
- **模組化**：Providers 可獨立升級和擴展

---

## 六、快速開始

### 6.1 啟動服務

```bash
# 啟動主服務（包含 UI）
python main.py --ui

# 或單獨啟動 MCP Server
python -m mcp.server
```

### 6.2 測試 MCP 服務

```bash
# 執行 MCP 服務測試
python Scripts/test_mcp_services.py --all
```

### 6.3 API 端點

| 端點 | 說明 |
|------|------|
| `http://localhost:1130/` | 主 API |
| `http://localhost:1130/docs` | Swagger 文檔 |
| `http://localhost:1131/` | Web UI |
| `ws://localhost:1130/ws` | WebSocket |

---

## 七、路線圖

### Q1 2026
- [x] Multi-Agent 系統基礎架構
- [x] LangGraph PlanningAgent 整合
- [x] MCP 12+ Providers
- [ ] Claude Desktop 整合測試

### Q2 2026
- [ ] Enterprise SSO 整合
- [ ] Kubernetes 自動擴展
- [ ] 多語言 SDK (Python, JS, Go)

### Q3 2026
- [ ] 產業垂直解決方案包
- [ ] AI Agent Marketplace
- [ ] 自訂 Agent 訓練平台

---

## 附錄：技術規格

| 指標 | 規格 |
|------|------|
| 支援模型 | OpenAI GPT-4, Claude 3, Gemini |
| Vector DB | ChromaDB (可擴展至 Pinecone, Weaviate) |
| 最大併發 | 5 Agents 同時運行 |
| 回應延遲 | 簡單查詢 <2s, 複雜規劃 <10s |
| API 速率 | 100 req/min (可調整) |

---

*文檔版本：1.0 | 最後更新：2026-01-28*
