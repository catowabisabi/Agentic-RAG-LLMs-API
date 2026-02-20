"""
IVectorDBService — Vector-Database Manager Interface
====================================================
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class IVectorDBService(Protocol):
    """
    Structural interface for VectorDB management operations.

    Concrete implementation: ``services.vectordb_manager.VectorDBManager``
    """

    def list_databases(self) -> List[Dict[str, Any]]:
        """Return all registered databases with metadata."""
        ...

    def create_database(
        self,
        db_name: str,
        description: str = "",
        category: str = "general",
    ) -> Dict[str, Any]:
        """Create a new vector database."""
        ...

    def delete_database(self, db_name: str) -> Dict[str, Any]:
        """Delete a database and its data."""
        ...

    def get_database_info(self, db_name: str) -> Optional[Dict[str, Any]]:
        """Return metadata for a single database."""
        ...

    async def query(
        self,
        query: str,
        db_name: str,
        n_results: int = 5,
    ) -> Dict[str, Any]:
        """Query a database and return raw ChromaDB results."""
        ...

    def get_skills_summary(self) -> List[Dict[str, Any]]:
        """Return KB skills summary used for LLM routing."""
        ...

    def switch_database(self, db_name: str) -> Dict[str, Any]:
        """Switch the active database."""
        ...
