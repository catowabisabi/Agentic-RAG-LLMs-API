"""
RAG Router

REST API endpoints for RAG operations:
- Document queries
- Document management
- Embedding operations
- Vector database management (create, switch, list)
"""

import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from tools.retriever import DocumentRetriever
from services.document_loader import DocumentLoader
from services.vectordb_manager import vectordb_manager
from utils.path_security import (
    validate_collection_name,
    validate_db_name,
    validate_backup_filename,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])


def _require_safe_collection(name: str) -> str:
    """Validate collection name and raise HTTP 400 if invalid."""
    try:
        return validate_collection_name(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _require_safe_db(name: str) -> str:
    """Validate database name and raise HTTP 400 if invalid."""
    try:
        return validate_db_name(name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


def _require_safe_backup(filename: str) -> str:
    """Validate backup filename and raise HTTP 400 if invalid."""
    try:
        return validate_backup_filename(filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


class QueryRequest(BaseModel):
    """Request for RAG query"""
    query: str = Field(description="Query string")
    collection: str = Field(default="default", description="Collection to query")
    top_k: int = Field(default=5, description="Number of results")
    threshold: float = Field(default=0.0, description="Minimum relevance score")
    mode: str = Field(default="single", description="Query mode: single, multi, auto")


class SmartQueryRequest(BaseModel):
    """Request for smart RAG query with auto-routing"""
    query: str = Field(description="Query string")
    top_k: int = Field(default=5, description="Number of results per database")
    threshold: float = Field(default=0.0, description="Minimum relevance score")
    mode: str = Field(default="auto", description="auto, multi, or specific database name")


class DocumentRequest(BaseModel):
    """Request to add a document"""
    content: str = Field(description="Document content")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Document metadata")
    collection: str = Field(default="default", description="Target collection")


class QueryResponse(BaseModel):
    """Response from RAG query"""
    query: str
    results: List[Dict[str, Any]]
    count: int
    collection: str


@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    """Query documents using RAG"""
    try:
        retriever = DocumentRetriever(collection_name=request.collection)
        results = retriever.retrieve(request.query, top_k=request.top_k)
        
        # Filter by threshold
        if request.threshold > 0:
            results = [r for r in results if r.get("score", 0) >= request.threshold]
        
        return QueryResponse(
            query=request.query,
            results=results,
            count=len(results),
            collection=request.collection
        )
        
    except Exception as e:
        logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/smart-query")
async def smart_query(request: SmartQueryRequest):
    """Smart query with auto-routing or multi-database search"""
    try:
        if request.mode == "multi":
            # Search all databases
            return await _multi_database_search(request)
        elif request.mode == "auto":
            # Auto route to best database
            return await _auto_route_query(request)
        else:
            # Single database query
            retriever = DocumentRetriever(collection_name=request.mode)
            results = retriever.retrieve(request.query, top_k=request.top_k)
            
            if request.threshold > 0:
                results = [r for r in results if r.get("similarity_score", 0) >= request.threshold]
            
            return {
                "query": request.query,
                "mode": "single",
                "selected_database": request.mode,
                "results": results,
                "count": len(results)
            }
    except Exception as e:
        logger.error(f"Smart query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _multi_database_search(request: SmartQueryRequest) -> Dict[str, Any]:
    """Search across all databases and merge results"""
    databases = vectordb_manager.list_databases()
    all_results = []
    database_counts = {}
    databases_searched = []
    
    for db_info in databases:
        db_name = db_info.get("name")
        if db_info.get("document_count", 0) == 0:
            continue
            
        try:
            # Use vectordb_manager.query instead of DocumentRetriever
            result = await vectordb_manager.query(
                query=request.query,
                db_name=db_name,
                n_results=request.top_k
            )
            
            results = result.get("results", [])
            databases_searched.append(db_name)
            
            # Add database info to each result
            for r in results:
                r["source_database"] = db_name
                r["database_description"] = db_info.get("description", "")
                all_results.append(r)
            
            database_counts[db_name] = len(results)
        except Exception as e:
            logger.warning(f"Error searching {db_name}: {e}")
            continue
    
    # Sort by relevance score (lower distance = better)
    all_results.sort(key=lambda x: x.get("distance", 999))
    
    # Filter by threshold if specified
    if request.threshold > 0:
        # Convert distance to similarity for threshold comparison
        all_results = [r for r in all_results if (1 - r.get("distance", 1) / 2) >= request.threshold]
    
    # Limit total results
    all_results = all_results[:request.top_k * 3]
    
    return {
        "query": request.query,
        "mode": "multi",
        "databases_searched": databases_searched,
        "database_counts": database_counts,
        "results": all_results,
        "total_results": len(all_results)
    }


async def _auto_route_query(request: SmartQueryRequest) -> Dict[str, Any]:
    """Automatically route query to the best database(s)"""
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    from pydantic import BaseModel, Field
    from config.config import Config
    
    config = Config()
    llm = ChatOpenAI(
        model=config.DEFAULT_MODEL,
        temperature=0,
        api_key=config.OPENAI_API_KEY
    )
    
    class DatabaseSelection(BaseModel):
        selected_databases: List[str] = Field(description="List of database names to search")
        reasoning: str = Field(description="Reasoning for database selection")
    
    # Get available databases
    databases = vectordb_manager.list_databases()
    db_descriptions = {}
    db_map = {}  # name -> info mapping
    
    for db_info in databases:
        db_name = db_info.get("name")
        db_map[db_name] = db_info
        if db_info.get("document_count", 0) > 0:
            db_descriptions[db_name] = {
                "description": db_info.get("description", ""),
                "category": db_info.get("category", ""),
                "document_count": db_info.get("document_count", 0)
            }
    
    # Create routing prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a database routing expert. Given a user query and available databases,
select the most relevant database(s) to search.

Available Databases:
{databases}

Rules:
1. Select 1-3 most relevant databases
2. Consider the query topic, keywords, and database descriptions
3. Prefer databases with more documents if relevance is similar
4. Return database names exactly as shown"""),
        ("user", "Query: {query}")
    ])
    
    chain = prompt | llm.with_structured_output(DatabaseSelection)
    
    try:
        selection = await chain.ainvoke({
            "query": request.query,
            "databases": json.dumps(db_descriptions, indent=2, ensure_ascii=False)
        })
        
        # Search selected databases
        all_results = []
        database_counts = {}
        
        for db_name in selection.selected_databases:
            if db_name not in db_map:
                continue
                
            try:
                retriever = DocumentRetriever(collection_name=db_name)
                results = retriever.retrieve(request.query, top_k=request.top_k)
                
                for result in results:
                    result["source_database"] = db_name
                    result["database_description"] = db_map[db_name].get("description", "")
                    all_results.append(result)
                
                database_counts[db_name] = len(results)
            except Exception as e:
                logger.warning(f"Error searching {db_name}: {e}")
                continue
        
        # Sort and filter
        all_results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
        
        if request.threshold > 0:
            all_results = [r for r in all_results if r.get("similarity_score", 0) >= request.threshold]
        
        all_results = all_results[:request.top_k * 2]
        
        return {
            "query": request.query,
            "mode": "auto",
            "selected_databases": selection.selected_databases,
            "reasoning": selection.reasoning,
            "database_counts": database_counts,
            "results": all_results,
            "count": len(all_results)
        }
        
    except Exception as e:
        logger.error(f"Auto routing error: {e}")
        # Fallback to current active database
        active_db = vectordb_manager.get_active_database()
        retriever = DocumentRetriever(collection_name=active_db)
        results = retriever.retrieve(request.query, top_k=request.top_k)
        
        return {
            "query": request.query,
            "mode": "auto_fallback",
            "selected_databases": [active_db],
            "reasoning": f"Fallback to active database due to routing error: {e}",
            "results": results,
            "count": len(results)
        }


@router.post("/document")
async def add_document(request: DocumentRequest):
    """Add a document to the vector store"""
    try:
        retriever = DocumentRetriever(collection_name=request.collection)
        
        # Add document
        doc_id = retriever.add_document(
            content=request.content,
            metadata=request.metadata
        )
        
        return {
            "success": True,
            "document_id": doc_id,
            "collection": request.collection
        }
        
    except Exception as e:
        logger.error(f"Add document error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    collection: str = Form(default="default")
):
    """Upload a document file"""
    try:
        content = await file.read()
        content_str = content.decode("utf-8")
        
        loader = DocumentLoader()
        retriever = DocumentRetriever(collection_name=collection)
        
        # Process based on file type
        filename = file.filename or "unknown"
        
        if filename.endswith(".txt"):
            doc_id = retriever.add_document(
                content=content_str,
                metadata={"filename": filename, "type": "text"}
            )
        elif filename.endswith(".md"):
            doc_id = retriever.add_document(
                content=content_str,
                metadata={"filename": filename, "type": "markdown"}
            )
        elif filename.endswith(".json"):
            doc_id = retriever.add_document(
                content=content_str,
                metadata={"filename": filename, "type": "json"}
            )
        else:
            doc_id = retriever.add_document(
                content=content_str,
                metadata={"filename": filename, "type": "unknown"}
            )
        
        return {
            "success": True,
            "filename": filename,
            "document_id": doc_id,
            "collection": collection
        }
        
    except Exception as e:
        logger.error(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections")
async def list_collections():
    """List available collections"""
    try:
        loader = DocumentLoader()
        collections = loader.list_collections()
        
        return {
            "success": True,
            "collections": collections
        }
        
    except Exception as e:
        logger.error(f"List collections error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/{collection_name}")
async def get_collection_info(collection_name: str):
    """Get information about a collection"""
    try:
        retriever = DocumentRetriever(collection_name=collection_name)
        info = retriever.get_collection_info()
        
        return {
            "success": True,
            "collection": collection_name,
            "info": info
        }
        
    except Exception as e:
        logger.error(f"Collection info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str):
    """Delete a collection"""
    collection_name = _require_safe_collection(collection_name)
    try:
        loader = DocumentLoader()
        loader.delete_collection(collection_name)
        
        return {
            "success": True,
            "deleted": collection_name
        }
        
    except Exception as e:
        logger.error(f"Delete collection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/embed")
async def embed_text(text: str = Form(...)):
    """Get embeddings for text"""
    try:
        retriever = DocumentRetriever()
        embeddings = retriever.get_embeddings(text)
        
        return {
            "success": True,
            "text": text[:100] + "..." if len(text) > 100 else text,
            "embedding_dim": len(embeddings),
            "embeddings": embeddings[:10]  # Return first 10 dimensions
        }
        
    except Exception as e:
        logger.error(f"Embed error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Vector Database Management ==============

class CreateDatabaseRequest(BaseModel):
    """Request to create a new vector database"""
    name: str = Field(description="Database name (unique)")
    description: str = Field(default="", description="Database description")
    category: str = Field(default="general", description="Database category")


class InsertDocumentRequest(BaseModel):
    """Request to insert document into vector database"""
    database: str = Field(description="Target database name")
    content: str = Field(description="Document content")
    title: str = Field(default="", description="Document title")
    source: str = Field(default="", description="Document source")
    category: str = Field(default="general", description="Document category")
    tags: List[str] = Field(default_factory=list, description="Document tags")
    summarize: bool = Field(default=True, description="Summarize before insertion")


class QueryDatabaseRequest(BaseModel):
    """Request to query a vector database"""
    query: str = Field(description="Query string")
    database: str = Field(default=None, description="Database to query (uses active if not specified)")
    n_results: int = Field(default=5, description="Number of results")
    filter_metadata: Dict[str, Any] = Field(default=None, description="Metadata filters")


@router.post("/databases")
async def create_database(request: CreateDatabaseRequest):
    """Create a new vector database"""
    try:
        result = vectordb_manager.create_database(
            db_name=request.name,
            description=request.description,
            category=request.category
        )
        return {
            "success": True,
            "database": result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Create database error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/databases")
async def list_databases():
    """List all available vector databases"""
    try:
        databases = vectordb_manager.list_databases()
        return {
            "success": True,
            "databases": databases,
            "count": len(databases)
        }
    except Exception as e:
        logger.error(f"List databases error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Knowledge Base Skills ==============
# NOTE: These fixed-path routes MUST come before /databases/{db_name}

class UpdateSkillsRequest(BaseModel):
    """Request to update KB skills metadata"""
    display_name: Optional[str] = None
    description: Optional[str] = None
    capabilities: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=list)


@router.get("/databases/skills")
async def get_all_skills():
    """Get skills summary for all knowledge bases (for routing/display)"""
    try:
        skills = vectordb_manager.get_skills_summary()
        return {
            "success": True,
            "skills": skills,
            "count": len(skills)
        }
    except Exception as e:
        logger.error(f"Get skills error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/skills/generate-all")
async def generate_all_skills():
    """Use LLM to generate skills metadata for ALL databases"""
    try:
        results = await vectordb_manager.generate_all_skills()
        return {
            "success": True,
            "results": results
        }
    except Exception as e:
        logger.error(f"Generate all skills error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Smart Ingestion ==============

class SmartInsertRequest(BaseModel):
    """Request for smart content insertion with auto-routing"""
    content: str = Field(description="Document content")
    title: str = Field(default="", description="Document title")
    source: str = Field(default="", description="Document source")
    category: str = Field(default="", description="Document category")
    tags: List[str] = Field(default_factory=list, description="Document tags")
    summarize: bool = Field(default=True, description="Summarize before insertion")
    auto_create: bool = Field(default=True, description="Auto-create new DB if needed")


@router.post("/databases/smart-insert")
async def smart_insert_document(request: SmartInsertRequest):
    """Smart insert: LLM decides which database to add content to"""
    try:
        result = await vectordb_manager.smart_insert(
            content=request.content,
            title=request.title,
            source=request.source,
            category=request.category,
            tags=request.tags,
            summarize=request.summarize,
            auto_create=request.auto_create
        )
        return {
            "success": True,
            **result
        }
    except Exception as e:
        logger.error(f"Smart insert error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/smart-upload")
async def smart_upload_document(
    file: UploadFile = File(...),
    title: str = Form(default=""),
    category: str = Form(default=""),
    summarize: bool = Form(default=True),
    auto_create: bool = Form(default=True)
):
    """Smart upload: LLM decides which database to add uploaded file to"""
    try:
        content = await file.read()
        content_str = content.decode("utf-8")
        filename = file.filename or "unknown"
        
        result = await vectordb_manager.smart_insert(
            content=content_str,
            title=title or filename,
            source=filename,
            filename=filename,
            category=category,
            tags=[filename.split(".")[-1]] if "." in filename else [],
            summarize=summarize,
            auto_create=auto_create
        )
        return {
            "success": True,
            "filename": filename,
            **result
        }
    except Exception as e:
        logger.error(f"Smart upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/suggest-target")
async def suggest_target_database(
    content: str = Form(...),
    title: str = Form(default=""),
    filename: str = Form(default="")
):
    """Preview which database LLM would route content to (without inserting)"""
    try:
        suggestion = await vectordb_manager.suggest_database_for_content(content, title, filename)
        return {
            "success": True,
            "suggestion": suggestion
        }
    except Exception as e:
        logger.error(f"Suggest target error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Backup & Consolidation ==============

@router.post("/databases/backup")
async def create_backup():
    """Create a zip backup of all databases"""
    try:
        result = vectordb_manager.create_backup()
        return {
            "success": True,
            **result
        }
    except Exception as e:
        logger.error(f"Backup error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/databases/backups")
async def list_backups():
    """List all available backups"""
    try:
        backups = vectordb_manager.list_backups()
        return {
            "success": True,
            "backups": backups,
            "count": len(backups)
        }
    except Exception as e:
        logger.error(f"List backups error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/restore/{backup_filename}")
async def restore_backup(backup_filename: str):
    """Restore from a backup. Creates a safety backup first."""
    backup_filename = _require_safe_backup(backup_filename)
    try:
        result = vectordb_manager.restore_backup(backup_filename)
        return {
            "success": True,
            **result
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Restore error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/consolidate")
async def consolidate_databases():
    """LLM-guided database consolidation. Backs up first, then merges related DBs."""
    try:
        result = await vectordb_manager.consolidate_databases()
        return {
            "success": True,
            **result
        }
    except Exception as e:
        logger.error(f"Consolidation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/databases/backup/download/{backup_filename}")
async def download_backup(backup_filename: str):
    """Download a backup file"""
    from fastapi.responses import FileResponse
    from utils.path_security import sanitize_path

    backup_filename = _require_safe_backup(backup_filename)
    backup_dir = vectordb_manager._get_backup_dir()
    try:
        backup_path = sanitize_path(backup_filename, allowed_root=backup_dir)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid backup filename.")
    
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail=f"Backup file not found: {backup_filename}")
    
    return FileResponse(
        path=str(backup_path),
        filename=backup_filename,
        media_type="application/zip"
    )


# ============== Database CRUD (parameterized routes AFTER fixed paths) ==============

@router.get("/databases/{db_name}")
async def get_database_info(db_name: str):
    """Get information about a specific database"""
    db_name = _require_safe_db(db_name)
    try:
        info = vectordb_manager.get_database_info(db_name)
        if not info:
            raise HTTPException(status_code=404, detail=f"Database '{db_name}' not found")
        return {
            "success": True,
            "database": info
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get database info error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/{db_name}/activate")
async def switch_database(db_name: str):
    """Switch to a different active database"""
    db_name = _require_safe_db(db_name)
    try:
        vectordb_manager.switch_database(db_name)
        return {
            "success": True,
            "active_database": db_name,
            "message": f"Switched to database '{db_name}'"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Switch database error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/databases/{db_name}")
async def delete_database(db_name: str):
    """Delete a vector database"""
    db_name = _require_safe_db(db_name)
    try:
        vectordb_manager.delete_database(db_name)
        return {
            "success": True,
            "deleted": db_name
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Delete database error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/insert")
async def insert_document_to_db(request: InsertDocumentRequest):
    """Insert a document into a vector database with optional summarization"""
    try:
        if request.summarize:
            result = await vectordb_manager.insert_with_summary(
                db_name=request.database,
                content=request.content,
                title=request.title,
                source=request.source,
                category=request.category,
                tags=request.tags
            )
        else:
            result = await vectordb_manager.insert_full_text(
                db_name=request.database,
                content=request.content,
                title=request.title,
                source=request.source,
                category=request.category,
                tags=request.tags
            )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Insert document error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/query")
async def query_database(request: QueryDatabaseRequest):
    """Query a vector database"""
    try:
        result = await vectordb_manager.query(
            query=request.query,
            db_name=request.database,
            n_results=request.n_results,
            filter_metadata=request.filter_metadata
        )
        return {
            "success": True,
            **result
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Query database error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/query-all")
async def query_all_databases(query: str = Form(...), n_results: int = Form(default=3)):
    """Query across all databases"""
    try:
        result = await vectordb_manager.query_all_databases(
            query=query,
            n_results=n_results
        )
        return {
            "success": True,
            **result
        }
    except Exception as e:
        logger.error(f"Query all databases error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/upload")
async def upload_to_database(
    file: UploadFile = File(...),
    database: str = Form(...),
    title: str = Form(default=""),
    category: str = Form(default="general"),
    summarize: bool = Form(default=True)
):
    """Upload a document file to a vector database"""
    try:
        content = await file.read()
        content_str = content.decode("utf-8")
        
        filename = file.filename or "unknown"
        
        if summarize:
            result = await vectordb_manager.insert_with_summary(
                db_name=database,
                content=content_str,
                title=title or filename,
                source=filename,
                category=category,
                tags=[filename.split(".")[-1]]  # File extension as tag
            )
        else:
            result = await vectordb_manager.insert_full_text(
                db_name=database,
                content=content_str,
                title=title or filename,
                source=filename,
                category=category,
                tags=[filename.split(".")[-1]]
            )
        
        return {
            "success": True,
            "filename": filename,
            **result
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Upload to database error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Document Management ==============

@router.get("/databases/{db_name}/documents")
async def list_database_documents(db_name: str, limit: int = 100, offset: int = 0):
    """List all documents in a database with their content preview"""
    db_name = _require_safe_db(db_name)
    try:
        info = vectordb_manager.get_database_info(db_name)
        if not info:
            raise HTTPException(status_code=404, detail=f"Database '{db_name}' not found")
        
        # Get documents from the collection
        collection = vectordb_manager._get_collection(db_name)
        if not collection:
            return {
                "success": True,
                "database": db_name,
                "documents": [],
                "total": 0
            }
        
        # Get all documents
        result = collection.get(
            limit=limit,
            offset=offset,
            include=["documents", "metadatas"]
        )
        
        documents = []
        if result and result.get("ids"):
            for i, doc_id in enumerate(result["ids"]):
                doc = {
                    "id": doc_id,
                    "content": result["documents"][i] if result.get("documents") else "",
                    "metadata": result["metadatas"][i] if result.get("metadatas") else {}
                }
                # Add preview
                content = doc["content"] or ""
                doc["preview"] = content[:200] + "..." if len(content) > 200 else content
                documents.append(doc)
        
        return {
            "success": True,
            "database": db_name,
            "documents": documents,
            "total": len(documents),
            "limit": limit,
            "offset": offset
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"List documents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/databases/{db_name}/documents/{doc_id}")
async def delete_document(db_name: str, doc_id: str):
    """Delete a specific document from a database"""
    db_name = _require_safe_db(db_name)
    try:
        collection = vectordb_manager._get_collection(db_name)
        if not collection:
            raise HTTPException(status_code=404, detail=f"Database '{db_name}' not found")
        
        # Delete the document
        collection.delete(ids=[doc_id])
        
        return {
            "success": True,
            "deleted": doc_id,
            "database": db_name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Delete document error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============== Per-Database Skills (parameterized routes) ==============

@router.get("/databases/{db_name}/skills")
async def get_database_skills(db_name: str):
    """Get skills metadata for a specific database"""
    try:
        info = vectordb_manager.get_database_info(db_name)
        if not info:
            raise HTTPException(status_code=404, detail=f"Database '{db_name}' not found")
        
        skills = info.get("skills", vectordb_manager._generate_default_skills(db_name, info))
        return {
            "success": True,
            "database": db_name,
            "skills": skills
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get DB skills error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/databases/{db_name}/skills")
async def update_database_skills(db_name: str, request: UpdateSkillsRequest):
    """Manually update skills metadata for a database"""
    try:
        skills = request.dict(exclude_none=True)
        skills["auto_generated"] = False
        skills["updated_at"] = datetime.now().isoformat()
        result = vectordb_manager.update_database_skills(db_name, skills)
        return {
            "success": True,
            "database": db_name,
            "skills": result.get("skills")
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Update skills error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/databases/{db_name}/skills/generate")
async def generate_database_skills(db_name: str):
    """Use LLM to auto-generate skills metadata by sampling DB content"""
    try:
        skills = await vectordb_manager.generate_skills_with_llm(db_name)
        return {
            "success": True,
            "database": db_name,
            "skills": skills
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Generate skills error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

