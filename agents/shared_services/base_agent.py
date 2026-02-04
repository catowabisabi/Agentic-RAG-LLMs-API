# -*- coding: utf-8 -*-
"""
=============================================================================
代理基類 (Base Agent Class)
=============================================================================

結構說明：
-----------
所有代理的抽象基類，提供通用功能：
- WebSocket 通訊
- 訊息處理
- 生命週期管理
- EventBus 即時狀態更新

核心方法：
-----------
1. process_task(task)    : [抽象] 處理任務（必須實現）
2. start()               : 啟動代理
3. stop()                : 停止代理
4. send_message(msg)     : 發送訊息給其他代理
5. broadcast_status()    : 廣播狀態更新

生命週期：
-----------
初始化 → start() → process_task() → stop()

繼承使用：
-----------
from agents.shared_services.base_agent import BaseAgent

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_name="my_agent",
            agent_role="My Role",
            agent_description="我的代理描述"
        )
    
    async def process_task(self, task: TaskAssignment) -> Dict[str, Any]:
        # 處理任務邏輯
        return {"response": "完成"}

=============================================================================
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime

from .message_protocol import (
    AgentMessage,
    MessageType,
    MessageProtocol,
    AgentStatus,
    TaskAssignment,
    ValidationResult
)
from .websocket_manager import WebSocketManager

# Import EventBus for real-time updates
try:
    from services.event_bus import event_bus, EventType, AgentState
    HAS_EVENT_BUS = True
except ImportError:
    HAS_EVENT_BUS = False
    event_bus = None

# Import new Service Layer
try:
    from services.llm_service import get_llm_service, LLMService
    from services.rag_service import get_rag_service, RAGService
    from services.broadcast_service import get_broadcast_service, BroadcastService
    from services.prompt_manager import get_prompt_manager, PromptManager
    HAS_SERVICE_LAYER = True
except ImportError:
    HAS_SERVICE_LAYER = False
    get_llm_service = None
    get_rag_service = None
    get_broadcast_service = None
    get_prompt_manager = None

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    Each agent should:
    1. Inherit from this class
    2. Implement the process_task method
    3. Define its role and capabilities
    
    Now supports Service Layer dependency injection:
    - llm_service: Unified LLM service
    - rag_service: Unified RAG service
    - broadcast_service: Unified WebSocket broadcasting
    - prompt_manager: Prompt template management
    """
    
    def __init__(
        self,
        agent_name: str,
        agent_role: str,
        agent_description: str = "",
        llm_service: Optional[LLMService] = None,
        rag_service: Optional[RAGService] = None,
        broadcast_service: Optional[BroadcastService] = None,
        prompt_manager: Optional[PromptManager] = None
    ):
        self.agent_name = agent_name
        self.agent_role = agent_role
        self.agent_description = agent_description
        
        self.ws_manager = WebSocketManager()
        self.message_queue: Optional[asyncio.Queue] = None
        self.message_history: List[AgentMessage] = []
        
        self.status = AgentStatus.IDLE
        self.current_task: Optional[TaskAssignment] = None
        self.is_running = False
        self.should_stop = False
        
        # Error tracking
        self.consecutive_errors = 0
        self.max_consecutive_errors = 3
        
        # Service Layer (使用依賴注入或默認單例)
        if HAS_SERVICE_LAYER:
            self.llm_service = llm_service or get_llm_service()
            self.rag_service = rag_service or get_rag_service()
            self.broadcast = broadcast_service or get_broadcast_service()
            self.prompt_manager = prompt_manager or get_prompt_manager()
        else:
            self.llm_service = None
            self.rag_service = None
            self.broadcast = None
            self.prompt_manager = None
        
        # Message handlers for specific message types
        self._message_handlers: Dict[MessageType, Callable] = {
            MessageType.INTERRUPT: self._handle_interrupt,
            MessageType.TASK_ASSIGNED: self._handle_task_assignment,
            MessageType.ROLE_CORRECTION: self._handle_role_correction,
            MessageType.RAG_RESULT: self._handle_rag_result,
        }
        
        logger.info(f"Agent initialized: {agent_name} ({agent_role})")
        
        # Register with EventBus
        if HAS_EVENT_BUS and event_bus:
            event_bus.register_agent(agent_name, agent_role, agent_description)
    
    # ============== Lifecycle Methods ==============
    
    async def start(self):
        """Start the agent and begin processing messages"""
        self.message_queue = await self.ws_manager.register_agent(self.agent_name)
        self.is_running = True
        self.should_stop = False
        
        await self._update_status(AgentStatus.IDLE)
        
        # Emit start event
        if HAS_EVENT_BUS and event_bus:
            await event_bus.emit(
                EventType.AGENT_STARTED,
                self.agent_name,
                {"role": self.agent_role, "description": self.agent_description}
            )
        
        # Start message processing loop
        asyncio.create_task(self._message_loop())
        
        logger.info(f"Agent started: {self.agent_name}")
    
    async def stop(self):
        """Stop the agent gracefully"""
        self.should_stop = True
        self.is_running = False
        
        # Emit stop event
        if HAS_EVENT_BUS and event_bus:
            await event_bus.emit(
                EventType.AGENT_STOPPED,
                self.agent_name,
                {"reason": "graceful_shutdown"}
            )
        
        await self.ws_manager.unregister_agent(self.agent_name)
        
        logger.info(f"Agent stopped: {self.agent_name}")
    
    async def _message_loop(self):
        """Main message processing loop"""
        while self.is_running and not self.should_stop:
            try:
                # Wait for messages with timeout
                try:
                    message = await asyncio.wait_for(
                        self.message_queue.get(), 
                        timeout=1.0
                    )
                    await self._process_message(message)
                except asyncio.TimeoutError:
                    # No message received, continue loop
                    continue
                    
            except Exception as e:
                logger.error(f"Error in message loop for {self.agent_name}: {e}")
                self.consecutive_errors += 1
                
                if self.consecutive_errors >= self.max_consecutive_errors:
                    await self._report_error_to_manager(
                        f"Too many consecutive errors: {e}"
                    )
                    break
    
    async def _process_message(self, message: AgentMessage):
        """Process an incoming message"""
        # Record message in history
        self.message_history.append(message)
        # Keep only last 100 messages
        if len(self.message_history) > 100:
            self.message_history = self.message_history[-100:]
        
        handler = self._message_handlers.get(message.type)
        
        if handler:
            await handler(message)
        else:
            # Default handling - subclasses can override
            await self.on_message(message)
    
    # ============== Message Handlers ==============
    
    async def _handle_interrupt(self, message: AgentMessage):
        """Handle interrupt command from manager"""
        content = message.content
        reason = content.get("reason", "Unknown reason")
        action = content.get("action", "stop")
        
        logger.warning(f"Agent {self.agent_name} interrupted: {reason}")
        
        await self._update_status(AgentStatus.INTERRUPTED, reason)
        
        if action == "stop":
            self.current_task = None
            await self._update_status(AgentStatus.IDLE)
        elif action == "restart":
            self.current_task = None
            await self._update_status(AgentStatus.IDLE)
        elif action == "reassign":
            new_task = content.get("new_assignment")
            if new_task:
                self.current_task = TaskAssignment(**new_task)
                await self._execute_task()
        
        # Notify frontend
        await self.ws_manager.send_agent_message_to_clients(
            MessageProtocol.create_status_update(
                self.agent_name,
                AgentStatus.INTERRUPTED,
                message=f"Interrupted: {reason}"
            )
        )
    
    async def _handle_task_assignment(self, message: AgentMessage):
        """Handle new task assignment"""
        task_data = message.content
        self.current_task = TaskAssignment(**task_data)
        
        logger.info(f"Agent {self.agent_name} received task: {self.current_task.task_type}")
        
        await self._execute_task()
    
    async def _handle_role_correction(self, message: AgentMessage):
        """Handle role correction from role agent"""
        content = message.content
        error_description = content.get("error_description", "")
        
        logger.warning(
            f"Agent {self.agent_name} received role correction: {error_description}"
        )
        
        # Subclasses can override this for specific handling
        await self.on_role_correction(content.get("role", {}), error_description)
    
    async def _handle_rag_result(self, message: AgentMessage):
        """Handle RAG check result"""
        content = message.content
        should_use_rag = content.get("should_use_rag", False)
        retrieved_docs = content.get("documents", [])
        
        # Store for use in task processing
        self._rag_result = {
            "should_use": should_use_rag,
            "documents": retrieved_docs
        }
    
    # ============== Task Execution ==============
    
    async def _execute_task(self):
        """Execute the current task"""
        if not self.current_task:
            return
        
        task_id = self.current_task.task_id
        await self._update_status(AgentStatus.WORKING)
        
        # Emit task assigned event via EventBus
        if HAS_EVENT_BUS and event_bus:
            await event_bus.emit(
                EventType.TASK_ASSIGNED,
                self.agent_name,
                {
                    "task_type": self.current_task.task_type,
                    "description": self.current_task.description[:100] if self.current_task.description else ""
                },
                task_id=task_id
            )
            await event_bus.update_status(
                self.agent_name,
                AgentState.WORKING,
                task_id=task_id,
                message=f"Processing {self.current_task.task_type}"
            )
        
        # Notify frontend that agent started working
        await self.ws_manager.send_agent_message_to_clients(
            MessageProtocol.create_agent_started(
                self.agent_name,
                {"task_type": self.current_task.task_type}
            )
        )
        
        try:
            # Check if RAG is needed before processing
            should_check_rag = await self.should_check_rag(self.current_task)
            
            if should_check_rag:
                await self._request_rag_check(self.current_task)
            
            # Process the task
            result = await self.process_task(self.current_task)
            
            # Validate result
            validation = await self.validate_result(result)
            
            if not validation.is_valid:
                await self._handle_validation_failure(validation)
                return
            
            # Report success
            await self._report_task_complete(result)
            self.consecutive_errors = 0
            
        except Exception as e:
            logger.error(f"Error executing task in {self.agent_name}: {e}")
            # Emit error event
            if HAS_EVENT_BUS and event_bus:
                await event_bus.emit(
                    EventType.TASK_FAILED,
                    self.agent_name,
                    {"error": str(e)},
                    task_id=task_id
                )
                await event_bus.update_status(
                    self.agent_name,
                    AgentState.ERROR,
                    task_id=task_id,
                    error=str(e)
                )
            await self._report_error_to_manager(str(e))
        
        finally:
            # Emit completion/idle event
            if HAS_EVENT_BUS and event_bus:
                await event_bus.update_status(
                    self.agent_name,
                    AgentState.IDLE,
                    message="Ready"
                )
            self.current_task = None
            await self._update_status(AgentStatus.IDLE)
    
    async def _request_rag_check(self, task: TaskAssignment):
        """Request RAG agent to check if retrieval is needed"""
        query = task.input_data.get("query", task.description)
        
        message = MessageProtocol.create_rag_check(self.agent_name, query)
        await self.ws_manager.send_to_agent(message)
        
        # Wait for RAG result (with timeout)
        try:
            await asyncio.wait_for(self._wait_for_rag_result(), timeout=10.0)
        except asyncio.TimeoutError:
            logger.warning(f"RAG check timeout for {self.agent_name}")
            self._rag_result = {"should_use": False, "documents": []}
    
    async def _wait_for_rag_result(self):
        """Wait for RAG result"""
        while not hasattr(self, '_rag_result'):
            await asyncio.sleep(0.1)
    
    async def _handle_validation_failure(self, validation: ValidationResult):
        """Handle validation failure"""
        if validation.should_retry and self.current_task:
            if self.current_task.retry_count < self.current_task.max_retries:
                self.current_task.retry_count += 1
                await self._execute_task()
                return
        
        # Report validation error to manager
        await self.send_message(
            MessageProtocol.create_error(
                self.agent_name,
                "Validation failed",
                {"errors": validation.errors}
            ),
            target="manager_agent"
        )
    
    # ============== Communication Methods ==============
    
    async def send_message(self, message: AgentMessage, target: str = None):
        """Send a message to another agent"""
        if target:
            message.target_agent = target
        
        await self.ws_manager.send_to_agent(message)
        
        # Also forward to frontend for visibility
        await self.ws_manager.send_agent_message_to_clients(message)
    
    async def broadcast(self, message: AgentMessage):
        """Broadcast a message to all agents"""
        await self.ws_manager.broadcast_to_agents(
            message, 
            exclude={self.agent_name}
        )
    
    async def stream_to_frontend(self, content: str, chunk_index: int):
        """Stream content to frontend (for planning/thinking agents)"""
        # Use EventBus for real-time streaming
        if HAS_EVENT_BUS and event_bus:
            task_id = self.current_task.task_id if self.current_task else None
            await event_bus.emit(
                EventType.THINKING,
                self.agent_name,
                {"content": content, "chunk_index": chunk_index},
                task_id=task_id
            )
        
        # Also use legacy method
        message = MessageProtocol.create_stream_chunk(
            self.agent_name, 
            content, 
            chunk_index
        )
        await self.ws_manager.send_agent_message_to_clients(message)
    
    async def emit_thinking(self, thought: str, step: int = None):
        """Emit a thinking event for real-time display"""
        if HAS_EVENT_BUS and event_bus:
            task_id = self.current_task.task_id if self.current_task else None
            await event_bus.emit_thinking(self.agent_name, thought, step, task_id)
    
    async def emit_progress(self, progress: float, step: str = None, message: str = None):
        """Emit progress update"""
        if HAS_EVENT_BUS and event_bus:
            task_id = self.current_task.task_id if self.current_task else None
            await event_bus.emit(
                EventType.TASK_PROGRESS,
                self.agent_name,
                {"progress": progress, "step": step, "message": message},
                task_id=task_id
            )
            await event_bus.update_status(
                self.agent_name,
                AgentState.WORKING,
                task_id=task_id,
                step=step,
                progress=progress,
                message=message
            )
    
    async def _update_status(self, status: AgentStatus, reason: str = None):
        """Update agent status"""
        self.status = status
        await self.ws_manager.update_agent_status(self.agent_name, status, reason)
    
    async def _report_task_complete(self, result: Any):
        """Report task completion"""
        task_id = self.current_task.task_id if self.current_task else None
        
        # Emit completion event via EventBus
        if HAS_EVENT_BUS and event_bus:
            await event_bus.emit(
                EventType.TASK_COMPLETED,
                self.agent_name,
                {"result_summary": str(result)[:200] if result else ""},
                task_id=task_id
            )
            await event_bus.update_status(
                self.agent_name,
                AgentState.IDLE,
                task_id=task_id,
                progress=100.0,
                message="Completed"
            )
        
        message = MessageProtocol.create_agent_completed(self.agent_name, result, task_id)
        
        # Send to manager
        message.target_agent = "manager_agent"
        await self.ws_manager.send_to_agent(message)
        
        # Notify frontend
        await self.ws_manager.send_agent_message_to_clients(message)
    
    async def _report_error_to_manager(self, error: str):
        """Report error to manager agent"""
        message = MessageProtocol.create_error(
            self.agent_name,
            error,
            {"task": self.current_task.model_dump() if self.current_task else None}
        )
        message.target_agent = "manager_agent"
        await self.ws_manager.send_to_agent(message)
    
    # ============== Abstract Methods ==============
    
    @abstractmethod
    async def process_task(self, task: TaskAssignment) -> Any:
        """
        Process a task. Must be implemented by subclasses.
        
        Args:
            task: The task to process
            
        Returns:
            The result of processing the task
        """
        pass
    
    # ============== Optional Override Methods ==============
    
    async def on_message(self, message: AgentMessage):
        """Handle messages not covered by default handlers. Override as needed."""
        logger.debug(f"Agent {self.agent_name} received unhandled message: {message.type}")
    
    async def on_role_correction(self, role: Dict, error_description: str):
        """Handle role correction. Override as needed."""
        logger.warning(f"Role correction received but not handled: {error_description}")
    
    async def should_check_rag(self, task: TaskAssignment) -> bool:
        """Determine if RAG check is needed. Override as needed."""
        return False
    
    async def validate_result(self, result: Any) -> ValidationResult:
        """Validate task result. Override as needed."""
        return ValidationResult(is_valid=True)
    
    def get_agent_info(self) -> Dict[str, Any]:
        """Get agent information"""
        return {
            "name": self.agent_name,
            "role": self.agent_role,
            "description": self.agent_description,
            "status": self.status.value,
            "current_task": self.current_task.model_dump() if self.current_task else None
        }
