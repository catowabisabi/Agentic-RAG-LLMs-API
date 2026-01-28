# Agentic RAG LLMs API - 專案文件夾結構

> 最後更新: 2026-01-27

## 📁 目錄結構

```
Agentic-RAG-LLMs-API/
├── 📄 main.py                    # 主入口點（API 伺服器啟動）
├── 📄 memory.json                # 對話記憶存儲
├── 📄 .env                       # 環境變數配置
├── 📄 .env.example               # 環境變數範例
│
├── 📁 agents/                    # 多代理系統
│   ├── __init__.py               # 模組初始化和導出
│   ├── 📁 core/                  # 核心代理
│   │   ├── manager_agent.py      # 管理代理（中央協調）
│   │   ├── rag_agent.py          # RAG 代理（知識檢索）
│   │   ├── planning_agent.py     # 規劃代理
│   │   ├── thinking_agent.py     # 思考代理
│   │   ├── memory_agent.py       # 記憶代理
│   │   ├── notes_agent.py        # 筆記代理
│   │   ├── validation_agent.py   # 驗證代理
│   │   ├── roles_agent.py        # 角色代理
│   │   └── casual_chat_agent.py  # 閒聊代理
│   ├── 📁 auxiliary/             # 輔助代理
│   │   ├── data_agent.py         # 資料代理
│   │   ├── tool_agent.py         # 工具代理
│   │   ├── summarize_agent.py    # 摘要代理
│   │   ├── translate_agent.py    # 翻譯代理
│   │   └── calculation_agent.py  # 計算代理
│   ├── 📁 shared_services/       # 共享服務
│   │   ├── base_agent.py         # 代理基類
│   │   ├── agent_registry.py     # 代理註冊表
│   │   ├── websocket_manager.py  # WebSocket 管理
│   │   ├── message_protocol.py   # 訊息協議
│   │   └── response_models.py    # 響應模型
│   └── 📁 legacy/                # 遺留代碼
│       ├── rag_agent.py          # 舊版 RAG（LangGraph）
│       └── nodes.py              # 舊版節點定義
│
├── 📁 services/                  # 服務層
│   ├── __init__.py               # 服務導出
│   ├── vectordb_manager.py       # 向量資料庫管理
│   ├── event_bus.py              # 事件總線系統
│   ├── session_db.py             # 會話資料庫（SQLite）
│   └── task_manager.py           # 背景任務管理
│
├── 📁 fast_api/                  # FastAPI 應用
│   ├── app.py                    # 主應用入口
│   └── 📁 routers/               # API 路由
│       ├── agent_router.py       # 代理相關 API
│       ├── chat_router.py        # 聊天相關 API
│       ├── rag_router.py         # RAG 相關 API
│       ├── session_router.py     # 會話相關 API
│       └── websocket_router.py   # WebSocket 路由
│
├── 📁 tools/                     # 工具模組
│   ├── retriever.py              # 文檔檢索器
│   └── memory.py                 # 對話記憶工具
│
├── 📁 config/                    # 配置
│   └── config.py                 # 應用配置類
│
├── 📁 documents/                 # 文檔加載
│   └── load_documents.py         # 文檔加載腳本
│
├── 📁 Scripts/                   # 腳本工具
│   ├── 📁 maintenance/           # 維護腳本
│   │   ├── rebuild_embeddings.py # 重建嵌入向量
│   │   ├── rebuild_embeddings_auto.py
│   │   ├── rebuild_simple.py
│   │   └── rebuild_output.log
│   ├── 📁 tests/                 # 測試腳本
│   │   └── test_rag.py           # RAG 測試
│   ├── load_docs_to_vectordb.py  # 加載文檔到向量DB
│   ├── load_docs_to_rag.py       # 加載文檔到 RAG
│   ├── migrate_legacy_db.py      # 遷移舊資料庫
│   ├── run_api.bat               # 啟動 API（Windows）
│   ├── run_client.bat            # 啟動客戶端
│   ├── run_with_ui.bat           # 啟動 API + UI
│   ├── setup.bat                 # 環境設置
│   ├── setup_ui.bat              # UI 設置
│   ├── start_services.sh         # 啟動服務（Linux）
│   └── start_tmux.sh             # Tmux 啟動腳本
│
├── 📁 app_docs/                  # 專案文檔
│   ├── README.md                 # 專案說明
│   ├── PLANNING.md               # 規劃文檔
│   ├── SYSTEM_DOCUMENTATION.md   # 系統文檔
│   ├── VECTOR_DATABASE_GUIDE.md  # 向量資料庫指南
│   ├── REBUILD_GUIDE.md          # 重建指南
│   ├── UI_LOGIC_ANALYSIS.md      # UI 邏輯分析
│   ├── project-folder-structure.md # 本文件
│   ├── requirements.txt          # Python 依賴
│   └── 📁 Agentic-Rag-Examples/  # 範例代碼
│
├── 📁 ui/                        # Next.js 前端
│   ├── package.json              # NPM 配置
│   ├── next.config.js            # Next.js 配置
│   ├── 📁 app/                   # App Router 頁面
│   ├── 📁 components/            # React 組件
│   │   ├── ChatPageV2.tsx        # 主聊天頁面
│   │   └── ...
│   ├── 📁 lib/                   # 工具庫
│   └── 📁 styles/                # 樣式文件
│
├── 📁 rag-database/              # RAG 資料庫
│   ├── sessions.db               # SQLite 會話資料庫
│   └── 📁 vectordb/              # ChromaDB 向量存儲
│
├── 📁 mcp/                       # MCP 伺服器
│   ├── server.py                 # MCP 主伺服器
│   ├── 📁 providers/             # 資料提供者
│   └── 📁 services/              # MCP 服務
│
├── 📁 docker/                    # Docker 配置
│   ├── Dockerfile                # 主 Dockerfile
│   ├── Dockerfile.mcp            # MCP Dockerfile
│   └── docker-compose.yml        # Compose 配置
│
└── 📁 Todo/                      # 待辦事項
    └── todo_2026_01_25.txt
```

## 🔧 主要技術棧

| 類別 | 技術 |
|------|------|
| 後端 | Python 3.11+, FastAPI, LangChain |
| 前端 | Next.js 14, React 18, TypeScript |
| AI/ML | OpenAI GPT-4, Embeddings |
| 資料庫 | ChromaDB (向量), SQLite (會話) |
| 通訊 | WebSocket, REST API |

## 📊 向量資料庫列表

| 資料庫名稱 | 文檔數 | 說明 |
|-----------|--------|------|
| agentic-rag-docs | 8+ | 系統文檔 |
| visual-basic | 128 | VBA 編程 |
| labs | 172 | 實驗室文檔 |
| solidworks-pdm-api | 68 | PDM API |
| solidworks-document-manager-api | 48 | 文檔管理 API |
| edrawings-api | 28 | eDrawings API |
| hosting | 24 | 託管相關 |
| angular | 14 | Angular 開發 |

## 🚀 快速啟動

```bash
# 1. 安裝依賴
pip install -r app_docs/requirements.txt
cd ui && npm install

# 2. 配置環境
cp .env.example .env
# 編輯 .env 設置 OPENAI_API_KEY

# 3. 啟動 API 伺服器
python -m uvicorn fast_api.app:app --host 0.0.0.0 --port 1130 --reload

# 4. 啟動 UI（另一終端）
cd ui && npm run dev
```

## 📝 代碼風格

- 所有 Python 模組都包含繁體中文注解
- 使用 `# -*- coding: utf-8 -*-` 確保編碼
- 每個模組頂部有結構說明和使用方式
