"""
RAG Router

REST API endpoints for RAG operations:
- Document queries
- Document management
- Embedding operations
- Vector database management (create, switch, list)
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from tools.retriever import DocumentRetriever
from documents.load_documents import DocumentLoader
from services.vectordb_manager import vectordb_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["rag"])


class QueryRequest(BaseModel):
    """Request for RAG query"""
    query: str = Field(description="Query string")
    collection: str = Field(default="default", description="Collection to query")
    top_k: int = Field(default=5, description="Number of results")
    threshold: float = Field(default=0.0, description="Minimum relevance score")


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


@router.get("/databases/{db_name}")
async def get_database_info(db_name: str):
    """Get information about a specific database"""
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
