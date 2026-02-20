"""
agents/agent_factory.py
========================

統一的 Agent 工廠模組 (Single Source of Truth)

原本 main.py 和 fast_api/app.py 各自維護一份幾乎相同的
create_agents() 函數，容易在新增 Agent 時遺漏其中一份。

此模組提供唯一的 create_agents() 實作，兩處皆由此導入：

    from agents.agent_factory import create_agents

新增 Agent 時只需修改這一個檔案。
"""

import logging

logger = logging.getLogger(__name__)


async def create_agents():
    """
    建立並向 AgentRegistry 注冊所有 Agent。

    Returns
    -------
    AgentRegistry
        已注冊所有 Agent 的 registry 實例
    """
    from agents.shared_services.agent_registry import AgentRegistry

    registry = AgentRegistry()

    # ── 核心 Agents ──────────────────────────────────────
    logger.info("Registering core agents...")

    from agents.core.entry_classifier import EntryClassifier
    from agents.core.manager_agent import ManagerAgent
    from agents.core.rag_agent import RAGAgent
    from agents.core.memory_agent import MemoryAgent
    from agents.core.notes_agent import NotesAgent
    from agents.core.validation_agent import ValidationAgent
    from agents.core.planning_agent import PlanningAgent
    from agents.core.thinking_agent import ThinkingAgent
    from agents.core.roles_agent import RolesAgent
    from agents.core.casual_chat_agent import CasualChatAgent

    await registry.register_agent(EntryClassifier())
    await registry.register_agent(ManagerAgent())
    await registry.register_agent(RAGAgent())
    await registry.register_agent(MemoryAgent())
    await registry.register_agent(NotesAgent())
    await registry.register_agent(ValidationAgent())
    await registry.register_agent(PlanningAgent())
    await registry.register_agent(ThinkingAgent())
    await registry.register_agent(RolesAgent())
    await registry.register_agent(CasualChatAgent())

    # ── 輔助 Agents ────────────────────────────────────────
    logger.info("Registering auxiliary agents...")

    from agents.auxiliary.data_agent import DataAgent
    from agents.auxiliary.tool_agent import ToolAgent
    from agents.auxiliary.summarize_agent import SummarizeAgent
    from agents.auxiliary.translate_agent import TranslateAgent
    from agents.auxiliary.calculation_agent import CalculationAgent
    from agents.auxiliary.memory_capture_agent import MemoryCaptureAgent
    from agents.auxiliary.sw_agent import SWAgent

    await registry.register_agent(DataAgent())
    await registry.register_agent(ToolAgent())
    await registry.register_agent(SummarizeAgent())
    await registry.register_agent(TranslateAgent())
    await registry.register_agent(CalculationAgent())
    await registry.register_agent(MemoryCaptureAgent())
    await registry.register_agent(SWAgent())

    logger.info(f"Registered {len(registry._agents)} agents successfully")

    return registry
