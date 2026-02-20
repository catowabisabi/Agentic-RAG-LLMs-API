"""
FastAPI Dependency Providers
============================

Thin wrappers that resolve services from the DI container
and expose them as FastAPI ``Depends()`` callables.

Usage in routers::

    from fast_api.dependencies import get_chat, get_llm, get_rag, get_vdb

    @router.post("/send")
    async def send_message(
        request: ChatRequest,
        chat: ChatService = Depends(get_chat),
    ):
        result = await chat.process_message(...)

Why ``Depends``?
----------------
* **Testability** — ``app.dependency_overrides[get_chat] = lambda: mock``
  replaces the real service in one line, no monkeypatching needed.
* **Consistency** — every handler gets its service the same way;
  no more scattered ``from services.xxx import get_xxx_service`` calls.
* **DI integration** — the container is the single source of truth for
  which implementation backs each interface.
"""

from __future__ import annotations

from services.container import container
from services.interfaces import ILLMService, IRAGService, IVectorDBService, IDomainEventBus

# ── ChatService ──────────────────────────────────────────────────────────────
# ChatService doesn't have a Protocol interface yet — resolve via its own
# singleton getter (still gains the Depends testability benefit).

from services.chat_service import ChatService, get_chat_service


def get_chat() -> ChatService:
    """Provide ChatService via ``Depends(get_chat)``."""
    return get_chat_service()


# ── LLM Service ─────────────────────────────────────────────────────────────

def get_llm() -> ILLMService:
    """Provide LLMService via ``Depends(get_llm)``."""
    return container.resolve(ILLMService)


# ── RAG Service ──────────────────────────────────────────────────────────────

def get_rag() -> IRAGService:
    """Provide RAGService via ``Depends(get_rag)``."""
    return container.resolve(IRAGService)


# ── VectorDB Service ─────────────────────────────────────────────────────────

def get_vdb() -> IVectorDBService:
    """Provide VectorDBManager via ``Depends(get_vdb)``."""
    return container.resolve(IVectorDBService)


# ── Domain Event Bus ─────────────────────────────────────────────────────────

def get_event_bus() -> IDomainEventBus:
    """Provide DomainEventBus via ``Depends(get_event_bus)``."""
    return container.resolve(IDomainEventBus)
