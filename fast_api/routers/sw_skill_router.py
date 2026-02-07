# -*- coding: utf-8 -*-
"""
=============================================================================
SolidWorks Skill Database Router
=============================================================================

New API endpoint that uses the structured 689MB database from .claude/skills.
This is separate from the existing RAG system.

Database: .claude/skills/sw-api-skill/asset/sw_api_doc.db
- chunks: 158,380 rows (FTS5 searchable content)
- code_examples: 2,396 rows (VBA/C# code samples)
- documents: 11,087 rows (API documentation)
- namespaces: 18 rows (API categories)

Vector DB: .claude/skills/sw-api-skill/asset/sw_api_doc_vector.db
- chunk_embeddings: 299,461 rows (semantic search)

Founding DB: .claude/skills/sw-api-skill/asset/founding.db
- learned_codes: User-generated code for comparison and improvement

=============================================================================
"""

import logging
import sqlite3
import numpy as np
import json
from typing import Dict, Any, List, Optional, Union
from pathlib import Path
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sw-skill", tags=["SolidWorks Skill DB"])

# Database paths
SKILL_DB_PATH = Path(".claude/skills/sw-api-skill/asset/sw_api_doc.db")
VECTOR_DB_PATH = Path(".claude/skills/sw-api-skill/asset/sw_api_doc_vector.db")
FOUNDING_DB_PATH = Path(".claude/skills/sw-api-skill/asset/founding.db")


# ============== Pydantic Models ==============

class SearchResult(BaseModel):
    """Single search result"""
    id: int
    title: str
    chunk_type: str
    content: str
    breadcrumb: Optional[str] = None
    language: Optional[str] = None
    relevance_score: float = 0.0


class CodeExample(BaseModel):
    """Code example from database"""
    id: int
    title: str
    language: str
    code: str
    related_method: Optional[str] = None
    related_interface: Optional[str] = None


class SemanticResult(BaseModel):
    """Semantic search result with similarity score"""
    chunk_id: int
    doc_id: int
    content_preview: str
    similarity: float
    chunk_type: Optional[str] = None
    interface_name: Optional[str] = None
    namespace: Optional[str] = None


class LearnedCode(BaseModel):
    """User-generated code for learning"""
    id: Optional[int] = None
    user_query: str
    generated_code: str
    language: str
    is_working: bool = True
    llm_model: str
    improvement_notes: Optional[str] = None
    created_at: Optional[datetime] = None


class FoundingCodeSubmission(BaseModel):
    """Submit code to founding database"""
    user_query: str = Field(..., description="Original user question")
    generated_code: str = Field(..., description="LLM generated code")
    language: str = Field(..., description="Programming language (vba, csharp, python)")
    is_working: bool = Field(True, description="Whether the code works correctly")
    llm_model: str = Field("claude-3.5-sonnet", description="LLM model used")
    improvement_notes: Optional[str] = Field(None, description="Notes for improvement")


class SearchResponse(BaseModel):
    """Search API response"""
    query: str
    total_results: int
    chunks: List[SearchResult] = []
    code_examples: List[CodeExample] = []
    search_time_ms: float


class NamespaceInfo(BaseModel):
    """API namespace info"""
    id: int
    name: str
    api_category: str
    description: Optional[str] = None


# ============== Database Helpers ==============

def get_connection() -> sqlite3.Connection:
    """Get SQLite connection with row factory"""
    if not SKILL_DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=f"SolidWorks Skill database not found at {SKILL_DB_PATH}"
        )
    conn = sqlite3.connect(str(SKILL_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_vector_connection() -> sqlite3.Connection:
    """Get vector database connection"""
    if not VECTOR_DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Vector database not found at {VECTOR_DB_PATH}"
        )
    conn = sqlite3.connect(str(VECTOR_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_founding_connection() -> sqlite3.Connection:
    """Get or create founding database connection"""
    conn = sqlite3.connect(str(FOUNDING_DB_PATH))
    conn.row_factory = sqlite3.Row
    
    # Initialize founding database if empty
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS learned_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_query TEXT NOT NULL,
            generated_code TEXT NOT NULL,
            language TEXT NOT NULL,
            is_working BOOLEAN DEFAULT 1,
            llm_model TEXT DEFAULT 'claude-3.5-sonnet',
            improvement_notes TEXT,
            similarity_hash TEXT, -- For finding similar codes
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_learned_codes_language 
        ON learned_codes(language)
    """)
    
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_learned_codes_working 
        ON learned_codes(is_working)
    """)
    
    conn.commit()
    return conn


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors"""
    try:
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    except Exception as e:
        logger.warning(f"Cosine similarity calculation failed: {e}")
        return 0.0


def search_chunks_fts(query: str, limit: int = 10) -> List[Dict]:
    """Search chunks using FTS5 full-text search"""
    conn = get_connection()
    cursor = conn.cursor()
    
    results = []
    try:
        # FTS5 search on chunks
        cursor.execute("""
            SELECT c.id, c.chunk_type, c.content, c.parent_title, c.breadcrumb, c.language,
                   bm25(chunks_fts) as score
            FROM chunks c
            JOIN chunks_fts fts ON c.rowid = fts.rowid
            WHERE chunks_fts MATCH ?
            ORDER BY bm25(chunks_fts)
            LIMIT ?
        """, (query, limit))
        
        for row in cursor.fetchall():
            results.append({
                "id": row["id"],
                "title": row["parent_title"] or "Untitled",
                "chunk_type": row["chunk_type"],
                "content": row["content"][:1000] if row["content"] else "",
                "breadcrumb": row["breadcrumb"],
                "language": row["language"],
                "relevance_score": abs(row["score"]) if row["score"] else 0.0
            })
    except sqlite3.OperationalError as e:
        logger.warning(f"FTS search failed, falling back to LIKE: {e}")
        # Fallback to LIKE search
        cursor.execute("""
            SELECT id, chunk_type, content, parent_title, breadcrumb, language
            FROM chunks
            WHERE content LIKE ?
            LIMIT ?
        """, (f"%{query}%", limit))
        
        for row in cursor.fetchall():
            results.append({
                "id": row["id"],
                "title": row["parent_title"] or "Untitled",
                "chunk_type": row["chunk_type"],
                "content": row["content"][:1000] if row["content"] else "",
                "breadcrumb": row["breadcrumb"],
                "language": row["language"],
                "relevance_score": 0.5
            })
    finally:
        conn.close()
    
    return results


def semantic_search_chunks(query_text: str, limit: int = 10, min_similarity: float = 0.3) -> List[Dict]:
    """
    Semantic search using embeddings (placeholder - requires embedding model)
    Currently returns similar structure for API consistency
    """
    # TODO: Implement actual embedding search when embedding model is available
    # For now, fall back to FTS search but return semantic result format
    
    vector_conn = get_vector_connection()
    cursor = vector_conn.cursor()
    
    results = []
    try:
        # Get sample embeddings for testing (first few records)
        cursor.execute("""
            SELECT chunk_id, doc_id, content_preview, chunk_type, 
                   interface_name, namespace, embedding
            FROM chunk_embeddings
            WHERE content_preview LIKE ?
            LIMIT ?
        """, (f"%{query_text}%", limit))
        
        for row in cursor.fetchall():
            # For testing, use content match as similarity score
            similarity = 0.8 if query_text.lower() in row["content_preview"].lower() else 0.5
            
            if similarity >= min_similarity:
                results.append({
                    "chunk_id": row["chunk_id"],
                    "doc_id": row["doc_id"],
                    "content_preview": row["content_preview"][:500],
                    "similarity": similarity,
                    "chunk_type": row["chunk_type"],
                    "interface_name": row["interface_name"],
                    "namespace": row["namespace"]
                })
        
        # Sort by similarity
        results.sort(key=lambda x: x["similarity"], reverse=True)
        
    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        # Fallback to empty results
        results = []
    finally:
        vector_conn.close()
    
    return results


def search_founding_codes(query: str, language: Optional[str] = None) -> List[Dict]:
    """Search learned codes in founding database"""
    conn = get_founding_connection()
    cursor = conn.cursor()
    
    results = []
    try:
        if language:
            cursor.execute("""
                SELECT id, user_query, generated_code, language, is_working, 
                       llm_model, improvement_notes, created_at
                FROM learned_codes
                WHERE (user_query LIKE ? OR generated_code LIKE ?) 
                AND language = ?
                ORDER BY is_working DESC, created_at DESC
                LIMIT 10
            """, (f"%{query}%", f"%{query}%", language))
        else:
            cursor.execute("""
                SELECT id, user_query, generated_code, language, is_working,
                       llm_model, improvement_notes, created_at
                FROM learned_codes
                WHERE user_query LIKE ? OR generated_code LIKE ?
                ORDER BY is_working DESC, created_at DESC
                LIMIT 10
            """, (f"%{query}%", f"%{query}%"))
        
        for row in cursor.fetchall():
            code = row["generated_code"]
            if len(code) > 1500:
                code = code[:1500] + "\n... (truncated)"
            
            results.append({
                "id": row["id"],
                "user_query": row["user_query"],
                "generated_code": code,
                "language": row["language"],
                "is_working": bool(row["is_working"]),
                "llm_model": row["llm_model"],
                "improvement_notes": row["improvement_notes"],
                "created_at": row["created_at"]
            })
    finally:
        conn.close()
    
    return results


def search_code_examples(query: str, limit: int = 5) -> List[Dict]:
    """Search code examples table"""
    conn = get_connection()
    cursor = conn.cursor()
    
    results = []
    try:
        cursor.execute("""
            SELECT id, title, language, code, related_method, related_interface
            FROM code_examples
            WHERE code LIKE ? OR title LIKE ? OR related_method LIKE ?
            LIMIT ?
        """, (f"%{query}%", f"%{query}%", f"%{query}%", limit))
        
        for row in cursor.fetchall():
            code = row["code"]
            # Truncate very long code
            if code and len(code) > 2000:
                code = code[:2000] + "\n... (truncated)"
            
            results.append({
                "id": row["id"],
                "title": row["title"] or "Untitled Example",
                "language": row["language"] or "unknown",
                "code": code or "",
                "related_method": row["related_method"],
                "related_interface": row["related_interface"]
            })
    finally:
        conn.close()
    
    return results


# ============== API Endpoints ==============

@router.get("/health")
async def health_check():
    """Check if the skill database is accessible"""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Get stats
        cursor.execute("SELECT COUNT(*) FROM chunks")
        chunks_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM code_examples")
        examples_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM documents")
        docs_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "status": "healthy",
            "database": str(SKILL_DB_PATH),
            "stats": {
                "chunks": chunks_count,
                "code_examples": examples_count,
                "documents": docs_count
            }
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query", min_length=1),
    limit: int = Query(10, ge=1, le=50, description="Max results per category"),
    include_code: bool = Query(True, description="Include code examples")
):
    """
    Search the SolidWorks API documentation database.
    
    Uses FTS5 full-text search on 158K+ content chunks.
    Optionally includes matching code examples.
    """
    start_time = datetime.now()
    
    # Search chunks
    chunks = search_chunks_fts(q, limit)
    
    # Search code examples
    code_examples = []
    if include_code:
        code_examples = search_code_examples(q, min(limit, 10))
    
    search_time = (datetime.now() - start_time).total_seconds() * 1000
    
    return SearchResponse(
        query=q,
        total_results=len(chunks) + len(code_examples),
        chunks=[SearchResult(**c) for c in chunks],
        code_examples=[CodeExample(**e) for e in code_examples],
        search_time_ms=round(search_time, 2)
    )


@router.get("/semantic-search")
async def semantic_search(
    q: str = Query(..., description="Semantic search query", min_length=1),
    limit: int = Query(10, ge=1, le=30, description="Max results"),
    min_similarity: float = Query(0.3, ge=0.0, le=1.0, description="Minimum similarity score")
):
    """
    Semantic search using vector embeddings.
    
    Finds conceptually similar content even with different wording.
    Currently uses content matching as fallback - full embedding search coming soon.
    """
    start_time = datetime.now()
    
    # Semantic search on embeddings
    semantic_results = semantic_search_chunks(q, limit, min_similarity)
    
    search_time = (datetime.now() - start_time).total_seconds() * 1000
    
    return {
        "query": q,
        "search_type": "semantic",
        "total_results": len(semantic_results),
        "min_similarity": min_similarity,
        "results": [SemanticResult(**r) for r in semantic_results],
        "search_time_ms": round(search_time, 2),
        "note": "Full embedding search coming soon - currently using content matching fallback"
    }


@router.post("/founding/submit-code")
async def submit_learned_code(submission: FoundingCodeSubmission):
    """
    Submit user-generated code to the founding database for learning and comparison.
    
    This helps improve future code generation by storing working solutions.
    """
    conn = get_founding_connection()
    cursor = conn.cursor()
    
    try:
        # Generate a simple hash for similarity detection
        import hashlib
        code_text = f"{submission.user_query} {submission.generated_code}".lower()
        similarity_hash = hashlib.md5(code_text.encode()).hexdigest()[:16]
        
        cursor.execute("""
            INSERT INTO learned_codes 
            (user_query, generated_code, language, is_working, llm_model, 
             improvement_notes, similarity_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            submission.user_query,
            submission.generated_code,
            submission.language,
            submission.is_working,
            submission.llm_model,
            submission.improvement_notes,
            similarity_hash
        ))
        
        code_id = cursor.lastrowid
        conn.commit()
        
        return {
            "status": "success",
            "code_id": code_id,
            "message": "Code submitted to founding database for learning",
            "similarity_hash": similarity_hash
        }
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to save code: {str(e)}")
    finally:
        conn.close()


@router.get("/founding/search")
async def search_learned_codes(
    q: str = Query(..., description="Search query for learned codes"),
    language: Optional[str] = Query(None, description="Language filter (vba, csharp, python)"),
    working_only: bool = Query(True, description="Only return working codes")
):
    """
    Search the founding database for previously learned code solutions.
    
    Helps find existing solutions to similar problems before generating new code.
    """
    start_time = datetime.now()
    
    results = search_founding_codes(q, language)
    
    # Filter by working status if requested
    if working_only:
        results = [r for r in results if r["is_working"]]
    
    search_time = (datetime.now() - start_time).total_seconds() * 1000
    
    return {
        "query": q,
        "language_filter": language,
        "working_only": working_only,
        "total_results": len(results),
        "learned_codes": results,
        "search_time_ms": round(search_time, 2)
    }


@router.get("/founding/stats")
async def founding_stats():
    """Get statistics about the founding database"""
    conn = get_founding_connection()
    cursor = conn.cursor()
    
    try:
        # Total codes
        cursor.execute("SELECT COUNT(*) FROM learned_codes")
        total = cursor.fetchone()[0]
        
        # By language
        cursor.execute("""
            SELECT language, COUNT(*) as count
            FROM learned_codes
            GROUP BY language
            ORDER BY count DESC
        """)
        by_language = dict(cursor.fetchall())
        
        # Working vs not working
        cursor.execute("""
            SELECT is_working, COUNT(*) as count
            FROM learned_codes  
            GROUP BY is_working
        """)
        by_status = {bool(row[0]): row[1] for row in cursor.fetchall()}
        
        # Recent submissions
        cursor.execute("""
            SELECT COUNT(*) FROM learned_codes
            WHERE created_at >= datetime('now', '-7 days')
        """)
        recent_week = cursor.fetchone()[0]
        
        return {
            "total_codes": total,
            "by_language": by_language,
            "working_codes": by_status.get(True, 0),
            "non_working_codes": by_status.get(False, 0),
            "submitted_last_week": recent_week,
            "database_path": str(FOUNDING_DB_PATH)
        }
        
    finally:
        conn.close()


@router.get("/namespaces", response_model=List[NamespaceInfo])
async def list_namespaces():
    """List all SolidWorks API namespaces/categories"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, name, api_category, description
            FROM namespaces
            ORDER BY name
        """)
        
        return [
            NamespaceInfo(
                id=row["id"],
                name=row["name"],
                api_category=row["api_category"] or "",
                description=row["description"]
            )
            for row in cursor.fetchall()
        ]
    finally:
        conn.close()


@router.get("/code-examples")
async def list_code_examples(
    language: Optional[str] = Query(None, description="Filter by language (vba, csharp)"),
    limit: int = Query(20, ge=1, le=100)
):
    """List code examples, optionally filtered by language"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        if language:
            cursor.execute("""
                SELECT id, title, language, code, related_method, related_interface
                FROM code_examples
                WHERE language LIKE ?
                LIMIT ?
            """, (f"%{language}%", limit))
        else:
            cursor.execute("""
                SELECT id, title, language, code, related_method, related_interface
                FROM code_examples
                LIMIT ?
            """, (limit,))
        
        results = []
        for row in cursor.fetchall():
            code = row["code"]
            if code and len(code) > 1000:
                code = code[:1000] + "\n... (truncated)"
            
            results.append({
                "id": row["id"],
                "title": row["title"],
                "language": row["language"],
                "code": code,
                "related_method": row["related_method"],
                "related_interface": row["related_interface"]
            })
        
        return {
            "total": len(results),
            "language_filter": language,
            "examples": results
        }
    finally:
        conn.close()


@router.get("/document/{doc_id}")
async def get_document(doc_id: int):
    """Get full document details by ID"""
    conn = get_connection()
    cursor = conn.cursor()
    
    try:
        # Get document
        cursor.execute("""
            SELECT id, title, doc_type, interface_name, description, full_text, source_url
            FROM documents
            WHERE id = ?
        """, (doc_id,))
        
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
        
        # Get related chunks
        cursor.execute("""
            SELECT id, chunk_type, content, parent_title
            FROM chunks
            WHERE doc_id = ?
            LIMIT 10
        """, (doc_id,))
        
        chunks = [dict(r) for r in cursor.fetchall()]
        
        return {
            "id": row["id"],
            "title": row["title"],
            "doc_type": row["doc_type"],
            "interface_name": row["interface_name"],
            "description": row["description"],
            "full_text": row["full_text"][:5000] if row["full_text"] else None,
            "source_url": row["source_url"],
            "related_chunks": chunks
        }
    finally:
        conn.close()
