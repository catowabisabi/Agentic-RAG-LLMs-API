# -*- coding: utf-8 -*-
"""
=============================================================================
Redis Service - 統一的 Redis 連接管理
=============================================================================

功能說明：
-----------
提供全局 Redis 連接池和工具方法，供 ChatService、TaskManager 等使用。

特性：
-----------
1. 連接池管理（高併發友好）
2. 優雅降級（Redis 不可用時自動 fallback 到內存）
3. JSON 序列化/反序列化
4. TTL 支持
5. Pub/Sub 支持（未來用於跨進程通訊）

配置：
-----------
- REDIS_URL: Redis 連接 URL（默認 redis://localhost:6379/0）
- REDIS_ENABLED: 是否啟用 Redis（默認 false）
- REDIS_PREFIX: Key 前綴（默認 agentic_rag:）
- REDIS_TTL: 默認 TTL（默認 86400 秒 = 24 小時）

使用方式：
-----------
from services.redis_service import get_redis_service, RedisService

redis = get_redis_service()

# 基本操作
await redis.set("key", {"data": "value"})
data = await redis.get("key")

# 會話操作
await redis.set_conversation("conv_id", messages)
messages = await redis.get_conversation("conv_id")

# 任務操作
await redis.set_task("task_id", task_data)
task = await redis.get_task("task_id")

=============================================================================
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import redis
try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False
    aioredis = None
    logger.info("redis package not installed. Redis features disabled. Install with: pip install redis")

if TYPE_CHECKING:
    from redis.asyncio import Redis as RedisType


class RedisService:
    """
    統一的 Redis 服務
    
    支持：
    - 會話存儲（替代內存 Dict）
    - 任務狀態存儲（替代內存 Dict）
    - 快取層
    - 優雅降級到內存
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # Configuration
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.enabled = os.getenv("REDIS_ENABLED", "false").lower() == "true"
        self.prefix = os.getenv("REDIS_PREFIX", "agentic_rag:")
        self.default_ttl = int(os.getenv("REDIS_TTL", "86400"))  # 24 hours
        
        # Connection
        self._redis = None  # type: Optional[Any]
        self._connected = False
        
        # Fallback in-memory storage
        self._memory_store: Dict[str, Any] = {}
        
        if not HAS_REDIS:
            self.enabled = False
            logger.info("Redis disabled: redis package not installed")
        elif not self.enabled:
            logger.info("Redis disabled by configuration (REDIS_ENABLED=false)")
        else:
            logger.info(f"Redis enabled, URL: {self.redis_url}")
    
    async def connect(self) -> bool:
        """建立 Redis 連接"""
        if not self.enabled or not HAS_REDIS:
            return False
        
        try:
            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=20,
                socket_timeout=5,
                socket_connect_timeout=5,
                retry_on_timeout=True
            )
            # Test connection
            await self._redis.ping()
            self._connected = True
            logger.info(f"Redis connected successfully: {self.redis_url}")
            return True
        except Exception as e:
            logger.warning(f"Redis connection failed, falling back to memory: {e}")
            self._connected = False
            self._redis = None
            return False
    
    async def disconnect(self):
        """關閉 Redis 連接"""
        if self._redis:
            await self._redis.close()
            self._connected = False
            logger.info("Redis disconnected")
    
    @property
    def is_connected(self) -> bool:
        """檢查 Redis 是否已連接"""
        return self._connected and self._redis is not None
    
    def _key(self, key: str) -> str:
        """生成帶前綴的 key"""
        return f"{self.prefix}{key}"
    
    # ========================================
    # 基本操作
    # ========================================
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """設置值（支持 JSON 序列化）"""
        full_key = self._key(key)
        serialized = json.dumps(value, default=str, ensure_ascii=False)
        ttl = ttl or self.default_ttl
        
        if self.is_connected:
            try:
                await self._redis.setex(full_key, ttl, serialized)
                return True
            except Exception as e:
                logger.warning(f"Redis SET failed, using memory: {e}")
        
        # Fallback to memory
        self._memory_store[full_key] = {
            "value": serialized,
            "expires": datetime.now().timestamp() + ttl
        }
        return True
    
    async def get(self, key: str) -> Optional[Any]:
        """獲取值（自動 JSON 反序列化）"""
        full_key = self._key(key)
        
        if self.is_connected:
            try:
                data = await self._redis.get(full_key)
                if data:
                    return json.loads(data)
                return None
            except Exception as e:
                logger.warning(f"Redis GET failed, using memory: {e}")
        
        # Fallback to memory
        entry = self._memory_store.get(full_key)
        if entry:
            if entry["expires"] > datetime.now().timestamp():
                return json.loads(entry["value"])
            else:
                del self._memory_store[full_key]
        return None
    
    async def delete(self, key: str) -> bool:
        """刪除鍵"""
        full_key = self._key(key)
        
        if self.is_connected:
            try:
                await self._redis.delete(full_key)
                return True
            except Exception as e:
                logger.warning(f"Redis DELETE failed: {e}")
        
        # Fallback
        self._memory_store.pop(full_key, None)
        return True
    
    async def exists(self, key: str) -> bool:
        """檢查鍵是否存在"""
        full_key = self._key(key)
        
        if self.is_connected:
            try:
                return bool(await self._redis.exists(full_key))
            except Exception as e:
                logger.warning(f"Redis EXISTS failed: {e}")
        
        entry = self._memory_store.get(full_key)
        return entry is not None and entry["expires"] > datetime.now().timestamp()
    
    # ========================================
    # 會話操作
    # ========================================
    
    async def set_conversation(self, conversation_id: str, messages: List[Dict]) -> bool:
        """存儲會話消息"""
        return await self.set(f"conv:{conversation_id}", messages)
    
    async def get_conversation(self, conversation_id: str) -> Optional[List[Dict]]:
        """獲取會話消息"""
        return await self.get(f"conv:{conversation_id}")
    
    async def append_message(self, conversation_id: str, message: Dict) -> bool:
        """追加消息到會話"""
        messages = await self.get_conversation(conversation_id) or []
        messages.append(message)
        return await self.set_conversation(conversation_id, messages)
    
    async def delete_conversation(self, conversation_id: str) -> bool:
        """刪除會話"""
        return await self.delete(f"conv:{conversation_id}")
    
    async def list_conversation_ids(self) -> List[str]:
        """列出所有會話 ID"""
        pattern = self._key("conv:*")
        prefix_len = len(self._key("conv:"))
        
        if self.is_connected:
            try:
                keys = []
                async for key in self._redis.scan_iter(match=pattern, count=100):
                    keys.append(key[prefix_len:])
                return keys
            except Exception as e:
                logger.warning(f"Redis SCAN failed: {e}")
        
        # Fallback
        prefix = self._key("conv:")
        return [
            k[len(prefix):] for k in self._memory_store.keys()
            if k.startswith(prefix)
        ]
    
    # ========================================
    # 任務操作
    # ========================================
    
    async def set_task(self, task_id: str, task_data: Dict, ttl: int = None) -> bool:
        """存儲任務狀態"""
        ttl = ttl or self.default_ttl
        return await self.set(f"task:{task_id}", task_data, ttl=ttl)
    
    async def get_task(self, task_id: str) -> Optional[Dict]:
        """獲取任務狀態"""
        return await self.get(f"task:{task_id}")
    
    async def delete_task(self, task_id: str) -> bool:
        """刪除任務"""
        return await self.delete(f"task:{task_id}")
    
    # ========================================
    # 快取操作
    # ========================================
    
    async def cache_set(self, key: str, value: Any, ttl: int = 1800) -> bool:
        """設置快取（默認 30 分鐘）"""
        return await self.set(f"cache:{key}", value, ttl=ttl)
    
    async def cache_get(self, key: str) -> Optional[Any]:
        """獲取快取"""
        return await self.get(f"cache:{key}")
    
    # ========================================
    # 健康檢查
    # ========================================
    
    async def health_check(self) -> Dict[str, Any]:
        """Redis 健康檢查"""
        status = {
            "enabled": self.enabled,
            "has_redis_package": HAS_REDIS,
            "connected": self.is_connected,
            "url": self.redis_url if self.enabled else None,
            "fallback_keys": len(self._memory_store)
        }
        
        if self.is_connected:
            try:
                info = await self._redis.info("memory")
                status["used_memory"] = info.get("used_memory_human", "unknown")
                status["connected_clients"] = (await self._redis.info("clients")).get("connected_clients", 0)
            except Exception:
                pass
        
        return status


# ========================================
# 全局單例
# ========================================

_redis_service: Optional[RedisService] = None


def get_redis_service() -> RedisService:
    """獲取 Redis 服務單例"""
    global _redis_service
    if _redis_service is None:
        _redis_service = RedisService()
    return _redis_service
