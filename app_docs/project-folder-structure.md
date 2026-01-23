# Agentic RAG LLMs API - 專案資料夾結構

## 專案概述
此專案是一個基於 LangGraph 的 RAG (Retrieval-Augmented Generation) 系統，整合了多種 Agentic 架構模式，提供強大的 AI 代理服務。

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
├── .gitignore                         # Git 忽略文件配置
├── main.py                            # 主程式進入點
├── agents/                            # AI 代理模組
│   ├── nodes.py                       # 節點定義
│   └── rag_agent.py                   # RAG 代理核心邏輯
├── app_docs/                          # 應用程式文檔
│   ├── PLANNING.md                    # 專案規劃文件
│   ├── README.md                      # 專案說明文件
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
├── config/                            # 配置文件目錄
│   ├── .env.example                   # 環境變數範本
│   └── config.py                      # 配置管理模組
├── docker/                            # Docker 容器化配置
│   ├── .dockerignore                  # Docker 忽略文件
│   ├── docker-compose.yml             # Docker Compose 配置
│   └── Dockerfile                     # Docker 鏡像構建文件
├── documents/                         # 文檔處理模組
│   └── load_documents.py              # 文檔載入工具
├── fast-api/                          # FastAPI 服務模組
│   ├── rag-chatbot-api.py             # RAG 聊天機器人 API 服務
│   └── rag-chatbot-client.py          # RAG 聊天機器人客戶端
├── mcp/                               # Model Context Protocol (MCP) 相關
│   ├── providers/                     # MCP 提供者 (目前空)
│   └── services/                      # MCP 服務 (目前空)
├── rag-database/                      # RAG 資料庫存儲
│   └── vectordb/                      # 向量資料庫
│       ├── index.json                 # 主索引文件
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
├── Scripts/                           # 執行腳本目錄
│   ├── run_api.bat                    # 啟動 API 服務腳本
│   ├── run_client.bat                 # 啟動客戶端腳本
│   └── setup.bat                      # 環境設置腳本
└── tools/                             # 工具模組
    ├── memory.py                      # 記憶體管理工具
    └── retriever.py                   # 檢索工具
```

## 主要模組說明

### 核心模組

- **main.py**: 專案主要進入點，負責啟動整個 RAG 系統
- **agents/**: 包含 AI 代理的核心邏輯，實現各種 Agentic 架構模式
- **tools/**: 核心工具模組，包含記憶體管理和資訊檢索功能

### API 服務

- **fast-api/**: 提供 RESTful API 和 WebSocket 服務
  - 支援即時對話功能
  - 非同步任務處理
  - 背景任務佇列管理

### 資料存儲

- **rag-database/vectordb/**: 分領域的向量資料庫
  - 化學、醫學、金融等多個專業領域
  - 支援向量化文檔檢索和語義搜尋

### 範例與文檔

- **app_docs/Agentic-Rag-Examples/**: 17 種 Agentic 架構模式的完整範例
- **app_docs/**: 專案規劃和技術文檔

### 自動化與部署

- **docker/**: Docker 容器化配置
- **Scripts/**: Windows 批次處理腳本
- **.claude/skills/**: AI 輔助開發的專業技能模組

## 技術特色

1. **多樣化 Agentic 架構**: 實現 17 種不同的 AI 代理模式
2. **領域專業化**: 支援多個專業領域的知識檢索
3. **API 優先設計**: 提供完整的 REST 和 WebSocket API
4. **容器化部署**: 支援 Docker 部署和擴展
5. **模組化架構**: 清晰的代碼組織和模組分離

## 開發環境

- **Python**: 主要開發語言
- **LangGraph**: AI 代理編排框架
- **FastAPI**: 高效能 Web 框架
- **Vector Database**: 語義檢索和向量存儲
- **Docker**: 容器化部署

---

*最後更新: 2026年1月23日*
*版本: 1.0.0*