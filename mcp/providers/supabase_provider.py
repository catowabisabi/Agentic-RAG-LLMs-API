"""
Supabase Provider

Postgres database integration with Supabase.
Supports SQL queries, table management, and realtime subscriptions.

Features:
- Direct SQL queries
- Table CRUD operations
- Schema inspection
- Realtime capabilities
"""

import logging
from typing import Dict, Any, List, Optional

import httpx

from .base_provider import BaseProvider, ProviderConfig, ProviderResult

logger = logging.getLogger(__name__)


class SupabaseConfig(ProviderConfig):
    """Configuration for Supabase"""
    project_url: str = ""
    service_role_key: str = ""  # For admin operations
    anon_key: str = ""  # For client operations


class SupabaseProvider(BaseProvider):
    """
    Supabase provider for Postgres database operations.
    
    Capabilities:
    - query: Execute SQL queries
    - select: Select from tables
    - insert: Insert rows
    - update: Update rows
    - delete: Delete rows
    - schema: Get table schemas
    """
    
    def __init__(self, config: SupabaseConfig = None):
        super().__init__(config or SupabaseConfig())
        self.config: SupabaseConfig = self.config
        self._client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self) -> bool:
        """Initialize the Supabase client"""
        try:
            if not self.config.project_url:
                logger.warning("Supabase project URL not configured")
                return False
            
            api_key = self.config.service_role_key or self.config.anon_key
            if not api_key:
                logger.warning("Supabase API key not configured")
                return False
            
            self._client = httpx.AsyncClient(
                base_url=self.config.project_url,
                headers={
                    "apikey": api_key,
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation"
                },
                timeout=self.config.timeout
            )
            
            self._initialized = True
            logger.info("Supabase provider initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Supabase: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check if Supabase is available"""
        try:
            await self.ensure_initialized()
            response = await self._client.get("/rest/v1/")
            self._is_healthy = response.status_code < 500
            return self._is_healthy
        except Exception as e:
            logger.error(f"Supabase health check failed: {e}")
            self._is_healthy = False
            return False
    
    def get_capabilities(self) -> List[str]:
        """Get available operations"""
        return ["select", "insert", "update", "delete", "rpc", "schema"]
    
    async def select(
        self,
        table: str,
        columns: str = "*",
        filters: Dict[str, Any] = None,
        order: str = None,
        limit: int = None,
        offset: int = None
    ) -> ProviderResult:
        """
        Select rows from a table.
        
        Args:
            table: Table name
            columns: Columns to select (comma-separated or *)
            filters: Filter conditions (eq, neq, gt, gte, lt, lte, like, ilike, in)
            order: Order by column (column.asc or column.desc)
            limit: Maximum rows
            offset: Row offset
            
        Returns:
            ProviderResult with rows
        """
        try:
            await self.ensure_initialized()
            
            params = {"select": columns}
            
            # Add filters
            if filters:
                for key, value in filters.items():
                    if isinstance(value, dict):
                        # Handle operators: {"column": {"eq": "value"}}
                        for op, val in value.items():
                            params[key] = f"{op}.{val}"
                    else:
                        params[key] = f"eq.{value}"
            
            if order:
                params["order"] = order
            if limit:
                params["limit"] = limit
            if offset:
                params["offset"] = offset
            
            response = await self._client.get(f"/rest/v1/{table}", params=params)
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="select",
                data={
                    "table": table,
                    "rows": data,
                    "count": len(data)
                }
            )
            
        except Exception as e:
            logger.error(f"Supabase select error: {e}")
            return self._error("select", str(e), table=table)
    
    async def insert(
        self,
        table: str,
        data: Dict[str, Any] | List[Dict[str, Any]],
        upsert: bool = False
    ) -> ProviderResult:
        """
        Insert rows into a table.
        
        Args:
            table: Table name
            data: Row data (single dict or list of dicts)
            upsert: Whether to upsert (insert or update)
            
        Returns:
            ProviderResult with inserted rows
        """
        try:
            await self.ensure_initialized()
            
            headers = {}
            if upsert:
                headers["Prefer"] = "resolution=merge-duplicates"
            
            response = await self._client.post(
                f"/rest/v1/{table}",
                json=data,
                headers=headers
            )
            response.raise_for_status()
            
            result = response.json()
            
            return self._success(
                operation="insert",
                data={
                    "table": table,
                    "inserted": result,
                    "count": len(result) if isinstance(result, list) else 1
                }
            )
            
        except Exception as e:
            logger.error(f"Supabase insert error: {e}")
            return self._error("insert", str(e), table=table)
    
    async def update(
        self,
        table: str,
        data: Dict[str, Any],
        filters: Dict[str, Any]
    ) -> ProviderResult:
        """
        Update rows in a table.
        
        Args:
            table: Table name
            data: Update data
            filters: Filter conditions
            
        Returns:
            ProviderResult with updated rows
        """
        try:
            await self.ensure_initialized()
            
            # Build filter params
            params = {}
            for key, value in filters.items():
                if isinstance(value, dict):
                    for op, val in value.items():
                        params[key] = f"{op}.{val}"
                else:
                    params[key] = f"eq.{value}"
            
            response = await self._client.patch(
                f"/rest/v1/{table}",
                json=data,
                params=params
            )
            response.raise_for_status()
            
            result = response.json()
            
            return self._success(
                operation="update",
                data={
                    "table": table,
                    "updated": result,
                    "count": len(result) if isinstance(result, list) else 1
                }
            )
            
        except Exception as e:
            logger.error(f"Supabase update error: {e}")
            return self._error("update", str(e), table=table)
    
    async def delete(
        self,
        table: str,
        filters: Dict[str, Any]
    ) -> ProviderResult:
        """
        Delete rows from a table.
        
        Args:
            table: Table name
            filters: Filter conditions
            
        Returns:
            ProviderResult with deleted rows
        """
        try:
            await self.ensure_initialized()
            
            # Build filter params
            params = {}
            for key, value in filters.items():
                if isinstance(value, dict):
                    for op, val in value.items():
                        params[key] = f"{op}.{val}"
                else:
                    params[key] = f"eq.{value}"
            
            response = await self._client.delete(
                f"/rest/v1/{table}",
                params=params
            )
            response.raise_for_status()
            
            result = response.json()
            
            return self._success(
                operation="delete",
                data={
                    "table": table,
                    "deleted": result,
                    "count": len(result) if isinstance(result, list) else 1
                }
            )
            
        except Exception as e:
            logger.error(f"Supabase delete error: {e}")
            return self._error("delete", str(e), table=table)
    
    async def rpc(
        self,
        function_name: str,
        params: Dict[str, Any] = None
    ) -> ProviderResult:
        """
        Call a stored procedure/function.
        
        Args:
            function_name: Function name
            params: Function parameters
            
        Returns:
            ProviderResult with function result
        """
        try:
            await self.ensure_initialized()
            
            response = await self._client.post(
                f"/rest/v1/rpc/{function_name}",
                json=params or {}
            )
            response.raise_for_status()
            
            result = response.json()
            
            return self._success(
                operation="rpc",
                data={
                    "function": function_name,
                    "result": result
                }
            )
            
        except Exception as e:
            logger.error(f"Supabase rpc error: {e}")
            return self._error("rpc", str(e), function=function_name)
    
    async def get_schema(self, table: str = None) -> ProviderResult:
        """
        Get table schema information.
        
        Args:
            table: Specific table name (optional)
            
        Returns:
            ProviderResult with schema info
        """
        try:
            await self.ensure_initialized()
            
            # OpenAPI spec contains schema info
            response = await self._client.get("/rest/v1/")
            response.raise_for_status()
            
            data = response.json()
            
            if table:
                table_info = data.get("definitions", {}).get(table)
                return self._success(
                    operation="schema",
                    data={
                        "table": table,
                        "schema": table_info
                    }
                )
            else:
                tables = list(data.get("definitions", {}).keys())
                return self._success(
                    operation="schema",
                    data={
                        "tables": tables,
                        "count": len(tables)
                    }
                )
            
        except Exception as e:
            logger.error(f"Supabase schema error: {e}")
            return self._error("schema", str(e))
    
    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
