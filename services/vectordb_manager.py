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
import shutil
import zipfile
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Optional import for ChromaDB
try:
    import chromadb
    from chromadb.config import Settings
    HAS_CHROMADB = True
except ImportError:
    HAS_CHROMADB = False
    chromadb = None
    Settings = None
    logger.warning("ChromaDB not installed. Vector database features will be disabled.")

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

# ============== Cross-Encoder Reranking Service (Phase 1) ==============
class RerankerService:
    """Cross-Encoder reranker for precise relevance scoring."""
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
        self._model = None
        self._model_name = _config.RERANK_MODEL
        self._enabled = _config.RERANK_ENABLED
        
    def _load_model(self):
        """Lazy-load cross-encoder model (only when first needed)."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import CrossEncoder
            logger.info(f"Loading reranker model: {self._model_name}")
            self._model = CrossEncoder(self._model_name)
            logger.info("Reranker model loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load reranker model: {e}. Reranking disabled.")
            self._enabled = False
    
    def rerank(self, query: str, documents: list, top_k: int = 5) -> list:
        """
        Rerank documents using cross-encoder.
        
        Args:
            query: The search query
            documents: List of dicts with 'content' field
            top_k: Number of top results to return
            
        Returns:
            Reranked and filtered list
        """
        if not self._enabled or not documents:
            return documents[:top_k]
        
        self._load_model()
        if self._model is None:
            return documents[:top_k]
        
        try:
            # Prepare query-document pairs
            pairs = [(query, doc.get("content", "")[:512]) for doc in documents]
            
            # Get cross-encoder scores
            scores = self._model.predict(pairs)
            
            # Attach scores and sort
            for doc, score in zip(documents, scores):
                doc["rerank_score"] = float(score)
            
            documents.sort(key=lambda x: x.get("rerank_score", -999), reverse=True)
            
            return documents[:top_k]
        except Exception as e:
            logger.warning(f"Reranking failed: {e}")
            return documents[:top_k]

# Global reranker instance
_reranker = RerankerService()


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
        
        # Check if ChromaDB is available
        if not HAS_CHROMADB:
            logger.warning("ChromaDB not available. Vector database features disabled.")
            self.base_path = Path(CHROMA_DB_PATH)
            self._active_db = None
            self._clients = {}
            self._collections = {}
            self._metadata = {}
            self.metadata_file = None
            self._llm = None
            self._embeddings = None
            self._text_splitter = None
            return
        
        # Base path for vector databases
        self.base_path = Path(CHROMA_DB_PATH)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Active database tracking
        self._active_db: Optional[str] = None
        self._clients: Dict[str, Any] = {}  # Changed from chromadb.Client to Any
        self._collections: Dict[str, Any] = {}  # Changed from chromadb.Collection to Any
        
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
        
        # Text splitter for chunking (Phase 2: configurable sizes)
        self._text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=_config.CHUNK_SIZE,
            chunk_overlap=_config.CHUNK_OVERLAP,
            length_function=len
        )
        
        # Parent chunk splitter (Phase 2: larger context windows)
        self._parent_splitter = RecursiveCharacterTextSplitter(
            chunk_size=_config.PARENT_CHUNK_SIZE,
            chunk_overlap=400,
            length_function=len
        )
        
        logger.info(f"VectorDBManager initialized. Base path: {self.base_path}")
    
    def _load_metadata(self) -> Dict[str, Any]:
        """Load database metadata from file"""
        if not HAS_CHROMADB or not self.metadata_file:
            return {}
        
        if self.metadata_file.exists():
            with open(self.metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"databases": {}, "active": None}
    
    def _save_metadata(self):
        """Save database metadata to file"""
        if not HAS_CHROMADB or not self.metadata_file:
            return
        
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
        if not HAS_CHROMADB:
            raise RuntimeError("ChromaDB is not installed. Please install chromadb to use vector database features.")
        
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
        """List all available databases with skills metadata"""
        databases = []
        for name, info in self._metadata["databases"].items():
            db_info = info.copy()
            db_info["is_active"] = (name == self._active_db)
            # Include skills metadata if present
            if "skills" not in db_info:
                db_info["skills"] = self._generate_default_skills(name, info)
            databases.append(db_info)
        return databases
    
    def _generate_default_skills(self, name: str, info: Dict) -> Dict[str, Any]:
        """Generate default skills metadata from existing DB info"""
        desc = info.get("description", "")
        cat = info.get("category", "general")
        doc_count = info.get("document_count", 0)
        return {
            "display_name": name.replace("-", " ").title(),
            "description": desc or f"Knowledge base for {name}",
            "capabilities": [],
            "keywords": [name.replace("-", " "), cat],
            "doc_count": doc_count,
            "auto_generated": True
        }
    
    def update_database_skills(self, db_name: str, skills: Dict[str, Any]) -> Dict[str, Any]:
        """Update the skills metadata for a knowledge base"""
        if db_name not in self._metadata["databases"]:
            raise ValueError(f"Database '{db_name}' not found")
        self._metadata["databases"][db_name]["skills"] = skills
        self._save_metadata()
        return self._metadata["databases"][db_name]
    
    async def generate_skills_with_llm(self, db_name: str) -> Dict[str, Any]:
        """Use LLM to generate skills metadata by sampling DB content"""
        if db_name not in self._metadata["databases"]:
            raise ValueError(f"Database '{db_name}' not found")
        
        info = self._metadata["databases"][db_name]
        doc_count = info.get("document_count", 0)
        
        # Sample some documents from the DB
        sample_content = ""
        if doc_count > 0:
            try:
                collection = self._get_collection(db_name)
                sample = collection.get(limit=5, include=["documents", "metadatas"])
                if sample and sample.get("documents"):
                    previews = [d[:300] for d in sample["documents"][:5]]
                    sample_content = "\n---\n".join(previews)
            except Exception as e:
                logger.warning(f"Could not sample content from {db_name}: {e}")
        
        prompt = f"""Analyze this knowledge base and generate structured metadata.

Database name: {db_name}
Current description: {info.get('description', '')}
Category: {info.get('category', 'general')}
Document count: {doc_count}

Sample content (first 5 docs, truncated):
{sample_content or 'No content available'}

Generate a JSON object with:
- display_name: A human-friendly name (e.g., "PineScript Trading Indicators")
- description: A 1-2 sentence description of what this knowledge base contains
- capabilities: List of 3-5 things this KB can help with (e.g., ["Write PineScript strategies", "Explain indicator logic"])
- keywords: List of 5-10 relevant keywords for routing queries to this KB
- topics: List of main topics covered

Respond with ONLY the JSON object."""

        try:
            response = await asyncio.to_thread(self._llm.invoke, prompt)
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.content)
            if json_match:
                skills = json.loads(json_match.group())
                skills["auto_generated"] = True
                skills["generated_at"] = datetime.now().isoformat()
                skills["doc_count"] = doc_count
                
                # Save to metadata
                self._metadata["databases"][db_name]["skills"] = skills
                self._save_metadata()
                return skills
        except Exception as e:
            logger.error(f"Failed to generate skills for {db_name}: {e}")
        
        # Fallback
        return self._generate_default_skills(db_name, info)
    
    async def generate_all_skills(self) -> Dict[str, Any]:
        """Generate skills metadata for ALL databases"""
        results = {}
        for db_name in self._metadata["databases"]:
            try:
                skills = await self.generate_skills_with_llm(db_name)
                results[db_name] = skills
            except Exception as e:
                logger.warning(f"Skipped {db_name}: {e}")
                results[db_name] = {"error": str(e)}
        return results
    
    def get_skills_summary(self) -> List[Dict[str, Any]]:
        """Get a summary of all KB skills for LLM routing"""
        summary = []
        for name, info in self._metadata["databases"].items():
            skills = info.get("skills", self._generate_default_skills(name, info))
            summary.append({
                "name": name,
                "display_name": skills.get("display_name", name),
                "description": skills.get("description", info.get("description", "")),
                "capabilities": skills.get("capabilities", []),
                "keywords": skills.get("keywords", []),
                "doc_count": info.get("document_count", 0),
                "category": info.get("category", "general")
            })
        return summary
    
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
            
            # Get the correct collection - check metadata or find the one with documents
            collection_names = db_info.get("collections", ["documents"])
            collection_name = collection_names[0] if collection_names else "documents"
            
            # Helper to safely iterate collections (handles ChromaDB version differences)
            def _iter_collections_safe(cli):
                """Iterate collections yielding Collection objects, handles ChromaDB 0.5+ API"""
                try:
                    items = cli.list_collections()
                    for item in items:
                        try:
                            if isinstance(item, str):
                                yield cli.get_collection(item)
                            elif hasattr(item, 'count'):
                                yield item
                            else:
                                name = getattr(item, 'name', str(item))
                                yield cli.get_collection(name)
                        except Exception:
                            continue
                except (KeyError, Exception) as e:
                    # ChromaDB 0.5+ may fail with '_type' KeyError on DBs created with older versions
                    logger.debug(f"list_collections failed for {db_name}: {e}, using fallback")
                    # Try common collection names directly
                    for fallback_name in collection_names + ["documents", "default"]:
                        try:
                            coll = cli.get_or_create_collection(fallback_name)
                            yield coll
                        except Exception:
                            continue
            
            # Try to get the collection with documents
            try:
                # First try the collection name from metadata
                collection = client.get_collection(collection_name)
                if collection.count() > 0:
                    self._collections[db_name] = collection
                    logger.info(f"Using collection '{collection_name}' for {db_name} ({collection.count()} docs)")
                else:
                    # Try to find a collection with documents
                    for coll in _iter_collections_safe(client):
                        if coll.count() > 0:
                            self._collections[db_name] = coll
                            logger.info(f"Found collection '{coll.name}' with {coll.count()} docs for {db_name}")
                            break
                    else:
                        # Fall back to the named collection
                        self._collections[db_name] = collection
            except Exception as e:
                logger.warning(f"Error getting collection for {db_name}: {e}")
                # Try to find any collection with documents
                for coll in _iter_collections_safe(client):
                    if coll.count() > 0:
                        self._collections[db_name] = coll
                        logger.info(f"Fallback: using collection '{coll.name}' for {db_name}")
                        break
                else:
                    # Create documents collection as last resort
                    self._collections[db_name] = client.get_or_create_collection("documents")
        
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
        summarize: bool = False,
        chunk: bool = True
    ) -> Dict[str, Any]:
        """
        Insert a document into a vector database.
        
        Phase 2 Enhancement: Parent-child document retrieval.
        - Child chunks (small, 2000 chars) are used for precise vector search
        - Parent chunks (large, 6000 chars) are stored in metadata for context expansion
        - When a child chunk matches, the parent chunk provides full surrounding context
        
        Note: summarize defaults to False (Phase 2.5 fix).
        Summarizing domain documents (medical, legal, accounting) destroys precision.
        Use summarize=True only for general/overview documents.
        
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
        
        # Phase 2.4: Auto-enhance metadata
        import hashlib
        if "content_hash" not in metadata:
            metadata["content_hash"] = hashlib.md5(content[:5000].encode()).hexdigest()
        if "content_length" not in metadata:
            metadata["content_length"] = len(content)
        if "inserted_at" not in metadata:
            metadata["inserted_at"] = datetime.now().isoformat()
        # Auto-detect document type from source path if available
        source = metadata.get("source", "")
        if source and "document_type" not in metadata:
            ext = source.rsplit(".", 1)[-1].lower() if "." in source else ""
            type_map = {
                "pdf": "pdf", "docx": "word", "doc": "word",
                "xlsx": "excel", "xls": "excel", "csv": "csv",
                "txt": "text", "md": "markdown", "html": "html",
                "json": "json", "xml": "xml", "py": "code",
                "js": "code", "ts": "code", "java": "code"
            }
            metadata["document_type"] = type_map.get(ext, "unknown")
        
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
            # Phase 2: Parent-child chunking for better context
            if chunk:
                # Step 1: Create parent chunks (large context windows)
                parent_chunks = self._parent_splitter.split_text(content)
                
                child_index = 0
                for parent_idx, parent_text in enumerate(parent_chunks):
                    # Step 2: Split each parent into child chunks (for search)
                    child_chunks = self._text_splitter.split_text(parent_text)
                    
                    for child_offset, child_text in enumerate(child_chunks):
                        documents_to_insert.append({
                            "content": child_text,
                            "metadata": {
                                **metadata,
                                "chunk_index": child_index,
                                "parent_index": parent_idx,
                                "child_offset": child_offset,
                                "parent_content": parent_text[:_config.PARENT_CHUNK_SIZE],
                                "chunk_type": "child"
                            }
                        })
                        child_index += 1
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
            
            # Sanitize metadata: ChromaDB only accepts str, int, float, bool
            clean_meta = {}
            for k, v in doc["metadata"].items():
                if v is None:
                    clean_meta[k] = ""
                elif isinstance(v, (str, int, float, bool)):
                    clean_meta[k] = v
                else:
                    clean_meta[k] = str(v)
            
            collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[doc["content"]],
                metadatas=[clean_meta]
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
    
    async def insert_hierarchical(
        self,
        db_name: str,
        content: str,
        title: str = "",
        source: str = "",
        category: str = "general",
        tags: List[str] = None,
        sections: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Phase 2.3: Hierarchical document ingestion.
        
        Creates a two-layer index:
        - Layer 1: Document/section summaries (stored with chunk_type='summary_index')
                    These act as routing signals to find which sections are relevant.
        - Layer 2: Original content chunks (stored with chunk_type='child')
                    These provide the actual detail content.
        
        This means:
        - Quick queries first match against summaries (fast routing)
        - Detailed retrieval then fetches relevant child chunks
        
        Args:
            db_name: Target database
            content: Full document content
            title: Document title
            source: Source file path
            category: Document category
            tags: Document tags
            sections: Optional pre-split sections [{title, content}]
        """
        metadata = {
            "title": title,
            "source": source,
            "category": category,
            "tags": ",".join(tags) if tags else "",
            "inserted_at": datetime.now().isoformat(),
            "content_length": len(content)
        }
        
        all_ids = []
        
        # Split into sections if not provided
        if not sections:
            # Use parent splitter to create section-sized chunks
            section_texts = self._parent_splitter.split_text(content)
            sections = [{"title": f"{title} - Section {i+1}", "content": s} 
                       for i, s in enumerate(section_texts)]
        
        # Layer 1: Generate and store section summaries
        for i, section in enumerate(sections):
            section_content = section.get("content", "")
            section_title = section.get("title", f"Section {i+1}")
            
            if len(section_content) < 100:
                continue
            
            try:
                # Generate section summary  
                summary = await self.summarize_document(section_content, max_length=200)
                
                summary_meta = {
                    **metadata,
                    "chunk_type": "summary_index",
                    "section_index": i,
                    "section_title": section_title,
                    "is_summary": True,
                    "original_section_length": len(section_content)
                }
                
                # Insert summary as Layer 1 index entry
                summary_id = f"{db_name}_summary_{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}"
                embedding = await asyncio.to_thread(
                    self._embeddings.embed_query, summary
                )
                
                collection = self._get_collection(db_name)
                clean_meta = {}
                for k, v in summary_meta.items():
                    if v is None:
                        clean_meta[k] = ""
                    elif isinstance(v, (str, int, float, bool)):
                        clean_meta[k] = v
                    else:
                        clean_meta[k] = str(v)
                
                collection.add(
                    ids=[summary_id],
                    embeddings=[embedding],
                    documents=[summary],
                    metadatas=[clean_meta]
                )
                all_ids.append(summary_id)
                
            except Exception as e:
                logger.warning(f"Failed to create summary for section {i}: {e}")
        
        # Layer 2: Insert original content with parent-child chunking
        result = await self.insert_document(
            db_name=db_name,
            content=content,
            metadata={**metadata, "has_hierarchical_index": True},
            summarize=False,
            chunk=True
        )
        all_ids.extend(result.get("document_ids", []))
        
        # Update document count
        collection = self._get_collection(db_name)
        self._metadata["databases"][db_name]["document_count"] = collection.count()
        self._save_metadata()
        
        logger.info(f"[Hierarchical] Inserted {len(all_ids)} items ({len(sections)} summaries + chunks) into {db_name}")
        
        return {
            "success": True,
            "database": db_name,
            "document_ids": all_ids,
            "summary_count": len(sections),
            "total_items": len(all_ids),
            "hierarchical": True
        }
    
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
            n_results: Number of results (must be > 0)
            filter_metadata: Metadata filters
            
        Returns:
            Query results
        """
        if not HAS_CHROMADB:
            logger.warning("ChromaDB not available. Returning empty results.")
            return {"results": [], "db_name": db_name or "none", "query": query}
        
        # Validate n_results
        if n_results < 1:
            n_results = 1
            logger.warning(f"n_results must be >= 1, defaulting to 1")
        
        target_db = db_name or self._active_db
        if not target_db:
            raise ValueError("No database specified and no active database set")
        
        collection = self._get_collection(target_db)
        
        # Check if collection has documents
        doc_count = collection.count()
        if doc_count == 0:
            logger.warning(f"Collection {target_db} is empty")
            return {
                "database": target_db,
                "query": query,
                "results": [],
                "total_results": 0
            }
        
        # Adjust n_results if it exceeds document count
        n_results = min(n_results, doc_count)
        
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
    
    async def query_with_rerank(
        self,
        query: str,
        db_name: str = None,
        top_k: int = 5,
        candidates: int = None,
        min_similarity: float = None,
        filter_metadata: Dict[str, Any] = None,
        rerank: bool = None
    ) -> Dict[str, Any]:
        """
        Enhanced query with reranking and score filtering (Phase 1).
        
        Pipeline: Retrieve candidates → Score filter → Rerank → Return top_k
        
        Args:
            query: Query string
            db_name: Target database
            top_k: Final number of results
            candidates: Number of initial candidates (default: config.TOP_K_CANDIDATES)
            min_similarity: Minimum similarity threshold (default: config.MIN_SIMILARITY)
            filter_metadata: ChromaDB metadata filter
            rerank: Override reranking enabled/disabled
        """
        candidates = candidates or _config.TOP_K_CANDIDATES
        min_similarity = min_similarity if min_similarity is not None else _config.MIN_SIMILARITY
        should_rerank = rerank if rerank is not None else _config.RERANK_ENABLED
        
        # Step 1: Get more candidates than needed
        raw_result = await self.query(
            query=query,
            db_name=db_name,
            n_results=candidates,
            filter_metadata=filter_metadata
        )
        
        results = raw_result.get("results", [])
        
        if not results:
            return raw_result
        
        # Step 2: Score filtering — convert distance to similarity
        filtered = []
        for r in results:
            distance = r.get("distance", 0)
            # ChromaDB L2 distance → similarity: sim = 1 / (1 + distance)
            similarity = 1.0 / (1.0 + distance) if distance is not None else 0.5
            r["similarity"] = similarity
            if similarity >= min_similarity:
                filtered.append(r)
        
        if not filtered:
            # Fallback: keep top 3 even if below threshold
            results.sort(key=lambda x: x.get("distance", 999))
            filtered = results[:3]
            for r in filtered:
                r["similarity"] = 1.0 / (1.0 + r.get("distance", 0))
        
        logger.info(f"[Query+Rerank] {len(results)} candidates → {len(filtered)} after score filter (min_sim={min_similarity})")
        
        # Step 3: Rerank
        if should_rerank and len(filtered) > 1:
            filtered = _reranker.rerank(query, filtered, top_k=top_k)
            logger.info(f"[Query+Rerank] Reranked to top {len(filtered)}")
        else:
            # Sort by similarity and limit
            filtered.sort(key=lambda x: x.get("similarity", 0), reverse=True)
            filtered = filtered[:top_k]
        
        # Step 4: Parent context expansion (Phase 2)
        # If child chunks have parent_content in metadata, use it for richer context
        for r in filtered:
            meta = r.get("metadata", {})
            parent_content = meta.get("parent_content", "")
            if parent_content and meta.get("chunk_type") == "child":
                # Store original child content for reference
                r["child_content"] = r.get("content", "")
                # Expand content to parent chunk for better context
                r["content"] = parent_content
                r["metadata"]["context_expanded"] = True
        
        return {
            "database": raw_result.get("database"),
            "query": query,
            "results": filtered,
            "total_results": len(filtered),
            "candidates_evaluated": len(results),
            "reranked": should_rerank
        }
    
    async def query_targeted_dbs(
        self,
        query: str,
        db_names: List[str],
        top_k: int = 5,
        min_similarity: float = None,
        rerank: bool = None
    ) -> Dict[str, Any]:
        """
        Query specific databases only (Phase 1: Skills-based routing).
        
        Instead of querying ALL databases, only query the ones
        identified as relevant by KB Skills routing.
        """
        all_results = []
        candidates_per_db = max(10, _config.TOP_K_CANDIDATES // max(len(db_names), 1))
        
        for db_name in db_names:
            try:
                result = await self.query_with_rerank(
                    query=query,
                    db_name=db_name,
                    top_k=candidates_per_db,
                    min_similarity=min_similarity,
                    rerank=False  # Rerank after merging all results
                )
                for r in result.get("results", []):
                    r["metadata"] = r.get("metadata", {})
                    r["metadata"]["source_db"] = db_name
                    all_results.append(r)
            except Exception as e:
                logger.warning(f"Error querying {db_name}: {e}")
        
        # Merge and rerank across all targeted DBs
        should_rerank = rerank if rerank is not None else _config.RERANK_ENABLED
        if should_rerank and len(all_results) > 1:
            all_results = _reranker.rerank(query, all_results, top_k=top_k)
        else:
            all_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)
            all_results = all_results[:top_k]
        
        return {
            "query": query,
            "databases_queried": db_names,
            "results": all_results,
            "total_results": len(all_results),
            "reranked": should_rerank
        }
    
    async def query_all(
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
    
    # ============== Smart Ingestion Routing ==============
    
    async def suggest_database_for_content(self, content: str, title: str = "", filename: str = "") -> Dict[str, Any]:
        """
        Use LLM to suggest which database new content should be added to.
        
        Returns:
            Dict with suggested_database, reasoning, confidence, create_new (bool)
        """
        skills_summary = self.get_skills_summary()
        
        # Build KB descriptions for LLM
        kb_descriptions = []
        for s in skills_summary:
            kb_descriptions.append(
                f"- {s['name']}: {s['description']} (category: {s['category']}, docs: {s['doc_count']}, "
                f"keywords: {', '.join(s.get('keywords', [])[:5])})"
            )
        kb_list = "\n".join(kb_descriptions)
        
        content_preview = content[:1000] if len(content) > 1000 else content
        
        prompt = f"""You are a knowledge base router. Given new content, determine which existing knowledge base it should be added to.

Available Knowledge Bases:
{kb_list}

New Content:
Title: {title or filename or 'Untitled'}
Filename: {filename or 'N/A'}
Content Preview:
{content_preview}

Analyze the content and respond with JSON:
{{
    "suggested_database": "database-name",
    "reasoning": "why this KB is the best match",
    "confidence": 0.0-1.0,
    "create_new": false,
    "new_db_name": null,
    "new_db_description": null,
    "new_db_category": null
}}

Rules:
1. Match content topic to the most relevant existing KB
2. If no existing KB matches well (confidence < 0.4), set create_new=true and suggest new_db_name/description/category
3. Consider keywords, category, and capabilities
4. Return ONLY the JSON object"""

        try:
            response = await asyncio.to_thread(self._llm.invoke, prompt)
            import re
            json_match = re.search(r'\{[\s\S]*?\}', response.content)
            if json_match:
                suggestion = json.loads(json_match.group())
                # Validate suggested DB exists
                if not suggestion.get("create_new") and suggestion.get("suggested_database") not in self._metadata["databases"]:
                    suggestion["suggested_database"] = None
                    suggestion["create_new"] = True
                return suggestion
        except Exception as e:
            logger.error(f"Smart ingestion routing failed: {e}")
        
        return {
            "suggested_database": None,
            "reasoning": "Could not determine best database",
            "confidence": 0.0,
            "create_new": True,
            "new_db_name": None,
            "new_db_description": None,
            "new_db_category": None
        }
    
    async def smart_insert(
        self,
        content: str,
        title: str = "",
        source: str = "",
        filename: str = "",
        category: str = "",
        tags: List[str] = None,
        summarize: bool = True,
        auto_create: bool = True
    ) -> Dict[str, Any]:
        """
        Smart insert: LLM decides which database to add content to.
        Optionally creates new DB if none match.
        """
        # Get LLM suggestion
        suggestion = await self.suggest_database_for_content(content, title, filename)
        
        target_db = suggestion.get("suggested_database")
        
        if suggestion.get("create_new") and auto_create:
            new_name = suggestion.get("new_db_name") or f"auto-{datetime.now().strftime('%Y%m%d')}"
            new_desc = suggestion.get("new_db_description") or f"Auto-created for: {title or filename}"
            new_cat = suggestion.get("new_db_category") or category or "general"
            
            safe_name = new_name.lower().replace(" ", "-").replace("_", "-")
            if safe_name not in self._metadata["databases"]:
                self.create_database(safe_name, new_desc, new_cat)
            target_db = safe_name
        elif not target_db:
            # Fallback to first non-empty or create default
            target_db = "default"
            if "default" not in self._metadata["databases"]:
                self.create_database("default", "Default knowledge base", "general")
        
        # Verify target DB is accessible before inserting
        try:
            self._get_collection(target_db)
        except Exception as e:
            logger.warning(f"Target DB '{target_db}' is inaccessible ({e}), creating new compatible DB")
            # Create a new compatible database for this content
            new_name = f"{target_db}-v2"
            if new_name not in self._metadata["databases"]:
                old_info = self._metadata["databases"].get(target_db, {})
                self.create_database(
                    new_name,
                    old_info.get("description", f"Migrated from {target_db}"),
                    old_info.get("category", "general")
                )
            target_db = new_name
            suggestion["routing_note"] = f"Original target was inaccessible, created {new_name}"
        
        # Insert into target DB
        if summarize:
            result = await self.insert_with_summary(
                db_name=target_db,
                content=content,
                title=title,
                source=source or filename,
                category=category or suggestion.get("new_db_category", "general"),
                tags=tags
            )
        else:
            result = await self.insert_full_text(
                db_name=target_db,
                content=content,
                title=title,
                source=source or filename,
                category=category or suggestion.get("new_db_category", "general"),
                tags=tags
            )
        
        result["routing"] = {
            "target_database": target_db,
            "reasoning": suggestion.get("reasoning", ""),
            "confidence": suggestion.get("confidence", 0.0),
            "created_new_db": suggestion.get("create_new", False)
        }
        
        return result
    
    # ============== Backup & Consolidation ==============
    
    def _get_backup_dir(self) -> Path:
        """Get the backup directory path"""
        backup_dir = self.base_path / "_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        return backup_dir
    
    def create_backup(self) -> Dict[str, Any]:
        """
        Create a zip backup of ALL databases (metadata + vector data).
        Keeps max 5 backups, deletes oldest if needed.
        """
        backup_dir = self._get_backup_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"vectordb_backup_{timestamp}.zip"
        backup_path = backup_dir / backup_name
        
        # Zip all databases
        db_count = 0
        total_size = 0
        with zipfile.ZipFile(str(backup_path), 'w', zipfile.ZIP_DEFLATED) as zf:
            # Add metadata
            if self.metadata_file and self.metadata_file.exists():
                zf.write(str(self.metadata_file), "db_metadata.json")
            
            # Add each database directory
            for db_name, db_info in self._metadata.get("databases", {}).items():
                db_path = Path(db_info.get("path", ""))
                if db_path.exists() and db_path.is_dir():
                    for root, dirs, files in os.walk(str(db_path)):
                        # Skip backup directories
                        if "_backups" in root:
                            continue
                        for file in files:
                            file_path = Path(root) / file
                            arcname = f"{db_name}/{file_path.relative_to(db_path)}"
                            zf.write(str(file_path), arcname)
                            total_size += file_path.stat().st_size
                    db_count += 1
        
        # Enforce max 5 backups
        self._cleanup_old_backups(max_count=5)
        
        backup_size = backup_path.stat().st_size
        logger.info(f"Backup created: {backup_name} ({backup_size} bytes, {db_count} databases)")
        
        return {
            "backup_file": backup_name,
            "backup_path": str(backup_path),
            "timestamp": timestamp,
            "databases_backed_up": db_count,
            "original_size": total_size,
            "backup_size": backup_size
        }
    
    def _cleanup_old_backups(self, max_count: int = 5):
        """Remove old backups beyond max_count"""
        backup_dir = self._get_backup_dir()
        backups = sorted(backup_dir.glob("vectordb_backup_*.zip"), key=lambda p: p.stat().st_mtime)
        
        while len(backups) > max_count:
            oldest = backups.pop(0)
            oldest.unlink()
            logger.info(f"Removed old backup: {oldest.name}")
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups"""
        backup_dir = self._get_backup_dir()
        backups = []
        for f in sorted(backup_dir.glob("vectordb_backup_*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
            backups.append({
                "filename": f.name,
                "path": str(f),
                "size": f.stat().st_size,
                "created_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat()
            })
        return backups
    
    def restore_backup(self, backup_filename: str) -> Dict[str, Any]:
        """
        Restore from a backup zip file.
        Creates a pre-restore backup first.
        """
        backup_dir = self._get_backup_dir()
        backup_path = backup_dir / backup_filename
        
        if not backup_path.exists():
            raise ValueError(f"Backup file not found: {backup_filename}")
        
        # Create a safety backup before restore
        safety = self.create_backup()
        logger.info(f"Safety backup created before restore: {safety['backup_file']}")
        
        # Close all clients
        self._clients.clear()
        self._collections.clear()
        
        # Extract backup
        restored_dbs = []
        with zipfile.ZipFile(str(backup_path), 'r') as zf:
            # First extract metadata
            if "db_metadata.json" in zf.namelist():
                metadata_content = zf.read("db_metadata.json")
                restored_metadata = json.loads(metadata_content)
            else:
                raise ValueError("Backup does not contain db_metadata.json")
            
            # Clean existing DB directories that are in the backup
            for db_name in restored_metadata.get("databases", {}):
                db_info = restored_metadata["databases"][db_name]
                db_path = Path(db_info.get("path", ""))
                if db_path.exists():
                    shutil.rmtree(str(db_path))
            
            # Extract all files
            for member in zf.namelist():
                if member == "db_metadata.json":
                    continue
                # Determine which DB this belongs to
                parts = member.split("/", 1)
                if len(parts) >= 2:
                    db_name = parts[0]
                    if db_name in restored_metadata.get("databases", {}):
                        db_path = Path(restored_metadata["databases"][db_name].get("path", ""))
                        if db_path:
                            target_path = db_path / parts[1]
                            target_path.parent.mkdir(parents=True, exist_ok=True)
                            with open(str(target_path), 'wb') as f:
                                f.write(zf.read(member))
                            if db_name not in restored_dbs:
                                restored_dbs.append(db_name)
        
        # Restore metadata
        self._metadata = restored_metadata
        self._save_metadata()
        self._active_db = self._metadata.get("active")
        
        logger.info(f"Restored {len(restored_dbs)} databases from {backup_filename}")
        
        return {
            "restored_from": backup_filename,
            "safety_backup": safety["backup_file"],
            "databases_restored": restored_dbs,
            "count": len(restored_dbs)
        }
    
    async def consolidate_databases(self) -> Dict[str, Any]:
        """
        Use LLM to identify related databases, merge them.
        Creates a backup first.
        
        Returns merge plan and result.
        """
        # Step 1: Backup first
        backup = self.create_backup()
        
        # Step 2: Get LLM to suggest merges
        skills_summary = self.get_skills_summary()
        db_descriptions = []
        for s in skills_summary:
            db_descriptions.append(
                f"- {s['name']}: {s['description']} (category: {s['category']}, docs: {s['doc_count']})"
            )
        db_list = "\n".join(db_descriptions)
        
        prompt = f"""Analyze these knowledge bases and suggest which ones should be merged together.

Knowledge Bases:
{db_list}

Rules:
1. Merge databases that cover the same or very similar topics
2. Keep distinct topics separate
3. Don't merge a large DB into a tiny one - use the larger one as target
4. Empty databases (0 docs) can be merged into the closest matching non-empty DB
5. Be conservative - only merge when clearly related

Respond with JSON:
{{
    "merge_groups": [
        {{
            "target": "target-db-name",
            "sources": ["source-db-1", "source-db-2"],
            "new_name": "merged-name-if-renamed",
            "new_description": "updated description",
            "reasoning": "why these should be merged"
        }}
    ],
    "keep_separate": ["db-names-that-should-stay-separate"],
    "reasoning": "overall reasoning"
}}

Return ONLY the JSON object."""

        try:
            response = await asyncio.to_thread(self._llm.invoke, prompt)
            import re
            json_match = re.search(r'\{[\s\S]*\}', response.content)
            if not json_match:
                return {"error": "LLM did not return valid JSON", "backup": backup}
            
            plan = json.loads(json_match.group())
        except Exception as e:
            return {"error": f"Failed to generate merge plan: {e}", "backup": backup}
        
        # Step 3: Execute merges
        merge_results = []
        for group in plan.get("merge_groups", []):
            target = group.get("target")
            sources = group.get("sources", [])
            
            if not target or target not in self._metadata["databases"]:
                merge_results.append({"group": group, "status": "skipped", "reason": f"Target '{target}' not found"})
                continue
            
            merged_docs = 0
            for source_db in sources:
                if source_db not in self._metadata["databases"]:
                    continue
                if source_db == target:
                    continue
                
                source_info = self._metadata["databases"][source_db]
                if source_info.get("document_count", 0) == 0:
                    # Just remove empty source
                    try:
                        self.delete_database(source_db)
                    except Exception:
                        pass
                    continue
                
                # Copy documents from source to target
                try:
                    source_collection = self._get_collection(source_db)
                    target_collection = self._get_collection(target)
                    
                    # Get all docs from source
                    all_docs = source_collection.get(include=["documents", "metadatas", "embeddings"])
                    
                    if all_docs and all_docs.get("ids"):
                        # Add to target with new IDs
                        new_ids = [f"{target}_{source_db}_{i}" for i in range(len(all_docs["ids"]))]
                        
                        target_collection.add(
                            ids=new_ids,
                            documents=all_docs.get("documents", []),
                            metadatas=all_docs.get("metadatas", []),
                            embeddings=all_docs.get("embeddings")
                        )
                        merged_docs += len(new_ids)
                    
                    # Delete source DB
                    self.delete_database(source_db)
                    
                except Exception as e:
                    logger.error(f"Error merging {source_db} into {target}: {e}")
                    merge_results.append({"source": source_db, "target": target, "status": "error", "error": str(e)})
                    continue
            
            # Update target metadata
            if group.get("new_description"):
                self._metadata["databases"][target]["description"] = group["new_description"]
            self._metadata["databases"][target]["document_count"] = self._get_collection(target).count()
            self._save_metadata()
            
            merge_results.append({
                "target": target,
                "sources": sources,
                "docs_merged": merged_docs,
                "status": "success"
            })
        
        return {
            "backup": backup,
            "plan": plan,
            "merge_results": merge_results,
            "databases_after": list(self._metadata["databases"].keys())
        }
    
    def get_active_database(self) -> Optional[str]:
        """Get the name of the currently active database"""
        return self._active_db or self._metadata.get("active")


# Singleton instance
vectordb_manager = VectorDBManager()
