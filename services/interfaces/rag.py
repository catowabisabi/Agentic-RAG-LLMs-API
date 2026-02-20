"""
IRAGService — Retrieval-Augmented Generation Service Interface
=============================================================
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class IRAGService(Protocol):
    """
    Structural interface for the unified RAG query service.

    Concrete implementation: ``services.rag_service.RAGService``
    """

    async def query(
        self,
        query: str,
        *,
        strategy: Any = None,          # RAGStrategy enum value or None
        top_k: int = 5,
        threshold: float = 0.3,
        databases: Optional[List[str]] = None,
        use_cache: bool = True,
    ) -> Any:
        """
        Execute a RAG query across one or more knowledge bases.

        Returns a ``RAGResult``-compatible object with at minimum:
            - ``.context: str``
            - ``.sources: list``
            - ``.databases_queried: list``
            - ``.cached: bool``
        """
        ...

    async def query_single(
        self,
        query: str,
        database: str,
        top_k: int = 5,
        threshold: float = 0.3,
    ) -> Any:
        """Query a single named knowledge base."""
        ...

    def clear_cache(self) -> None:
        """Invalidate the query cache."""
        ...

    def get_cache_stats(self) -> Dict[str, Any]:
        """Return cache hit/miss statistics."""
        ...
