"""
Complete ChromaDB Migration and Consolidation Script
Extracts data from old format databases and creates a unified new database

Author: Migration Tool
Date: 2026-01-29
"""
import sqlite3
import os
import json
import struct
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
import shutil

# Try to import chromadb, but we'll also work without it for extraction
try:
    import chromadb
    from langchain_openai import OpenAIEmbeddings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    print("Warning: chromadb not available, extraction only mode")


def read_hnsw_vectors(segment_path: str) -> Optional[np.ndarray]:
    """
    Read vectors from HNSW segment files (data_level0.bin)
    ChromaDB uses HNSW for vector storage
    """
    data_file = os.path.join(segment_path, 'data_level0.bin')
    header_file = os.path.join(segment_path, 'header.bin')
    
    if not os.path.exists(data_file) or not os.path.exists(header_file):
        return None
    
    try:
        # Read header to get dimensions
        with open(header_file, 'rb') as f:
            header_data = f.read()
        
        # HNSW header format varies, but typically contains:
        # - max_elements (size_t)
        # - cur_element_count (size_t) 
        # - size_data_per_element (size_t)
        # - dimension (size_t)
        # We need to figure out the exact format
        
        # Read data file
        with open(data_file, 'rb') as f:
            data = f.read()
        
        # For OpenAI embeddings, dimension is 1536
        dimension = 1536
        element_size = dimension * 4  # float32
        
        if len(data) < element_size:
            return None
        
        # Calculate number of vectors
        # Data format: each element has [links_data][vector_data]
        # Links size varies, but vector is always dimension * 4 bytes
        
        # Try to detect the format by looking at data patterns
        # For now, we'll use a heuristic approach
        
        return data
        
    except Exception as e:
        print(f"Error reading HNSW vectors: {e}")
        return None


def extract_from_sqlite(db_path: str, collection_name: str = None) -> Dict[str, Any]:
    """
    Extract all data from SQLite database
    """
    sqlite_path = os.path.join(db_path, 'chroma.sqlite3')
    
    if not os.path.exists(sqlite_path):
        return {"error": "Database not found"}
    
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    
    result = {
        "path": db_path,
        "collections": {},
        "documents": [],
        "metadata": {}
    }
    
    # Get all collections
    cursor.execute("SELECT id, name FROM collections")
    collections = cursor.fetchall()
    
    for col_id, col_name in collections:
        result["collections"][col_id] = col_name
    
    # Get all embeddings
    # Structure: id, segment_id, embedding_id (doc_id), seq_id, created_at
    cursor.execute("SELECT id, segment_id, embedding_id FROM embeddings")
    embeddings = cursor.fetchall()
    
    # Build embedding mapping
    embedding_map = {}
    for emb in embeddings:
        embedding_map[emb[0]] = {  # Use internal id as key
            "internal_id": emb[0],
            "segment_id": emb[1],
            "doc_id": emb[2]  # This is the embedding_id (document identifier)
        }
    
    result["embeddings"] = embedding_map
    result["embeddings_count"] = len(embeddings)
    
    # Get metadata for each embedding (including document content)
    # id in embedding_metadata corresponds to id in embeddings table
    cursor.execute("""
        SELECT id, key, string_value, int_value, float_value, bool_value
        FROM embedding_metadata
    """)
    metadata_rows = cursor.fetchall()
    
    documents = {}  # internal_id -> document content
    metadata_dict = {}  # internal_id -> metadata dict
    
    for emb_id, key, str_val, int_val, float_val, bool_val in metadata_rows:
        if emb_id not in metadata_dict:
            metadata_dict[emb_id] = {}
        
        # Determine value
        if str_val is not None:
            value = str_val
        elif int_val is not None:
            value = int_val
        elif float_val is not None:
            value = float_val
        elif bool_val is not None:
            value = bool(bool_val)
        else:
            value = None
        
        # Special handling for document content
        if key == "chroma:document":
            documents[emb_id] = value
        else:
            metadata_dict[emb_id][key] = value
    
    result["documents"] = documents
    result["metadata"] = metadata_dict
    result["documents_count"] = len(documents)
    
    conn.close()
    return result


def migrate_to_new_format(
    source_databases: List[Dict[str, str]],
    target_db_name: str,
    target_path: str,
    description: str = ""
) -> Dict[str, Any]:
    """
    Migrate multiple old databases to a single new ChromaDB database
    
    Args:
        source_databases: List of {"path": path, "name": name} dicts
        target_db_name: Name of the new consolidated database
        target_path: Path for the new database
        description: Description for the new database
    """
    
    print(f"\n{'='*70}")
    print(f"Starting Migration to: {target_db_name}")
    print(f"{'='*70}")
    
    # Collect all documents and metadata
    all_documents = []
    all_ids = []
    all_metadatas = []
    source_stats = {}
    
    for source in source_databases:
        db_path = source["path"]
        db_name = source["name"]
        
        print(f"\nExtracting from: {db_name}")
        
        extracted = extract_from_sqlite(db_path)
        
        if "error" in extracted:
            print(f"  Error: {extracted['error']}")
            continue
        
        docs_count = 0
        
        # Iterate through embeddings and get their documents
        for internal_id, emb_info in extracted["embeddings"].items():
            # Get document content from documents dict
            doc_content = extracted["documents"].get(internal_id)
            
            if doc_content:
                # Get metadata
                meta = extracted["metadata"].get(internal_id, {})
                meta["source_database"] = db_name
                meta["original_doc_id"] = emb_info["doc_id"]
                meta["migrated_at"] = datetime.now().isoformat()
                
                # Create unique ID
                unique_id = f"{db_name}_{internal_id}"
                
                all_documents.append(doc_content)
                all_ids.append(unique_id)
                all_metadatas.append(meta)
                docs_count += 1
        
        source_stats[db_name] = {
            "embeddings_found": extracted["embeddings_count"],
            "documents_extracted": docs_count
        }
        
        print(f"  Embeddings: {extracted['embeddings_count']}")
        print(f"  Documents extracted: {docs_count}")
    
    print(f"\n{'='*70}")
    print(f"Total documents to migrate: {len(all_documents)}")
    print(f"{'='*70}")
    
    if not all_documents:
        return {"error": "No documents extracted", "stats": source_stats}
    
    # Create new database
    if not CHROMADB_AVAILABLE:
        return {
            "error": "ChromaDB not available for writing",
            "documents_ready": len(all_documents),
            "stats": source_stats
        }
    
    # Prepare target path
    if os.path.exists(target_path):
        backup_path = target_path + f"_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"Backing up existing database to: {backup_path}")
        shutil.move(target_path, backup_path)
    
    os.makedirs(target_path, exist_ok=True)
    
    # Create new ChromaDB client
    print(f"\nCreating new database at: {target_path}")
    client = chromadb.PersistentClient(path=target_path)
    
    # Create collection
    try:
        client.delete_collection(target_db_name)
    except:
        pass
    
    collection = client.create_collection(
        name=target_db_name,
        metadata={"description": description}
    )
    
    # Add documents in batches with embeddings
    print("\nGenerating embeddings and adding documents...")
    
    # Initialize embeddings
    from config.config import Config
    config = Config()
    embeddings_model = OpenAIEmbeddings(
        model=config.EMBEDDING_MODEL,
        api_key=config.OPENAI_API_KEY
    )
    
    batch_size = 50
    total_added = 0
    
    for i in range(0, len(all_documents), batch_size):
        batch_docs = all_documents[i:i+batch_size]
        batch_ids = all_ids[i:i+batch_size]
        batch_meta = all_metadatas[i:i+batch_size]
        
        try:
            # Generate embeddings
            embeddings = embeddings_model.embed_documents(batch_docs)
            
            # Add to collection
            collection.add(
                ids=batch_ids,
                embeddings=embeddings,
                documents=batch_docs,
                metadatas=batch_meta
            )
            
            total_added += len(batch_docs)
            print(f"  Added {total_added}/{len(all_documents)} documents...")
            
        except Exception as e:
            print(f"  Error adding batch {i//batch_size}: {e}")
            continue
    
    print(f"\n{'='*70}")
    print(f"Migration Complete!")
    print(f"{'='*70}")
    print(f"Total documents migrated: {total_added}")
    print(f"Target database: {target_db_name}")
    print(f"Target path: {target_path}")
    
    return {
        "success": True,
        "total_documents": total_added,
        "target_database": target_db_name,
        "target_path": target_path,
        "source_stats": source_stats
    }


if __name__ == "__main__":
    base_path = "./rag-database/vectordb"
    
    # Define migration groups
    
    # Group 1: SolidWorks related databases -> solidworks-consolidated
    solidworks_sources = [
        {"path": os.path.join(base_path, "solidworks-document-manager-api"), "name": "solidworks-document-manager-api"},
        {"path": os.path.join(base_path, "solidworks-pdm-api"), "name": "solidworks-pdm-api"},
        {"path": os.path.join(base_path, "solidworks-tools"), "name": "solidworks-tools"},
        {"path": os.path.join(base_path, "edrawings-api"), "name": "edrawings-api"},
        {"path": os.path.join(base_path, "codestack-general"), "name": "codestack-general"},
    ]
    
    # Group 2: Programming related -> programming-docs
    programming_sources = [
        {"path": os.path.join(base_path, "visual-basic"), "name": "visual-basic"},
        {"path": os.path.join(base_path, "angular"), "name": "angular"},
    ]
    
    # Group 3: Labs/Examples -> agentic-examples  
    example_sources = [
        {"path": os.path.join(base_path, "labs"), "name": "labs"},
    ]
    
    # Group 4: Hosting
    hosting_sources = [
        {"path": os.path.join(base_path, "hosting"), "name": "hosting"},
    ]
    
    # Perform migrations
    results = []
    
    # Migration 1: SolidWorks
    result = migrate_to_new_format(
        source_databases=solidworks_sources,
        target_db_name="solidworks",
        target_path=os.path.join(base_path, "solidworks-new"),
        description="SolidWorks API 完整文檔 (Document Manager API, PDM API, Tools, eDrawings, CodeStack)"
    )
    results.append(("solidworks", result))
    
    # Migration 2: Programming
    result = migrate_to_new_format(
        source_databases=programming_sources,
        target_db_name="programming",
        target_path=os.path.join(base_path, "programming"),
        description="編程文檔 (Visual Basic, Angular)"
    )
    results.append(("programming", result))
    
    # Migration 3: Agentic Examples
    result = migrate_to_new_format(
        source_databases=example_sources,
        target_db_name="agentic-examples",
        target_path=os.path.join(base_path, "agentic-examples"),
        description="Agentic AI 範例和教程"
    )
    results.append(("agentic-examples", result))
    
    # Migration 4: Hosting
    result = migrate_to_new_format(
        source_databases=hosting_sources,
        target_db_name="hosting-docs",
        target_path=os.path.join(base_path, "hosting-docs"),
        description="主機和部署文檔"
    )
    results.append(("hosting-docs", result))
    
    # Summary
    print("\n" + "=" * 70)
    print("MIGRATION SUMMARY")
    print("=" * 70)
    
    for name, result in results:
        if result.get("success"):
            print(f"\n{name}:")
            print(f"  Status: SUCCESS")
            print(f"  Documents: {result['total_documents']}")
            print(f"  Path: {result['target_path']}")
        else:
            print(f"\n{name}:")
            print(f"  Status: FAILED")
            print(f"  Error: {result.get('error', 'Unknown')}")
