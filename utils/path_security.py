"""
utils/path_security.py
======================

共用路徑安全工具

提供路徑遍歷攻擊防護 (Path Traversal Prevention) 與
集合名稱 / 資料庫名稱驗證，統一管理安全邏輯。

使用範例
---------
from utils.path_security import sanitize_path, validate_collection_name

# 路徑沙箱
safe_path = sanitize_path("../../etc/passwd", allowed_root=Path("/data/chroma"))
# → raises ValueError: Access denied

# 集合名稱驗證
clean_name = validate_collection_name("../../evil")
# → raises ValueError: Invalid collection name
"""

import re
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 常數
# ──────────────────────────────────────────────

# 只允許字母、數字、底線、連字號
_SAFE_NAME_RE = re.compile(r'^[a-zA-Z0-9_\-]+$')
_MAX_NAME_LEN = 64
_MIN_NAME_LEN = 1

# ──────────────────────────────────────────────
# 路徑沙箱
# ──────────────────────────────────────────────

def sanitize_path(user_path: str, allowed_root: Path) -> Path:
    """
    解析使用者提供的路徑，確保路徑在 ``allowed_root`` 目錄內。

    安全做法：
    - 使用 ``Path.resolve()`` 展開 ``..`` 和符號鏈接
    - 使用 ``Path.is_relative_to()`` 做嚴格子路徑比較（避免
      str.startswith 的 ``/var/data`` vs ``/var/data_evil`` 邊界問題）

    Parameters
    ----------
    user_path : str
        使用者提供的路徑字串
    allowed_root : Path
        允許存取的根目錄（應為絕對路徑且已 resolve）

    Returns
    -------
    Path
        驗證後的安全路徑（絕對路徑）

    Raises
    ------
    ValueError
        若路徑逃出 allowed_root
    """
    allowed_root = Path(allowed_root).resolve()
    candidate = Path(user_path)

    # 相對路徑 → 相對於 allowed_root
    if not candidate.is_absolute():
        candidate = allowed_root / candidate

    resolved = candidate.resolve()

    # Python 3.9+ is_relative_to 是最安全的比較方式
    try:
        resolved.relative_to(allowed_root)
    except ValueError:
        logger.warning(
            "Path traversal attempt blocked: '%s' resolves to '%s', "
            "which is outside allowed root '%s'",
            user_path, resolved, allowed_root
        )
        raise ValueError(
            f"Access denied: path '{user_path}' is outside the allowed directory."
        )

    return resolved


# ──────────────────────────────────────────────
# 集合 / DB 名稱驗證
# ──────────────────────────────────────────────

def validate_collection_name(name: str) -> str:
    """
    驗證 ChromaDB 集合名稱是否安全。

    規則：
    - 只允許 ``[a-zA-Z0-9_-]``
    - 長度 1–64 個字元
    - 不允許 ``..``、``/``、``\\``、空白

    Parameters
    ----------
    name : str
        使用者提供的集合名稱

    Returns
    -------
    str
        驗證通過的名稱（原值回傳）

    Raises
    ------
    ValueError
        若名稱不符合安全規則
    """
    if not name or not isinstance(name, str):
        raise ValueError("Collection name must be a non-empty string.")

    name = name.strip()

    if len(name) < _MIN_NAME_LEN or len(name) > _MAX_NAME_LEN:
        raise ValueError(
            f"Collection name must be between {_MIN_NAME_LEN} "
            f"and {_MAX_NAME_LEN} characters. Got: {len(name)}"
        )

    # 明確拒絕路徑分隔符與遍歷序列
    if any(c in name for c in ('/', '\\', '..', '\0')):
        raise ValueError(
            f"Collection name contains forbidden characters: '{name}'"
        )

    if not _SAFE_NAME_RE.match(name):
        raise ValueError(
            f"Collection name '{name}' contains invalid characters. "
            "Only letters, numbers, underscores and hyphens are allowed."
        )

    return name


def validate_db_name(name: str) -> str:
    """
    等同 ``validate_collection_name``，用於資料庫名稱驗證。
    並額外將空白轉換為連字號（對齊現有 VectorDBManager 的行為）。

    Parameters
    ----------
    name : str
        使用者提供的資料庫名稱

    Returns
    -------
    str
        已清理並驗證的名稱（小寫，空白轉 ``-``）

    Raises
    ------
    ValueError
        若名稱不符合安全規則（在空白轉換之後）
    """
    if not name or not isinstance(name, str):
        raise ValueError("Database name must be a non-empty string.")

    # 對齊現有行為：小寫 + 空白/底線轉連字號
    name = name.strip().lower().replace(" ", "-").replace("_", "-")

    return validate_collection_name(name)


# ──────────────────────────────────────────────
# 備份檔案名稱驗證
# ──────────────────────────────────────────────

def validate_backup_filename(filename: str) -> str:
    """
    驗證備份檔案名稱，防止路徑遍歷攻擊。

    只允許字母、數字、底線、連字號和點號（.zip, .tar.gz）。

    Parameters
    ----------
    filename : str
        備份檔案名稱

    Returns
    -------
    str
        驗證通過的檔案名稱

    Raises
    ------
    ValueError
        若檔案名稱不安全
    """
    if not filename or not isinstance(filename, str):
        raise ValueError("Backup filename must be a non-empty string.")

    filename = filename.strip()

    # 拒絕路徑分隔符
    if any(c in filename for c in ('/', '\\', '\0')):
        raise ValueError(
            f"Backup filename contains forbidden characters: '{filename}'"
        )

    # 只允許安全字元（包含點號用於副檔名）
    safe_backup_re = re.compile(r'^[a-zA-Z0-9_\-\.]+$')
    if not safe_backup_re.match(filename):
        raise ValueError(
            f"Backup filename '{filename}' contains invalid characters."
        )

    if len(filename) > 255:
        raise ValueError("Backup filename is too long.")

    return filename
