#!/usr/bin/env python
"""Test RAG database queries - Standalone version"""
import sys
sys.path.insert(0, '/mnt/d/codebase/Agentic-RAG-LLMs-API')

from tools.retriever import DocumentRetriever

def test_rag():
    """Test RAG retrieval"""
    # Test default collection
    print("Testing default collection...")
    retriever = DocumentRetriever(collection_name="default")
    stats = retriever.get_collection_stats()
    print(f"Stats: {stats}")
    
    # Test query
    results = retriever.retrieve("SolidWorks VBA", top_k=3)
    print(f"Results count: {len(results)}")
    
    for i, r in enumerate(results):
        print(f"\n--- Result {i+1} ---")
        print(f"Content: {r.get('content', '')[:200]}")
        print(f"Score: {r.get('similarity_score', 'N/A')}")
        print(f"Metadata: {r.get('metadata', {})}")

if __name__ == "__main__":
    test_rag()
