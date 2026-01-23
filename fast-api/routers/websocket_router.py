"""
WebSocket Router

Handles WebSocket connections for real-time agent communication:
- Client connections for frontend
- Agent status updates
- Task streaming
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from agents.shared_services.websocket_manager import WebSocketManager
from agents.shared_services.agent_registry import AgentRegistry
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    MessageProtocol,
    TaskAssignment
)

logger = logging.getLogger(__name__)

router = APIRouter()


class ClientMessage(BaseModel):
    """Message from frontend client"""
    type: str  # query, interrupt, status, subscribe
    content: Dict[str, Any] = {}


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint for frontend clients.
    
    Handles:
    - Agent status updates
    - Task streaming
    - Interrupt commands
    """
    ws_manager = WebSocketManager()
    registry = AgentRegistry()
    
    client_id = await ws_manager.connect_client(websocket)
    
    try:
        # Send initial status
        await websocket.send_json({
            "type": "connected",
            "client_id": client_id,
            "timestamp": datetime.now().isoformat(),
            "agents": registry.get_system_health()
        })
        
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                message_type = message.get("type", "")
                content = message.get("content", {})
                
                if message_type == "query":
                    # Send query to manager agent
                    await handle_query(ws_manager, registry, content, client_id)
                    
                elif message_type == "interrupt":
                    # Handle interrupt request
                    await handle_interrupt(ws_manager, registry, content, client_id)
                    
                elif message_type == "status":
                    # Send current system status
                    await websocket.send_json({
                        "type": "status_update",
                        "agents": registry.get_system_health(),
                        "timestamp": datetime.now().isoformat()
                    })
                    
                elif message_type == "subscribe":
                    # Subscribe to specific agent updates
                    agent_names = content.get("agents", [])
                    ws_manager.subscribe(client_id, agent_names)
                    await websocket.send_json({
                        "type": "subscribed",
                        "agents": agent_names
                    })
                    
                elif message_type == "ping":
                    await websocket.send_json({"type": "pong"})
                    
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown message type: {message_type}"
                    })
                    
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON"
                })
                
    except WebSocketDisconnect:
        ws_manager.disconnect_client(client_id)
        logger.info(f"Client {client_id} disconnected")


async def handle_query(
    ws_manager: WebSocketManager,
    registry: AgentRegistry,
    content: Dict[str, Any],
    client_id: str
):
    """Handle a query from the frontend"""
    query = content.get("query", "")
    context = content.get("context", {})
    
    # Get manager agent
    manager = registry.get_agent("manager_agent")
    
    if not manager:
        await ws_manager.send_to_client(client_id, {
            "type": "error",
            "message": "Manager agent not available"
        })
        return
    
    # Notify client that processing started
    await ws_manager.send_to_client(client_id, {
        "type": "processing_started",
        "query": query,
        "timestamp": datetime.now().isoformat()
    })
    
    # Create task for manager
    task = TaskAssignment(
        task_id=f"query-{datetime.now().timestamp()}",
        task_type="process_query",
        input_data={"query": query, "context": context},
        context=query,
        priority=1
    )
    
    # Send to manager
    message = AgentMessage(
        type=MessageType.TASK_ASSIGNED,
        source_agent="api",
        target_agent="manager_agent",
        content=task.model_dump(),
        priority=1,
        metadata={"client_id": client_id}
    )
    
    await ws_manager.send_to_agent(message)


async def handle_interrupt(
    ws_manager: WebSocketManager,
    registry: AgentRegistry,
    content: Dict[str, Any],
    client_id: str
):
    """Handle an interrupt request from the frontend"""
    target_agent = content.get("agent", "")
    reason = content.get("reason", "User requested interrupt")
    interrupt_all = content.get("all", False)
    
    # Get manager agent
    manager = registry.get_agent("manager_agent")
    
    if not manager:
        await ws_manager.send_to_client(client_id, {
            "type": "error",
            "message": "Manager agent not available"
        })
        return
    
    # Forward interrupt request to manager
    if interrupt_all:
        # Request to interrupt all agents
        await manager.interrupt_all_agents(reason)
        
        await ws_manager.send_to_client(client_id, {
            "type": "interrupt_sent",
            "target": "all",
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
    elif target_agent:
        # Request to interrupt specific agent
        await manager.interrupt_agent(target_agent, reason)
        
        await ws_manager.send_to_client(client_id, {
            "type": "interrupt_sent",
            "target": target_agent,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
    else:
        await ws_manager.send_to_client(client_id, {
            "type": "error",
            "message": "No target agent specified"
        })


@router.websocket("/ws/agent/{agent_name}")
async def agent_websocket_endpoint(websocket: WebSocket, agent_name: str):
    """
    WebSocket endpoint for specific agent updates.
    
    Allows clients to subscribe to updates from a specific agent.
    """
    ws_manager = WebSocketManager()
    registry = AgentRegistry()
    
    # Check if agent exists
    agent = registry.get_agent(agent_name)
    if not agent:
        await websocket.close(code=4004, reason=f"Agent {agent_name} not found")
        return
    
    client_id = await ws_manager.connect_client(websocket)
    ws_manager.subscribe(client_id, [agent_name])
    
    try:
        await websocket.send_json({
            "type": "connected",
            "agent": agent_name,
            "status": agent.status,
            "timestamp": datetime.now().isoformat()
        })
        
        while True:
            # Keep connection alive and forward messages
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        ws_manager.disconnect_client(client_id)
        logger.info(f"Client {client_id} disconnected from agent {agent_name}")


@router.websocket("/ws/stream")
async def stream_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for streaming agent outputs.
    
    Receives real-time updates from planning and thinking agents.
    """
    ws_manager = WebSocketManager()
    
    client_id = await ws_manager.connect_client(websocket)
    
    # Subscribe to streaming agents
    streaming_agents = ["planning_agent", "thinking_agent"]
    ws_manager.subscribe(client_id, streaming_agents)
    
    try:
        await websocket.send_json({
            "type": "connected",
            "subscribed_to": streaming_agents,
            "timestamp": datetime.now().isoformat()
        })
        
        while True:
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                if message.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                    
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        ws_manager.disconnect_client(client_id)
        logger.info(f"Stream client {client_id} disconnected")
