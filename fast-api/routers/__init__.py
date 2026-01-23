"""
Fast API Routers Package

Contains all API route handlers:
- WebSocket Router: Real-time communication
- Agent Router: Agent management
- RAG Router: Document retrieval
- Chat Router: Chat interface
"""

from .websocket_router import router as websocket_router
from .agent_router import router as agent_router
from .rag_router import router as rag_router
from .chat_router import router as chat_router

__all__ = [
    "websocket_router",
    "agent_router",
    "rag_router",
    "chat_router"
]
