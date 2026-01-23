# Agentic RAG LLMs API - 專案資料夾結構

## 專案概述
此專案是一個基於 LangGraph 的 RAG (Retrieval-Augmented Generation) 系統，整合了多種 Agentic 架構模式，提供強大的 AI 代理服務。支援多租戶向量資料庫、並行代理執行（最多 5 個同時運行）、即時 WebSocket 串流，以及 MCP (Model Context Protocol) 外部工具整合。

## 專案根目錄結構

```
Agentic-RAG-LLMs-API/
├── .claude/                           # Claude AI 相關配置與技能
│   └── skills/                        # 自定義技能模組
│       ├── feature-spec-qa-skill/
│       ├── flutter-page-ui-checking-skill/
│       ├── flutter-user-test-skill/
│       ├── logic_bug_scanner_skill/
│       ├── nodebb-life-services-controller-skill/
│       ├── review-existing-code-references-skill/
│       ├── simple-api-call-skill/
│       ├── skill-creator/
│       ├── start-flutter-skill/
│       ├── ui_state_loading_checking_skill/
│       ├── virtual-user-test-skill/
│       └── webapp-testing-skill/
├── .copilot/                          # GitHub Copilot 配置
├── .env.example                       # 環境變數範本
├── .gitignore                         # Git 忽略文件配置
├── main.py                            # 主程式進入點
├── project-folder-structure.md        # 專案結構文檔 (本文件)
│
├── agents/                            # AI 代理模組
│   ├── __init__.py                    # 模組初始化
│   ├── nodes.py                       # 節點定義
│   ├── rag_agent.py                   # RAG 代理核心邏輯
│   │
│   ├── core/                          # 核心代理 (主要功能代理)
│   │   ├── __init__.py
│   │   ├── manager_agent.py           # 管理代理 (協調其他代理)
│   │   ├── memory_agent.py            # 記憶代理 (管理對話記憶)
│   │   ├── notes_agent.py             # 筆記代理 (管理用戶筆記)
│   │   ├── planning_agent.py          # 規劃代理 (任務規劃)
│   │   ├── rag_agent.py               # RAG 代理 (向量檢索)
│   │   ├── roles_agent.py             # 角色代理 (角色扮演)
│   │   ├── thinking_agent.py          # 思考代理 (推理分析)
│   │   └── validation_agent.py        # 驗證代理 (結果驗證)
│   │
│   ├── auxiliary/                     # 輔助代理 (支援功能)
│   │   ├── __init__.py
│   │   ├── calculation_agent.py       # 計算代理 (數學運算)
│   │   ├── data_agent.py              # 資料代理 (資料處理)
│   │   ├── summarize_agent.py         # 摘要代理 (文本摘要)
│   │   ├── tool_agent.py              # 工具代理 (外部工具調用)
│   │   └── translate_agent.py         # 翻譯代理 (多語言翻譯)
│   │
│   └── shared_services/               # 共享服務 (代理間共用)
│       ├── __init__.py
│       ├── agent_registry.py          # 代理註冊表 + 並行控制 (最多5個)
│       ├── base_agent.py              # 代理基類
│       ├── message_protocol.py        # 訊息協議定義
│       ├── response_models.py         # 結構化回應模型 (JSON格式)
│       └── websocket_manager.py       # WebSocket 管理 + 即時UI串流
│
├── app_docs/                          # 應用程式文檔
│   ├── PLANNING.md                    # 專案規劃文件
│   ├── README.md                      # 專案說明文件
│   ├── VECTOR_DATABASE_GUIDE.md       # 向量資料庫使用指南 (NEW)
│   ├── project-folder-structure.md    # 專案結構文檔
│   ├── requirements.txt               # Python 依賴套件
│   ├── requirements2.txt              # 額外依賴套件
│   └── Agentic-Rag-Examples/          # Agentic RAG 範例集合
│       ├── .env                       # 環境變數配置
│       ├── LICENSE                    # 授權文件
│       ├── README.md                  # 範例說明文件
│       ├── requirements.txt           # 範例依賴套件
│       ├── 01_reflection.ipynb        # 反思模式範例
│       ├── 02_tool_use.ipynb          # 工具使用範例
│       ├── 03_ReAct.ipynb             # ReAct 推理範例
│       ├── 04_planning.ipynb          # 規劃模式範例
│       ├── 05_multi_agent.ipynb       # 多代理協作範例
│       ├── 06_PEV.ipynb               # Plan-Execute-Verify 範例
│       ├── 07_blackboard.ipynb        # 黑板架構範例
│       ├── 08_episodic_with_semantic.ipynb  # 情節記憶範例
│       ├── 09_tree_of_thoughts.ipynb  # 思維樹範例
│       ├── 10_mental_loop.ipynb       # 心理循環範例
│       ├── 11_meta_controller.ipynb   # 元控制器範例
│       ├── 12_graph.ipynb             # 圖形架構範例
│       ├── 13_ensemble.ipynb          # 集成方法範例
│       ├── 14_dry_run.ipynb           # 試運行範例
│       ├── 15_RLHF.ipynb              # 人類回饋強化學習範例
│       ├── 16_cellular_automata.ipynb # 細胞自動機範例
│       └── 17_reflexive_metacognitive.ipynb  # 反思元認知範例
│
├── config/                            # 配置文件目錄
│   ├── .env.example                   # 環境變數範本
│   └── config.py                      # 配置管理模組
│
├── docker/                            # Docker 容器化配置
│   ├── .dockerignore                  # Docker 忽略文件
│   ├── docker-compose.yml             # Docker Compose 配置
│   └── Dockerfile                     # Docker 鏡像構建文件
│
├── documents/                         # 文檔處理模組
│   └── load_documents.py              # 文檔載入工具
│
├── fast_api/                          # FastAPI 服務模組 (使用下劃線)
│   ├── __init__.py                    # 模組初始化
│   ├── app.py                         # FastAPI 應用主體
│   └── routers/                       # API 路由
│       ├── __init__.py
│       ├── agent_router.py            # 代理相關 API
│       ├── chat_router.py             # 聊天 API
│       ├── rag_router.py              # RAG 與資料庫管理 API
│       └── websocket_router.py        # WebSocket 端點
│
├── mcp/                               # Model Context Protocol (MCP)
│   ├── __init__.py                    # 模組初始化
│   ├── server.py                      # MCP 伺服器
│   │
│   ├── providers/                     # MCP 提供者 (外部服務整合)
│   │   ├── __init__.py
│   │   ├── base_provider.py           # 提供者基類
│   │   ├── brave_search_provider.py   # Brave Search 網頁搜尋
│   │   ├── e2b_provider.py            # E2B 沙箱代碼執行
│   │   ├── exa_provider.py            # Exa AI 搜尋
│   │   ├── firecrawl_provider.py      # Firecrawl 網頁爬取
│   │   ├── github_provider.py         # GitHub API 整合
│   │   ├── supabase_provider.py       # Supabase 資料庫
│   │   └── zapier_provider.py         # Zapier 自動化
│   │
│   └── services/                      # MCP 服務層 (組合多個提供者)
│       ├── __init__.py
│       ├── automation_service.py      # 自動化服務 (Zapier + GitHub)
│       ├── code_execution_service.py  # 代碼執行服務 (E2B)
│       ├── database_service.py        # 資料庫服務 (Supabase)
│       └── web_scraping_service.py    # 網頁爬取服務 (Firecrawl + Exa + Brave)
│
├── rag-database/                      # RAG 資料庫存儲
│   └── vectordb/                      # 向量資料庫 (ChromaDB)
│       ├── index.json                 # 主索引文件
│       ├── db_metadata.json           # 資料庫元資料 (多租戶管理)
│       ├── chemistry/                 # 化學領域向量資料
│       │   └── index.json
│       ├── market-data/               # 市場資料向量資料
│       │   └── index.json
│       ├── medicine/                  # 醫學領域向量資料
│       │   └── index.json
│       ├── personal-finance/          # 個人理財向量資料
│       │   └── index.json
│       ├── pinescript/                # Pine Script 向量資料
│       │   └── index.json
│       ├── python-tradebot/           # Python 交易機器人向量資料
│       │   └── index.json
│       ├── short-trading/             # 短線交易向量資料
│       │   └── index.json
│       └── solidworks-api/            # SolidWorks API 向量資料
│           └── index.json
│
├── Scripts/                           # 執行腳本目錄
│   ├── run_api.bat                    # 啟動 API 服務腳本
│   ├── run_client.bat                 # 啟動客戶端腳本
│   └── setup.bat                      # 環境設置腳本
│
├── services/                          # 業務邏輯服務
│   ├── __init__.py                    # 模組初始化
│   └── vectordb_manager.py            # 向量資料庫管理器 (多租戶支援)
│
├── tools/                             # 工具模組
│   ├── memory.py                      # 記憶體管理工具
│   └── retriever.py                   # 檢索工具
│
└── utils/                             # 通用工具模組
    └── ...                            # 通用輔助函數
```

## 主要模組說明

### 核心模組

#### agents/ - AI 代理系統
分為三層架構：
- **core/**: 核心功能代理，處理主要業務邏輯（管理、記憶、規劃、思考、驗證等）
- **auxiliary/**: 輔助功能代理，提供支援服務（計算、摘要、翻譯、工具調用）
- **shared_services/**: 共享服務，包含代理間通用功能
  - `agent_registry.py`: 代理註冊表，包含 **ConcurrencyController** 限制最多 5 個代理同時運行
  - `response_models.py`: 結構化 JSON 回應模型（是/否、建議、計算結果、思考過程等）
  - `websocket_manager.py`: WebSocket 管理器，支援即時 UI 狀態盒更新

#### services/ - 業務邏輯服務
- **vectordb_manager.py**: 多租戶向量資料庫管理器
  - 支援動態創建/切換/刪除資料庫
  - LLM 摘要後插入功能
  - 跨資料庫查詢支援

### API 服務

#### fast_api/ - FastAPI 服務模組
提供 RESTful API 和 WebSocket 服務：

- **routers/rag_router.py**: RAG 與資料庫管理 API
  - `POST /databases` - 創建新資料庫
  - `GET /databases` - 列出所有資料庫
  - `POST /databases/{name}/activate` - 切換活躍資料庫
  - `DELETE /databases/{name}` - 刪除資料庫
  - `POST /databases/insert` - 插入文檔（含 LLM 摘要）
  - `POST /databases/query` - 查詢資料庫
  - `POST /databases/query-all` - 跨資料庫查詢

- **routers/websocket_router.py**: WebSocket 即時通訊
  - 支援代理狀態盒即時更新
  - 串流 Token 輸出
  - 並行狀態監控

### MCP 整合

#### mcp/providers/ - 外部服務提供者
整合 7 種外部服務：

| 提供者 | 用途 | 主要功能 |
|--------|------|----------|
| Firecrawl | 網頁爬取 | scrape, crawl, map_site |
| Exa | AI 搜尋 | search, find_similar, get_contents |
| Brave Search | 網頁搜尋 | web_search, news_search, image_search |
| Supabase | 資料庫 | select, insert, update, delete, rpc |
| E2B | 代碼執行 | execute_python, execute_javascript, run_command |
| Zapier | 自動化 | list_actions, run_action, trigger_webhook |
| GitHub | 版本控制 | get_file, create_file, create_pr, search_code |

#### mcp/services/ - 服務層
組合多個提供者的統一服務：
- **web_scraping_service.py**: 智能網頁研究（Firecrawl + Exa + Brave）
- **database_service.py**: 統一資料庫操作
- **code_execution_service.py**: 沙箱代碼執行與資料分析
- **automation_service.py**: 工作流程自動化（Zapier + GitHub）

### 資料存儲

#### rag-database/vectordb/ - 向量資料庫
- 使用 ChromaDB 作為向量存儲後端
- 支援多租戶分離（不同公司使用不同資料庫）
- `db_metadata.json` 追蹤所有資料庫元資料

### 文檔

#### app_docs/ - 應用程式文檔
- **VECTOR_DATABASE_GUIDE.md**: 向量資料庫使用指南（供 API 使用者參考）
- **PLANNING.md**: 專案規劃與架構設計
- **Agentic-Rag-Examples/**: 17 種 Agentic 架構模式完整範例

## 技術特色

### 1. 多代理並行控制
- 最多 5 個代理同時執行
- 超過限制自動排隊等待
- 即時並行狀態監控

### 2. 結構化 JSON 回應
所有代理回應統一格式：
```json
{
  "response_type": "yes_no | suggestion | calculation | thinking | ...",
  "success": true,
  "agent_name": "thinking_agent",
  "result": { ... },
  "timestamp": "2026-01-23T10:30:00Z"
}
```

### 3. 即時 WebSocket UI 更新
- 代理狀態盒即時顯示
- 思考過程串流輸出
- 佇列狀態即時反饋

### 4. 多租戶向量資料庫
- 動態創建資料庫
- LLM 摘要後插入
- 跨資料庫聯合查詢
- 公司級別資料隔離

### 5. MCP 外部工具整合
- 網頁爬取與搜尋
- 資料庫操作
- 沙箱代碼執行
- 自動化工作流程

## 開發環境

- **Python 3.11+**: 主要開發語言
- **LangGraph**: AI 代理編排框架
- **FastAPI**: 高效能 Web 框架
- **ChromaDB**: 向量資料庫
- **Pydantic**: 資料驗證與序列化
- **Docker**: 容器化部署
- **httpx**: 非同步 HTTP 客戶端

## 環境變數配置

必要的環境變數（參考 `.env.example`）：
```bash
# OpenAI
OPENAI_API_KEY=sk-...

# MCP Providers
FIRECRAWL_API_KEY=...
EXA_API_KEY=...
BRAVE_API_KEY=...
SUPABASE_URL=...
SUPABASE_KEY=...
E2B_API_KEY=...
ZAPIER_API_KEY=...
GITHUB_TOKEN=...

# ChromaDB
CHROMA_DB_PATH=./rag-database/vectordb
```

---

*最後更新: 2026年1月23日*
*版本: 2.0.0*