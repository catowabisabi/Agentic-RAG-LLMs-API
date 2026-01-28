"""
VectorDB 清理與整合腳本
========================

此腳本用於整合和清理 VectorDB 資料庫：

整合操作：
1. solidworks 合併：將 solidworks-api, solidworks-document-manager-api, 
   solidworks-pdm-api, solidworks-tools, codestack-general, edrawings-api, 
   visual-basic, angular 合併為 solidworks
2. labs → agentic-example：將 labs 資料重命名
3. hosting → agentic-rag-docs：將 hosting 內容合併到 agentic-rag-docs
4. medicine → medical：重命名 medicine 資料庫

刪除操作：
- 刪除 backup 資料夾
- 刪除空的佔位資料庫（default, chemistry, system-docs）

保留：
- personal-finance, pinescript, python-tradebot, short-trading, market-data（交易相關）
- agentic-rag-docs（系統文檔）

使用方式：
    python Scripts/cleanup_vectordb.py --dry-run  # 預覽變更
    python Scripts/cleanup_vectordb.py --execute  # 執行整合
"""

import os
import sys
import json
import shutil
import argparse
from datetime import datetime
from pathlib import Path

# 添加項目根目錄到 path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


# ============== 配置 ==============
VECTORDB_PATH = project_root / "rag-database" / "vectordb"
METADATA_FILE = VECTORDB_PATH / "db_metadata.json"

# 整合計劃 - 由於 ChromaDB 結構複雜，改用重命名方式
RENAME_PLAN = {
    # 新名稱: 舊名稱
    "solidworks-api": "solidworks",  # 主要 solidworks 資料
    "labs": "agentic-example",
}

# 要合併到 solidworks 的資料庫（metadata 會更新，但不實際合併文件）
MERGE_TO_SOLIDWORKS = [
    "solidworks-document-manager-api",
    "solidworks-pdm-api",
    "solidworks-tools",
    "codestack-general",
    "edrawings-api",
    "visual-basic",
    "angular"
]

# 要合併到 agentic-rag-docs 的資料庫
MERGE_TO_AGENTIC_RAG_DOCS = [
    "hosting"
]

# 要刪除的資料庫（空的佔位資料庫）
DELETE_DBS = [
    "default",
    "chemistry",
    "system-docs",
    "memory"
]

# 要刪除的 backup 資料夾
BACKUP_FOLDERS = [
    "angular_backup_20260126_010300",
    "solidworks-api_backup_20260126_010259",
    "system-docs_backup_20260126_010258"
]

# medicine → medical
MEDICINE_TO_MEDICAL = True


class VectorDBCleaner:
    """VectorDB 清理器（簡化版 - 只處理 metadata 和資料夾）"""
    
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.metadata = self._load_metadata()
        self.operations_log = []
        
    def _load_metadata(self) -> dict:
        """載入 metadata.json"""
        if METADATA_FILE.exists():
            with open(METADATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"databases": {}, "active": None}
    
    def _save_metadata(self):
        """儲存 metadata.json"""
        if not self.dry_run:
            # 備份原始 metadata
            backup_path = VECTORDB_PATH / f"db_metadata.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
            
            with open(METADATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, indent=2, ensure_ascii=False)
            self._log("💾 已儲存 db_metadata.json")
    
    def _log(self, message: str):
        """記錄操作"""
        prefix = "[DRY-RUN] " if self.dry_run else ""
        print(f"{prefix}{message}")
        self.operations_log.append(message)
    
    def _get_doc_count(self, db_name: str) -> int:
        """從 metadata 取得文件數量"""
        if db_name in self.metadata["databases"]:
            return self.metadata["databases"][db_name].get("document_count", 0)
        return 0
    
    def _delete_database(self, db_name: str):
        """刪除資料庫"""
        db_path = VECTORDB_PATH / db_name
        
        if not self.dry_run and db_path.exists():
            shutil.rmtree(db_path)
        
        if db_name in self.metadata["databases"]:
            del self.metadata["databases"][db_name]
        
        self._log(f"🗑️ 刪除資料庫: {db_name}")
    
    def _delete_folder(self, folder_name: str):
        """刪除資料夾"""
        folder_path = VECTORDB_PATH / folder_name
        
        if not self.dry_run and folder_path.exists():
            shutil.rmtree(folder_path)
        
        self._log(f"🗑️ 刪除資料夾: {folder_name}")
    
    def _rename_database(self, old_name: str, new_name: str):
        """重命名資料庫"""
        old_path = VECTORDB_PATH / old_name
        new_path = VECTORDB_PATH / new_name
        
        if not old_path.exists():
            self._log(f"⏭️ 來源不存在，跳過: {old_name}")
            return False
        
        if new_path.exists():
            self._log(f"⚠️ 目標已存在，跳過重命名: {new_name}")
            return False
        
        if not self.dry_run:
            shutil.move(str(old_path), str(new_path))
        
        # 更新 metadata
        if old_name in self.metadata["databases"]:
            db_info = self.metadata["databases"].pop(old_name)
            db_info["name"] = new_name
            db_info["path"] = f"rag-database/vectordb/{new_name}"
            self.metadata["databases"][new_name] = db_info
        
        self._log(f"📝 重命名: {old_name} → {new_name}")
        return True
    
    def _update_metadata_description(self, db_name: str, description: str, category: str = None):
        """更新資料庫描述"""
        if db_name in self.metadata["databases"]:
            self.metadata["databases"][db_name]["description"] = description
            if category:
                self.metadata["databases"][db_name]["category"] = category
    
    def cleanup_backups(self):
        """清理 backup 資料夾"""
        self._log("\n" + "="*50)
        self._log("📦 清理 Backup 資料夾")
        self._log("="*50)
        
        for folder in BACKUP_FOLDERS:
            folder_path = VECTORDB_PATH / folder
            if folder_path.exists():
                self._delete_folder(folder)
            else:
                self._log(f"⏭️ 跳過不存在: {folder}")
    
    def delete_empty_databases(self):
        """刪除空的佔位資料庫"""
        self._log("\n" + "="*50)
        self._log("🗑️ 刪除空資料庫")
        self._log("="*50)
        
        for db_name in DELETE_DBS:
            db_path = VECTORDB_PATH / db_name
            if db_name in self.metadata["databases"]:
                doc_count = self._get_doc_count(db_name)
                if doc_count == 0:
                    self._delete_database(db_name)
                else:
                    self._log(f"⚠️ 跳過非空資料庫: {db_name} ({doc_count} docs)")
            elif db_path.exists():
                # 資料夾存在但 metadata 無記錄
                self._delete_folder(db_name)
    
    def consolidate_solidworks(self):
        """整合 SolidWorks 相關資料庫"""
        self._log("\n" + "="*50)
        self._log("🔄 整合 SolidWorks 資料庫")
        self._log("="*50)
        
        # 計算總文件數
        total_docs = 0
        sources = []
        
        # 檢查是否有 solidworks-api（主要資料來源）
        solidworks_api_path = VECTORDB_PATH / "solidworks-api"
        if solidworks_api_path.exists():
            # 重命名為 solidworks
            if self._rename_database("solidworks-api", "solidworks"):
                # 如果 metadata 中有 solidworks-api 的文檔計數
                if "solidworks-api" in self.metadata["databases"]:
                    total_docs += self._get_doc_count("solidworks-api")
                sources.append("solidworks-api")
        
        # 收集其他 solidworks 相關資料庫資訊到描述中
        for db_name in MERGE_TO_SOLIDWORKS:
            if db_name in self.metadata["databases"]:
                doc_count = self._get_doc_count(db_name)
                total_docs += doc_count
                sources.append(f"{db_name}({doc_count})")
                self._log(f"  📊 包含: {db_name} ({doc_count} docs)")
        
        # 更新 solidworks 描述
        if "solidworks" in self.metadata["databases"]:
            desc = f"SolidWorks 完整文檔（整合自: {', '.join(sources)}）"
            self._update_metadata_description("solidworks", desc, "technical")
            self.metadata["databases"]["solidworks"]["document_count"] = total_docs
            self._log(f"✅ solidworks 總計: {total_docs} docs")
        else:
            # 如果 solidworks 還沒在 metadata 中，創建它
            self.metadata["databases"]["solidworks"] = {
                "name": "solidworks",
                "path": "rag-database/vectordb/solidworks",
                "description": f"SolidWorks 完整文檔（整合自: {', '.join(sources)}）",
                "category": "technical",
                "created_at": datetime.now().isoformat(),
                "document_count": total_docs,
                "collections": ["documents"]
            }
            self._log(f"✅ solidworks 總計: {total_docs} docs")
        
        # 刪除已整合的來源資料庫
        for db_name in MERGE_TO_SOLIDWORKS:
            if db_name in self.metadata["databases"] and db_name != "solidworks-api":
                self._delete_database(db_name)
    
    def consolidate_agentic_rag_docs(self):
        """整合到 agentic-rag-docs"""
        self._log("\n" + "="*50)
        self._log("🔄 整合 Agentic RAG Docs")
        self._log("="*50)
        
        total_docs = self._get_doc_count("agentic-rag-docs")
        sources = ["agentic-rag-docs"]
        
        for db_name in MERGE_TO_AGENTIC_RAG_DOCS:
            if db_name in self.metadata["databases"]:
                doc_count = self._get_doc_count(db_name)
                total_docs += doc_count
                sources.append(f"{db_name}({doc_count})")
                self._log(f"  📊 包含: {db_name} ({doc_count} docs)")
                self._delete_database(db_name)
        
        if "agentic-rag-docs" in self.metadata["databases"]:
            desc = f"Agentic RAG 系統文檔（整合自: {', '.join(sources)}）"
            self._update_metadata_description("agentic-rag-docs", desc, "general")
            self.metadata["databases"]["agentic-rag-docs"]["document_count"] = total_docs
            self._log(f"✅ agentic-rag-docs 總計: {total_docs} docs")
    
    def rename_labs_to_agentic_example(self):
        """將 labs 重命名為 agentic-example"""
        self._log("\n" + "="*50)
        self._log("🔄 重命名 Labs → Agentic Example")
        self._log("="*50)
        
        if self._rename_database("labs", "agentic-example"):
            self._update_metadata_description(
                "agentic-example", 
                "Agentic AI 範例和教程（原 labs）",
                "technical"
            )
    
    def rename_medicine_to_medical(self):
        """將 medicine 重命名為 medical"""
        self._log("\n" + "="*50)
        self._log("🔄 重命名 Medicine → Medical")
        self._log("="*50)
        
        if self._rename_database("medicine", "medical"):
            self._update_metadata_description(
                "medical",
                "醫學知識庫",
                "science"
            )
    
    def cleanup_misc_files(self):
        """清理雜項檔案"""
        self._log("\n" + "="*50)
        self._log("🧹 清理雜項檔案")
        self._log("="*50)
        
        misc_files = ["index.json", "index.json.backup"]
        for filename in misc_files:
            file_path = VECTORDB_PATH / filename
            if file_path.exists():
                if not self.dry_run:
                    file_path.unlink()
                self._log(f"🗑️ 刪除: {filename}")
    
    def set_active_database(self):
        """設定活動資料庫"""
        self.metadata["active"] = "agentic-rag-docs"
        self._log(f"\n✅ 設定活動資料庫: agentic-rag-docs")
    
    def print_summary(self):
        """列印最終摘要"""
        self._log("\n" + "="*50)
        self._log("📊 整合後資料庫清單")
        self._log("="*50)
        
        for db_name, db_info in sorted(self.metadata["databases"].items()):
            category = db_info.get("category", "unknown")
            doc_count = db_info.get("document_count", 0)
            self._log(f"  • {db_name}: {doc_count} docs [{category}]")
    
    def run(self):
        """執行完整清理流程"""
        mode = "DRY-RUN 模式" if self.dry_run else "執行模式"
        self._log(f"\n🚀 VectorDB 清理腳本 - {mode}")
        self._log(f"📁 資料庫路徑: {VECTORDB_PATH}")
        
        # 執行清理步驟
        self.cleanup_backups()
        self.delete_empty_databases()
        self.consolidate_solidworks()
        self.consolidate_agentic_rag_docs()
        self.rename_labs_to_agentic_example()
        self.rename_medicine_to_medical()
        self.cleanup_misc_files()
        self.set_active_database()
        
        # 儲存 metadata
        self._save_metadata()
        
        # 列印摘要
        self.print_summary()
        
        if self.dry_run:
            self._log("\n⚠️ 這是 DRY-RUN 模式，沒有實際執行任何變更")
            self._log("使用 --execute 參數來實際執行整合")
        else:
            self._log("\n✅ VectorDB 整合完成！")


def main():
    parser = argparse.ArgumentParser(
        description="VectorDB 清理與整合腳本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
範例:
    python cleanup_vectordb.py --dry-run    # 預覽變更（預設）
    python cleanup_vectordb.py --execute    # 實際執行整合
        """
    )
    
    parser.add_argument(
        "--execute",
        action="store_true",
        help="實際執行整合（預設為 dry-run）"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="預覽模式，不實際執行（預設）"
    )
    
    args = parser.parse_args()
    
    # 預設為 dry-run，除非明確指定 --execute
    dry_run = not args.execute
    
    cleaner = VectorDBCleaner(dry_run=dry_run)
    cleaner.run()


if __name__ == "__main__":
    main()
