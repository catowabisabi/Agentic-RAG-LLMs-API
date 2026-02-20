"""
IDomainEventBus — Domain Event Bus Interface
============================================
"""

from __future__ import annotations

from typing import Any, Callable, Protocol, Type, TypeVar, runtime_checkable

T = TypeVar("T")


@runtime_checkable
class IDomainEventBus(Protocol):
    """
    Structural interface for the typed domain event bus.

    Concrete implementation: ``services.domain_events.DomainEventBus``
    """

    def subscribe(
        self,
        event_type: Type[T],
        handler: Callable[[T], Any],
    ) -> str:
        """
        Register *handler* to be called whenever an event of *event_type*
        is published.

        Returns a subscription ID that can be passed to :meth:`unsubscribe`.
        """
        ...

    def unsubscribe(self, subscription_id: str) -> None:
        """Cancel a subscription by its ID."""
        ...

    def publish(self, event: Any) -> None:
        """
        Fire-and-forget publish.

        Async handlers are scheduled as background tasks; sync handlers
        are called via ``loop.call_soon``.  Never raises.
        """
        ...
