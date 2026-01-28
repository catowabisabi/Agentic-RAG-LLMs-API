"""
Document Loader Service

Provides document loading and collection management functionality.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from services.vectordb_manager import vectordb_manager

logger = logging.getLogger(__name__)


class DocumentLoader:
    """
    Document Loader for managing document collections.
    
    Provides:
    - Collection listing
    - Collection deletion
    - Document loading from files
    """
    
    def __init__(self, base_path: str = None):
        """Initialize document loader"""
        self.base_path = base_path or "./app_docs"
        self.vectordb = vectordb_manager
    
    def list_collections(self) -> List[Dict[str, Any]]:
        """List all available collections/databases"""
        try:
            databases = self.vectordb.list_databases()
            return [
                {
                    "name": db["name"],
                    "document_count": db.get("document_count", 0),
                    "description": db.get("description", ""),
                    "created_at": db.get("created_at", "")
                }
                for db in databases
            ]
        except Exception as e:
            logger.error(f"Error listing collections: {e}")
            return []
    
    def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection/database"""
        try:
            self.vectordb.delete_database(collection_name)
            logger.info(f"Deleted collection: {collection_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting collection {collection_name}: {e}")
            raise
    
    def load_file(self, file_path: str) -> Dict[str, Any]:
        """Load content from a file"""
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return {
            "content": content,
            "filename": path.name,
            "file_type": path.suffix,
            "size": len(content)
        }
    
    def load_directory(
        self,
        directory: str,
        extensions: List[str] = None
    ) -> List[Dict[str, Any]]:
        """Load all documents from a directory"""
        extensions = extensions or [".txt", ".md", ".json", ".py"]
        documents = []
        
        path = Path(directory)
        if not path.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")
        
        for file_path in path.rglob("*"):
            if file_path.is_file() and file_path.suffix.lower() in extensions:
                try:
                    doc = self.load_file(str(file_path))
                    doc["relative_path"] = str(file_path.relative_to(path))
                    documents.append(doc)
                except Exception as e:
                    logger.warning(f"Could not load {file_path}: {e}")
        
        return documents
