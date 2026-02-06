# -*- coding: utf-8 -*-
"""
=============================================================================
Agentic Task Queue - 任務隊列系統
=============================================================================

Architecture V2 核心組件：管理 Manager Agent 的任務隊列

功能：
1. TodoTask 模型 - 單一任務定義
2. TaskQueue - 任務隊列管理
3. 狀態追蹤 - 任務生命週期管理
4. 依賴解析 - 確定任務執行順序

設計原則：
- 所有操作都是 async
- 錯誤不靜默處理（測試模式）
- 完整的狀態追蹤和事件發射

=============================================================================
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
import uuid

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TodoStatus(str, Enum):
    """任務狀態"""
    NOT_STARTED = "not_started"   # 尚未開始
    WAITING = "waiting"           # 等待依賴完成
    IN_PROGRESS = "in_progress"   # 執行中
    COMPLETED = "completed"       # 成功完成
    FAILED = "failed"             # 執行失敗
    CANCELLED = "cancelled"       # 已取消
    RETRYING = "retrying"         # 重試中


class TodoTask(BaseModel):
    """
    單一任務定義
    
    這是 Agentic AI 的基本工作單位。
    Manager 記錄並追蹤每個任務的狀態。
    """
    id: str = Field(default_factory=lambda: f"task_{uuid.uuid4().hex[:8]}")
    title: str = Field(description="任務標題（簡短描述）")
    description: str = Field(description="詳細描述（給 Agent 的指令）")
    
    # === 執行配置 ===
    assigned_agent: Optional[str] = Field(default=None, description="分配給哪個 Agent")
    depends_on: List[str] = Field(default_factory=list, description="依賴的任務 ID 列表")
    priority: int = Field(default=0, description="優先級（0=普通, >0=高優先）")
    
    # === 狀態追蹤 ===
    status: TodoStatus = Field(default=TodoStatus.NOT_STARTED)
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=5, description="最大重試次數")
    
    # === 結果 ===
    result: Optional[Dict[str, Any]] = Field(default=None, description="執行結果")
    error: Optional[str] = Field(default=None, description="錯誤信息")
    
    # === 時間戳 ===
    created_at: datetime = Field(default_factory=datetime.now)
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    
    # === 中間結果 ===
    can_show_to_user: bool = Field(default=False, description="是否可以推送給用戶")
    intermediate_message: Optional[str] = Field(default=None, description="可展示給用戶的中間消息")
    
    class Config:
        use_enum_values = True
    
    def is_terminal(self) -> bool:
        """任務是否已終結（成功或失敗）"""
        return self.status in [TodoStatus.COMPLETED, TodoStatus.FAILED, TodoStatus.CANCELLED]
    
    def can_retry(self) -> bool:
        """是否可以重試"""
        return self.status == TodoStatus.FAILED and self.retry_count < self.max_retries
    
    def mark_started(self):
        """標記為開始執行"""
        self.status = TodoStatus.IN_PROGRESS
        self.started_at = datetime.now()
    
    def mark_completed(self, result: Dict[str, Any], message: Optional[str] = None):
        """標記為完成"""
        self.status = TodoStatus.COMPLETED
        self.result = result
        self.completed_at = datetime.now()
        if message:
            self.intermediate_message = message
            self.can_show_to_user = True
    
    def mark_failed(self, error: str):
        """標記為失敗"""
        self.status = TodoStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()
    
    def mark_retry(self):
        """標記為重試"""
        self.retry_count += 1
        self.status = TodoStatus.RETRYING
        self.error = None
        self.started_at = None
        logger.info(f"[Task {self.id}] Retry {self.retry_count}/{self.max_retries}")


class TaskQueue:
    """
    Manager Agent 的任務隊列
    
    核心職責：
    1. 管理所有任務的生命週期
    2. 解析任務依賴關係
    3. 提供可執行任務列表
    4. 追蹤整體進度
    """
    
    def __init__(
        self, 
        goal: str,
        session_id: str,
        on_task_update: Optional[Callable[[TodoTask], Awaitable[None]]] = None
    ):
        self.goal = goal
        self.session_id = session_id
        self.tasks: Dict[str, TodoTask] = {}
        self.execution_order: List[str] = []  # 記錄執行順序
        self.on_task_update = on_task_update
        
        self.created_at = datetime.now()
        self.completed_at: Optional[datetime] = None
        
        logger.info(f"[TaskQueue] Created for goal: {goal[:50]}...")
    
    def add_task(self, task: TodoTask) -> str:
        """添加任務到隊列"""
        self.tasks[task.id] = task
        logger.info(f"[TaskQueue] Added task: {task.id} - {task.title}")
        return task.id
    
    def add_tasks(self, tasks: List[TodoTask]) -> List[str]:
        """批量添加任務"""
        ids = []
        for task in tasks:
            ids.append(self.add_task(task))
        return ids
    
    def get_task(self, task_id: str) -> Optional[TodoTask]:
        """獲取指定任務"""
        return self.tasks.get(task_id)
    
    def get_ready_tasks(self) -> List[TodoTask]:
        """
        獲取可以開始執行的任務
        
        條件：
        1. 狀態是 NOT_STARTED 或 RETRYING
        2. 所有依賴的任務都已完成
        """
        ready = []
        for task in self.tasks.values():
            if task.status not in [TodoStatus.NOT_STARTED, TodoStatus.RETRYING]:
                continue
            
            # 檢查依賴
            deps_satisfied = True
            for dep_id in task.depends_on:
                dep_task = self.tasks.get(dep_id)
                if dep_task is None or dep_task.status != TodoStatus.COMPLETED:
                    deps_satisfied = False
                    break
            
            if deps_satisfied:
                ready.append(task)
        
        # 按優先級排序
        ready.sort(key=lambda t: t.priority, reverse=True)
        return ready
    
    def get_in_progress(self) -> List[TodoTask]:
        """獲取正在執行的任務"""
        return [t for t in self.tasks.values() if t.status == TodoStatus.IN_PROGRESS]
    
    def get_completed(self) -> List[TodoTask]:
        """獲取已完成的任務"""
        return [t for t in self.tasks.values() if t.status == TodoStatus.COMPLETED]
    
    def get_failed(self) -> List[TodoTask]:
        """獲取失敗的任務"""
        return [t for t in self.tasks.values() if t.status == TodoStatus.FAILED]
    
    def get_retryable(self) -> List[TodoTask]:
        """獲取可重試的失敗任務"""
        return [t for t in self.tasks.values() if t.can_retry()]
    
    def has_all_completed(self) -> bool:
        """所有任務都成功完成"""
        if not self.tasks:
            return False
        return all(t.status == TodoStatus.COMPLETED for t in self.tasks.values())
    
    def has_terminal_failures(self) -> bool:
        """有無法重試的失敗任務"""
        return any(
            t.status == TodoStatus.FAILED and not t.can_retry()
            for t in self.tasks.values()
        )
    
    def is_terminal_state(self) -> bool:
        """
        隊列是否達到終結狀態
        
        終結條件：
        1. 所有任務都成功完成
        2. 有無法重試的失敗任務
        """
        if not self.tasks:
            return True
        return self.has_all_completed() or self.has_terminal_failures()
    
    def get_progress(self) -> Dict[str, Any]:
        """獲取整體進度"""
        total = len(self.tasks)
        if total == 0:
            return {"progress": 0, "completed": 0, "total": 0}
        
        completed = len(self.get_completed())
        in_progress = len(self.get_in_progress())
        failed = len(self.get_failed())
        
        return {
            "progress": int((completed / total) * 100),
            "completed": completed,
            "in_progress": in_progress,
            "failed": failed,
            "total": total,
            "is_terminal": self.is_terminal_state()
        }
    
    def summary(self) -> str:
        """生成隊列摘要"""
        progress = self.get_progress()
        return f"Goal: {self.goal[:30]}... | Progress: {progress['progress']}% ({progress['completed']}/{progress['total']})"
    
    async def update_task(self, task_id: str, **updates):
        """
        更新任務並發射事件
        
        NOTE: 這是核心更新方法，確保狀態變更被追蹤和廣播
        """
        task = self.tasks.get(task_id)
        if not task:
            raise ValueError(f"Task {task_id} not found")
        
        for key, value in updates.items():
            if hasattr(task, key):
                setattr(task, key, value)
        
        # 記錄執行順序
        if task.status == TodoStatus.IN_PROGRESS and task_id not in self.execution_order:
            self.execution_order.append(task_id)
        
        # 發射事件
        if self.on_task_update:
            await self.on_task_update(task)
        
        logger.debug(f"[TaskQueue] Task {task_id} updated: {task.status}")
    
    def get_all_results(self) -> Dict[str, Any]:
        """獲取所有任務的結果"""
        return {
            task_id: task.result
            for task_id, task in self.tasks.items()
            if task.result is not None
        }
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """獲取執行摘要（用於最終總結）"""
        return {
            "goal": self.goal,
            "session_id": self.session_id,
            "total_tasks": len(self.tasks),
            "completed_tasks": len(self.get_completed()),
            "failed_tasks": len(self.get_failed()),
            "execution_order": self.execution_order,
            "all_completed": self.has_all_completed(),
            "has_failures": self.has_terminal_failures(),
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "tasks": {
                task_id: {
                    "title": task.title,
                    "status": task.status,
                    "agent": task.assigned_agent,
                    "retry_count": task.retry_count,
                    "has_result": task.result is not None
                }
                for task_id, task in self.tasks.items()
            }
        }


class AgenticLoopState(str, Enum):
    """Agentic Loop 狀態"""
    IDLE = "idle"                     # 等待輸入
    GOAL_DETECTING = "goal_detecting" # 發現目標
    PLANNING = "planning"             # 產生計劃
    EXECUTING = "executing"           # 執行任務
    WAITING = "waiting"               # 等待子任務
    AGGREGATING = "aggregating"       # 收集結果
    SUMMARIZING = "summarizing"       # 生成總結
    DONE = "done"                     # 完成
    ERROR = "error"                   # 錯誤


@dataclass
class AgenticLoopContext:
    """
    Agentic Loop 上下文
    
    保持循環運行期間的所有狀態
    """
    session_id: str
    user_query: str
    goal: Optional[str] = None
    task_queue: Optional[TaskQueue] = None
    state: AgenticLoopState = AgenticLoopState.IDLE
    
    # 思考過程保留
    thinking_steps: List[Dict[str, Any]] = field(default_factory=list)
    
    # 中間結果
    intermediate_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # 最終結果
    final_summary: Optional[str] = None
    
    # 時間戳
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def add_thinking_step(self, step_type: str, content: str, metadata: Dict = None):
        """添加思考步驟"""
        self.thinking_steps.append({
            "type": step_type,
            "content": content,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        })
    
    def add_intermediate_result(self, task_id: str, result: Dict[str, Any], message: str):
        """添加中間結果（可推送給用戶）"""
        self.intermediate_results.append({
            "task_id": task_id,
            "result": result,
            "message": message,
            "timestamp": datetime.now().isoformat()
        })


# =============================================================================
# 工廠函數
# =============================================================================

def create_task_queue(goal: str, session_id: str, on_update: Callable = None) -> TaskQueue:
    """創建任務隊列"""
    return TaskQueue(goal=goal, session_id=session_id, on_task_update=on_update)


def create_todo_task(
    title: str,
    description: str,
    agent: str = None,
    depends_on: List[str] = None,
    priority: int = 0
) -> TodoTask:
    """創建單一任務"""
    return TodoTask(
        title=title,
        description=description,
        assigned_agent=agent,
        depends_on=depends_on or [],
        priority=priority
    )
