# -*- coding: utf-8 -*-
"""
=============================================================================
核心代理模組 (Core Agents Module)
=============================================================================

結構說明：
-----------
系統的核心代理，負責主要任務處理和協調。

代理列表：
-----------
- ManagerAgent     : 中央管理器，任務路由和分配
- RAGAgent         : 檢索增強生成，知識庫查詢
- PlanningAgent    : 任務規劃和分解
- ThinkingAgent    : 深度推理和分析
- MemoryAgent      : 長期記憶管理
- NotesAgent       : 筆記和上下文存儲
- ValidationAgent  : 結果驗證和品質檢查
- RolesAgent       : 角色監控和調整
- CasualChatAgent  : 簡單對話和問候處理

作者：Agentic RAG Team
版本：2.0
=============================================================================
"""

# 核心代理
from .manager_agent import ManagerAgent
from .rag_agent import RAGAgent
from .memory_agent import MemoryAgent
from .notes_agent import NotesAgent
from .validation_agent import ValidationAgent
from .planning_agent import PlanningAgent
from .thinking_agent import ThinkingAgent
from .roles_agent import RolesAgent
from .casual_chat_agent import CasualChatAgent

# 新增: ReAct Loop 和 Metacognition Engine
from .react_loop import (
    ReActLoop, 
    get_react_loop, 
    create_react_loop,
    ActionType, 
    ReActResult,
    VerificationResult
)
from .metacognition_engine import (
    SelfEvaluator,
    ExperienceLearner,
    StrategyAdapter,
    MetacognitionEngine,
    MetacognitiveSelfModel,
    get_self_evaluator,
    get_experience_learner,
    get_strategy_adapter,
    get_metacognition_engine,
    get_metacognitive_self_model
)

# 新增: Agentic Orchestrator
from .agentic_orchestrator import (
    AgenticOrchestrator,
    AgentSelfModel,
    AgentStrategy,
    MetacognitiveAnalysis,
    OrchestratorResult,
    get_agentic_orchestrator,
    create_agentic_orchestrator
)

# 新增: Manager Agent V2
from .manager_agent_v2 import ManagerAgentV2, get_manager_agent_v2

__all__ = [
    'ManagerAgent',
    'RAGAgent',
    'MemoryAgent',
    'NotesAgent',
    'ValidationAgent',
    'PlanningAgent',
    'ThinkingAgent',
    'RolesAgent',
    'CasualChatAgent',
    # ReAct Loop (Enhanced)
    'ReActLoop',
    'get_react_loop',
    'create_react_loop',
    'ActionType',
    'ReActResult',
    'VerificationResult',
    # Metacognition (Enhanced)
    'SelfEvaluator',
    'ExperienceLearner',
    'StrategyAdapter',
    'MetacognitionEngine',
    'MetacognitiveSelfModel',
    'get_self_evaluator',
    'get_experience_learner',
    'get_strategy_adapter',
    'get_metacognition_engine',
    'get_metacognitive_self_model',
    # Agentic Orchestrator (New)
    'AgenticOrchestrator',
    'AgentSelfModel',
    'AgentStrategy',
    'MetacognitiveAnalysis',
    'OrchestratorResult',
    'get_agentic_orchestrator',
    'create_agentic_orchestrator',
    # Manager Agent V2
    'ManagerAgentV2',
    'get_manager_agent_v2'
]
