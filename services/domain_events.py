"""
Domain Events
=============

Typed pub/sub system for **internal** domain events.

This is intentionally separate from the WebSocket-centric ``event_bus``
(``services/event_bus.py``) and ``UnifiedEventManager``
(``services/unified_event_manager.py``), which broadcast to UI clients.

Domain events carry business facts ("an LLM call finished", "a RAG query
completed") and exist so that cross-cutting concerns — metrics, logging,
audit trails — can subscribe without being hard-coded into LLMService or
RAGService.

Architecture
------------
    LLMService ──publish──► DomainEventBus ──► MetricsSubscriber
                                           ──► AuditSubscriber
                                           ──► (future) BillingSubscriber

Why not the existing event_bus?
--------------------------------
The existing ``event_bus`` is tightly coupled to WebSocket broadcasting and
``AgentState``; it is for *UI telemetry*, not *service-layer communication*.
The two buses serve different audiences and can coexist.

Usage
-----
    from services.domain_events import domain_event_bus, LLMCallCompleted

    # Subscribe (returns a subscription id for later unsubscribing)
    def on_llm(event: LLMCallCompleted):
        print(f"LLM call cost ${event.cost:.4f}")

    sub_id = domain_event_bus.subscribe(LLMCallCompleted, on_llm)

    # Publish (fire-and-forget — never blocks)
    domain_event_bus.publish(LLMCallCompleted(model="gpt-4o-mini", cost=0.0003))

    # Unsubscribe
    domain_event_bus.unsubscribe(sub_id)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T", bound="DomainEvent")

# ---------------------------------------------------------------------------
# Base event
# ---------------------------------------------------------------------------


@dataclass
class DomainEvent:
    """Base class for all domain events."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    @property
    def event_type(self) -> str:
        return type(self).__name__


# ---------------------------------------------------------------------------
# LLM events
# ---------------------------------------------------------------------------


@dataclass
class LLMCallCompleted(DomainEvent):
    """Fired after every successful LLM generate() call."""

    agent_name: str = ""
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost: float = 0.0
    cached: bool = False
    session_id: str = "default"


@dataclass
class LLMCallFailed(DomainEvent):
    """Fired when an LLM call raises an exception."""

    agent_name: str = ""
    model: str = ""
    error: str = ""
    session_id: str = "default"


# ---------------------------------------------------------------------------
# RAG events
# ---------------------------------------------------------------------------


@dataclass
class RAGQueryCompleted(DomainEvent):
    """Fired after every RAG query() call (hit or miss)."""

    query_preview: str = ""          # first 120 chars
    databases: List[str] = field(default_factory=list)
    result_count: int = 0
    avg_relevance: float = 0.0
    strategy_used: str = ""
    cached: bool = False


@dataclass
class RAGQueryFailed(DomainEvent):
    """Fired when a RAG query raises an exception."""

    query_preview: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# Agent lifecycle events
# ---------------------------------------------------------------------------


@dataclass
class AgentTaskStarted(DomainEvent):
    """Fired when an agent begins processing a task."""

    agent_name: str = ""
    task_id: str = ""
    task_type: str = ""
    session_id: str = ""


@dataclass
class AgentTaskCompleted(DomainEvent):
    """Fired when an agent finishes a task successfully."""

    agent_name: str = ""
    task_id: str = ""
    duration_ms: float = 0.0
    session_id: str = ""


@dataclass
class AgentTaskFailed(DomainEvent):
    """Fired when an agent task raises an unhandled exception."""

    agent_name: str = ""
    task_id: str = ""
    error: str = ""
    session_id: str = ""


# ---------------------------------------------------------------------------
# Chat / conversation events
# ---------------------------------------------------------------------------


@dataclass
class ChatMessageReceived(DomainEvent):
    """Fired when a new user message arrives at ChatService."""

    conversation_id: str = ""
    message_preview: str = ""    # first 120 chars


@dataclass
class ChatResponseSent(DomainEvent):
    """Fired when ChatService delivers a final response to the caller."""

    conversation_id: str = ""
    response_preview: str = ""
    agents_involved: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Domain Event Bus
# ---------------------------------------------------------------------------


class DomainEventBus:
    """
    Lightweight, type-safe, async-capable pub/sub bus.

    Thread-safety
    -------------
    Subscriptions are protected by a ``threading.Lock`` so that
    ``subscribe`` / ``unsubscribe`` are safe from multiple threads
    (FastAPI runs in threads for sync endpoints).

    Handler errors
    ---------------
    Exceptions raised by handlers are caught and logged — they must
    never crash the publisher.
    """

    def __init__(self) -> None:
        # event_type -> list of (subscription_id, handler)
        self._handlers: Dict[type, List[Tuple[str, Callable]]] = {}
        # sub_id -> event_type  (for O(1) unsubscribe)
        self._index: Dict[str, type] = {}

        import threading
        self._lock = threading.Lock()

    # ── Subscription management ──────────────────────────────────────────────

    def subscribe(
        self,
        event_type: Type[T],
        handler: Callable[[T], Any],
    ) -> str:
        """
        Register *handler* for *event_type*.

        The handler may be a plain function **or** an ``async def``
        coroutine function.  Both are supported.

        Returns a subscription ID string.
        """
        sub_id = str(uuid.uuid4())
        with self._lock:
            self._handlers.setdefault(event_type, []).append((sub_id, handler))
            self._index[sub_id] = event_type
        logger.debug(
            f"[DomainEventBus] Subscribed {handler.__name__!r} to {event_type.__name__} "
            f"(sub={sub_id[:8]})"
        )
        return sub_id

    def unsubscribe(self, subscription_id: str) -> None:
        """Remove a previously registered subscription."""
        with self._lock:
            event_type = self._index.pop(subscription_id, None)
            if event_type is None:
                return
            self._handlers[event_type] = [
                (sid, h)
                for sid, h in self._handlers.get(event_type, [])
                if sid != subscription_id
            ]
        logger.debug(f"[DomainEventBus] Unsubscribed {subscription_id[:8]}")

    def subscribers(self, event_type: Type[T]) -> int:
        """Return the number of handlers registered for *event_type*."""
        with self._lock:
            return len(self._handlers.get(event_type, []))

    # ── Publishing ───────────────────────────────────────────────────────────

    def publish(self, event: DomainEvent) -> None:
        """
        Fire-and-forget publish.

        * Async handlers → scheduled as ``asyncio`` background tasks.
        * Sync handlers  → scheduled via ``loop.call_soon`` (non-blocking).
        * If no event loop is running (e.g. during startup / test) →
          sync handlers are called directly; async handlers are skipped
          with a warning.

        This method **never raises**.
        """
        event_type = type(event)
        with self._lock:
            handlers = list(self._handlers.get(event_type, []))

        if not handlers:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        for sub_id, handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    if loop is not None:
                        loop.create_task(
                            self._safe_async_call(handler, event, sub_id),
                            name=f"domain-event-{event_type.__name__}-{sub_id[:8]}",
                        )
                    else:
                        logger.warning(
                            f"[DomainEventBus] No event loop — skipping async handler "
                            f"{handler.__name__!r} for {event_type.__name__}"
                        )
                else:
                    if loop is not None:
                        loop.call_soon(self._safe_sync_call, handler, event, sub_id)
                    else:
                        self._safe_sync_call(handler, event, sub_id)
            except Exception as e:
                logger.error(
                    f"[DomainEventBus] Failed to schedule handler "
                    f"{handler.__name__!r}: {e}"
                )

    # ── Internal helpers ─────────────────────────────────────────────────────

    async def _safe_async_call(
        self,
        handler: Callable,
        event: DomainEvent,
        sub_id: str,
    ) -> None:
        try:
            await handler(event)
        except Exception as e:
            logger.error(
                f"[DomainEventBus] Async handler {handler.__name__!r} "
                f"(sub={sub_id[:8]}) raised: {e}",
                exc_info=True,
            )

    def _safe_sync_call(
        self,
        handler: Callable,
        event: DomainEvent,
        sub_id: str,
    ) -> None:
        try:
            handler(event)
        except Exception as e:
            logger.error(
                f"[DomainEventBus] Sync handler {handler.__name__!r} "
                f"(sub={sub_id[:8]}) raised: {e}",
                exc_info=True,
            )

    # ── Debug helpers ────────────────────────────────────────────────────────

    def registered_handlers(self) -> Dict[str, int]:
        """Return {event_type_name: handler_count} for all registered types."""
        with self._lock:
            return {
                et.__name__: len(hs)
                for et, hs in self._handlers.items()
                if hs
            }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

#: Global singleton — import and use directly.
domain_event_bus = DomainEventBus()
