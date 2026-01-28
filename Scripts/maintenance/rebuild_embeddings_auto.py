#!/usr/bin/env python
"""
重建 embeddings - 非互動版本
自動確認並執行重建
"""

import sys
sys.path.insert(0, '/mnt/d/codebase/Agentic-RAG-LLMs-API')

from rebuild_embeddings import EmbeddingRebuilder

if __name__ == "__main__":
    rebuilder = EmbeddingRebuilder()
    
    # 直接執行重建，跳過確認
    import logging
    from services.vectordb_manager import vectordb_manager
    from config.config import Config
    from datetime import datetime
    
    logger = logging.getLogger(__name__)
    config = Config()
    
    logger.info("\n" + "="*60)
    logger.info("EMBEDDING REBUILD PROCESS STARTED (AUTO)")
    logger.info("="*60)
    
    # 列出所有資料庫
    all_dbs = vectordb_manager.list_databases()
    logger.info(f"\nTotal databases: {len(all_dbs)}")
    
    # 篩選需要重建的資料庫（有文檔的）
    problem_dbs = [
        db for db in all_dbs 
        if db.get("document_count", 0) > 0
    ]
    
    logger.info(f"Databases to rebuild: {len(problem_dbs)}")
    for db in problem_dbs:
        logger.info(f"  - {db['name']}: {db['document_count']} docs")
    
    logger.info("\n✓ AUTO-CONFIRMED: Proceeding with rebuild...")
    logger.info(f"🔄 New embedding model: {config.EMBEDDING_MODEL} (1536 dimensions)\n")
    
    # 重建每個資料庫
    success_count = 0
    failed_count = 0
    
    for db in problem_dbs:
        db_name = db["name"]
        if rebuilder.rebuild_database(db_name):
            success_count += 1
        else:
            failed_count += 1
    
    # 保存日誌
    rebuilder.save_log()
    
    logger.info("\n" + "="*60)
    logger.info("REBUILD SUMMARY")
    logger.info("="*60)
    logger.info(f"Total databases: {len(problem_dbs)}")
    logger.info(f"✓ Successfully rebuilt: {success_count}")
    logger.info(f"✗ Failed: {failed_count}")
    logger.info(f"📄 Log saved to: embedding_rebuild_log.json")
    logger.info("="*60)
    
    logger.info("\n⚠️  IMPORTANT NEXT STEPS:")
    logger.info("1. Re-import documents into the rebuilt databases")
    logger.info("2. Use: python Scripts/load_docs_to_rag.py")
    logger.info("3. Verify embeddings work with test queries")
