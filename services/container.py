"""
Service Container (Dependency Inversion)
=========================================

A lightweight, zero-magic dependency-injection container.

Design goals
------------
* No decorators, no metaclass magic, no import-time side-effects.
* Register by **interface** (Protocol class); resolve by that same interface.
* Singleton or transient lifetime per registration.
* ``override()`` lets tests inject mock implementations in a single line.
* ``wire()`` constructs an object and injects its declared dependencies.

Quick start
-----------
    # 1. Register at application startup (main.py / app.py)
    from services.container import container
    from services.interfaces import ILLMService, IRAGService, IVectorDBService
    from services.llm_service import get_llm_service
    from services.rag_service import get_rag_service
    from services.vectordb_manager import vectordb_manager

    container.register(ILLMService, get_llm_service)
    container.register(IRAGService, get_rag_service)
    container.register(IVectorDBService, lambda: vectordb_manager)

    # 2. Resolve anywhere in the codebase
    llm: ILLMService = container.resolve(ILLMService)

    # 3. Override with a mock in tests
    container.override(ILLMService, MockLLMService())

Advanced: constructor injection
---------------------------------
    class MyService:
        def __init__(self, llm: ILLMService, rag: IRAGService):
            self.llm = llm
            self.rag  = rag

    svc = container.wire(MyService, llm=ILLMService, rag=IRAGService)
    # container.wire resolves each keyword argument from the container
    # before passing it to MyService.__init__.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Callable, Dict, Generic, Optional, Set, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class _NotRegistered:
    """Sentinel used instead of None so ``None`` can be a valid value."""


_SENTINEL = _NotRegistered()


class ServiceContainer:
    """
    A simple, thread-safe dependency-injection container.

    Lifetimes
    ---------
    singleton (default)
        The factory is called once; subsequent calls to ``resolve()``
        return the same instance.

    transient
        The factory is called every time ``resolve()`` is called.
    """

    def __init__(self) -> None:
        self._factories: Dict[type, Callable[[], Any]] = {}
        self._singletons: Dict[type, Any] = {}
        self._singleton_keys: Set[type] = set()
        self._lock = threading.Lock()

    # ── Registration ─────────────────────────────────────────────────────────

    def register(
        self,
        interface: Type[T],
        factory: Callable[[], T],
        *,
        singleton: bool = True,
    ) -> None:
        """
        Register *factory* as the provider of *interface*.

        Parameters
        ----------
        interface
            The type key (typically a ``Protocol`` class) used to look up
            this service later.
        factory
            A zero-argument callable that produces the implementation.
            e.g. ``get_llm_service``, ``lambda: MyService()``.
        singleton
            When ``True`` (the default) the factory is called at most once
            and the result is cached for the lifetime of the container.
        """
        with self._lock:
            self._factories[interface] = factory
            if singleton:
                self._singleton_keys.add(interface)
            elif interface in self._singleton_keys:
                self._singleton_keys.discard(interface)
        logger.debug(
            f"[Container] Registered {interface.__name__!r} "
            f"({'singleton' if singleton else 'transient'})"
        )

    def override(self, interface: Type[T], instance: T) -> None:
        """
        Override a registration with a pre-built instance.

        This is the primary hook for test doubles:

            container.override(ILLMService, MockLLMService())

        The existing factory (if any) is kept so the override can be
        reverted with :meth:`reset_override`.
        """
        with self._lock:
            self._singletons[interface] = instance
            self._singleton_keys.add(interface)
        logger.debug(f"[Container] Override registered for {interface.__name__!r}")

    def reset_override(self, interface: Type[T]) -> None:
        """Remove an override, reverting to the registered factory."""
        with self._lock:
            self._singletons.pop(interface, None)
        logger.debug(f"[Container] Override reset for {interface.__name__!r}")

    # ── Resolution ───────────────────────────────────────────────────────────

    def resolve(self, interface: Type[T]) -> T:
        """
        Return the implementation for *interface*.

        Raises
        ------
        KeyError
            If *interface* has not been registered.
        """
        with self._lock:
            # Singleton: return cached instance if already built
            if interface in self._singleton_keys:
                if interface in self._singletons:
                    return self._singletons[interface]  # type: ignore[return-value]

            if interface not in self._factories:
                raise KeyError(
                    f"[Container] No registration found for {interface!r}. "
                    "Did you forget to call container.register(...)?"
                )

            instance = self._factories[interface]()

            if interface in self._singleton_keys:
                self._singletons[interface] = instance

        logger.debug(f"[Container] Resolved {interface.__name__!r}")
        return instance  # type: ignore[return-value]

    def try_resolve(self, interface: Type[T], default: Any = None) -> Optional[T]:
        """Like :meth:`resolve` but returns *default* instead of raising."""
        try:
            return self.resolve(interface)
        except KeyError:
            return default

    # ── Constructor injection ────────────────────────────────────────────────

    def wire(self, cls: type, **dep_map: type) -> Any:
        """
        Construct *cls* with dependencies resolved from the container.

        Parameters
        ----------
        cls
            The class to instantiate.
        **dep_map
            Keyword arguments to pass to ``cls.__init__``, where each
            value is an interface type to resolve:

                container.wire(MyService, llm=ILLMService, rag=IRAGService)

            is equivalent to:

                MyService(
                    llm=container.resolve(ILLMService),
                    rag=container.resolve(IRAGService),
                )
        """
        resolved = {name: self.resolve(iface) for name, iface in dep_map.items()}
        return cls(**resolved)

    # ── Introspection ────────────────────────────────────────────────────────

    def registered(self) -> Dict[str, str]:
        """Return {interface_name: 'singleton'|'transient'} for all registrations."""
        with self._lock:
            return {
                iface.__name__: (
                    "singleton" if iface in self._singleton_keys else "transient"
                )
                for iface in self._factories
            }

    def is_registered(self, interface: type) -> bool:
        """Return True if *interface* has been registered."""
        with self._lock:
            return interface in self._factories or interface in self._singletons

    def reset(self) -> None:
        """Clear all registrations and cached singletons (mainly for tests)."""
        with self._lock:
            self._factories.clear()
            self._singletons.clear()
            self._singleton_keys.clear()
        logger.debug("[Container] All registrations cleared")


# ---------------------------------------------------------------------------
# Singleton container + bootstrap helper
# ---------------------------------------------------------------------------

#: Global singleton container — import and use directly.
container = ServiceContainer()


def bootstrap(container: ServiceContainer = container) -> None:
    """
    Register all core service interfaces with their concrete factories.

    Call this **once** at application startup, before any request handling
    begins (in ``main.py`` or ``fast_api/app.py``).

    The function is idempotent — calling it multiple times is safe.
    """
    from services.interfaces import (
        IDomainEventBus,
        ILLMService,
        IRAGService,
        IVectorDBService,
    )

    # ── LLM Service ──────────────────────────────────────────────────────────
    if not container.is_registered(ILLMService):
        from services.llm_service import get_llm_service
        container.register(ILLMService, get_llm_service)

    # ── RAG Service ──────────────────────────────────────────────────────────
    if not container.is_registered(IRAGService):
        from services.rag_service import get_rag_service
        container.register(IRAGService, get_rag_service)

    # ── VectorDB Service ─────────────────────────────────────────────────────
    if not container.is_registered(IVectorDBService):
        from services.vectordb_manager import vectordb_manager as _vdb
        container.register(IVectorDBService, lambda: _vdb)

    # ── Domain Event Bus ─────────────────────────────────────────────────────
    if not container.is_registered(IDomainEventBus):
        from services.domain_events import domain_event_bus as _deb
        container.register(IDomainEventBus, lambda: _deb)

    logger.info(
        f"[Container] Bootstrap complete: {list(container.registered().keys())}"
    )
