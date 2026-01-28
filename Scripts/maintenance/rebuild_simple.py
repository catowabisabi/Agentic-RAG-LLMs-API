#!/usr/bin/env python
"""
重建 embeddings - 簡化版（無備份）
直接刪除舊資料庫並重建空的資料庫結構
之後需要重新導入文檔
"""

import sys
import os
import shutil
import json
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, '/mnt/d/codebase/Agentic-RAG-LLMs-API')

from services.vectordb_manager import vectordb_manager
from config.config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

config = Config()

def rebuild_databases():
    """重建所有有問題的資料庫"""
    logger.info("\n" + "="*70)
    logger.info("EMBEDDING REBUILD - SIMPLIFIED (NO BACKUP)")
    logger.info("="*70)
    logger.info(f"New embedding model: {config.EMBEDDING_MODEL} (1536 dimensions)")
    
    # 列出所有資料庫
    all_dbs = vectordb_manager.list_databases()
    problem_dbs = [db for db in all_dbs if db.get("document_count", 0) > 0]
    
    logger.info(f"\nDatabases to rebuild: {len(problem_dbs)}")
    for db in problem_dbs:
        logger.info(f"  - {db['name']}: {db['document_count']} docs")
    
    rebuild_log = {
        "rebuild_date": datetime.now().isoformat(),
        "embedding_model": config.EMBEDDING_MODEL,
        "databases_rebuilt": []
    }
    
    success_count = 0
    failed_count = 0
    
    for db in problem_dbs:
        db_name = db["name"]
        db_path = db["path"]
        doc_count = db.get("document_count", 0)
        
        logger.info(f"\n{'='*70}")
        logger.info(f"Processing: {db_name} ({doc_count} docs)")
        logger.info(f"{'='*70}")
        
        try:
            # Step 1: Delete old database directory
            if os.path.exists(db_path):
                logger.info(f"  1. Deleting old database directory: {db_path}")
                shutil.rmtree(db_path, ignore_errors=True)
            
            # Step 2: Remove from metadata
            if db_name in vectordb_manager._metadata["databases"]:
                logger.info(f"  2. Removing from metadata...")
                vectordb_manager._metadata["databases"].pop(db_name)
                vectordb_manager._save_metadata()
            
            # Step 3: Create new empty database
            logger.info(f"  3. Creating new database with {config.EMBEDDING_MODEL}...")
            new_db = vectordb_manager.create_database(
                db_name=db_name,
                description=db.get("description", ""),
                category=db.get("category", "general")
            )
            
            logger.info(f"  ✓ {db_name} rebuilt successfully")
            rebuild_log["databases_rebuilt"].append({
                "name": db_name,
                "original_docs": doc_count,
                "status": "success"
            })
            success_count += 1
            
        except Exception as e:
            logger.error(f"  ✗ Failed to rebuild {db_name}: {e}")
            rebuild_log["databases_rebuilt"].append({
                "name": db_name,
                "original_docs": doc_count,
                "status": "failed",
                "error": str(e)
            })
            failed_count += 1
    
    # Save log
    log_file = "embedding_rebuild_simple.json"
    with open(log_file, 'w') as f:
        json.dump(rebuild_log, f, indent=2)
    
    logger.info("\n" + "="*70)
    logger.info("REBUILD SUMMARY")
    logger.info("="*70)
    logger.info(f"Total databases: {len(problem_dbs)}")
    logger.info(f"✓ Successfully rebuilt: {success_count}")
    logger.info(f"✗ Failed: {failed_count}")
    logger.info(f"📄 Log: {log_file}")
    logger.info("="*70)
    
    logger.info("\n⚠️  CRITICAL NEXT STEPS:")
    logger.info("="*70)
    logger.info("All databases are now EMPTY. You MUST re-import documents:")
    logger.info("")
    logger.info("1. Check where original documents are stored")
    logger.info("2. Run: python Scripts/load_docs_to_rag.py")
    logger.info("3. Or manually add documents via API:")
    logger.info("   curl -X POST http://localhost:1130/rag/document \\")
    logger.info("     -H 'Content-Type: application/json' \\")
    logger.info("     -d '{\"database\":\"db_name\",\"content\":\"...\",\"metadata\":{...}}'")
    logger.info("")
    logger.info("Without re-importing, RAG queries will return ZERO results!")
    logger.info("="*70)

if __name__ == "__main__":
    rebuild_databases()
