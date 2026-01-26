"""
Database Control MCP Provider

Handles SQLite, PostgreSQL, and other database operations.
Provides secure query execution with parameterized queries.
"""

import os
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .base_provider import BaseProvider, ProviderConfig, ProviderResult

logger = logging.getLogger(__name__)


class DatabaseConfig(ProviderConfig):
    """Configuration for database provider"""
    default_db_path: str = "./data/local.db"
    max_query_time_seconds: int = 30
    max_rows_return: int = 1000
    allow_write_operations: bool = True
    # PostgreSQL settings (optional)
    pg_host: Optional[str] = None
    pg_port: int = 5432
    pg_database: Optional[str] = None
    pg_user: Optional[str] = None
    pg_password: Optional[str] = None


class DatabaseControlProvider(BaseProvider):
    """
    MCP Provider for database operations.
    
    Capabilities:
    - SQLite: Full CRUD operations
    - PostgreSQL: Connect and query (if configured)
    - Schema inspection
    - Safe parameterized queries
    """
    
    # Dangerous keywords to block in queries
    BLOCKED_KEYWORDS = ["DROP DATABASE", "TRUNCATE", "--", ";--", "/*", "*/", "EXEC ", "EXECUTE "]
    
    def __init__(self, config: DatabaseConfig = None):
        super().__init__(config or DatabaseConfig())
        self.config: DatabaseConfig = self.config
        self._connections = {}
        
    async def initialize(self) -> bool:
        """Initialize the database provider"""
        try:
            # Ensure data directory exists
            os.makedirs(os.path.dirname(self.config.default_db_path) or '.', exist_ok=True)
            
            # Test SQLite connection
            import sqlite3
            conn = sqlite3.connect(self.config.default_db_path)
            conn.close()
            
            self._initialized = True
            logger.info("DatabaseControlProvider initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize DatabaseControlProvider: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check if provider is healthy"""
        try:
            import sqlite3
            conn = sqlite3.connect(self.config.default_db_path)
            conn.execute("SELECT 1")
            conn.close()
            self._is_healthy = True
        except Exception:
            self._is_healthy = False
        
        self._last_health_check = datetime.now()
        return self._is_healthy
    
    def get_capabilities(self) -> List[str]:
        """List available operations"""
        caps = [
            "query_sqlite",
            "execute_sqlite", 
            "list_tables",
            "describe_table",
            "create_table",
            "insert_data",
            "backup_database"
        ]
        if self.config.pg_host:
            caps.extend(["query_postgres", "execute_postgres"])
        return caps
    
    def _is_query_safe(self, query: str) -> tuple[bool, str]:
        """Check if a query is safe to execute"""
        query_upper = query.upper()
        
        for keyword in self.BLOCKED_KEYWORDS:
            if keyword in query_upper:
                return False, f"Blocked keyword detected: {keyword}"
        
        return True, "OK"
    
    # ==================== SQLite Operations ====================
    
    async def query_sqlite(
        self, 
        query: str, 
        params: tuple = None, 
        db_path: str = None
    ) -> ProviderResult:
        """Execute a SELECT query on SQLite database"""
        try:
            import sqlite3
            
            db_path = db_path or self.config.default_db_path
            
            # Safety check
            is_safe, reason = self._is_query_safe(query)
            if not is_safe:
                return ProviderResult(
                    success=False,
                    error=f"Query rejected: {reason}",
                    provider=self.provider_name,
                    operation="query_sqlite"
                )
            
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            rows = cursor.fetchmany(self.config.max_rows_return)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            
            # Convert to list of dicts
            data = [dict(row) for row in rows]
            
            conn.close()
            
            return ProviderResult(
                success=True,
                data={
                    "rows": data,
                    "row_count": len(data),
                    "columns": columns,
                    "query": query
                },
                provider=self.provider_name,
                operation="query_sqlite"
            )
            
        except Exception as e:
            logger.error(f"SQLite query error: {e}")
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="query_sqlite"
            )
    
    async def execute_sqlite(
        self, 
        statement: str, 
        params: tuple = None, 
        db_path: str = None
    ) -> ProviderResult:
        """Execute an INSERT/UPDATE/DELETE statement on SQLite"""
        if not self.config.allow_write_operations:
            return ProviderResult(
                success=False,
                error="Write operations are disabled",
                provider=self.provider_name,
                operation="execute_sqlite"
            )
        
        try:
            import sqlite3
            
            db_path = db_path or self.config.default_db_path
            
            # Safety check
            is_safe, reason = self._is_query_safe(statement)
            if not is_safe:
                return ProviderResult(
                    success=False,
                    error=f"Statement rejected: {reason}",
                    provider=self.provider_name,
                    operation="execute_sqlite"
                )
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if params:
                cursor.execute(statement, params)
            else:
                cursor.execute(statement)
            
            conn.commit()
            rows_affected = cursor.rowcount
            last_id = cursor.lastrowid
            conn.close()
            
            return ProviderResult(
                success=True,
                data={
                    "rows_affected": rows_affected,
                    "last_insert_id": last_id,
                    "statement": statement
                },
                provider=self.provider_name,
                operation="execute_sqlite"
            )
            
        except Exception as e:
            logger.error(f"SQLite execute error: {e}")
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="execute_sqlite"
            )
    
    async def list_tables(self, db_path: str = None) -> ProviderResult:
        """List all tables in the database"""
        try:
            import sqlite3
            
            db_path = db_path or self.config.default_db_path
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT name, type 
                FROM sqlite_master 
                WHERE type IN ('table', 'view') 
                AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            
            tables = [{"name": row[0], "type": row[1]} for row in cursor.fetchall()]
            conn.close()
            
            return ProviderResult(
                success=True,
                data={"tables": tables, "count": len(tables), "database": db_path},
                provider=self.provider_name,
                operation="list_tables"
            )
            
        except Exception as e:
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="list_tables"
            )
    
    async def describe_table(self, table_name: str, db_path: str = None) -> ProviderResult:
        """Get schema information for a table"""
        try:
            import sqlite3
            
            db_path = db_path or self.config.default_db_path
            
            # Validate table name (prevent injection)
            if not table_name.isalnum() and "_" not in table_name:
                return ProviderResult(
                    success=False,
                    error="Invalid table name",
                    provider=self.provider_name,
                    operation="describe_table"
                )
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get column info
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = []
            for row in cursor.fetchall():
                columns.append({
                    "id": row[0],
                    "name": row[1],
                    "type": row[2],
                    "not_null": bool(row[3]),
                    "default": row[4],
                    "primary_key": bool(row[5])
                })
            
            # Get row count
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            
            conn.close()
            
            return ProviderResult(
                success=True,
                data={
                    "table": table_name,
                    "columns": columns,
                    "column_count": len(columns),
                    "row_count": row_count
                },
                provider=self.provider_name,
                operation="describe_table"
            )
            
        except Exception as e:
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="describe_table"
            )
    
    async def create_table(
        self, 
        table_name: str, 
        columns: List[Dict[str, str]], 
        db_path: str = None
    ) -> ProviderResult:
        """Create a new table
        
        columns format: [{"name": "id", "type": "INTEGER PRIMARY KEY"}, ...]
        """
        if not self.config.allow_write_operations:
            return ProviderResult(
                success=False,
                error="Write operations are disabled",
                provider=self.provider_name,
                operation="create_table"
            )
        
        try:
            import sqlite3
            
            db_path = db_path or self.config.default_db_path
            
            # Build CREATE TABLE statement
            col_defs = ", ".join([f"{c['name']} {c['type']}" for c in columns])
            statement = f"CREATE TABLE IF NOT EXISTS {table_name} ({col_defs})"
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(statement)
            conn.commit()
            conn.close()
            
            return ProviderResult(
                success=True,
                data={"table": table_name, "columns": len(columns), "statement": statement},
                provider=self.provider_name,
                operation="create_table"
            )
            
        except Exception as e:
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="create_table"
            )
    
    async def insert_data(
        self, 
        table_name: str, 
        data: List[Dict], 
        db_path: str = None
    ) -> ProviderResult:
        """Insert multiple rows into a table"""
        if not self.config.allow_write_operations:
            return ProviderResult(
                success=False,
                error="Write operations are disabled",
                provider=self.provider_name,
                operation="insert_data"
            )
        
        try:
            import sqlite3
            
            db_path = db_path or self.config.default_db_path
            
            if not data:
                return ProviderResult(
                    success=False,
                    error="No data provided",
                    provider=self.provider_name,
                    operation="insert_data"
                )
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Build INSERT statement
            columns = list(data[0].keys())
            placeholders = ", ".join(["?" for _ in columns])
            col_names = ", ".join(columns)
            statement = f"INSERT INTO {table_name} ({col_names}) VALUES ({placeholders})"
            
            # Insert rows
            rows_inserted = 0
            for row in data:
                values = tuple(row.get(col) for col in columns)
                cursor.execute(statement, values)
                rows_inserted += 1
            
            conn.commit()
            conn.close()
            
            return ProviderResult(
                success=True,
                data={"table": table_name, "rows_inserted": rows_inserted},
                provider=self.provider_name,
                operation="insert_data"
            )
            
        except Exception as e:
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="insert_data"
            )
    
    async def backup_database(self, db_path: str = None, backup_path: str = None) -> ProviderResult:
        """Create a backup of the database"""
        try:
            import sqlite3
            import shutil
            
            db_path = db_path or self.config.default_db_path
            
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"{db_path}.backup_{timestamp}"
            
            # Create backup
            shutil.copy2(db_path, backup_path)
            
            return ProviderResult(
                success=True,
                data={"source": db_path, "backup": backup_path},
                provider=self.provider_name,
                operation="backup_database"
            )
            
        except Exception as e:
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="backup_database"
            )
    
    # ==================== PostgreSQL Operations ====================
    
    async def query_postgres(self, query: str, params: tuple = None) -> ProviderResult:
        """Execute a SELECT query on PostgreSQL database"""
        if not self.config.pg_host:
            return ProviderResult(
                success=False,
                error="PostgreSQL not configured",
                provider=self.provider_name,
                operation="query_postgres"
            )
        
        try:
            import psycopg2
            from psycopg2.extras import RealDictCursor
            
            # Safety check
            is_safe, reason = self._is_query_safe(query)
            if not is_safe:
                return ProviderResult(
                    success=False,
                    error=f"Query rejected: {reason}",
                    provider=self.provider_name,
                    operation="query_postgres"
                )
            
            conn = psycopg2.connect(
                host=self.config.pg_host,
                port=self.config.pg_port,
                database=self.config.pg_database,
                user=self.config.pg_user,
                password=self.config.pg_password
            )
            
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            rows = cursor.fetchmany(self.config.max_rows_return)
            data = [dict(row) for row in rows]
            
            conn.close()
            
            return ProviderResult(
                success=True,
                data={"rows": data, "row_count": len(data), "query": query},
                provider=self.provider_name,
                operation="query_postgres"
            )
            
        except ImportError:
            return ProviderResult(
                success=False,
                error="psycopg2 not installed. Run: pip install psycopg2-binary",
                provider=self.provider_name,
                operation="query_postgres"
            )
        except Exception as e:
            return ProviderResult(
                success=False,
                error=str(e),
                provider=self.provider_name,
                operation="query_postgres"
            )


# Singleton instance
database_provider = DatabaseControlProvider()
