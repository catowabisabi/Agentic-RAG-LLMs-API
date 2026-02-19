# -*- coding: utf-8 -*-
"""
=============================================================================
背景任務管理器 (Background Task Manager)
=============================================================================

功能說明：
-----------
管理異步背景任務，即使用戶離開頁面也能繼續運行。

工作流程：
-----------
1. 用戶提交任務 → 立即返回 task_id
2. 任務在背景運行 → 狀態存儲在內存/Redis
3. 用戶可以輪詢狀態或接收 WebSocket 更新
4. 結果被存儲，隨時可檢索

任務狀態 (TaskStatus)：
-----------
- PENDING   : 已創建，等待開始
- RUNNING   : 正在處理
- COMPLETED : 成功完成
- FAILED    : 執行失敗
- CANCELLED : 已取消

使用方式：
-----------
from services import task_manager, TaskStatus

# 創建任務
task_id = task_manager.create_task("chat", {"message": "Hello"})

# 獲取任務狀態
result = task_manager.get_task(task_id)

# 更新進度
task_manager.update_progress(task_id, 50, "處理中...", ["manager_agent"])

# 完成任務
task_manager.complete_task(task_id, result_data)


=============================================================================
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field, asdict
import uuid
import traceback

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status enumeration"""
    PENDING = "pending"       # Task created, waiting to start
    RUNNING = "running"       # Task is being processed
    COMPLETED = "completed"   # Task finished successfully
    FAILED = "failed"         # Task failed with error
    CANCELLED = "cancelled"   # Task was cancelled


@dataclass
class TaskResult:
    """Stores task execution result"""
    task_id: str
    status: TaskStatus
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # Input
    task_type: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)
    
    # Progress
    progress: float = 0.0  # 0-100
    current_step: str = ""
    agents_involved: List[str] = field(default_factory=list)
    thinking_steps: List[Dict[str, Any]] = field(default_factory=list)
    
    # Output
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BackgroundTaskManager:
    """
    Singleton manager for background tasks.
    
    Features:
    - Submit tasks that run independently
    - Track task progress and status
    - Store results for later retrieval
    - WebSocket notifications for real-time updates
    - Automatic cleanup of old tasks
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
        self._tasks: Dict[str, TaskResult] = {}
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._max_tasks = 1000  # Max stored tasks
        self._task_ttl = 3600 * 24  # Keep tasks for 24 hours
        
        logger.info("BackgroundTaskManager initialized")
    
    def create_task(
        self,
        task_type: str,
        input_data: Dict[str, Any]
    ) -> str:
        """
        Create a new task and return its ID.
        The task is not started yet - call run_task() to start it.
        """
        task_id = str(uuid.uuid4())
        
        task = TaskResult(
            task_id=task_id,
            status=TaskStatus.PENDING,
            created_at=datetime.now().isoformat(),
            task_type=task_type,
            input_data=input_data
        )
        
        self._tasks[task_id] = task
        self._cleanup_old_tasks()
        
        logger.info(f"Created task {task_id} of type {task_type}")
        return task_id
    
    async def run_task(
        self,
        task_id: str,
        handler: Callable,
        *args,
        **kwargs
    ) -> None:
        """
        Start running a task in the background.
        
        Args:
            task_id: The task ID
            handler: Async function to execute
            *args, **kwargs: Arguments to pass to handler
        """
        if task_id not in self._tasks:
            raise ValueError(f"Task {task_id} not found")
        
        task = self._tasks[task_id]
        
        async def _execute():
            try:
                # Update status to running
                task.status = TaskStatus.RUNNING
                task.started_at = datetime.now().isoformat()
                task.current_step = "Starting..."
                
                # Notify via WebSocket
                await self._notify_update(task)
                
                # Execute the handler
                result = await handler(task_id, *args, **kwargs)
                
                # Update with result
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.now().isoformat()
                task.progress = 100.0
                task.current_step = "Completed"
                task.result = result if isinstance(result, dict) else {"response": str(result)}
                
                logger.info(f"Task {task_id} completed successfully")
                
            except asyncio.CancelledError:
                task.status = TaskStatus.CANCELLED
                task.completed_at = datetime.now().isoformat()
                task.current_step = "Cancelled"
                logger.info(f"Task {task_id} was cancelled")
                
            except Exception as e:
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now().isoformat()
                task.error = str(e)
                task.current_step = f"Failed: {str(e)}"
                logger.error(f"Task {task_id} failed: {e}", exc_info=True)
            
            finally:
                # Final notification
                await self._notify_update(task)
                
                # Remove from running tasks
                if task_id in self._running_tasks:
                    del self._running_tasks[task_id]
        
        # Create and store the asyncio task
        asyncio_task = asyncio.create_task(_execute())
        self._running_tasks[task_id] = asyncio_task
    
    def get_task(self, task_id: str) -> Optional[TaskResult]:
        """Get task by ID"""
        return self._tasks.get(task_id)
    
    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task status as dictionary"""
        task = self._tasks.get(task_id)
        if task:
            return task.to_dict()
        return None
    
    def update_progress(
        self,
        task_id: str,
        progress: float,
        current_step: str = "",
        agents: List[str] = None,
        thinking_step: Dict[str, Any] = None
    ) -> None:
        """Update task progress (called from within task handler)"""
        task = self._tasks.get(task_id)
        if not task:
            return
        
        task.progress = min(progress, 99.9)  # Keep < 100 until complete
        if current_step:
            task.current_step = current_step
        if agents:
            task.agents_involved = list(set(task.agents_involved + agents))
        if thinking_step:
            task.thinking_steps.append(thinking_step)
        
        # Fire-and-forget notification
        asyncio.create_task(self._notify_update(task))
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task"""
        if task_id in self._running_tasks:
            self._running_tasks[task_id].cancel()
            return True
        return False
    
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """List tasks, optionally filtered by status"""
        tasks = list(self._tasks.values())
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        # Sort by created_at descending
        tasks.sort(key=lambda t: t.created_at, reverse=True)
        
        return [t.to_dict() for t in tasks[:limit]]
    
    async def _notify_update(self, task: TaskResult) -> None:
        """Send WebSocket notification about task update"""
        try:
            from agents.shared_services.websocket_manager import WebSocketManager
            ws_manager = WebSocketManager()
            
            await ws_manager.broadcast_agent_activity({
                "type": "task_update",
                "task_id": task.task_id,
                "status": task.status.value,
                "progress": task.progress,
                "current_step": task.current_step,
                "agents_involved": task.agents_involved,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.debug(f"Failed to send WebSocket notification: {e}")
    
    def _cleanup_old_tasks(self) -> None:
        """Remove old completed/failed tasks"""
        if len(self._tasks) <= self._max_tasks:
            return
        
        now = datetime.now()
        to_remove = []
        
        for task_id, task in self._tasks.items():
            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                try:
                    completed_at = datetime.fromisoformat(task.completed_at or task.created_at)
                    if (now - completed_at).total_seconds() > self._task_ttl:
                        to_remove.append(task_id)
                except (ValueError, TypeError):
                    pass
        
        for task_id in to_remove:
            del self._tasks[task_id]
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} old tasks")


# Singleton instance
task_manager = BackgroundTaskManager()
