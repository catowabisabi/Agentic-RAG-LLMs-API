# -*- coding: utf-8 -*-
"""
=============================================================================
Task Planning Models - 任務規劃模型
=============================================================================

定義 Manager Agent 使用的規劃和 Todo 模型

=============================================================================
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
import uuid


class TaskStatus(str, Enum):
    """Task/Todo status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING = "waiting"  # Waiting for dependency
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskPriority(str, Enum):
    """Task priority"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class TodoItem(BaseModel):
    """A single todo item in the execution plan"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = Field(description="Short title of the task")
    description: str = Field(default="", description="Detailed description")
    agent: str = Field(description="Target agent to execute this task")
    task_type: str = Field(description="Type of task for the agent")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    
    # Dependencies
    depends_on: List[str] = Field(default_factory=list, description="IDs of tasks this depends on")
    
    # Execution info
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    # Input/Output
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    
    def to_ui_dict(self) -> Dict[str, Any]:
        """Convert to UI-friendly dict"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "agent": self.agent,
            "task_type": self.task_type,
            "priority": self.priority.value,
            "status": self.status.value,
            "depends_on": self.depends_on,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "has_result": self.result is not None,
            "has_error": self.error is not None
        }


class ExecutionPlan(BaseModel):
    """The full execution plan with todos"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    query: str = Field(description="Original user query")
    goal: str = Field(description="High-level goal")
    strategy: str = Field(default="", description="Execution strategy")
    
    todos: List[TodoItem] = Field(default_factory=list)
    
    # Execution state
    current_step: int = Field(default=0)
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    
    # Results
    final_response: Optional[str] = None
    collected_data: Dict[str, Any] = Field(default_factory=dict)
    
    def get_next_todo(self) -> Optional[TodoItem]:
        """Get the next pending todo that has all dependencies satisfied"""
        completed_ids = {t.id for t in self.todos if t.status == TaskStatus.COMPLETED}
        
        for todo in self.todos:
            if todo.status == TaskStatus.PENDING:
                # Check if all dependencies are completed
                if all(dep_id in completed_ids for dep_id in todo.depends_on):
                    return todo
        return None
    
    def get_running_todos(self) -> List[TodoItem]:
        """Get todos currently in progress"""
        return [t for t in self.todos if t.status == TaskStatus.IN_PROGRESS]
    
    def mark_todo_started(self, todo_id: str):
        """Mark a todo as started"""
        for todo in self.todos:
            if todo.id == todo_id:
                todo.status = TaskStatus.IN_PROGRESS
                todo.started_at = datetime.now()
                self.updated_at = datetime.now()
                break
    
    def mark_todo_completed(self, todo_id: str, result: Dict[str, Any] = None):
        """Mark a todo as completed"""
        for todo in self.todos:
            if todo.id == todo_id:
                todo.status = TaskStatus.COMPLETED
                todo.completed_at = datetime.now()
                todo.result = result
                if result:
                    todo.output_data = result
                self.updated_at = datetime.now()
                break
        
        # Check if all todos are completed
        if all(t.status == TaskStatus.COMPLETED for t in self.todos):
            self.status = TaskStatus.COMPLETED
    
    def mark_todo_failed(self, todo_id: str, error: str):
        """Mark a todo as failed"""
        for todo in self.todos:
            if todo.id == todo_id:
                todo.status = TaskStatus.FAILED
                todo.error = error
                self.updated_at = datetime.now()
                break
    
    def add_todo(self, todo: TodoItem):
        """Add a new todo to the plan"""
        self.todos.append(todo)
        self.updated_at = datetime.now()
    
    def get_progress(self) -> Dict[str, Any]:
        """Get execution progress"""
        total = len(self.todos)
        completed = sum(1 for t in self.todos if t.status == TaskStatus.COMPLETED)
        in_progress = sum(1 for t in self.todos if t.status == TaskStatus.IN_PROGRESS)
        pending = sum(1 for t in self.todos if t.status == TaskStatus.PENDING)
        failed = sum(1 for t in self.todos if t.status == TaskStatus.FAILED)
        
        return {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "failed": failed,
            "percentage": (completed / total * 100) if total > 0 else 0
        }
    
    def to_ui_dict(self) -> Dict[str, Any]:
        """Convert to UI-friendly dict for WebSocket broadcast"""
        return {
            "id": self.id,
            "query": self.query,
            "goal": self.goal,
            "strategy": self.strategy,
            "status": self.status.value,
            "progress": self.get_progress(),
            "todos": [t.to_ui_dict() for t in self.todos],
            "current_step": self.current_step,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class PlanningRequest(BaseModel):
    """Request to planning agent"""
    query: str
    context: str = ""
    user_context: str = ""
    chat_history: List[Dict[str, str]] = Field(default_factory=list)
    available_agents: List[str] = Field(default_factory=list)


class PlanningResponse(BaseModel):
    """Response from planning agent"""
    goal: str = Field(description="The main goal to achieve")
    strategy: str = Field(description="High-level strategy")
    todos: List[Dict[str, Any]] = Field(description="List of todo items")
    estimated_steps: int = Field(default=1)
    complexity: str = Field(default="simple")  # simple, medium, complex
