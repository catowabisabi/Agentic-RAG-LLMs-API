import chromadb
import os

db_path = './rag-database/vectordb/solidworks'
print(f"Checking database at: {db_path}")
print(f"Database exists: {os.path.exists(db_path)}")

try:
    client = chromadb.PersistentClient(path=db_path)
    collections = client.list_collections()
    print(f"\nCollections found: {len(collections)}")
    
    for col in collections:
        print(f"\nCollection: {col.name}")
        print(f"  Documents: {col.count()}")
        
        if col.count() > 0:
            # Sample a few documents
            results = col.get(limit=3)
            print(f"  Sample documents:")
            for i, doc in enumerate(results['documents'][:3]):
                print(f"    {i+1}. {doc[:100]}...")
        else:
            print(f"  ⚠️  Collection is EMPTY!")
            
except Exception as e:
    print(f"Error: {e}")
