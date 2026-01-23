"""
RAG Router

REST API endpoints for RAG operations:
- Document queries
- Document management
- Embedding operations
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from tools.retriever import DocumentRetriever
from documents.load_documents import DocumentLoader

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
