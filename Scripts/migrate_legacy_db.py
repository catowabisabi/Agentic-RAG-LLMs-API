#!/usr/bin/env python3
"""
Migrate Legacy Vector DB to ChromaDB

This script migrates the legacy index.json format to ChromaDB collections.
"""

import json
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import chromadb
from chromadb.config import Settings

def main():
    base_path = Path(__file__).parent.parent / "rag-database" / "vectordb"
    legacy_index = base_path / "index.json"
    
    if not legacy_index.exists():
        print("No legacy index.json found. Nothing to migrate.")
        return
    
    print(f"Loading legacy index from: {legacy_index}")
    
    with open(legacy_index, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    documents = data.get('documents', [])
    print(f"Found {len(documents)} documents to migrate")
    
    # Categorize documents by source folder
    categories = {}
    for doc in documents:
        source = doc.get('metadata', {}).get('source', '')
        # Extract main category from path
        parts = source.split('\\')
        if len(parts) >= 3:
            category = parts[2].lower()
            # Map to known databases
            if 'solidworks-api' in category or 'solidworks_api' in category:
                db_name = 'solidworks-api'
            elif 'solidworks-pdm' in category:
                db_name = 'solidworks-pdm-api'
            elif 'solidworks-document-manager' in category:
                db_name = 'solidworks-document-manager-api'
            elif 'solidworks-tools' in category:
                db_name = 'solidworks-tools'
            elif 'edrawings' in category:
                db_name = 'edrawings-api'
            elif 'angular' in category:
                db_name = 'angular'
            elif 'visual-basic' in category:
                db_name = 'visual-basic'
            elif 'hosting' in category:
                db_name = 'hosting'
            elif 'labs' in category:
                db_name = 'labs'
            else:
                db_name = 'codestack-general'
        else:
            db_name = 'codestack-general'
        
        if db_name not in categories:
            categories[db_name] = []
        categories[db_name].append(doc)
    
    print(f"\nCategories found:")
    for cat, docs in categories.items():
        print(f"  {cat}: {len(docs)} documents")
    
    # Create ChromaDB collections for each category
    for db_name, docs in categories.items():
        db_path = base_path / db_name
        db_path.mkdir(parents=True, exist_ok=True)
        
        print(f"\nMigrating {db_name} ({len(docs)} docs)...")
        
        try:
            client = chromadb.PersistentClient(
                path=str(db_path),
                settings=Settings(anonymized_telemetry=False)
            )
            
            # Get or create collection
            try:
                collection = client.get_collection("documents")
                print(f"  Using existing collection")
            except:
                collection = client.create_collection(
                    name="documents",
                    metadata={"description": f"{db_name} documentation"}
                )
                print(f"  Created new collection")
            
            # Add documents in batches
            batch_size = 100
            for i in range(0, len(docs), batch_size):
                batch = docs[i:i+batch_size]
                
                ids = [doc['id'] for doc in batch]
                contents = [doc['content'] for doc in batch]
                embeddings = [doc['embedding'] for doc in batch]
                metadatas = [doc.get('metadata', {}) for doc in batch]
                
                collection.add(
                    ids=ids,
                    documents=contents,
                    embeddings=embeddings,
                    metadatas=metadatas
                )
                print(f"  Added batch {i//batch_size + 1}/{(len(docs)-1)//batch_size + 1}")
            
            print(f"  ✓ Migrated {len(docs)} documents to {db_name}")
            
        except Exception as e:
            print(f"  ✗ Error migrating {db_name}: {e}")
    
    # Update metadata
    metadata_file = base_path / "db_metadata.json"
    if metadata_file.exists():
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
    else:
        metadata = {"databases": {}, "active": None}
    
    for db_name in categories.keys():
        if db_name not in metadata["databases"]:
            metadata["databases"][db_name] = {
                "name": db_name,
                "path": f"rag-database/vectordb/{db_name}",
                "description": f"{db_name} documentation from CodeStack",
                "category": "technical",
                "created_at": "2026-01-25T00:00:00",
                "document_count": len(categories[db_name]),
                "collections": ["documents"]
            }
        else:
            metadata["databases"][db_name]["document_count"] = len(categories[db_name])
    
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✓ Updated metadata in {metadata_file}")
    
    # Backup and optionally remove legacy file
    backup_path = base_path / "index.json.backup"
    if not backup_path.exists():
        import shutil
        shutil.copy(legacy_index, backup_path)
        print(f"✓ Backed up legacy index to {backup_path}")
    
    print("\n=== Migration Complete ===")
    print("You can delete index.json after verifying the migration worked correctly.")

if __name__ == "__main__":
    main()
