# -*- coding: utf-8 -*-
"""
=============================================================================
文檔加載腳本 (Document Loader Script)
=============================================================================

功能說明：
-----------
將 app_docs/ 目錄中的文檔加載到向量資料庫。

支持的文件類型：
-----------
- Markdown (.md)
- Text (.txt)
- Python (.py) - 代碼文檔

使用方法：
-----------
# Windows
python Scripts/load_docs_to_vectordb.py

# WSL
python3 Scripts/load_docs_to_vectordb.py


=============================================================================
"""

import os
import sys
import asyncio
import logging
from pathlib import Path
from datetime import datetime

# 添加項目根目錄到路徑
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from services.vectordb_manager import vectordb_manager
from config.config import Config

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# 要加載的文檔目錄和對應的資料庫名稱
DOCUMENT_SOURCES = [
    {
        "path": "app_docs",
        "database": "agentic-rag-docs",  # 使用新的資料庫名稱
        "description": "Agentic RAG 系統文檔和指南",
        "extensions": [".md", ".txt"]
    }
]


async def load_documents():
    """加載所有文檔到向量資料庫"""
    
    logger.info("=" * 60)
    logger.info("開始加載文檔到向量資料庫")
    logger.info("=" * 60)
    
    total_loaded = 0
    total_errors = 0
    
    for source in DOCUMENT_SOURCES:
        source_path = project_root / source["path"]
        db_name = source["database"]
        extensions = source["extensions"]
        
        logger.info(f"\n處理目錄: {source_path}")
        logger.info(f"目標資料庫: {db_name}")
        
        # 確保資料庫存在
        existing_dbs = vectordb_manager.list_databases()
        db_exists = any(db["name"] == db_name for db in existing_dbs)
        
        if not db_exists:
            logger.info(f"創建資料庫: {db_name}")
            try:
                vectordb_manager.create_database(db_name, source["description"])
            except ValueError as e:
                logger.info(f"資料庫已存在: {db_name}")
        else:
            logger.info(f"使用現有資料庫: {db_name}")
        
        # 遍歷文件
        if source_path.exists():
            for file_path in source_path.rglob("*"):
                if file_path.is_file() and file_path.suffix.lower() in extensions:
                    try:
                        # 讀取文件內容
                        with open(file_path, "r", encoding="utf-8") as f:
                            content = f.read()
                        
                        if len(content.strip()) < 50:
                            logger.warning(f"跳過（內容太短）: {file_path.name}")
                            continue
                        
                        # 準備元數據
                        metadata = {
                            "title": file_path.stem,
                            "source": str(file_path.relative_to(project_root)),
                            "file_type": file_path.suffix,
                            "loaded_at": datetime.now().isoformat()
                        }
                        
                        # 添加到資料庫
                        result = await vectordb_manager.insert_full_text(
                            db_name=db_name,
                            content=content,
                            title=file_path.stem,
                            source=str(file_path.relative_to(project_root)),
                            category="documentation",
                            tags=[file_path.suffix.replace(".", "")]
                        )
                        
                        logger.info(f"✓ 已加載: {file_path.name}")
                        total_loaded += 1
                        
                    except Exception as e:
                        import traceback
                        logger.error(f"✗ 加載失敗: {file_path.name} - {e}")
                        logger.error(traceback.format_exc())
                        total_errors += 1
        else:
            logger.warning(f"目錄不存在: {source_path}")
    
    # 總結
    logger.info("\n" + "=" * 60)
    logger.info("加載完成！")
    logger.info(f"成功: {total_loaded} 個文件")
    logger.info(f"失敗: {total_errors} 個文件")
    logger.info("=" * 60)
    
    # 列出所有資料庫狀態
    logger.info("\n資料庫狀態:")
    for db in vectordb_manager.list_databases():
        logger.info(f"  - {db['name']}: {db.get('document_count', 0)} 個文檔")
    
    return {
        "loaded": total_loaded,
        "errors": total_errors
    }


if __name__ == "__main__":
    asyncio.run(load_documents())
