"""
Database Service

Unified service for database operations.
Integrates with Supabase and other database providers.

Features:
- Natural language to SQL
- Schema introspection
- Query execution
- CRUD operations
"""

import logging
from typing import Dict, Any, List, Optional

from mcp.providers.supabase_provider import SupabaseProvider, SupabaseConfig

logger = logging.getLogger(__name__)


class DatabaseService:
    """
    Unified database service.
    
    Provides:
    - Schema exploration
    - Natural language queries
    - CRUD operations
    - Query building
    """
    
    def __init__(
        self,
        supabase_url: str = None,
        supabase_key: str = None
    ):
        self._supabase: Optional[SupabaseProvider] = None
        
        if supabase_url and supabase_key:
            config = SupabaseConfig(
                project_url=supabase_url,
                service_role_key=supabase_key
            )
            self._supabase = SupabaseProvider(config)
        
        # Cache for schema info
        self._schema_cache: Dict[str, Any] = {}
        
        logger.info("DatabaseService initialized")
    
    async def initialize(self):
        """Initialize database connections"""
        if self._supabase:
            await self._supabase.initialize()
    
    async def get_tables(self) -> Dict[str, Any]:
        """
        Get list of all tables.
        
        Returns:
            Dict with table names
        """
        if not self._supabase:
            return {"error": "No database configured"}
        
        result = await self._supabase.get_schema()
        if result.success:
            return {
                "tables": result.data.get("tables", []),
                "count": result.data.get("count", 0)
            }
        return {"error": result.error}
    
    async def describe_table(self, table: str) -> Dict[str, Any]:
        """
        Get detailed table schema.
        
        Args:
            table: Table name
            
        Returns:
            Table schema
        """
        if not self._supabase:
            return {"error": "No database configured"}
        
        result = await self._supabase.get_schema(table)
        if result.success:
            return {
                "table": table,
                "schema": result.data.get("schema", {})
            }
        return {"error": result.error}
    
    async def query(
        self,
        table: str,
        select: str = "*",
        filters: Dict[str, Any] = None,
        order: str = None,
        limit: int = None
    ) -> Dict[str, Any]:
        """
        Query a table.
        
        Args:
            table: Table name
            select: Columns to select
            filters: Filter conditions
            order: Order by
            limit: Max rows
            
        Returns:
            Query results
        """
        if not self._supabase:
            return {"error": "No database configured"}
        
        result = await self._supabase.select(
            table=table,
            columns=select,
            filters=filters,
            order=order,
            limit=limit
        )
        
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def insert(
        self,
        table: str,
        data: Dict[str, Any] | List[Dict[str, Any]],
        upsert: bool = False
    ) -> Dict[str, Any]:
        """
        Insert rows into a table.
        
        Args:
            table: Table name
            data: Row data
            upsert: Whether to upsert
            
        Returns:
            Insert result
        """
        if not self._supabase:
            return {"error": "No database configured"}
        
        result = await self._supabase.insert(table, data, upsert)
        
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def update(
        self,
        table: str,
        data: Dict[str, Any],
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Update rows in a table.
        
        Args:
            table: Table name
            data: Update data
            filters: Filter conditions
            
        Returns:
            Update result
        """
        if not self._supabase:
            return {"error": "No database configured"}
        
        result = await self._supabase.update(table, data, filters)
        
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def delete(
        self,
        table: str,
        filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Delete rows from a table.
        
        Args:
            table: Table name
            filters: Filter conditions
            
        Returns:
            Delete result
        """
        if not self._supabase:
            return {"error": "No database configured"}
        
        result = await self._supabase.delete(table, filters)
        
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def call_function(
        self,
        function_name: str,
        params: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Call a stored procedure.
        
        Args:
            function_name: Function name
            params: Function parameters
            
        Returns:
            Function result
        """
        if not self._supabase:
            return {"error": "No database configured"}
        
        result = await self._supabase.rpc(function_name, params)
        
        if result.success:
            return result.data
        return {"error": result.error}
    
    async def execute_query(
        self,
        query_parts: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Execute a structured query.
        
        Query structure:
        {
            "operation": "select|insert|update|delete",
            "table": "table_name",
            "data": {...},  # for insert/update
            "filters": {...},  # for select/update/delete
            "columns": "*",  # for select
            "order": "column.asc",  # for select
            "limit": 10  # for select
        }
        
        Args:
            query_parts: Structured query
            
        Returns:
            Query result
        """
        operation = query_parts.get("operation", "select")
        table = query_parts.get("table")
        
        if not table:
            return {"error": "Table name required"}
        
        if operation == "select":
            return await self.query(
                table=table,
                select=query_parts.get("columns", "*"),
                filters=query_parts.get("filters"),
                order=query_parts.get("order"),
                limit=query_parts.get("limit")
            )
        elif operation == "insert":
            return await self.insert(
                table=table,
                data=query_parts.get("data", {}),
                upsert=query_parts.get("upsert", False)
            )
        elif operation == "update":
            return await self.update(
                table=table,
                data=query_parts.get("data", {}),
                filters=query_parts.get("filters", {})
            )
        elif operation == "delete":
            return await self.delete(
                table=table,
                filters=query_parts.get("filters", {})
            )
        else:
            return {"error": f"Unknown operation: {operation}"}
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            "supabase": self._supabase.get_status() if self._supabase else {"available": False}
        }
    
    async def close(self):
        """Close database connections"""
        if self._supabase:
            await self._supabase.close()
