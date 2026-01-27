"""
Agents Package

Multi-agent system with WebSocket communication.
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
    # Shared services
    "WebSocketManager",
    "MessageProtocol",
    "AgentMessage",
    "MessageType",
    "BaseAgent",
    "AgentRegistry",
    
    # Core agents
    "ManagerAgent",
    "RAGAgent",
    "MemoryAgent",
    "NotesAgent",
    "ValidationAgent",
    "PlanningAgent",
    "ThinkingAgent",
    "RolesAgent",
    "CasualChatAgent",
    
    # Auxiliary agents
    "DataAgent",
    "ToolAgent",
    "SummarizeAgent",
    "TranslateAgent",
    "CalculationAgent"
]
