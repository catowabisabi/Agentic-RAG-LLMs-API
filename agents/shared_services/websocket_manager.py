"""
WebSocket Manager for Multi-Agent Communication

Manages WebSocket connections for real-time communication between:
- Agents (internal communication)
- Frontend clients (external communication)
"""

import asyncio
import json
import logging
from typing import Dict, Set, Optional, Callable, List, Any
from datetime import datetime
from fastapi import WebSocket
from collections import defaultdict

from .message_protocol import AgentMessage, MessageType, AgentStatus

logger = logging.getLogger(__name__)


class WebSocketConnection:
    """Represents a single WebSocket connection"""
    
    def __init__(
        self, 
        websocket: WebSocket, 
        connection_id: str,
        connection_type: str = "client"  # "client" or "agent"
    ):
        self.websocket = websocket
        self.connection_id = connection_id
        self.connection_type = connection_type
        self.connected_at = datetime.now()
        self.last_activity = datetime.now()
        self.subscriptions: Set[str] = set()  # Topics/agents to receive updates from
    
    async def send_message(self, message: AgentMessage):
        """Send a message through this connection"""
        try:
            await self.websocket.send_json(message.model_dump(mode='json'))
            self.last_activity = datetime.now()
        except Exception as e:
            logger.error(f"Error sending message to {self.connection_id}: {e}")
            raise
    
    async def send_json(self, data: Dict[str, Any]):
        """Send raw JSON data"""
        try:
            await self.websocket.send_json(data)
            self.last_activity = datetime.now()
        except Exception as e:
            logger.error(f"Error sending JSON to {self.connection_id}: {e}")
            raise


class WebSocketManager:
    """
    Central WebSocket manager for the multi-agent system.
    
    Handles:
    - Connection management
    - Message routing between agents
    - Broadcasting to frontend clients
    - Subscription management
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
        
        # Client connections (frontend)
        self.client_connections: Dict[str, WebSocketConnection] = {}
        
        # Agent connections (internal)
        self.agent_connections: Dict[str, WebSocketConnection] = {}
        
        # Message queues for agents
        self.agent_queues: Dict[str, asyncio.Queue] = defaultdict(asyncio.Queue)
        
        # Subscription management: topic -> set of connection_ids
        self.subscriptions: Dict[str, Set[str]] = defaultdict(set)
        
        # Message handlers
        self.message_handlers: Dict[MessageType, List[Callable]] = defaultdict(list)
        
        # Agent status tracking
        self.agent_statuses: Dict[str, AgentStatus] = {}
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        logger.info("WebSocketManager initialized")
    
    # ============== Connection Management ==============
    
    async def connect_client(self, websocket: WebSocket, client_id: str) -> WebSocketConnection:
        """Connect a frontend client"""
        await websocket.accept()
        
        async with self._lock:
            connection = WebSocketConnection(websocket, client_id, "client")
            self.client_connections[client_id] = connection
            
            # Subscribe client to all agent updates by default
            connection.subscriptions.add("all_agents")
            self.subscriptions["all_agents"].add(client_id)
        
        logger.info(f"Client connected: {client_id}")
        
        # Notify client of current agent statuses
        await self._send_agent_status_update(connection)
        
        return connection
    
    async def disconnect_client(self, client_id: str):
        """Disconnect a frontend client"""
        async with self._lock:
            if client_id in self.client_connections:
                connection = self.client_connections.pop(client_id)
                
                # Remove from all subscriptions
                for topic, subscribers in self.subscriptions.items():
                    subscribers.discard(client_id)
                
                logger.info(f"Client disconnected: {client_id}")
    
    async def register_agent(self, agent_name: str, websocket: WebSocket = None) -> asyncio.Queue:
        """
        Register an agent for internal communication.
        Returns a message queue for the agent to receive messages.
        """
        async with self._lock:
            if websocket:
                await websocket.accept()
                connection = WebSocketConnection(websocket, agent_name, "agent")
                self.agent_connections[agent_name] = connection
            
            # Create message queue for the agent
            if agent_name not in self.agent_queues:
                self.agent_queues[agent_name] = asyncio.Queue()
            
            self.agent_statuses[agent_name] = AgentStatus.IDLE
            
        logger.info(f"Agent registered: {agent_name}")
        
        # Broadcast to clients
        await self.broadcast_to_clients({
            "type": "agent_registered",
            "agent_name": agent_name,
            "status": AgentStatus.IDLE.value,
            "timestamp": datetime.now().isoformat()
        })
        
        return self.agent_queues[agent_name]
    
    async def unregister_agent(self, agent_name: str):
        """Unregister an agent"""
        async with self._lock:
            if agent_name in self.agent_connections:
                del self.agent_connections[agent_name]
            if agent_name in self.agent_queues:
                del self.agent_queues[agent_name]
            if agent_name in self.agent_statuses:
                del self.agent_statuses[agent_name]
        
        logger.info(f"Agent unregistered: {agent_name}")
        
        await self.broadcast_to_clients({
            "type": "agent_unregistered",
            "agent_name": agent_name,
            "timestamp": datetime.now().isoformat()
        })
    
    # ============== Message Routing ==============
    
    async def send_to_agent(self, message: AgentMessage):
        """Send a message to a specific agent"""
        target = message.target_agent
        
        if not target:
            logger.warning("No target agent specified in message")
            return
        
        if target in self.agent_queues:
            await self.agent_queues[target].put(message)
            logger.debug(f"Message queued for agent: {target}")
        else:
            logger.warning(f"Agent not found: {target}")
    
    async def broadcast_to_agents(self, message: AgentMessage, exclude: Set[str] = None):
        """Broadcast a message to all agents"""
        exclude = exclude or set()
        
        for agent_name, queue in self.agent_queues.items():
            if agent_name not in exclude:
                await queue.put(message)
        
        logger.debug(f"Message broadcast to {len(self.agent_queues) - len(exclude)} agents")
    
    async def broadcast_to_clients(self, data: Dict[str, Any]):
        """Broadcast a message to all connected frontend clients"""
        disconnected = []
        
        for client_id, connection in self.client_connections.items():
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.error(f"Error broadcasting to client {client_id}: {e}")
                disconnected.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected:
            await self.disconnect_client(client_id)
    
    async def send_agent_message_to_clients(self, message: AgentMessage):
        """Forward an agent message to subscribed clients"""
        data = {
            "type": message.type.value if isinstance(message.type, MessageType) else message.type,
            "source_agent": message.source_agent,
            "content": message.content,
            "timestamp": message.timestamp.isoformat() if message.timestamp else datetime.now().isoformat(),
            "metadata": message.metadata
        }
        
        await self.broadcast_to_clients(data)
    
    # ============== Status Management ==============
    
    async def update_agent_status(self, agent_name: str, status: AgentStatus, reason: str = None):
        """Update and broadcast an agent's status"""
        self.agent_statuses[agent_name] = status
        
        await self.broadcast_to_clients({
            "type": "agent_status_update",
            "agent_name": agent_name,
            "status": status.value,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
    
    async def _send_agent_status_update(self, connection: WebSocketConnection):
        """Send current agent statuses to a newly connected client"""
        statuses = {
            name: status.value 
            for name, status in self.agent_statuses.items()
        }
        
        await connection.send_json({
            "type": "agent_statuses",
            "statuses": statuses,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_agent_status(self, agent_name: str) -> Optional[AgentStatus]:
        """Get an agent's current status"""
        return self.agent_statuses.get(agent_name)
    
    def get_all_agent_statuses(self) -> Dict[str, AgentStatus]:
        """Get all agent statuses"""
        return self.agent_statuses.copy()
    
    # ============== Message Handlers ==============
    
    def register_handler(self, message_type: MessageType, handler: Callable):
        """Register a message handler for a specific message type"""
        self.message_handlers[message_type].append(handler)
    
    async def process_message(self, message: AgentMessage):
        """Process a message through registered handlers"""
        handlers = self.message_handlers.get(message.type, [])
        
        for handler in handlers:
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(message)
                else:
                    handler(message)
            except Exception as e:
                logger.error(f"Error in message handler: {e}")
    
    # ============== Utility Methods ==============
    
    def get_connected_clients(self) -> List[str]:
        """Get list of connected client IDs"""
        return list(self.client_connections.keys())
    
    def get_registered_agents(self) -> List[str]:
        """Get list of registered agent names"""
        return list(self.agent_queues.keys())
    
    async def get_agent_queue(self, agent_name: str) -> asyncio.Queue:
        """Get the message queue for an agent"""
        if agent_name not in self.agent_queues:
            self.agent_queues[agent_name] = asyncio.Queue()
        return self.agent_queues[agent_name]
