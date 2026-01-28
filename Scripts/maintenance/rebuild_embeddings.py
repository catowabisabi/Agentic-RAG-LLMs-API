#!/usr/bin/env python
"""
Rebuild All Embeddings Script
重建所有向量資料庫的 embeddings

執行步驟：
1. 列出所有現有資料庫
2. 備份舊資料庫
3. 刪除舊的 ChromaDB collections
4. 重新創建使用 text-embedding-3-small (1536維)
5. 記錄重建過程

使用方法：
python rebuild_embeddings.py
"""

import os
import json
import shutil
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List

from services.vectordb_manager import vectordb_manager
from config.config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 記錄文件
REBUILD_LOG_FILE = "embedding_rebuild_log.json"

config = Config()


class EmbeddingRebuilder:
    """重建 embeddings 的工具類"""
    
    def __init__(self):
        self.log = {
            "rebuild_date": datetime.now().isoformat(),
            "embedding_model": config.EMBEDDING_MODEL,
            "embedding_dimension": 1536,
            "databases": {}
        }
    
    def backup_database(self, db_name: str, db_path: str):
        """備份資料庫"""
        backup_path = f"{db_path}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        try:
            if os.path.exists(db_path):
                logger.info(f"Backing up {db_name} to {backup_path}")
                shutil.copytree(db_path, backup_path)
                self.log["databases"][db_name] = {
                    "backup_path": backup_path,
                    "status": "backed_up"
                }
                return True
        except Exception as e:
            logger.error(f"Failed to backup {db_name}: {e}")
            self.log["databases"][db_name] = {
                "error": str(e),
                "status": "backup_failed"
            }
            return False
    
    def rebuild_database(self, db_name: str):
        """重建單個資料庫"""
        logger.info(f"\n{'='*60}")
        logger.info(f"Rebuilding database: {db_name}")
        logger.info(f"{'='*60}")
        
        try:
            # 獲取資料庫信息
            db_info = vectordb_manager.get_database_info(db_name)
            if not db_info:
                logger.warning(f"Database {db_name} not found in metadata")
                return False
            
            db_path = db_info["path"]
            doc_count = db_info.get("document_count", 0)
            
            logger.info(f"Database path: {db_path}")
            logger.info(f"Original document count: {doc_count}")
            
            if doc_count == 0:
                logger.info(f"Skipping {db_name} - no documents")
                self.log["databases"][db_name]["status"] = "skipped_empty"
                return True
            
            # 備份
            if not self.backup_database(db_name, db_path):
                return False
            
            # 刪除舊資料庫目錄
            logger.info(f"Removing old database directory...")
            if os.path.exists(db_path):
                shutil.rmtree(db_path)
            
            # 從 metadata 移除
            if db_name in vectordb_manager._metadata["databases"]:
                old_info = vectordb_manager._metadata["databases"].pop(db_name)
                vectordb_manager._save_metadata()
                logger.info(f"Removed {db_name} from metadata")
            
            # 重新創建資料庫
            logger.info(f"Creating new database with text-embedding-3-small...")
            new_db = vectordb_manager.create_database(
                db_name=db_name,
                description=db_info.get("description", ""),
                category=db_info.get("category", "general")
            )
            
            logger.info(f"✓ Database {db_name} recreated successfully")
            logger.info(f"  New embedding model: {config.EMBEDDING_MODEL}")
            logger.info(f"  New dimension: 1536")
            
            self.log["databases"][db_name].update({
                "status": "rebuilt",
                "original_doc_count": doc_count,
                "rebuild_time": datetime.now().isoformat()
            })
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to rebuild {db_name}: {e}")
            self.log["databases"][db_name]["status"] = "failed"
            self.log["databases"][db_name]["error"] = str(e)
            return False
    
    def rebuild_all(self):
        """重建所有有問題的資料庫"""
        logger.info("\n" + "="*60)
        logger.info("EMBEDDING REBUILD PROCESS STARTED")
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
        
        # 詢問確認
        print("\n⚠️  WARNING: This will delete and recreate all database collections!")
        print("📦 Backups will be created before deletion.")
        print(f"🔄 New embedding model: {config.EMBEDDING_MODEL} (1536 dimensions)")
        
        confirm = input("\nProceed with rebuild? (yes/no): ").strip().lower()
        if confirm != "yes":
            logger.info("Rebuild cancelled by user")
            return
        
        # 重建每個資料庫
        success_count = 0
        failed_count = 0
        
        for db in problem_dbs:
            db_name = db["name"]
            if self.rebuild_database(db_name):
                success_count += 1
            else:
                failed_count += 1
        
        # 保存日誌
        self.save_log()
        
        logger.info("\n" + "="*60)
        logger.info("REBUILD SUMMARY")
        logger.info("="*60)
        logger.info(f"Total databases: {len(problem_dbs)}")
        logger.info(f"✓ Successfully rebuilt: {success_count}")
        logger.info(f"✗ Failed: {failed_count}")
        logger.info(f"📄 Log saved to: {REBUILD_LOG_FILE}")
        logger.info("="*60)
        
        logger.info("\n⚠️  IMPORTANT NEXT STEPS:")
        logger.info("1. Re-import documents into the rebuilt databases")
        logger.info("2. Use: python Scripts/load_docs_to_rag.py")
        logger.info("3. Verify embeddings work with test queries")
    
    def save_log(self):
        """保存重建日誌"""
        with open(REBUILD_LOG_FILE, 'w') as f:
            json.dump(self.log, f, indent=2)
        logger.info(f"Rebuild log saved to {REBUILD_LOG_FILE}")


def main():
    """主函數"""
    rebuilder = EmbeddingRebuilder()
    rebuilder.rebuild_all()


if __name__ == "__main__":
    main()
