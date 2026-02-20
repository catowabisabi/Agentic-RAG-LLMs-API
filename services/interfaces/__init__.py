"""
Service Interfaces
==================

Protocol-based interface definitions for the core service layer.

Using ``typing.Protocol`` (structural sub-typing) means concrete classes
need NOT inherit from these interfaces — they just need to implement the
required methods.  ``@runtime_checkable`` allows ``isinstance()`` guard checks.

Design rationale:
  - Agents and routers depend on **interfaces**, not concrete classes.
  - Concrete implementations (LLMService, RAGService, …) satisfy the
    protocols automatically — zero code change required.
  - Swapping an implementation (e.g. a mock for testing) requires only
    registering a different factory in the DI container.

Quick reference
---------------
from services.interfaces import (
    ILLMService,
    IRAGService,
    IVectorDBService,
    IDomainEventBus,
)
"""

from services.interfaces.llm import ILLMService
from services.interfaces.rag import IRAGService
from services.interfaces.vectordb import IVectorDBService
from services.interfaces.events import IDomainEventBus

__all__ = [
    "ILLMService",
    "IRAGService",
    "IVectorDBService",
    "IDomainEventBus",
]
