#!/usr/bin/env python
"""Test RAG database queries - Debug version"""
import sys
import os
sys.path.insert(0, '/mnt/d/codebase/Agentic-RAG-LLMs-API')
os.chdir('/mnt/d/codebase/Agentic-RAG-LLMs-API')

from tools.retriever import DocumentRetriever

def test_rag():
    """Test RAG retrieval after fix"""
    print("=" * 50)
    print("Testing default collection with fix...")
    retriever = DocumentRetriever(collection_name="default")
    
    # Check initial count
    try:
        count_before = retriever.vectorstore._collection.count()
        print(f"Document count before: {count_before}")
    except Exception as e:
        print(f"Error getting count: {e}")
    
    # Try to add a document
    print("\nAdding test document...")
    test_content = """
    SolidWorks VBA Automation Guide
    
    This document covers how to use VBA to automate SolidWorks.
    Key topics include:
    - Creating sketches programmatically
    - Drawing lines using CreateLine method
    - Working with IModelDocExtension interface
    - Using SelectByID2 for element selection
    """
    
    doc_id = retriever.add_document(
        content=test_content,
        metadata={"title": "VBA Guide", "source": "test"}
    )
    print(f"Added document ID: {doc_id}")
    
    # Check count after
    try:
        count_after = retriever.vectorstore._collection.count()
        print(f"Document count after: {count_after}")
    except Exception as e:
        print(f"Error getting count: {e}")
    
    # Test query
    print("\n" + "=" * 50)
    print("Testing query 'SolidWorks VBA draw line'...")
    results = retriever.retrieve("SolidWorks VBA draw line", top_k=3)
    print(f"Results count: {len(results)}")
    
    for i, r in enumerate(results):
        print(f"\n--- Result {i+1} ---")
        print(f"Content: {r.get('content', '')[:150]}")
        print(f"Score: {r.get('similarity_score', 'N/A')}")

if __name__ == "__main__":
    test_rag()
