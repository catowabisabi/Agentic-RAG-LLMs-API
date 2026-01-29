"""
Migrate old ChromaDB databases to new format
"""
import sqlite3
import chromadb
from chromadb.config import Settings
import os
from tqdm import tqdm

def migrate_database(old_db_path, collection_name, new_db_path=None):
    """
    Migrate an old ChromaDB database to new format
    """
    if new_db_path is None:
        new_db_path = old_db_path
    
    print(f"\nMigrating {collection_name}...")
    
    # Read from old database using SQLite
    old_sqlite_path = os.path.join(old_db_path, 'chroma.sqlite3')
    if not os.path.exists(old_sqlite_path):
        print(f"  Error: {old_sqlite_path} not found")
        return False
    
    conn = sqlite3.connect(old_sqlite_path)
    cursor = conn.cursor()
    
    # Get collection ID
    cursor.execute("SELECT id FROM collections WHERE name = ?", (collection_name,))
    result = cursor.fetchone()
    if not result:
        print(f"  Error: Collection '{collection_name}' not found in database")
        conn.close()
        return False
    
    collection_id = result[0]
    
    # Get all embeddings and documents
    cursor.execute("""
        SELECT e.id, e.embedding, e.document
        FROM embeddings e
        JOIN collections c ON e.segment_id IN (
            SELECT id FROM segments WHERE collection = c.id
        )
        WHERE c.id = ?
    """, (collection_id,))
    
    rows = cursor.fetchall()
    print(f"  Found {len(rows)} embeddings")
    
    if len(rows) == 0:
        conn.close()
        return True
    
    # Get metadata
    cursor.execute("""
        SELECT embedding_id, key, string_value, int_value, float_value
        FROM embedding_metadata
    """)
    metadata_rows = cursor.fetchall()
    
    # Build metadata dict
    metadata_dict = {}
    for emb_id, key, str_val, int_val, float_val in metadata_rows:
        if emb_id not in metadata_dict:
            metadata_dict[emb_id] = {}
        
        value = str_val if str_val is not None else (int_val if int_val is not None else float_val)
        metadata_dict[emb_id][key] = value
    
    conn.close()
    
    # Create new database
    if old_db_path != new_db_path:
        # Create in different location
        temp_path = new_db_path + '_temp'
        if os.path.exists(temp_path):
            import shutil
            shutil.rmtree(temp_path)
    else:
        # Backup old database
        backup_path = old_db_path + '_backup_migration'
        if os.path.exists(backup_path):
            import shutil
            shutil.rmtree(backup_path)
        import shutil
        shutil.copytree(old_db_path, backup_path)
        
        # Remove old database
        for file in os.listdir(old_db_path):
            file_path = os.path.join(old_db_path, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                import shutil
                shutil.rmtree(file_path)
    
    # Create new ChromaDB client and collection
    print(f"  Creating new collection...")
    client = chromadb.PersistentClient(path=new_db_path)
    
    # Delete collection if exists
    try:
        client.delete_collection(collection_name)
    except:
        pass
    
    collection = client.create_collection(name=collection_name)
    
    # Add documents in batches
    batch_size = 100
    for i in tqdm(range(0, len(rows), batch_size), desc=f"  Adding documents"):
        batch = rows[i:i+batch_size]
        
        ids = [row[0] for row in batch]
        embeddings = [eval(row[1]) if isinstance(row[1], str) else row[1] for row in batch]
        documents = [row[2] for row in batch if row[2]]
        metadatas = [metadata_dict.get(row[0], {}) for row in batch]
        
        try:
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents if documents else None,
                metadatas=metadatas if any(metadatas) else None
            )
        except Exception as e:
            print(f"    Error adding batch: {e}")
            continue
    
    print(f"  ✓ Migration complete: {len(rows)} documents")
    return True


if __name__ == "__main__":
    # Databases to migrate
    databases_to_migrate = [
        ("angular", "angular"),
        ("solidworks-document-manager-api", "solidworks-document-manager-api"),
        ("solidworks-pdm-api", "solidworks-pdm-api"),
        ("solidworks-tools", "solidworks-tools"),
        ("visual-basic", "visual-basic"),
        ("edrawings-api", "edrawings-api"),
        ("codestack-general", "codestack-general"),
        ("hosting", "hosting"),
        ("labs", "labs"),
    ]
    
    base_path = "./rag-database/vectordb"
    
    print("=" * 60)
    print("ChromaDB Database Migration")
    print("=" * 60)
    
    for db_name, collection_name in databases_to_migrate:
        db_path = os.path.join(base_path, db_name)
        if os.path.exists(db_path):
            try:
                migrate_database(db_path, collection_name)
            except Exception as e:
                print(f"  Error migrating {db_name}: {e}")
                import traceback
                traceback.print_exc()
        else:
            print(f"\nSkipping {db_name}: path not found")
    
    print("\n" + "=" * 60)
    print("Migration Complete!")
    print("=" * 60)
