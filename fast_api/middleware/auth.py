"""
Authentication & Rate Limiting Middleware
==========================================

提供：
1. API Key 認證
2. 速率限制（防止濫用）
3. 用戶識別與追蹤
4. 請求日誌記錄
"""

import asyncio
import logging
import time
import hashlib
import secrets
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps

from fastapi import Request, HTTPException, Depends, Header
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


# ============== 數據模型 ==============

class APIKeyInfo(BaseModel):
    """API Key 信息"""
    key_id: str
    key_hash: str  # 存儲 hash 而非原始 key
    user_id: str
    name: str
    permissions: List[str] = Field(default_factory=lambda: ["read", "write"])
    rate_limit: int = 100  # 每分鐘請求數
    daily_limit: int = 10000  # 每日請求數
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None
    is_active: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RateLimitInfo(BaseModel):
    """速率限制狀態"""
    requests_remaining: int
    reset_at: str
    daily_remaining: int
    daily_reset_at: str


class RequestLog(BaseModel):
    """請求日誌"""
    request_id: str
    timestamp: str
    user_id: str
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    ip_address: str
    user_agent: str


# ============== API Key 管理 ==============

class APIKeyManager:
    """
    API Key 管理器
    
    管理 API Key 的創建、驗證、撤銷
    """
    
    def __init__(self):
        # 存儲所有 API Keys（生產環境應使用數據庫）
        self.keys: Dict[str, APIKeyInfo] = {}
        
        # 創建一個默認的開發用 Key
        self._create_default_key()
        
        logger.info("APIKeyManager initialized")
    
    def _create_default_key(self):
        """創建默認開發用 API Key"""
        # 默認 key 僅用於開發環境
        default_key = "dev-key-agentic-rag-2024"
        key_hash = self._hash_key(default_key)
        
        self.keys[key_hash] = APIKeyInfo(
            key_id="default-dev",
            key_hash=key_hash,
            user_id="developer",
            name="Development Key",
            permissions=["read", "write", "admin"],
            rate_limit=1000,
            daily_limit=100000
        )
        
        logger.info(f"Default dev key created: {default_key}")
    
    def _hash_key(self, key: str) -> str:
        """Hash API Key"""
        return hashlib.sha256(key.encode()).hexdigest()
    
    def create_key(
        self,
        user_id: str,
        name: str,
        permissions: List[str] = None,
        rate_limit: int = 100,
        daily_limit: int = 10000,
        expires_days: int = None
    ) -> tuple[str, APIKeyInfo]:
        """
        創建新的 API Key
        
        Returns:
            (raw_key, key_info)
        """
        # 生成安全的隨機 key
        raw_key = f"sk-{secrets.token_urlsafe(32)}"
        key_hash = self._hash_key(raw_key)
        key_id = f"key-{secrets.token_hex(8)}"
        
        expires_at = None
        if expires_days:
            expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
        
        key_info = APIKeyInfo(
            key_id=key_id,
            key_hash=key_hash,
            user_id=user_id,
            name=name,
            permissions=permissions or ["read", "write"],
            rate_limit=rate_limit,
            daily_limit=daily_limit,
            expires_at=expires_at
        )
        
        self.keys[key_hash] = key_info
        
        logger.info(f"Created API key: {key_id} for user: {user_id}")
        
        return raw_key, key_info
    
    def validate_key(self, raw_key: str) -> Optional[APIKeyInfo]:
        """驗證 API Key"""
        if not raw_key:
            return None
        
        key_hash = self._hash_key(raw_key)
        key_info = self.keys.get(key_hash)
        
        if not key_info:
            return None
        
        if not key_info.is_active:
            return None
        
        # 檢查過期
        if key_info.expires_at:
            if datetime.fromisoformat(key_info.expires_at) < datetime.now():
                return None
        
        return key_info
    
    def revoke_key(self, key_id: str) -> bool:
        """撤銷 API Key"""
        for key_hash, info in self.keys.items():
            if info.key_id == key_id:
                info.is_active = False
                logger.info(f"Revoked API key: {key_id}")
                return True
        return False
    
    def list_keys(self, user_id: str = None) -> List[APIKeyInfo]:
        """列出 API Keys"""
        keys = list(self.keys.values())
        if user_id:
            keys = [k for k in keys if k.user_id == user_id]
        return keys
    
    def has_permission(self, key_info: APIKeyInfo, permission: str) -> bool:
        """檢查權限"""
        return permission in key_info.permissions or "admin" in key_info.permissions


# ============== 速率限制 ==============

class RateLimiter:
    """
    速率限制器
    
    使用滑動窗口算法限制請求速率
    """
    
    def __init__(self):
        # 請求計數：user_id -> [(timestamp, count)]
        self.request_windows: Dict[str, List[tuple]] = defaultdict(list)
        
        # 每日計數：user_id -> (date, count)
        self.daily_counts: Dict[str, tuple] = {}
        
        # 窗口大小（秒）
        self.window_size = 60
        
        # 清理間隔
        self._last_cleanup = time.time()
        self._cleanup_interval = 300  # 5 分鐘
        
        logger.info("RateLimiter initialized")
    
    def _cleanup_old_entries(self):
        """清理過期的條目"""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        
        cutoff = now - self.window_size * 2
        
        for user_id in list(self.request_windows.keys()):
            self.request_windows[user_id] = [
                (ts, count) for ts, count in self.request_windows[user_id]
                if ts > cutoff
            ]
            if not self.request_windows[user_id]:
                del self.request_windows[user_id]
        
        # 清理過期的每日計數
        today = datetime.now().date().isoformat()
        for user_id in list(self.daily_counts.keys()):
            date, _ = self.daily_counts[user_id]
            if date != today:
                del self.daily_counts[user_id]
        
        self._last_cleanup = now
    
    def check_rate_limit(
        self,
        user_id: str,
        rate_limit: int,
        daily_limit: int
    ) -> tuple[bool, RateLimitInfo]:
        """
        檢查速率限制
        
        Returns:
            (allowed, rate_limit_info)
        """
        self._cleanup_old_entries()
        
        now = time.time()
        today = datetime.now().date().isoformat()
        
        # 計算窗口內的請求數
        window_start = now - self.window_size
        windows = self.request_windows[user_id]
        recent_count = sum(
            count for ts, count in windows
            if ts > window_start
        )
        
        # 計算每日請求數
        daily_date, daily_count = self.daily_counts.get(user_id, (today, 0))
        if daily_date != today:
            daily_count = 0
        
        # 檢查是否超限
        minute_allowed = recent_count < rate_limit
        daily_allowed = daily_count < daily_limit
        allowed = minute_allowed and daily_allowed
        
        # 計算剩餘配額
        requests_remaining = max(0, rate_limit - recent_count - 1) if minute_allowed else 0
        daily_remaining = max(0, daily_limit - daily_count - 1) if daily_allowed else 0
        
        # 計算重置時間
        reset_at = datetime.fromtimestamp(now + self.window_size).isoformat()
        tomorrow = (datetime.now() + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        daily_reset_at = tomorrow.isoformat()
        
        info = RateLimitInfo(
            requests_remaining=requests_remaining,
            reset_at=reset_at,
            daily_remaining=daily_remaining,
            daily_reset_at=daily_reset_at
        )
        
        return allowed, info
    
    def record_request(self, user_id: str):
        """記錄一次請求"""
        now = time.time()
        today = datetime.now().date().isoformat()
        
        # 記錄到分鐘窗口
        self.request_windows[user_id].append((now, 1))
        
        # 記錄到每日計數
        daily_date, daily_count = self.daily_counts.get(user_id, (today, 0))
        if daily_date == today:
            self.daily_counts[user_id] = (today, daily_count + 1)
        else:
            self.daily_counts[user_id] = (today, 1)


# ============== 請求日誌 ==============

class RequestLogger:
    """請求日誌記錄器"""
    
    def __init__(self, max_logs: int = 10000):
        self.logs: List[RequestLog] = []
        self.max_logs = max_logs
    
    def log_request(
        self,
        request_id: str,
        user_id: str,
        endpoint: str,
        method: str,
        status_code: int,
        response_time_ms: float,
        ip_address: str,
        user_agent: str
    ):
        """記錄請求"""
        log = RequestLog(
            request_id=request_id,
            timestamp=datetime.now().isoformat(),
            user_id=user_id,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.logs.append(log)
        
        # 保持日誌數量限制
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]
    
    def get_recent_logs(
        self,
        user_id: str = None,
        endpoint: str = None,
        limit: int = 100
    ) -> List[RequestLog]:
        """獲取最近的日誌"""
        logs = self.logs
        
        if user_id:
            logs = [l for l in logs if l.user_id == user_id]
        
        if endpoint:
            logs = [l for l in logs if endpoint in l.endpoint]
        
        return logs[-limit:]
    
    def get_stats(self, user_id: str = None) -> Dict[str, Any]:
        """獲取統計信息"""
        logs = self.logs
        if user_id:
            logs = [l for l in logs if l.user_id == user_id]
        
        if not logs:
            return {}
        
        # 計算統計
        total = len(logs)
        avg_response_time = sum(l.response_time_ms for l in logs) / total
        success_count = sum(1 for l in logs if 200 <= l.status_code < 400)
        error_count = sum(1 for l in logs if l.status_code >= 400)
        
        # 端點分佈
        endpoint_counts: Dict[str, int] = {}
        for log in logs:
            ep = log.endpoint.split("?")[0]  # 移除查詢參數
            endpoint_counts[ep] = endpoint_counts.get(ep, 0) + 1
        
        return {
            "total_requests": total,
            "avg_response_time_ms": round(avg_response_time, 2),
            "success_rate": round(success_count / total * 100, 2),
            "error_count": error_count,
            "top_endpoints": sorted(
                endpoint_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }


# ============== FastAPI 中間件 ==============

class AuthMiddleware(BaseHTTPMiddleware):
    """認證和速率限制中間件"""
    
    # 不需要認證的路徑
    PUBLIC_PATHS = [
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/ws"  # WebSocket 使用不同的認證方式
    ]
    
    def __init__(self, app, api_key_manager: APIKeyManager, rate_limiter: RateLimiter, request_logger: RequestLogger):
        super().__init__(app)
        self.api_key_manager = api_key_manager
        self.rate_limiter = rate_limiter
        self.request_logger = request_logger
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        request_id = secrets.token_hex(8)
        
        # 添加 request_id 到 state
        request.state.request_id = request_id
        
        # 檢查是否是公開路徑
        path = request.url.path
        is_public = any(path.startswith(p) for p in self.PUBLIC_PATHS)
        
        if not is_public:
            # 獲取 API Key
            api_key = request.headers.get("X-API-Key") or request.headers.get("Authorization", "").replace("Bearer ", "")
            
            if not api_key:
                return Response(
                    content='{"detail": "API key required"}',
                    status_code=401,
                    media_type="application/json"
                )
            
            # 驗證 API Key
            key_info = self.api_key_manager.validate_key(api_key)
            if not key_info:
                return Response(
                    content='{"detail": "Invalid or expired API key"}',
                    status_code=401,
                    media_type="application/json"
                )
            
            # 檢查速率限制
            allowed, rate_info = self.rate_limiter.check_rate_limit(
                key_info.user_id,
                key_info.rate_limit,
                key_info.daily_limit
            )
            
            if not allowed:
                return Response(
                    content=f'{{"detail": "Rate limit exceeded", "rate_limit_info": {rate_info.model_dump_json()}}}',
                    status_code=429,
                    media_type="application/json",
                    headers={
                        "X-RateLimit-Remaining": str(rate_info.requests_remaining),
                        "X-RateLimit-Reset": rate_info.reset_at,
                        "Retry-After": "60"
                    }
                )
            
            # 記錄請求
            self.rate_limiter.record_request(key_info.user_id)
            
            # 添加用戶信息到 request state
            request.state.user_id = key_info.user_id
            request.state.key_info = key_info
        else:
            request.state.user_id = "anonymous"
            request.state.key_info = None
        
        # 執行請求
        response = await call_next(request)
        
        # 計算響應時間
        response_time_ms = (time.time() - start_time) * 1000
        
        # 記錄日誌
        self.request_logger.log_request(
            request_id=request_id,
            user_id=request.state.user_id,
            endpoint=str(request.url.path),
            method=request.method,
            status_code=response.status_code,
            response_time_ms=response_time_ms,
            ip_address=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("User-Agent", "unknown")
        )
        
        # 添加響應頭
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{response_time_ms:.2f}ms"
        
        return response


# ============== FastAPI 依賴 ==============

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_current_user(
    request: Request,
    api_key: str = Depends(api_key_header)
) -> Optional[APIKeyInfo]:
    """獲取當前用戶（用於路由依賴）"""
    return getattr(request.state, "key_info", None)


async def require_auth(
    key_info: APIKeyInfo = Depends(get_current_user)
) -> APIKeyInfo:
    """要求認證（用於需要認證的路由）"""
    if not key_info:
        raise HTTPException(status_code=401, detail="Authentication required")
    return key_info


async def require_admin(
    key_info: APIKeyInfo = Depends(require_auth)
) -> APIKeyInfo:
    """要求管理員權限"""
    if "admin" not in key_info.permissions:
        raise HTTPException(status_code=403, detail="Admin permission required")
    return key_info


# ============== 單例 ==============

_api_key_manager = None
_rate_limiter = None
_request_logger = None


def get_api_key_manager() -> APIKeyManager:
    """獲取 API Key 管理器單例"""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


def get_rate_limiter() -> RateLimiter:
    """獲取速率限制器單例"""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter()
    return _rate_limiter


def get_request_logger() -> RequestLogger:
    """獲取請求日誌器單例"""
    global _request_logger
    if _request_logger is None:
        _request_logger = RequestLogger()
    return _request_logger
