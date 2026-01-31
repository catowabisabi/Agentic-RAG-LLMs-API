# -*- coding: utf-8 -*-
"""
=============================================================================
共享服務層 (Shared Services Layer)
=============================================================================

結構說明：
-----------
提供多代理系統的核心基礎設施，包括通訊、註冊和生命週期管理。

包含組件：
-----------
1. BaseAgent       : 所有代理的抽象基類
2. AgentRegistry   : 代理註冊和管理中心
3. WebSocketManager: WebSocket 連接管理
4. MessageProtocol : 代理間通訊協議

使用方式：
-----------
from agents.shared_services import BaseAgent, AgentRegistry

class MyAgent(BaseAgent):
    async def process_task(self, task):
        # 處理任務
        pass

作者：Agentic RAG Team
版本：2.0
=============================================================================
"""

from .websocket_manager import WebSocketManager
from .message_protocol import MessageProtocol, AgentMessage, MessageType
from .base_agent import BaseAgent
from .agent_registry import AgentRegistry

# Memory 整合 (新版)
from .memory_integration import (
    MemoryManager,
    get_memory_manager,
    MemoryType,
    TaskCategory,
    EpisodeOutcome,
    ConversationContext,
    Episode
)

__all__ = [
    'WebSocketManager',
    'MessageProtocol',
    'AgentMessage', 
    'MessageType',
    'BaseAgent',
    'AgentRegistry',
    # Memory
    'MemoryManager',
    'get_memory_manager',
    'MemoryType',
    'TaskCategory',
    'EpisodeOutcome',
    'ConversationContext',
    'Episode'
]
