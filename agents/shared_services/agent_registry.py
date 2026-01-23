"""
Agent Registry

Central registry for all agents in the multi-agent system.
Manages agent lifecycle, discovery, and coordination.
Includes concurrency control with max 5 simultaneous agents.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Type, Any, Callable
from datetime import datetime
from collections import deque

from .base_agent import BaseAgent
from .message_protocol import AgentStatus

logger = logging.getLogger(__name__)


class ConcurrencyController:
    """
    Controls concurrent agent execution.
    Maximum 5 agents can work simultaneously.
    Additional tasks are queued.
    """
    
    def __init__(self, max_concurrent: int = 5):
        self.max_concurrent = max_concurrent
        self._running_count = 0
        self._queue: deque = deque()
        self._lock = asyncio.Lock()
        self._condition = asyncio.Condition(self._lock)
        
    async def acquire(self, agent_name: str) -> bool:
        """
        Acquire a slot for agent execution.
        Returns True when slot is acquired, blocks if queue is full.
        """
        async with self._condition:
            # Add to queue if at capacity
            if self._running_count >= self.max_concurrent:
                self._queue.append(agent_name)
                logger.info(f"Agent {agent_name} queued. Position: {len(self._queue)}")
                
                # Wait until we're at the front and there's capacity
                while (self._running_count >= self.max_concurrent or 
                       (self._queue and self._queue[0] != agent_name)):
                    await self._condition.wait()
                
                # Remove from queue when it's our turn
                if self._queue and self._queue[0] == agent_name:
                    self._queue.popleft()
            
            self._running_count += 1
            logger.info(f"Agent {agent_name} started. Running: {self._running_count}/{self.max_concurrent}")
            return True
    
    async def release(self, agent_name: str):
        """Release a slot after agent completes"""
        async with self._condition:
            self._running_count = max(0, self._running_count - 1)
            logger.info(f"Agent {agent_name} completed. Running: {self._running_count}/{self.max_concurrent}")
            self._condition.notify_all()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current concurrency status"""
        return {
            "running": self._running_count,
            "max_concurrent": self.max_concurrent,
            "queued": len(self._queue),
            "queue_order": list(self._queue)
        }


class AgentRegistry:
    """
    Central registry for managing all agents.
    
    Provides:
    - Agent registration and discovery
    - Lifecycle management
    - Agent capability lookup
    - Concurrency control (max 5 simultaneous agents)
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
        
        # Registered agent instances
        self._agents: Dict[str, BaseAgent] = {}
        
        # Agent metadata
        self._agent_metadata: Dict[str, Dict[str, Any]] = {}
        
        # Agent type registry (for factory pattern)
        self._agent_types: Dict[str, Type[BaseAgent]] = {}
        
        # Concurrency controller
        self._concurrency = ConcurrencyController(max_concurrent=5)
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        logger.info("AgentRegistry initialized with max 5 concurrent agents")
    
    # ============== Agent Registration ==============
    
    def register_agent_type(self, agent_type_name: str, agent_class: Type[BaseAgent]):
        """Register an agent type for factory creation"""
        self._agent_types[agent_type_name] = agent_class
        logger.info(f"Registered agent type: {agent_type_name}")
    
    async def register_agent(self, agent: BaseAgent) -> bool:
        """Register an agent instance"""
        async with self._lock:
            if agent.agent_name in self._agents:
                logger.warning(f"Agent already registered: {agent.agent_name}")
                return False
            
            self._agents[agent.agent_name] = agent
            self._agent_metadata[agent.agent_name] = {
                "registered_at": datetime.now().isoformat(),
                "role": agent.agent_role,
                "description": agent.agent_description,
                "capabilities": getattr(agent, 'capabilities', [])
            }
            
            logger.info(f"Agent registered: {agent.agent_name}")
            return True
    
    async def unregister_agent(self, agent_name: str) -> bool:
        """Unregister an agent"""
        async with self._lock:
            if agent_name not in self._agents:
                logger.warning(f"Agent not found: {agent_name}")
                return False
            
            agent = self._agents.pop(agent_name)
            self._agent_metadata.pop(agent_name, None)
            
            # Stop the agent if running
            if agent.is_running:
                await agent.stop()
            
            logger.info(f"Agent unregistered: {agent_name}")
            return True
    
    # ============== Agent Factory ==============
    
    async def create_agent(
        self, 
        agent_type: str, 
        agent_name: str = None,
        **kwargs
    ) -> Optional[BaseAgent]:
        """Create and register a new agent from a registered type"""
        if agent_type not in self._agent_types:
            logger.error(f"Unknown agent type: {agent_type}")
            return None
        
        agent_class = self._agent_types[agent_type]
        
        try:
            # Use provided name or generate default
            name = agent_name or f"{agent_type}_{len(self._agents)}"
            
            # Create agent instance
            agent = agent_class(agent_name=name, **kwargs)
            
            # Register and start
            await self.register_agent(agent)
            await agent.start()
            
            return agent
            
        except Exception as e:
            logger.error(f"Error creating agent {agent_type}: {e}")
            return None
    
    # ============== Agent Lookup ==============
    
    def get_agent(self, agent_name: str) -> Optional[BaseAgent]:
        """Get an agent by name"""
        return self._agents.get(agent_name)
    
    def get_agents_by_role(self, role: str) -> List[BaseAgent]:
        """Get all agents with a specific role"""
        return [
            agent for agent in self._agents.values()
            if agent.agent_role == role
        ]
    
    def get_agents_by_status(self, status: AgentStatus) -> List[BaseAgent]:
        """Get all agents with a specific status"""
        return [
            agent for agent in self._agents.values()
            if agent.status == status
        ]
    
    def get_all_agents(self) -> List[BaseAgent]:
        """Get all registered agents"""
        return list(self._agents.values())
    
    def get_agent_names(self) -> List[str]:
        """Get all registered agent names"""
        return list(self._agents.keys())
    
    def get_agent_metadata(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get metadata for an agent"""
        return self._agent_metadata.get(agent_name)
    
    def get_all_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Get metadata for all agents"""
        return self._agent_metadata.copy()
    
    # ============== Agent Lifecycle ==============
    
    async def start_all_agents(self):
        """Start all registered agents"""
        tasks = []
        for agent in self._agents.values():
            if not agent.is_running:
                tasks.append(agent.start())
        
        if tasks:
            await asyncio.gather(*tasks)
            logger.info(f"Started {len(tasks)} agents")
    
    async def stop_all_agents(self):
        """Stop all registered agents"""
        tasks = []
        for agent in self._agents.values():
            if agent.is_running:
                tasks.append(agent.stop())
        
        if tasks:
            await asyncio.gather(*tasks)
            logger.info(f"Stopped {len(tasks)} agents")
    
    async def restart_agent(self, agent_name: str) -> bool:
        """Restart a specific agent"""
        agent = self.get_agent(agent_name)
        if not agent:
            return False
        
        await agent.stop()
        await agent.start()
        return True
    
    # ============== Health Check ==============
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get overall system health"""
        total = len(self._agents)
        statuses = {}
        
        for agent in self._agents.values():
            status_key = agent.status.value
            statuses[status_key] = statuses.get(status_key, 0) + 1
        
        return {
            "total_agents": total,
            "status_breakdown": statuses,
            "healthy": statuses.get("error", 0) == 0,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_agent_health(self, agent_name: str) -> Optional[Dict[str, Any]]:
        """Get health status for a specific agent"""
        agent = self.get_agent(agent_name)
        if not agent:
            return None
        
        return {
            "name": agent.agent_name,
            "status": agent.status.value,
            "is_running": agent.is_running,
            "consecutive_errors": agent.consecutive_errors,
            "current_task": agent.current_task.task_id if agent.current_task else None,
            "timestamp": datetime.now().isoformat()
        }
    
    # ============== Concurrency Control ==============
    
    async def acquire_execution_slot(self, agent_name: str) -> bool:
        """Acquire a slot for agent execution (max 5 concurrent)"""
        return await self._concurrency.acquire(agent_name)
    
    async def release_execution_slot(self, agent_name: str):
        """Release execution slot when agent completes"""
        await self._concurrency.release(agent_name)
    
    def get_concurrency_status(self) -> Dict[str, Any]:
        """Get current concurrency status"""
        return self._concurrency.get_status()
    
    async def execute_with_concurrency(
        self, 
        agent_name: str, 
        task_fn: Callable,
        *args, 
        **kwargs
    ) -> Any:
        """
        Execute a task with concurrency control.
        Automatically acquires and releases execution slot.
        """
        try:
            await self.acquire_execution_slot(agent_name)
            return await task_fn(*args, **kwargs)
        finally:
            await self.release_execution_slot(agent_name)
