# -*- coding: utf-8 -*-
"""
=============================================================================
事件總線 - 即時多代理通訊系統 (Event Bus)
=============================================================================

功能說明：
-----------
中央事件系統，實現多代理之間的即時通訊和狀態同步。

核心功能：
-----------
1. 即時代理狀態更新廣播到所有前端
2. 非阻塞事件廣播機制
3. 活動日誌和歷史記錄
4. 中斷信號傳播

架構圖：
-----------
    ┌──────────────────────────────────────────────────────────┐
    │                    Event Bus (Singleton)                  │
    │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐         │
    │  │  Event      │ │  Activity   │ │  Status     │         │
    │  │  Queue      │ │  History    │ │  Registry   │         │
    │  └─────────────┘ └─────────────┘ └─────────────┘         │
    │                       │                                   │
    │              ┌────────┴────────┐                         │
    │              │  Broadcast Loop │ (async background task) │
    │              └────────┬────────┘                         │
    └──────────────────────-│──────────────────────────────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
    ┌────┴────┐        ┌────┴────┐        ┌────┴────┐
    │Dashboard│        │  Chat   │        │  Agents │
    └─────────┘        └─────────┘        └─────────┘

事件類型 (EventType)：
-----------
- AGENT_* : 代理生命週期事件
- TASK_*  : 任務生命週期事件
- THINKING/PLANNING : 代理思考過程
- RAG_*   : RAG 查詢和結果
- LLM_*   : LLM 調用事件

代理狀態 (AgentState)：
-----------
- IDLE      : 閒置
- WORKING   : 工作中
- THINKING  : 思考中
- CALLING_LLM : 調用 LLM
- QUERYING_RAG : 查詢 RAG

使用方式：
-----------
from services import event_bus, EventType, AgentState

# 發送事件
await event_bus.emit(EventType.TASK_COMPLETED, agent_name, data)

# 更新狀態
await event_bus.update_status(agent_name, AgentState.WORKING)

=============================================================================
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Callable, Awaitable
from enum import Enum
from dataclasses import dataclass, field
from collections import deque
import uuid

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events in the system"""
    # Agent lifecycle
    AGENT_STARTED = "agent_started"
    AGENT_STOPPED = "agent_stopped"
    AGENT_STATUS_CHANGED = "agent_status_changed"
    
    # Task lifecycle
    TASK_CREATED = "task_created"
    TASK_ASSIGNED = "task_assigned"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"
    
    # Agent activities
    THINKING = "thinking"
    PLANNING = "planning"
    PLAN_STEP = "plan_step"
    RAG_QUERY = "rag_query"
    RAG_RESULT = "rag_result"
    LLM_CALL_START = "llm_call_start"
    LLM_CALL_END = "llm_call_end"
    LLM_STREAMING = "llm_streaming"
    
    # Communication
    AGENT_MESSAGE = "agent_message"
    AGENT_RESPONSE = "agent_response"
    
    # System
    INTERRUPT_REQUESTED = "interrupt_requested"
    INTERRUPT_ACKNOWLEDGED = "interrupt_acknowledged"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class AgentState(str, Enum):
    """Agent operational states"""
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"  # Waiting for other agent
    THINKING = "thinking"
    CALLING_LLM = "calling_llm"
    QUERYING_RAG = "querying_rag"
    INTERRUPTED = "interrupted"
    ERROR = "error"


@dataclass
class Event:
    """A single event in the system"""
    event_id: str
    event_type: EventType
    agent_name: str
    timestamp: str
    data: Dict[str, Any]
    task_id: Optional[str] = None
    session_id: Optional[str] = None
    priority: int = 1
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "agent_name": self.agent_name,
            "timestamp": self.timestamp,
            "data": self.data,
            "task_id": self.task_id,
            "session_id": self.session_id,
            "priority": self.priority
        }


@dataclass
class AgentStatus:
    """Current status of an agent"""
    agent_name: str
    state: AgentState
    current_task: Optional[str] = None
    current_step: Optional[str] = None
    progress: float = 0.0
    last_activity: Optional[str] = None
    message: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "state": self.state.value,
            "current_task": self.current_task,
            "current_step": self.current_step,
            "progress": self.progress,
            "last_activity": self.last_activity,
            "message": self.message,
            "error": self.error,
            "started_at": self.started_at,
            "updated_at": self.updated_at
        }


class EventBus:
    """
    Central event bus for the multi-agent system.
    
    This is a singleton that:
    - Manages agent status in real-time
    - Broadcasts events to all connected WebSocket clients
    - Maintains activity history for each agent
    - Handles interrupt signals
    
    Usage:
        bus = EventBus()
        
        # Emit an event
        await bus.emit(EventType.AGENT_STARTED, "manager_agent", {"task": "process_query"})
        
        # Update agent status
        await bus.update_status("manager_agent", AgentState.WORKING, task_id="123", message="Processing...")
        
        # Get agent status
        status = bus.get_agent_status("manager_agent")
        
        # Get activity history
        history = bus.get_activity_history("manager_agent", limit=50)
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
        
        # Event queue for broadcasting
        self._event_queue: asyncio.Queue = asyncio.Queue()
        
        # Agent status registry
        self._agent_statuses: Dict[str, AgentStatus] = {}
        
        # Activity history per agent (last 100 events each)
        self._agent_history: Dict[str, deque] = {}
        
        # Global activity history (last 500 events)
        self._global_history: deque = deque(maxlen=500)
        
        # WebSocket broadcast function (set by WebSocketManager)
        self._broadcast_fn: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
        
        # Interrupt flags per task
        self._interrupt_flags: Dict[str, bool] = {}
        
        # Event subscribers: event_type -> list of callbacks
        self._subscribers: Dict[EventType, List[Callable[[Event], Awaitable[None]]]] = {}
        
        # Background task for broadcasting
        self._broadcast_task: Optional[asyncio.Task] = None
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        logger.info("EventBus initialized")
    
    def set_broadcast_function(self, fn: Callable[[Dict[str, Any]], Awaitable[None]]):
        """Set the function used to broadcast to WebSocket clients"""
        self._broadcast_fn = fn
        logger.info("EventBus broadcast function set")
    
    async def start(self):
        """Start the event bus background task"""
        if self._broadcast_task is None or self._broadcast_task.done():
            self._broadcast_task = asyncio.create_task(self._broadcast_loop())
            logger.info("EventBus broadcast loop started")
    
    async def stop(self):
        """Stop the event bus"""
        if self._broadcast_task:
            self._broadcast_task.cancel()
            try:
                await self._broadcast_task
            except asyncio.CancelledError:
                pass
            self._broadcast_task = None
        logger.info("EventBus stopped")
    
    async def _broadcast_loop(self):
        """Background loop that broadcasts events to clients"""
        while True:
            try:
                # Get event from queue (with timeout for heartbeat)
                try:
                    event = await asyncio.wait_for(
                        self._event_queue.get(),
                        timeout=5.0
                    )
                    
                    # Broadcast to WebSocket clients
                    if self._broadcast_fn:
                        try:
                            await self._broadcast_fn(event.to_dict())
                        except Exception as e:
                            logger.error(f"Error broadcasting event: {e}")
                    
                    # Notify subscribers
                    if event.event_type in self._subscribers:
                        for callback in self._subscribers[event.event_type]:
                            try:
                                await callback(event)
                            except Exception as e:
                                logger.error(f"Error in event subscriber: {e}")
                    
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connections alive
                    if self._broadcast_fn:
                        try:
                            await self._broadcast_fn({
                                "event_type": "heartbeat",
                                "timestamp": datetime.now().isoformat(),
                                "agents": {
                                    name: status.to_dict() 
                                    for name, status in self._agent_statuses.items()
                                }
                            })
                        except Exception:
                            pass
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in broadcast loop: {e}")
                await asyncio.sleep(1)
    
    # ============== Event Emission ==============
    
    async def emit(
        self,
        event_type: EventType,
        agent_name: str,
        data: Dict[str, Any] = None,
        task_id: str = None,
        session_id: str = None,
        priority: int = 1
    ) -> Event:
        """
        Emit an event to the event bus.
        
        This is the main method for agents to report their activities.
        Events are queued and broadcast asynchronously.
        """
        event = Event(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            agent_name=agent_name,
            timestamp=datetime.now().isoformat(),
            data=data or {},
            task_id=task_id,
            session_id=session_id,
            priority=priority
        )
        
        # Store in history
        async with self._lock:
            self._global_history.append(event)
            if agent_name not in self._agent_history:
                self._agent_history[agent_name] = deque(maxlen=100)
            self._agent_history[agent_name].append(event)
        
        # Queue for broadcasting
        await self._event_queue.put(event)
        
        logger.debug(f"Event emitted: {event_type.value} from {agent_name}")
        return event
    
    async def emit_thinking(
        self,
        agent_name: str,
        thought: str,
        step: int = None,
        task_id: str = None
    ):
        """Convenience method for emitting thinking events"""
        await self.emit(
            EventType.THINKING,
            agent_name,
            {"thought": thought, "step": step},
            task_id=task_id
        )
    
    async def emit_plan_step(
        self,
        agent_name: str,
        step_number: int,
        step_description: str,
        target_agent: str = None,
        task_id: str = None
    ):
        """Emit a planning step"""
        await self.emit(
            EventType.PLAN_STEP,
            agent_name,
            {
                "step_number": step_number,
                "description": step_description,
                "target_agent": target_agent
            },
            task_id=task_id
        )
    
    async def emit_llm_streaming(
        self,
        agent_name: str,
        token: str,
        is_complete: bool = False,
        task_id: str = None
    ):
        """Emit a streaming LLM token"""
        await self.emit(
            EventType.LLM_STREAMING,
            agent_name,
            {"token": token, "is_complete": is_complete},
            task_id=task_id,
            priority=0  # Lower priority for streaming
        )
    
    # ============== Agent Status Management ==============
    
    async def update_status(
        self,
        agent_name: str,
        state: AgentState,
        task_id: str = None,
        step: str = None,
        progress: float = None,
        message: str = None,
        error: str = None
    ):
        """Update an agent's status and broadcast the change"""
        now = datetime.now().isoformat()
        
        async with self._lock:
            if agent_name not in self._agent_statuses:
                self._agent_statuses[agent_name] = AgentStatus(
                    agent_name=agent_name,
                    state=AgentState.IDLE,
                    started_at=now
                )
            
            status = self._agent_statuses[agent_name]
            status.state = state
            status.updated_at = now
            
            if task_id is not None:
                status.current_task = task_id
            if step is not None:
                status.current_step = step
            if progress is not None:
                status.progress = progress
            if message is not None:
                status.message = message
            if error is not None:
                status.error = error
            
            status.last_activity = now
        
        # Emit status change event
        await self.emit(
            EventType.AGENT_STATUS_CHANGED,
            agent_name,
            status.to_dict(),
            task_id=task_id
        )
    
    def register_agent(self, agent_name: str, role: str = None, description: str = None):
        """Register an agent with the event bus"""
        now = datetime.now().isoformat()
        self._agent_statuses[agent_name] = AgentStatus(
            agent_name=agent_name,
            state=AgentState.IDLE,
            started_at=now,
            updated_at=now
        )
        self._agent_history[agent_name] = deque(maxlen=100)
        logger.info(f"Agent registered with EventBus: {agent_name}")
    
    def get_agent_status(self, agent_name: str) -> Optional[AgentStatus]:
        """Get current status of an agent"""
        return self._agent_statuses.get(agent_name)
    
    def get_all_agent_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all agents"""
        return {
            name: status.to_dict() 
            for name, status in self._agent_statuses.items()
        }
    
    def get_activity_history(
        self, 
        agent_name: str = None, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get activity history for an agent or global"""
        if agent_name and agent_name in self._agent_history:
            history = list(self._agent_history[agent_name])
        else:
            history = list(self._global_history)
        
        # Return most recent first, limited
        return [e.to_dict() for e in reversed(history)][:limit]
    
    # ============== Interrupt System ==============
    
    async def request_interrupt(
        self, 
        task_id: str = None, 
        agent_name: str = None,
        reason: str = "User requested interrupt"
    ):
        """Request to interrupt a task or agent"""
        if task_id:
            self._interrupt_flags[task_id] = True
        
        await self.emit(
            EventType.INTERRUPT_REQUESTED,
            agent_name or "system",
            {"task_id": task_id, "reason": reason},
            task_id=task_id,
            priority=3  # High priority
        )
        
        logger.warning(f"Interrupt requested: task={task_id}, agent={agent_name}, reason={reason}")
    
    def is_interrupted(self, task_id: str) -> bool:
        """Check if a task has been interrupted"""
        return self._interrupt_flags.get(task_id, False)
    
    def clear_interrupt(self, task_id: str):
        """Clear interrupt flag for a task"""
        self._interrupt_flags.pop(task_id, None)
    
    async def acknowledge_interrupt(self, agent_name: str, task_id: str):
        """Acknowledge that an interrupt was processed"""
        await self.emit(
            EventType.INTERRUPT_ACKNOWLEDGED,
            agent_name,
            {"task_id": task_id},
            task_id=task_id
        )
    
    # ============== Subscriptions ==============
    
    def subscribe(
        self, 
        event_type: EventType, 
        callback: Callable[[Event], Awaitable[None]]
    ):
        """Subscribe to events of a specific type"""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)
    
    def unsubscribe(
        self, 
        event_type: EventType, 
        callback: Callable[[Event], Awaitable[None]]
    ):
        """Unsubscribe from events"""
        if event_type in self._subscribers:
            self._subscribers[event_type] = [
                cb for cb in self._subscribers[event_type] if cb != callback
            ]


# Global instance
event_bus = EventBus()
