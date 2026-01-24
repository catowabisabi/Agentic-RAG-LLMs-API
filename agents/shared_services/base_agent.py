"""
Base Agent Class

Abstract base class for all agents in the multi-agent system.
Provides common functionality for WebSocket communication, 
message handling, and lifecycle management.
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

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents.
    
    Each agent should:
    1. Inherit from this class
    2. Implement the process_task method
    3. Define its role and capabilities
    """
    
    def __init__(
        self,
        agent_name: str,
        agent_role: str,
        agent_description: str = ""
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
        
        # Message handlers for specific message types
        self._message_handlers: Dict[MessageType, Callable] = {
            MessageType.INTERRUPT: self._handle_interrupt,
            MessageType.TASK_ASSIGNED: self._handle_task_assignment,
            MessageType.ROLE_CORRECTION: self._handle_role_correction,
            MessageType.RAG_RESULT: self._handle_rag_result,
        }
        
        logger.info(f"Agent initialized: {agent_name} ({agent_role})")
    
    # ============== Lifecycle Methods ==============
    
    async def start(self):
        """Start the agent and begin processing messages"""
        self.message_queue = await self.ws_manager.register_agent(self.agent_name)
        self.is_running = True
        self.should_stop = False
        
        await self._update_status(AgentStatus.IDLE)
        
        # Start message processing loop
        asyncio.create_task(self._message_loop())
        
        logger.info(f"Agent started: {self.agent_name}")
    
    async def stop(self):
        """Stop the agent gracefully"""
        self.should_stop = True
        self.is_running = False
        
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
        
        await self._update_status(AgentStatus.WORKING)
        
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
            await self._report_error_to_manager(str(e))
        
        finally:
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
        message = MessageProtocol.create_stream_chunk(
            self.agent_name, 
            content, 
            chunk_index
        )
        await self.ws_manager.send_agent_message_to_clients(message)
    
    async def _update_status(self, status: AgentStatus, reason: str = None):
        """Update agent status"""
        self.status = status
        await self.ws_manager.update_agent_status(self.agent_name, status, reason)
    
    async def _report_task_complete(self, result: Any):
        """Report task completion"""
        message = MessageProtocol.create_agent_completed(self.agent_name, result)
        
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
