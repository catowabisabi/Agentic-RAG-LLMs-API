# -*- coding: utf-8 -*-
"""
=============================================================================
向量資料庫管理器 (Vector Database Manager)
=============================================================================

功能說明：
-----------
管理多個向量資料庫，用於不同類別的資料存儲和檢索。

核心功能：
-----------
1. 創建新的向量資料庫（按類別分類）
2. 在不同資料庫之間切換
3. LLM 摘要後插入（可選）
4. 全文檔插入和分塊處理
5. 資料庫列表和狀態查詢

技術架構：
-----------
- 存儲引擎：ChromaDB（持久化向量存儲）
- 嵌入模型：OpenAI text-embedding-3-small (1536維)
- 文本分割：LangChain RecursiveCharacterTextSplitter

使用方式：
-----------
from services import vectordb_manager

# 創建資料庫
await vectordb_manager.create_database("my_docs", "我的文檔庫")

# 添加文檔
await vectordb_manager.add_document("my_docs", content, metadata)

# 查詢
results = await vectordb_manager.query("搜尋關鍵字", "my_docs", n_results=5)

# 列出所有資料庫
databases = vectordb_manager.list_databases()


=============================================================================
"""

import os
import json
import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

import chromadb
from chromadb.config import Settings
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except Exception:
    # Fallback minimal implementation if langchain.text_splitter is not installed
    class RecursiveCharacterTextSplitter:
        def __init__(self, chunk_size=1000, chunk_overlap=200, length_function=len):
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap
            self.length_function = length_function

        def split_text(self, text: str) -> list:
            if not text:
                return []
            chunks = []
            # compute step ensuring it's positive
            step = self.chunk_size - self.chunk_overlap
            if step <= 0:
                step = self.chunk_size
            start = 0
            text_len = self.length_function(text)
            while start < text_len:
                end = min(start + self.chunk_size, text_len)
                chunks.append(text[start:end])
                start += step
            return chunks

from langchain_core.documents import Document

from config.config import Config

# Get config values from the Config class
_config = Config()
CHROMA_DB_PATH = _config.CHROMA_DB_PATH
OPENAI_API_KEY = _config.OPENAI_API_KEY
EMBEDDING_MODEL = _config.EMBEDDING_MODEL
DEFAULT_MODEL = _config.DEFAULT_MODEL

logger = logging.getLogger(__name__)


class VectorDBManager:
    """
    Manages multiple vector databases for different categories.
    
    Features:
    - Create new vector DBs for different categories
    - Switch between active databases
    - LLM summarization before insertion
    - Full-text and chunked document insertion
    - List available databases
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # Base path for vector databases
        self.base_path = Path(CHROMA_DB_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Active database tracking
        self._active_db: Optional[str] = None
        self._clients: Dict[str, chromadb.Client] = {}
        self._collections: Dict[str, chromadb.Collection] = {}
        
        # Database metadata storage
        self.metadata_file = self.base_path / "db_metadata.json"
        self._metadata = self._load_metadata()
        
        # LLM for summarization
        self._llm = ChatOpenAI(
            api_key=OPENAI_API_KEY,
            model=DEFAULT_MODEL,
            temperature=0
        )
        
        # Embeddings
        self._embeddings = OpenAIEmbeddings(
            api_key=OPENAI_API_KEY,
            model=EMBEDDING_MODEL
        )
        
        # Text splitter for chunking
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len
        )
        
        logger.info(f"VectorDBManager initialized. Base path: {self.base_path}")
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load database metadata from file"""
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"databases": {}, "active": None}
    
    def _save_metadata(self):
        """Save database metadata to file"""
        with open(self.metadata_file, 'w', encoding='utf-8') as f:
            json.dump(self._metadata, f, indent=2, default=str, ensure_ascii=False)
    
    # ============== Database Management ==============
    
    def create_database(
        self, 
        db_name: str, 
        description: str = "",
        category: str = "general"
    ) -> Dict[str, Any]:
        """
        Create a new vector database.
        
        Args:
            db_name: Unique name for the database
            description: Description of the database purpose
            category: Category for organization
            
        Returns:
            Database info dict
        """
        # Validate name
        safe_name = db_name.lower().replace(" ", "-").replace("_", "-")
        db_path = self.base_path / safe_name
        
        if safe_name in self._metadata["databases"]:
            raise ValueError(f"Database '{safe_name}' already exists")
        
        # Create directory
        db_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize ChromaDB client
        client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(
                anonymized_telemetry=False
            )
        )
        
        # Create default collection
        collection = client.create_collection(
            name="documents",
            metadata={"description": description}
        )
        
        # Store metadata
        db_info = {
            "name": safe_name,
            "path": str(db_path),
            "description": description,
            "category": category,
            "created_at": datetime.now().isoformat(),
            "document_count": 0,
            "collections": ["documents"]
        }
        
        self._metadata["databases"][safe_name] = db_info
        self._save_metadata()
        
        # Cache client
        self._clients[safe_name] = client
        self._collections[safe_name] = collection
        
        logger.info(f"Created database: {safe_name}")
        
        return db_info
    
    def list_databases(self) -> List[Dict[str, Any]]:
        """List all available databases"""
        databases = []
        for name, info in self._metadata["databases"].items():
            db_info = info.copy()
            db_info["is_active"] = (name == self._active_db)
            databases.append(db_info)
        return databases
    
    def get_database_info(self, db_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific database"""
        return self._metadata["databases"].get(db_name)
    
    def switch_database(self, db_name: str) -> bool:
        """
        Switch to a different active database.
        
        Args:
            db_name: Name of database to switch to
            
        Returns:
            True if successful
        """
        if db_name not in self._metadata["databases"]:
            raise ValueError(f"Database '{db_name}' not found")
        
        self._active_db = db_name
        self._metadata["active"] = db_name
        self._save_metadata()
        
        # Ensure client is loaded
        self._get_client(db_name)
        
        logger.info(f"Switched to database: {db_name}")
        return True
    
    def delete_database(self, db_name: str) -> bool:
        """Delete a database"""
        if db_name not in self._metadata["databases"]:
            raise ValueError(f"Database '{db_name}' not found")
        
        db_path = Path(self._metadata["databases"][db_name]["path"])
        
        # Close client if open
        if db_name in self._clients:
            del self._clients[db_name]
            del self._collections[db_name]
        
        # Remove directory
        import shutil
        if db_path.exists():
            shutil.rmtree(db_path)
        
        # Update metadata
        del self._metadata["databases"][db_name]
        if self._active_db == db_name:
            self._active_db = None
            self._metadata["active"] = None
        self._save_metadata()
        
        logger.info(f"Deleted database: {db_name}")
        return True
    
    def _get_client(self, db_name: str) -> chromadb.Client:
        """Get or create a ChromaDB client for a database"""
        if db_name not in self._clients:
            db_info = self._metadata["databases"].get(db_name)
            if not db_info:
                raise ValueError(f"Database '{db_name}' not found")
            
            client = chromadb.PersistentClient(
                path=db_info["path"],
                settings=Settings(anonymized_telemetry=False)
            )
            self._clients[db_name] = client
            
            # Get or create documents collection
            try:
                self._collections[db_name] = client.get_collection("documents")
            except:
                self._collections[db_name] = client.create_collection("documents")
        
        return self._clients[db_name]
    
    def _get_collection(self, db_name: str) -> chromadb.Collection:
        """Get collection for a database"""
        self._get_client(db_name)  # Ensure client is loaded
        return self._collections[db_name]
    
    # ============== Document Insertion ==============
    
    async def summarize_document(self, content: str, max_length: int = 500) -> str:
        """
        Use LLM to summarize a document before insertion.
        
        Args:
            content: Full document content
            max_length: Maximum summary length
            
        Returns:
            Summarized content
        """
        prompt = f"""Summarize the following document in {max_length} words or less. 
Capture the key points and main ideas.

Document:
{content}

Summary:"""
        
        response = await asyncio.to_thread(
            self._llm.invoke,
            prompt
        )
        
        return response.content
    
    async def insert_document(
        self,
        db_name: str,
        content: str,
        metadata: Dict[str, Any] = None,
        summarize: bool = True,
        chunk: bool = True
    ) -> Dict[str, Any]:
        """
        Insert a document into a vector database.
        
        Args:
            db_name: Target database name
            content: Document content
            metadata: Additional metadata
            summarize: Whether to summarize before embedding
            chunk: Whether to chunk the document
            
        Returns:
            Insertion result
        """
        collection = self._get_collection(db_name)
        metadata = metadata or {}
        
        documents_to_insert = []
        
        if summarize:
            # Generate summary
            summary = await self.summarize_document(content)
            metadata["has_summary"] = True
            metadata["original_length"] = len(content)
            
            # Use summary as document
            if chunk:
                chunks = self._text_splitter.split_text(summary)
                for i, chunk_text in enumerate(chunks):
                    documents_to_insert.append({
                        "content": chunk_text,
                        "metadata": {**metadata, "chunk_index": i, "is_summary": True}
                    })
            else:
                documents_to_insert.append({
                    "content": summary,
                    "metadata": {**metadata, "is_summary": True}
                })
        else:
            # Use original content
            if chunk:
                chunks = self._text_splitter.split_text(content)
                for i, chunk_text in enumerate(chunks):
                    documents_to_insert.append({
                        "content": chunk_text,
                        "metadata": {**metadata, "chunk_index": i}
                    })
            else:
                documents_to_insert.append({
                    "content": content,
                    "metadata": metadata
                })
        
        # Generate embeddings and insert
        ids = []
        for i, doc in enumerate(documents_to_insert):
            doc_id = f"{db_name}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}"
            embedding = await asyncio.to_thread(
                self._embeddings.embed_query,
                doc["content"]
            )
            
            collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[doc["content"]],
                metadatas=[doc["metadata"]]
            )
            ids.append(doc_id)
        
        # Update document count
        self._metadata["databases"][db_name]["document_count"] = collection.count()
        self._save_metadata()
        
        logger.info(f"Inserted {len(ids)} chunks into {db_name}")
        
        return {
            "success": True,
            "database": db_name,
            "document_ids": ids,
            "chunks_created": len(ids),
            "summarized": summarize
        }
    
    async def insert_full_text(
        self,
        db_name: str,
        content: str,
        title: str = "",
        source: str = "",
        category: str = "general",
        tags: List[str] = None
    ) -> Dict[str, Any]:
        """
        Insert full text document without chunking.
        
        Args:
            db_name: Target database name
            content: Full document content
            title: Document title
            source: Document source
            category: Document category
            tags: Document tags
            
        Returns:
            Insertion result
        """
        metadata = {
            "title": title,
            "source": source,
            "category": category,
            "tags": ",".join(tags) if tags else "",
            "inserted_at": datetime.now().isoformat(),
            "content_length": len(content)
        }
        
        return await self.insert_document(
            db_name=db_name,
            content=content,
            metadata=metadata,
            summarize=False,
            chunk=False
        )
    
    async def insert_with_summary(
        self,
        db_name: str,
        content: str,
        title: str = "",
        source: str = "",
        category: str = "general",
        tags: List[str] = None
    ) -> Dict[str, Any]:
        """
        Insert document with LLM summarization first.
        
        Args:
            db_name: Target database name
            content: Full document content
            title: Document title
            source: Document source
            category: Document category
            tags: Document tags
            
        Returns:
            Insertion result with summary
        """
        metadata = {
            "title": title,
            "source": source,
            "category": category,
            "tags": ",".join(tags) if tags else "",
            "inserted_at": datetime.now().isoformat()
        }
        
        return await self.insert_document(
            db_name=db_name,
            content=content,
            metadata=metadata,
            summarize=True,
            chunk=True
        )
    
    # ============== Query ==============
    
    async def query(
        self,
        query: str,
        db_name: str = None,
        n_results: int = 5,
        filter_metadata: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Query a vector database.
        
        Args:
            query: Query string
            db_name: Database to query (uses active if not specified)
            n_results: Number of results
            filter_metadata: Metadata filters
            
        Returns:
            Query results
        """
        target_db = db_name or self._active_db
        if not target_db:
            raise ValueError("No database specified and no active database set")
        
        collection = self._get_collection(target_db)
        
        # Generate query embedding
        query_embedding = await asyncio.to_thread(
            self._embeddings.embed_query,
            query
        )
        
        # Query
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=filter_metadata
        )
        
        # Format results
        formatted = []
        if results["documents"] and results["documents"][0]:
            for i, doc in enumerate(results["documents"][0]):
                formatted.append({
                    "content": doc,
                    "id": results["ids"][0][i] if results["ids"] else None,
                    "distance": results["distances"][0][i] if results["distances"] else None,
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {}
                })
        
        return {
            "database": target_db,
            "query": query,
            "results": formatted,
            "total_results": len(formatted)
        }
    
    async def query_all_databases(
        self,
        query: str,
        n_results: int = 3,
        skip_empty: bool = True
    ) -> Dict[str, Any]:
        """
        Query across all databases.
        
        Args:
            query: Query string
            n_results: Results per database
            skip_empty: Skip databases with no documents
            
        Returns:
            Combined results from all databases
        """
        all_results = {}
        
        for db_name, db_info in self._metadata["databases"].items():
            # Skip empty databases if requested
            if skip_empty and db_info.get("document_count", 0) == 0:
                continue
                
            try:
                result = await self.query(query, db_name, n_results)
                all_results[db_name] = result["results"]
            except Exception as e:
                logger.warning(f"Skipping {db_name}: {e}")
                # Don't include error databases in results
                continue
        
        return {
            "query": query,
            "databases_queried": list(all_results.keys()),
            "results": all_results
        }


# Singleton instance
vectordb_manager = VectorDBManager()
