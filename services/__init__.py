# -*- coding: utf-8 -*-
"""
=============================================================================
服務層模組 (Services Layer)
=============================================================================

結構說明：
-----------
此模組提供系統核心服務，包含：
1. 向量資料庫管理 (VectorDB Manager)
2. 事件總線 (Event Bus) 
3. 會話資料庫 (Session Database)
4. 任務管理器 (Task Manager)

模組架構：
-----------
services/
├── __init__.py           # 模組初始化和導出
├── vectordb_manager.py   # 多向量資料庫管理（ChromaDB）
├── event_bus.py          # 即時事件廣播系統
├── session_db.py         # SQLite 會話持久化
└── task_manager.py       # 背景任務管理

使用方式：
-----------
from services import vectordb_manager, event_bus, session_db, task_manager

# 向量資料庫查詢
result = await vectordb_manager.query("搜尋關鍵字", "資料庫名稱")

# 事件廣播
await event_bus.emit(EventType.AGENT_STATUS_CHANGED, agent_name, data)

# 會話管理
session = session_db.get_or_create_session(session_id, title)

# 任務管理
task_id = task_manager.create_task("chat", input_data)

依賴關係：
-----------
- ChromaDB: 向量存儲
- SQLite: 會話持久化
- LangChain: 文本分割和嵌入
- OpenAI: 嵌入模型

作者：Agentic RAG Team
版本：2.0
=============================================================================
"""

from .vectordb_manager import VectorDBManager, vectordb_manager
from .event_bus import event_bus, EventType, AgentState
from .session_db import session_db, TaskStatus as DBTaskStatus, StepType
from .task_manager import task_manager, TaskStatus, TaskResult

__all__ = [
    # VectorDB
    'VectorDBManager',
    'vectordb_manager',
    
    # Event Bus
    'event_bus',
    'EventType',
    'AgentState',
    
    # Session DB
    'session_db',
    'DBTaskStatus',
    'StepType',
    
    # Task Manager
    'task_manager',
    'TaskStatus',
    'TaskResult'
]
