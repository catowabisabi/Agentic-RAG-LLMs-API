"""
Message Protocol for Multi-Agent Communication

Defines the standard message format and types for WebSocket communication
between agents and with the frontend.
"""

from enum import Enum
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class MessageType(str, Enum):
    """Types of messages that can be sent between agents"""
    # Agent lifecycle
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_ERROR = "agent_error"
    AGENT_INTERRUPTED = "agent_interrupted"
    
    # Task management
    TASK_ASSIGNED = "task_assigned"
    TASK_PROGRESS = "task_progress"
    TASK_RESULT = "task_result"
    
    # Communication
    QUERY = "query"
    RESPONSE = "response"
    STREAM_CHUNK = "stream_chunk"
    STREAM_END = "stream_end"
    
    # Control
    INTERRUPT = "interrupt"
    ROLE_CORRECTION = "role_correction"
    VALIDATION_ERROR = "validation_error"
    REQUEST_RETRY = "request_retry"
    
    # System
    HEARTBEAT = "heartbeat"
    STATUS_UPDATE = "status_update"
    RAG_CHECK = "rag_check"
    RAG_RESULT = "rag_result"
    
    # Memory & Notes
    NOTE_CREATED = "note_created"
    MEMORY_STORED = "memory_stored"
    MEMORY_RETRIEVED = "memory_retrieved"


class AgentStatus(str, Enum):
    """Status of an agent"""
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    ERROR = "error"
    INTERRUPTED = "interrupted"


class AgentMessage(BaseModel):
    """Standard message format for agent communication"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType
    source_agent: str
    target_agent: Optional[str] = None  # None means broadcast
    content: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    correlation_id: Optional[str] = None  # For tracking related messages
    priority: int = Field(default=5, ge=1, le=10)  # 1=highest, 10=lowest
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


class RoleAssignment(BaseModel):
    """Role assignment message content"""
    role_name: str
    role_description: str
    expected_output: str
    constraints: List[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """Validation result message content"""
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    error_count: int = 0
    should_retry: bool = False


class TaskAssignment(BaseModel):
    """Task assignment message content"""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str
    description: str
    input_data: Dict[str, Any] = Field(default_factory=dict)
    expected_output_format: Optional[str] = None
    timeout_seconds: int = 300
    retry_count: int = 0
    max_retries: int = 3


class InterruptCommand(BaseModel):
    """Interrupt command from manager"""
    reason: str
    action: str  # "stop", "restart", "reassign"
    new_assignment: Optional[TaskAssignment] = None


class MessageProtocol:
    """Helper class for creating standardized messages"""
    
    @staticmethod
    def create_agent_started(agent_name: str, task_info: Dict[str, Any] = None) -> AgentMessage:
        return AgentMessage(
            type=MessageType.AGENT_STARTED,
            source_agent=agent_name,
            content={
                "status": AgentStatus.WORKING.value,
                "task_info": task_info or {}
            }
        )
    
    @staticmethod
    def create_agent_completed(agent_name: str, result: Any, task_id: str = None) -> AgentMessage:
        return AgentMessage(
            type=MessageType.AGENT_COMPLETED,
            source_agent=agent_name,
            content={
                "status": AgentStatus.IDLE.value,
                "result": result,
                "task_id": task_id
            }
        )
    
    @staticmethod
    def create_error(agent_name: str, error: str, details: Dict = None) -> AgentMessage:
        return AgentMessage(
            type=MessageType.AGENT_ERROR,
            source_agent=agent_name,
            content={
                "error": error,
                "details": details or {},
                "status": AgentStatus.ERROR.value
            },
            priority=2
        )
    
    @staticmethod
    def create_interrupt(source: str, target: str, reason: str, action: str = "stop") -> AgentMessage:
        return AgentMessage(
            type=MessageType.INTERRUPT,
            source_agent=source,
            target_agent=target,
            content=InterruptCommand(reason=reason, action=action).model_dump(),
            priority=1
        )
    
    @staticmethod
    def create_role_correction(
        source: str, 
        target: str, 
        role: RoleAssignment,
        error_description: str
    ) -> AgentMessage:
        return AgentMessage(
            type=MessageType.ROLE_CORRECTION,
            source_agent=source,
            target_agent=target,
            content={
                "role": role.model_dump(),
                "error_description": error_description
            },
            priority=2
        )
    
    @staticmethod
    def create_stream_chunk(agent_name: str, content: str, chunk_index: int) -> AgentMessage:
        return AgentMessage(
            type=MessageType.STREAM_CHUNK,
            source_agent=agent_name,
            content={
                "text": content,
                "chunk_index": chunk_index
            }
        )
    
    @staticmethod
    def create_task_assignment(
        source: str,
        target: str,
        task: TaskAssignment
    ) -> AgentMessage:
        return AgentMessage(
            type=MessageType.TASK_ASSIGNED,
            source_agent=source,
            target_agent=target,
            content=task.model_dump()
        )
    
    @staticmethod
    def create_rag_check(agent_name: str, query: str) -> AgentMessage:
        return AgentMessage(
            type=MessageType.RAG_CHECK,
            source_agent=agent_name,
            target_agent="rag_agent",
            content={"query": query}
        )
    
    @staticmethod
    def create_status_update(
        agent_name: str, 
        status: AgentStatus,
        progress: float = None,
        message: str = None
    ) -> AgentMessage:
        return AgentMessage(
            type=MessageType.STATUS_UPDATE,
            source_agent=agent_name,
            content={
                "status": status.value,
                "progress": progress,
                "message": message
            }
        )
