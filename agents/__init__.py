# -*- coding: utf-8 -*-
"""
=============================================================================
多代理系統模組 (Multi-Agent System)
=============================================================================

結構說明：
-----------
此模組實現了一個完整的多代理協作系統，具備 WebSocket 即時通訊能力。

模組架構：
-----------
agents/
├── __init__.py           # 模組初始化和導出
├── shared_services/      # 共享服務層
│   ├── base_agent.py     # 代理基類
│   ├── agent_registry.py # 代理註冊表
│   ├── websocket_manager.py # WebSocket 管理
│   └── message_protocol.py  # 訊息協議
├── core/                 # 核心代理
│   ├── manager_agent.py  # 管理代理（中央協調）
│   ├── rag_agent.py      # RAG 代理（知識檢索）
│   ├── planning_agent.py # 規劃代理
│   ├── thinking_agent.py # 思考代理
│   ├── memory_agent.py   # 記憶代理
│   ├── notes_agent.py    # 筆記代理
│   ├── validation_agent.py # 驗證代理
│   ├── roles_agent.py    # 角色代理
│   └── casual_chat_agent.py # 閒聊代理
├── auxiliary/            # 輔助代理
│   ├── data_agent.py     # 資料代理
│   ├── tool_agent.py     # 工具代理
│   ├── summarize_agent.py # 摘要代理
│   ├── translate_agent.py # 翻譯代理
│   └── calculation_agent.py # 計算代理
└── legacy/               # 遺留代碼
    ├── rag_agent.py      # 舊版 RAG（LangGraph）
    └── nodes.py          # 舊版節點定義

代理類型說明：
-----------
核心代理 (Core Agents):
- ManagerAgent     : 中央協調器，負責任務分配和路由
- RAGAgent         : 知識檢索增強生成
- PlanningAgent    : 複雜任務規劃
- ThinkingAgent    : 深度推理
- MemoryAgent      : 長期記憶管理
- NotesAgent       : 筆記和上下文
- ValidationAgent  : 結果驗證
- RolesAgent       : 角色監控
- CasualChatAgent  : 簡單對話處理

輔助代理 (Auxiliary Agents):
- DataAgent        : 資料處理
- ToolAgent        : 工具調用
- SummarizeAgent   : 文本摘要
- TranslateAgent   : 翻譯服務
- CalculationAgent : 數學計算

使用方式：
-----------
from agents import ManagerAgent, RAGAgent, AgentRegistry

# 註冊代理
registry = AgentRegistry()
await registry.register_agent(ManagerAgent())
await registry.start_all_agents()

作者：Agentic RAG Team
版本：2.0
=============================================================================
"""

from agents.shared_services import (
    WebSocketManager,
    MessageProtocol,
    AgentMessage,
    MessageType,
    BaseAgent,
    AgentRegistry
)

from agents.core import (
    ManagerAgent,
    RAGAgent,
    MemoryAgent,
    NotesAgent,
    ValidationAgent,
    PlanningAgent,
    ThinkingAgent,
    RolesAgent,
    CasualChatAgent
)

from agents.auxiliary import (
    DataAgent,
    ToolAgent,
    SummarizeAgent,
    TranslateAgent,
    CalculationAgent
)

__all__ = [
    # 共享服務
    "WebSocketManager",
    "MessageProtocol",
    "AgentMessage",
    "MessageType",
    "BaseAgent",
    "AgentRegistry",
    
    # 核心代理
    "ManagerAgent",
    "RAGAgent",
    "MemoryAgent",
    "NotesAgent",
    "ValidationAgent",
    "PlanningAgent",
    "ThinkingAgent",
    "RolesAgent",
    "CasualChatAgent",
    
    # 輔助代理
    "DataAgent",
    "ToolAgent",
    "SummarizeAgent",
    "TranslateAgent",
    "CalculationAgent"
]
