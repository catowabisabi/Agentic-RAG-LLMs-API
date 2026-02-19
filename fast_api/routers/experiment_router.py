"""
Experiment Router — Isolated API endpoints for testing new RAG strategies.

These endpoints do NOT modify the existing agent pipeline.
They are designed for A/B comparison testing before merging.

Endpoints:
- POST /experiment/fast-rag     — 2 LLM calls only (route DB + generate answer)
- POST /experiment/hybrid-search — BM25 + Vector fusion search
- POST /experiment/compare       — Run all strategies and compare results
"""

import logging
import time
import asyncio
import re
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/experiment", tags=["experiment"])


# ============== Request/Response Models ==============

class FastRAGRequest(BaseModel):
    """Request for Fast RAG (2 LLM calls only)"""
    query: str = Field(description="User query")
    top_k: int = Field(default=5, description="Number of results to return")
    db_names: Optional[List[str]] = Field(default=None, description="Specific DBs to search (auto-route if empty)")
    min_similarity: float = Field(default=0.25, description="Minimum similarity threshold")


class HybridSearchRequest(BaseModel):
    """Request for BM25 + Vector hybrid search"""
    query: str = Field(description="Search query")
    top_k: int = Field(default=5, description="Number of results")
    db_name: Optional[str] = Field(default=None, description="Specific DB (searches all if empty)")
    alpha: float = Field(default=0.7, description="Weight for vector score (1-alpha = BM25 weight)")
    min_similarity: float = Field(default=0.25, description="Minimum similarity threshold")


class CompareRequest(BaseModel):
    """Request to compare all strategies"""
    query: str = Field(description="User query")
    top_k: int = Field(default=5, description="Number of results per strategy")


class RAGResult(BaseModel):
    """Standardized result format"""
    strategy: str
    answer: str
    sources: List[Dict[str, Any]] = []
    timing_ms: int
    llm_calls: int
    metadata: Dict[str, Any] = {}


# ============== Fast RAG: 2 LLM calls only ==============

@router.post("/fast-rag", response_model=RAGResult)
async def fast_rag_query(request: FastRAGRequest):
    """
    Fast RAG Pipeline — Only 2 LLM calls:
    1. DB routing (select relevant DBs via Skills)
    2. Generate answer from retrieved context
    
    Skips: ReAct loop, metacognition, planning, validation
    Purpose: Speed benchmark — compare with full agentic pipeline
    """
    start = time.time()
    llm_calls = 0
    
    try:
        from services.vectordb_manager import vectordb_manager
        from services.llm_service import get_llm_service
        
        llm_service = get_llm_service()
        
        # === LLM Call 1: Route to relevant DBs ===
        targeted_dbs = request.db_names
        
        if not targeted_dbs:
            targeted_dbs = await _route_dbs_fast(vectordb_manager, llm_service, request.query)
            llm_calls += 1
        
        if not targeted_dbs:
            # Fallback: get all non-empty DBs
            db_list = vectordb_manager.list_databases()
            targeted_dbs = [db["name"] for db in db_list if db.get("document_count", 0) > 0]
        
        if not targeted_dbs:
            return RAGResult(
                strategy="fast_rag",
                answer="No knowledge bases available to search.",
                sources=[],
                timing_ms=int((time.time() - start) * 1000),
                llm_calls=llm_calls,
                metadata={"dbs_searched": []}
            )
        
        logger.info(f"[FastRAG] Routing to DBs: {targeted_dbs}")
        
        # Retrieve with reranking (no LLM call — uses cross-encoder)
        result = await vectordb_manager.query_targeted_dbs(
            query=request.query,
            db_names=targeted_dbs,
            top_k=request.top_k,
            min_similarity=request.min_similarity
        )
        
        docs = result.get("results", [])
        
        if not docs:
            return RAGResult(
                strategy="fast_rag",
                answer="No relevant documents found in the knowledge base.",
                sources=[],
                timing_ms=int((time.time() - start) * 1000),
                llm_calls=llm_calls,
                metadata={"dbs_searched": targeted_dbs}
            )
        
        # Build context from retrieved docs
        context_parts = []
        sources = []
        for i, doc in enumerate(docs[:request.top_k]):
            content = doc.get("content", "")[:3000]
            meta = doc.get("metadata", {})
            context_parts.append(f"[Source {i+1}] ({meta.get('source_db', 'unknown')}):\n{content}")
            sources.append({
                "title": meta.get("title", meta.get("source", f"Doc {i+1}")),
                "database": meta.get("source_db", ""),
                "similarity": round(doc.get("similarity", 0), 3),
                "rerank_score": round(doc.get("rerank_score", 0), 3) if "rerank_score" in doc else None,
                "snippet": content[:200]
            })
        
        context = "\n\n".join(context_parts)
        
        # === LLM Call 2: Generate final answer ===
        answer_prompt = f"""Answer the user's question based on the following knowledge base context.
If the context doesn't contain enough information, say so honestly.
Match the language of the user's question.

Context:
{context[:16000]}

Question: {request.query}

Answer:"""
        
        answer_result = await llm_service.generate(
            prompt=answer_prompt,
            system_message="You are a helpful assistant. Answer based on the provided context. Be accurate and concise.",
            temperature=0.3
        )
        llm_calls += 1
        
        answer_text = answer_result.content if hasattr(answer_result, 'content') else str(answer_result)
        
        elapsed_ms = int((time.time() - start) * 1000)
        
        return RAGResult(
            strategy="fast_rag",
            answer=answer_text,
            sources=sources,
            timing_ms=elapsed_ms,
            llm_calls=llm_calls,
            metadata={
                "dbs_searched": targeted_dbs,
                "docs_retrieved": len(docs),
                "reranked": result.get("reranked", False),
                "context_chars": len(context)
            }
        )
        
    except Exception as e:
        logger.error(f"[FastRAG] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============== Hybrid BM25 + Vector Search ==============

@router.post("/hybrid-search", response_model=RAGResult)
async def hybrid_search(request: HybridSearchRequest):
    """
    Hybrid BM25 + Vector search — combines lexical and semantic matching.
    
    - BM25: Exact keyword matching (good for technical terms, codes, names)
    - Vector: Semantic similarity (good for meaning, paraphrasing)
    - Fusion: alpha * vector_score + (1-alpha) * bm25_score
    
    Purpose: See if hybrid search finds better documents than vector-only
    """
    start = time.time()
    
    try:
        from services.vectordb_manager import vectordb_manager
        
        # Determine which DBs to search
        if request.db_name:
            db_names = [request.db_name]
        else:
            db_list = vectordb_manager.list_databases()
            db_names = [db["name"] for db in db_list if db.get("document_count", 0) > 0]
        
        if not db_names:
            return RAGResult(
                strategy="hybrid_bm25_vector",
                answer="",
                sources=[],
                timing_ms=int((time.time() - start) * 1000),
                llm_calls=0,
                metadata={"error": "No databases available"}
            )
        
        all_hybrid_results = []
        
        for db_name in db_names:
            try:
                # Get vector results
                vector_result = await vectordb_manager.query_with_rerank(
                    query=request.query,
                    db_name=db_name,
                    top_k=request.top_k * 3,  # Get more candidates
                    min_similarity=0.1,  # Lower threshold for fusion
                    rerank=False  # Skip rerank, we'll do fusion scoring
                )
                vector_docs = vector_result.get("results", [])
                
                # BM25 scoring on the same corpus
                bm25_scores = _bm25_score_documents(request.query, vector_docs)
                
                # Fusion scoring
                for doc, bm25_score in zip(vector_docs, bm25_scores):
                    vector_score = doc.get("similarity", 0)
                    fusion_score = request.alpha * vector_score + (1 - request.alpha) * bm25_score
                    doc["fusion_score"] = fusion_score
                    doc["bm25_score"] = bm25_score
                    doc["vector_score"] = vector_score
                    doc["metadata"] = doc.get("metadata", {})
                    doc["metadata"]["source_db"] = db_name
                    all_hybrid_results.append(doc)
                    
            except Exception as e:
                logger.warning(f"[Hybrid] Error searching {db_name}: {e}")
        
        # Sort by fusion score
        all_hybrid_results.sort(key=lambda x: x.get("fusion_score", 0), reverse=True)
        top_results = all_hybrid_results[:request.top_k]
        
        # Filter by minimum similarity on fusion score
        filtered = [r for r in top_results if r.get("fusion_score", 0) >= request.min_similarity]
        if not filtered:
            filtered = top_results[:3]  # fallback
        
        sources = []
        for doc in filtered:
            meta = doc.get("metadata", {})
            sources.append({
                "title": meta.get("title", meta.get("source", "")),
                "database": meta.get("source_db", ""),
                "fusion_score": round(doc.get("fusion_score", 0), 4),
                "vector_score": round(doc.get("vector_score", 0), 4),
                "bm25_score": round(doc.get("bm25_score", 0), 4),
                "snippet": doc.get("content", "")[:200]
            })
        
        elapsed_ms = int((time.time() - start) * 1000)
        
        return RAGResult(
            strategy="hybrid_bm25_vector",
            answer="",  # This is a search endpoint, not a QA endpoint
            sources=sources,
            timing_ms=elapsed_ms,
            llm_calls=0,
            metadata={
                "dbs_searched": db_names,
                "total_candidates": len(all_hybrid_results),
                "alpha": request.alpha,
                "results_after_filter": len(filtered)
            }
        )
        
    except Exception as e:
        logger.error(f"[Hybrid] Error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============== Compare All Strategies ==============

@router.post("/compare")
async def compare_strategies(request: CompareRequest):
    """
    Run the same query through multiple strategies and return timing + results for comparison.
    
    Strategies compared:
    1. fast_rag: 2 LLM calls (route + answer)
    2. hybrid_search: BM25 + vector fusion (search only)
    3. vector_only: Standard vector search with reranking (search only)
    """
    results = {}
    
    # Strategy 1: Fast RAG
    try:
        fast_result = await fast_rag_query(FastRAGRequest(
            query=request.query,
            top_k=request.top_k
        ))
        results["fast_rag"] = fast_result.model_dump()
    except Exception as e:
        results["fast_rag"] = {"error": str(e)}
    
    # Strategy 2: Hybrid BM25+Vector
    try:
        hybrid_result = await hybrid_search(HybridSearchRequest(
            query=request.query,
            top_k=request.top_k
        ))
        results["hybrid_bm25_vector"] = hybrid_result.model_dump()
    except Exception as e:
        results["hybrid_bm25_vector"] = {"error": str(e)}
    
    # Strategy 3: Vector-only with reranking
    try:
        from services.vectordb_manager import vectordb_manager
        start = time.time()
        
        db_list = vectordb_manager.list_databases()
        active_dbs = [db["name"] for db in db_list if db.get("document_count", 0) > 0]
        
        vector_result = await vectordb_manager.query_targeted_dbs(
            query=request.query,
            db_names=active_dbs,
            top_k=request.top_k
        )
        
        elapsed_ms = int((time.time() - start) * 1000)
        
        sources = []
        for doc in vector_result.get("results", []):
            meta = doc.get("metadata", {})
            sources.append({
                "title": meta.get("title", meta.get("source", "")),
                "database": meta.get("source_db", ""),
                "similarity": round(doc.get("similarity", 0), 4),
                "rerank_score": round(doc.get("rerank_score", 0), 3) if "rerank_score" in doc else None,
                "snippet": doc.get("content", "")[:200]
            })
        
        results["vector_rerank"] = {
            "strategy": "vector_rerank",
            "answer": "",
            "sources": sources,
            "timing_ms": elapsed_ms,
            "llm_calls": 0,
            "metadata": {
                "dbs_searched": active_dbs,
                "reranked": vector_result.get("reranked", False)
            }
        }
    except Exception as e:
        results["vector_rerank"] = {"error": str(e)}
    
    return {
        "query": request.query,
        "timestamp": datetime.now().isoformat(),
        "strategies": results,
        "summary": {
            name: {
                "timing_ms": r.get("timing_ms", -1),
                "sources_count": len(r.get("sources", [])),
                "llm_calls": r.get("llm_calls", -1),
                "has_answer": bool(r.get("answer", ""))
            }
            for name, r in results.items()
            if "error" not in r
        }
    }


# ============== Helper Functions ==============

async def _route_dbs_fast(vectordb_manager, llm_service, query: str) -> List[str]:
    """Fast DB routing using Skills metadata + LLM."""
    try:
        skills = vectordb_manager.get_skills_summary()
        if not skills:
            return []
        
        skills_text = []
        for s in skills:
            if s.get("doc_count", 0) == 0:
                continue
            skills_text.append(
                f"- {s['name']}: {s['description']} "
                f"(keywords: {', '.join(s.get('keywords', [])[:8])}, docs: {s.get('doc_count', 0)})"
            )
        
        if not skills_text:
            return []
        
        prompt = f"""Select 1-3 most relevant knowledge bases for this query.

Query: {query}

Knowledge Bases:
{chr(10).join(skills_text)}

Return ONLY a JSON array of names, e.g. ["db1", "db2"]. Select fewest needed."""
        
        result = await llm_service.generate(
            prompt=prompt,
            system_message="Return only a JSON array of database names.",
            temperature=0.1
        )
        
        import json
        response = result.content.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[-1].rsplit("```", 1)[0]
        
        db_names = json.loads(response)
        valid_dbs = {s["name"] for s in skills if s.get("doc_count", 0) > 0}
        return [db for db in db_names if db in valid_dbs]
        
    except Exception as e:
        logger.warning(f"[FastRAG] DB routing failed: {e}")
        return []


def _bm25_score_documents(query: str, documents: list) -> list:
    """
    Simple BM25-like scoring for a set of documents.
    
    Uses TF-IDF inspired scoring without requiring a full index.
    Good enough for fusion scoring in a small candidate set.
    """
    import math
    
    # Tokenize query
    query_terms = set(re.findall(r'\w+', query.lower()))
    
    if not query_terms or not documents:
        return [0.0] * len(documents)
    
    # Parameters
    k1 = 1.5
    b = 0.75
    
    # Calculate avg document length
    doc_lengths = []
    doc_term_freqs = []
    
    for doc in documents:
        content = doc.get("content", "").lower()
        terms = re.findall(r'\w+', content)
        doc_lengths.append(len(terms))
        
        # Term frequency for this doc
        freq = {}
        for t in terms:
            freq[t] = freq.get(t, 0) + 1
        doc_term_freqs.append(freq)
    
    avg_dl = sum(doc_lengths) / max(len(doc_lengths), 1)
    n_docs = len(documents)
    
    # Calculate document frequency for query terms
    df = {}
    for term in query_terms:
        df[term] = sum(1 for freqs in doc_term_freqs if term in freqs)
    
    # BM25 score for each document
    scores = []
    for i, doc in enumerate(documents):
        score = 0.0
        dl = doc_lengths[i]
        
        for term in query_terms:
            if term not in doc_term_freqs[i]:
                continue
            
            tf = doc_term_freqs[i][term]
            n_t = df.get(term, 0)
            
            # IDF
            idf = math.log((n_docs - n_t + 0.5) / (n_t + 0.5) + 1)
            
            # BM25 TF component
            tf_norm = (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / max(avg_dl, 1)))
            
            score += idf * tf_norm
        
        # Normalize to [0, 1] range approximately
        max_possible = len(query_terms) * 3  # rough upper bound
        normalized = min(score / max(max_possible, 1), 1.0)
        scores.append(normalized)
    
    return scores
