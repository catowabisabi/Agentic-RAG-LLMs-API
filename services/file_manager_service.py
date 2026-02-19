"""
File Management Service

Move, copy and organise files into designated folders.
Supports:
  - Move file(s) to a target folder
  - Copy file(s)
  - List directory contents
  - Create directories
  - Get file metadata
  - Bulk operations

All I/O is async-safe (run_in_executor).
"""

import asyncio
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Safety: restrict operations to within the workspace root
WORKSPACE_ROOT = Path(os.getenv("FILE_MANAGER_ROOT", ".")).resolve()


class FileManagerError(Exception):
    """File management errors."""
    pass


class FileManagerService:
    """
    Async file manager.

    Public API:
      - move_file(src, dest_folder)
      - copy_file(src, dest_folder)
      - list_directory(path)
      - create_directory(path)
      - get_file_info(path)
      - delete_file(path)
      - move_batch(file_paths, dest_folder)
    """

    _instance: Optional["FileManagerService"] = None

    def __new__(cls) -> "FileManagerService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info(f"FileManagerService initialized – root: {WORKSPACE_ROOT}")

    # -------------------------------------------------------- #
    # Path helpers
    # -------------------------------------------------------- #

    def _resolve(self, path_str: str) -> Path:
        """Resolve a path, ensuring it's within workspace root."""
        p = Path(path_str)
        if not p.is_absolute():
            p = WORKSPACE_ROOT / p
        p = p.resolve()
        # Security check
        if not str(p).startswith(str(WORKSPACE_ROOT)):
            raise FileManagerError(
                f"Access denied: path '{p}' is outside workspace root '{WORKSPACE_ROOT}'"
            )
        return p

    @staticmethod
    async def _run(fn, *args, **kwargs):
        loop = asyncio.get_event_loop()
        from functools import partial
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    # -------------------------------------------------------- #
    # Public API
    # -------------------------------------------------------- #

    async def move_file(self, src: str, dest_folder: str, overwrite: bool = False) -> Dict[str, Any]:
        """Move a file to the destination folder."""
        return await self._run(self._move_file_sync, src, dest_folder, overwrite)

    def _move_file_sync(self, src: str, dest_folder: str, overwrite: bool = False) -> Dict[str, Any]:
        src_path = self._resolve(src)
        if not src_path.exists():
            raise FileManagerError(f"Source not found: {src}")
        if not src_path.is_file():
            raise FileManagerError(f"Source is not a file: {src}")

        dest_dir = self._resolve(dest_folder)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / src_path.name

        if dest_path.exists() and not overwrite:
            raise FileManagerError(f"Destination already exists: {dest_path}. Use overwrite=true.")

        shutil.move(str(src_path), str(dest_path))
        logger.info(f"Moved: {src_path} → {dest_path}")
        return {
            "action": "move",
            "source": str(src_path),
            "destination": str(dest_path),
            "size": dest_path.stat().st_size,
        }

    async def copy_file(self, src: str, dest_folder: str, overwrite: bool = False) -> Dict[str, Any]:
        """Copy a file to the destination folder."""
        return await self._run(self._copy_file_sync, src, dest_folder, overwrite)

    def _copy_file_sync(self, src: str, dest_folder: str, overwrite: bool = False) -> Dict[str, Any]:
        src_path = self._resolve(src)
        if not src_path.exists():
            raise FileManagerError(f"Source not found: {src}")
        if not src_path.is_file():
            raise FileManagerError(f"Source is not a file: {src}")

        dest_dir = self._resolve(dest_folder)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / src_path.name

        if dest_path.exists() and not overwrite:
            raise FileManagerError(f"Destination already exists: {dest_path}. Use overwrite=true.")

        shutil.copy2(str(src_path), str(dest_path))
        logger.info(f"Copied: {src_path} → {dest_path}")
        return {
            "action": "copy",
            "source": str(src_path),
            "destination": str(dest_path),
            "size": dest_path.stat().st_size,
        }

    async def list_directory(self, path: str = ".") -> Dict[str, Any]:
        """List contents of a directory."""
        return await self._run(self._list_directory_sync, path)

    def _list_directory_sync(self, path: str = ".") -> Dict[str, Any]:
        dir_path = self._resolve(path)
        if not dir_path.exists():
            raise FileManagerError(f"Directory not found: {path}")
        if not dir_path.is_dir():
            raise FileManagerError(f"Not a directory: {path}")

        items = []
        for entry in sorted(dir_path.iterdir()):
            stat = entry.stat()
            items.append({
                "name": entry.name,
                "type": "directory" if entry.is_dir() else "file",
                "size": stat.st_size if entry.is_file() else None,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "extension": entry.suffix.lower() if entry.is_file() else None,
            })

        return {
            "path": str(dir_path),
            "item_count": len(items),
            "items": items,
        }

    async def create_directory(self, path: str) -> Dict[str, Any]:
        """Create a directory (including parent directories)."""
        return await self._run(self._create_directory_sync, path)

    def _create_directory_sync(self, path: str) -> Dict[str, Any]:
        dir_path = self._resolve(path)
        dir_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directory created: {dir_path}")
        return {"action": "create_directory", "path": str(dir_path)}

    async def get_file_info(self, path: str) -> Dict[str, Any]:
        """Get metadata about a file."""
        return await self._run(self._get_file_info_sync, path)

    def _get_file_info_sync(self, path: str) -> Dict[str, Any]:
        file_path = self._resolve(path)
        if not file_path.exists():
            raise FileManagerError(f"File not found: {path}")

        stat = file_path.stat()
        return {
            "name": file_path.name,
            "path": str(file_path),
            "type": "directory" if file_path.is_dir() else "file",
            "size": stat.st_size,
            "extension": file_path.suffix.lower() if file_path.is_file() else None,
            "created": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "is_readable": os.access(str(file_path), os.R_OK),
            "is_writable": os.access(str(file_path), os.W_OK),
        }

    async def delete_file(self, path: str) -> Dict[str, Any]:
        """Delete a file (not directories — use with caution)."""
        return await self._run(self._delete_file_sync, path)

    def _delete_file_sync(self, path: str) -> Dict[str, Any]:
        file_path = self._resolve(path)
        if not file_path.exists():
            raise FileManagerError(f"File not found: {path}")
        if file_path.is_dir():
            raise FileManagerError("Cannot delete directories with delete_file. Use rmdir for empty dirs.")

        size = file_path.stat().st_size
        file_path.unlink()
        logger.info(f"Deleted: {file_path}")
        return {"action": "delete", "path": str(file_path), "size": size}

    async def move_batch(
        self, file_paths: List[str], dest_folder: str, overwrite: bool = False
    ) -> Dict[str, Any]:
        """Move multiple files to a destination folder."""
        results = []
        errors = []
        for fp in file_paths:
            try:
                r = await self.move_file(fp, dest_folder, overwrite=overwrite)
                results.append(r)
            except Exception as e:
                errors.append({"file": fp, "error": str(e)})
        return {"moved": results, "errors": errors, "total_moved": len(results)}
