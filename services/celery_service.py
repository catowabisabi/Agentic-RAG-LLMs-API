# -*- coding: utf-8 -*-
"""
=============================================================================
Celery Service - 分布式任務隊列
=============================================================================

功能說明：
-----------
提供 Celery 分布式任務隊列支持，適用於：
- 長時間運行的 Agent 任務
- RAG 文檔處理與索引
- 批量 LLM 調用
- 定時任務（如記憶清理）

特性：
-----------
1. Redis 作為 Broker 和 Result Backend
2. 優雅降級（Celery 不可用時 fallback 到 asyncio）
3. 任務重試與錯誤處理
4. 任務進度追蹤
5. 與現有 BackgroundTaskManager 整合

配置：
-----------
- CELERY_ENABLED: 是否啟用 Celery（默認 false）
- CELERY_BROKER_URL: Broker URL（默認 redis://localhost:6379/1）
- CELERY_RESULT_BACKEND: Result Backend URL（默認 redis://localhost:6379/2）

使用方式：
-----------
from services.celery_service import get_celery_service

celery = get_celery_service()

# 提交任務
task_id = celery.submit_task("process_chat", {
    "message": "Hello",
    "conversation_id": "abc123"
})

# 查詢狀態
status = celery.get_task_status(task_id)

=============================================================================
"""

import os
import json
import logging
from typing import Any, Dict, Optional, Callable, TYPE_CHECKING
from datetime import datetime

logger = logging.getLogger(__name__)

# Try to import Celery
try:
    from celery import Celery
    from celery.result import AsyncResult
    HAS_CELERY = True
except ImportError:
    HAS_CELERY = False
    Celery = None  # type: ignore
    AsyncResult = None  # type: ignore
    logger.info("celery package not installed. Celery features disabled. Install with: pip install celery[redis]")


class CeleryService:
    """
    Celery 分布式任務隊列服務
    
    支持：
    - 長時間運行的背景任務
    - 任務進度追蹤
    - 自動重試
    - 優雅降級到 asyncio
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
        self.enabled = os.getenv("CELERY_ENABLED", "false").lower() == "true"
        self.broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
        self.result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
        
        # Celery app
        self._app = None  # type: Optional[Any]
        self._tasks_registered = False
        
        if not HAS_CELERY:
            self.enabled = False
            logger.info("Celery disabled: celery package not installed")
        elif not self.enabled:
            logger.info("Celery disabled by configuration (CELERY_ENABLED=false)")
        else:
            self._init_celery()
    
    def _init_celery(self):
        """初始化 Celery 應用"""
        try:
            self._app = Celery(
                "agentic_rag",
                broker=self.broker_url,
                backend=self.result_backend,
            )
            
            # Celery 配置
            self._app.conf.update(
                # 序列化
                task_serializer="json",
                result_serializer="json",
                accept_content=["json"],
                
                # 時區
                timezone="UTC",
                enable_utc=True,
                
                # 任務設定
                task_track_started=True,
                task_time_limit=300,          # 5 分鐘硬限制
                task_soft_time_limit=240,      # 4 分鐘軟限制
                task_acks_late=True,           # 任務完成後才 ack
                worker_prefetch_multiplier=1,  # 一次只取一個任務
                
                # 重試設定
                task_default_retry_delay=30,   # 30 秒後重試
                task_max_retries=3,            # 最多重試 3 次
                
                # 結果設定
                result_expires=86400,          # 結果保留 24 小時
                
                # Worker 設定
                worker_max_tasks_per_child=100,  # 每個 worker 處理 100 個任務後重啟
                worker_max_memory_per_child=200000,  # 200MB 記憶體限制
            )
            
            # 註冊任務
            self._register_tasks()
            
            logger.info(f"Celery initialized: broker={self.broker_url}")
        except Exception as e:
            logger.error(f"Celery initialization failed: {e}")
            self.enabled = False
            self._app = None
    
    def _register_tasks(self):
        """註冊 Celery 任務"""
        if not self._app or self._tasks_registered:
            return
        
        app = self._app
        
        @app.task(bind=True, name="agentic_rag.process_chat", max_retries=3)
        def process_chat_task(self_task, message: str, conversation_id: str,
                              user_id: str = "default", use_rag: bool = True,
                              enable_memory: bool = True, context: dict = None):
            """
            Celery 任務：處理聊天消息
            
            在 Worker 進程中異步執行，支持重試和進度追蹤。
            """
            import asyncio
            
            async def _run():
                from services.chat_service import get_chat_service
                chat_service = get_chat_service()
                
                result = await chat_service.process_message(
                    message=message,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    use_rag=use_rag,
                    enable_memory=enable_memory,
                    context=context or {}
                )
                
                return {
                    "response": result.response,
                    "conversation_id": result.conversation_id,
                    "agents_involved": result.agents_involved,
                    "sources": result.sources,
                    "task_uid": result.task_uid,
                    "timestamp": result.timestamp
                }
            
            try:
                # 更新進度
                self_task.update_state(state="PROCESSING", meta={
                    "current": 0,
                    "total": 100,
                    "status": "Processing message..."
                })
                
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(_run())
                finally:
                    loop.close()
                    
            except Exception as exc:
                logger.error(f"Celery task failed: {exc}")
                raise self_task.retry(exc=exc, countdown=30)
        
        @app.task(bind=True, name="agentic_rag.process_document", max_retries=2)
        def process_document_task(self_task, file_path: str, db_name: str,
                                   chunk_size: int = 1000, chunk_overlap: int = 200):
            """
            Celery 任務：處理文檔並建立索引
            """
            import asyncio
            
            async def _run():
                from services.document_loader import DocumentLoader
                loader = DocumentLoader()
                
                self_task.update_state(state="LOADING", meta={
                    "status": f"Loading document: {file_path}"
                })
                
                result = await loader.process_file(
                    file_path=file_path,
                    db_name=db_name,
                    chunk_size=chunk_size,
                    chunk_overlap=chunk_overlap
                )
                
                return {
                    "file_path": file_path,
                    "db_name": db_name,
                    "chunks": result.get("chunks", 0),
                    "status": "completed"
                }
            
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(_run())
                finally:
                    loop.close()
            except Exception as exc:
                logger.error(f"Document processing failed: {exc}")
                raise self_task.retry(exc=exc, countdown=60)
        
        @app.task(name="agentic_rag.cleanup_memory")
        def cleanup_memory_task():
            """
            Celery 定時任務：清理過期記憶和快取
            """
            import asyncio
            
            async def _run():
                from services.redis_service import get_redis_service
                redis = get_redis_service()
                
                # 健康檢查
                health = await redis.health_check()
                
                return {
                    "status": "completed",
                    "redis_health": health,
                    "timestamp": datetime.now().isoformat()
                }
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(_run())
            finally:
                loop.close()
        
        self._tasks_registered = True
        logger.info("Celery tasks registered: process_chat, process_document, cleanup_memory")
    
    # ========================================
    # 公開 API
    # ========================================
    
    @property
    def app(self):
        """取得 Celery 應用"""
        return self._app
    
    @property
    def is_available(self) -> bool:
        """檢查 Celery 是否可用"""
        return self.enabled and self._app is not None
    
    def submit_chat_task(
        self,
        message: str,
        conversation_id: str,
        user_id: str = "default",
        use_rag: bool = True,
        enable_memory: bool = True,
        context: dict = None
    ) -> Optional[str]:
        """
        提交聊天任務到 Celery 隊列
        
        Returns:
            Celery task ID 或 None（若 Celery 不可用）
        """
        if not self.is_available:
            logger.info("Celery not available, task should use asyncio fallback")
            return None
        
        try:
            result = self._app.send_task(
                "agentic_rag.process_chat",
                kwargs={
                    "message": message,
                    "conversation_id": conversation_id,
                    "user_id": user_id,
                    "use_rag": use_rag,
                    "enable_memory": enable_memory,
                    "context": context or {}
                }
            )
            logger.info(f"Celery task submitted: {result.id}")
            return result.id
        except Exception as e:
            logger.error(f"Failed to submit Celery task: {e}")
            return None
    
    def submit_document_task(
        self,
        file_path: str,
        db_name: str,
        chunk_size: int = 1000,
        chunk_overlap: int = 200
    ) -> Optional[str]:
        """提交文檔處理任務"""
        if not self.is_available:
            return None
        
        try:
            result = self._app.send_task(
                "agentic_rag.process_document",
                kwargs={
                    "file_path": file_path,
                    "db_name": db_name,
                    "chunk_size": chunk_size,
                    "chunk_overlap": chunk_overlap
                }
            )
            return result.id
        except Exception as e:
            logger.error(f"Failed to submit document task: {e}")
            return None
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        查詢 Celery 任務狀態
        
        Returns:
            {
                "task_id": str,
                "status": str,  # PENDING, STARTED, PROCESSING, SUCCESS, FAILURE, RETRY
                "result": Any,
                "error": str or None,
                "meta": Dict
            }
        """
        if not self.is_available:
            return {"task_id": task_id, "status": "UNAVAILABLE", "error": "Celery not available"}
        
        try:
            result = AsyncResult(task_id, app=self._app)
            
            response = {
                "task_id": task_id,
                "status": result.status,
                "result": None,
                "error": None,
                "meta": {}
            }
            
            if result.ready():
                if result.successful():
                    response["result"] = result.result
                else:
                    response["error"] = str(result.result)
            elif result.status == "PROCESSING":
                response["meta"] = result.info or {}
            
            return response
        except Exception as e:
            return {"task_id": task_id, "status": "ERROR", "error": str(e)}
    
    def revoke_task(self, task_id: str, terminate: bool = False) -> bool:
        """取消 Celery 任務"""
        if not self.is_available:
            return False
        
        try:
            self._app.control.revoke(task_id, terminate=terminate)
            return True
        except Exception as e:
            logger.error(f"Failed to revoke task {task_id}: {e}")
            return False
    
    # ========================================
    # 健康檢查
    # ========================================
    
    def health_check(self) -> Dict[str, Any]:
        """Celery 健康檢查"""
        status = {
            "enabled": self.enabled,
            "has_celery_package": HAS_CELERY,
            "available": self.is_available,
            "broker_url": self.broker_url if self.enabled else None,
        }
        
        if self.is_available:
            try:
                # 檢查 worker 狀態
                inspect = self._app.control.inspect(timeout=3.0)
                active = inspect.active() or {}
                registered = inspect.registered() or {}
                
                status["workers"] = len(active)
                status["registered_tasks"] = len(registered)
                status["active_tasks"] = sum(len(tasks) for tasks in active.values())
            except Exception as e:
                status["worker_check_error"] = str(e)
        
        return status


# ========================================
# 全局單例
# ========================================

_celery_service: Optional[CeleryService] = None


def get_celery_service() -> CeleryService:
    """獲取 Celery 服務單例"""
    global _celery_service
    if _celery_service is None:
        _celery_service = CeleryService()
    return _celery_service


# ========================================
# Celery Worker 入口點
# ========================================

def create_celery_app():
    """
    創建 Celery 應用（用於 worker 啟動）
    
    使用方式：
        celery -A services.celery_service:create_celery_app worker --loglevel=info
    """
    service = get_celery_service()
    if service.app:
        return service.app
    
    logger.warning("Celery app not available")
    return None


# 為 Celery worker 提供 app 實例
celery_app = None
if HAS_CELERY and os.getenv("CELERY_ENABLED", "false").lower() == "true":
    _service = get_celery_service()
    celery_app = _service.app
