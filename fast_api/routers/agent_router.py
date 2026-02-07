"""
Agent Router

REST API endpoints for agent management:
- List agents
- Get agent status
- Send tasks to agents
- Activity history (via EventBus)
- Custom agent CRUD (SQLite-backed)
"""

import logging
import json
import sqlite3
import os
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from agents.shared_services.agent_registry import AgentRegistry
from agents.shared_services.websocket_manager import WebSocketManager
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    TaskAssignment
)

# Import EventBus for activity history
try:
    from services.event_bus import event_bus
    HAS_EVENT_BUS = True
except ImportError:
    HAS_EVENT_BUS = False
    event_bus = None

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])

# ============== Custom Agents DB ==============
CUSTOM_AGENTS_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "custom_agents.db")

def _init_custom_agents_db():
    conn = sqlite3.connect(CUSTOM_AGENTS_DB)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS custom_agents (
            name TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL,
            description TEXT,
            system_prompt TEXT,
            model TEXT DEFAULT 'gpt-4o-mini',
            temperature REAL DEFAULT 0.7,
            tools TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            enabled INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()

_init_custom_agents_db()


class TaskRequest(BaseModel):
    """Request to send a task to an agent"""
    agent_name: str = Field(description="Target agent name")
    task_type: str = Field(description="Type of task")
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Task input data")
    context: str = Field(default="", description="Additional context")
    priority: int = Field(default=1, description="Task priority 1-5")


class InterruptRequest(BaseModel):
    """Request to interrupt an agent"""
    agent_name: Optional[str] = Field(default=None, description="Target agent (None for all)")
    reason: str = Field(default="User requested", description="Reason for interrupt")


class AgentResponse(BaseModel):
    """Agent information response"""
    name: str
    role: str
    description: str
    status: str
    is_running: bool


class SystemHealthResponse(BaseModel):
    """System health response"""
    total_agents: int
    running_agents: int
    idle_agents: int
    busy_agents: int
    agents: Dict[str, Dict[str, Any]]


@router.get("/", response_model=List[AgentResponse])
async def list_agents():
    """List all registered agents"""
    registry = AgentRegistry()
    agents = []
    
    for name, agent in registry._agents.items():
        agents.append(AgentResponse(
            name=name,
            role=agent.agent_role,
            description=agent.agent_description,
            status=agent.status,
            is_running=agent.is_running
        ))
    
    return agents


@router.get("/health", response_model=SystemHealthResponse)
async def get_system_health():
    """Get system health status"""
    registry = AgentRegistry()
    health = registry.get_system_health()
    
    # Count agents by status
    running_count = 0
    idle_count = 0
    busy_count = 0
    agents_info = {}
    
    for name, agent in registry._agents.items():
        if agent.is_running:
            running_count += 1
        if agent.status.value == "idle":
            idle_count += 1
        elif agent.status.value == "busy" or agent.status.value == "processing":
            busy_count += 1
        
        agents_info[name] = {
            "status": agent.status.value,
            "is_running": agent.is_running,
            "role": agent.agent_role
        }
    
    return SystemHealthResponse(
        total_agents=health["total_agents"],
        running_agents=running_count,
        idle_agents=idle_count,
        busy_agents=busy_count,
        agents=agents_info
    )


@router.get("/{agent_name}")
async def get_agent(agent_name: str):
    """Get information about a specific agent"""
    registry = AgentRegistry()
    agent = registry.get_agent(agent_name)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")
    
    return {
        "name": agent.agent_name,
        "role": agent.agent_role,
        "description": agent.agent_description,
        "status": agent.status,
        "is_running": agent.is_running,
        "metrics": {
            "message_count": len(agent.message_history),
            "current_task": agent.current_task
        }
    }


@router.get("/{agent_name}/health")
async def get_agent_health(agent_name: str):
    """Get health status of a specific agent"""
    registry = AgentRegistry()
    health = registry.get_agent_health(agent_name)
    
    if not health:
        raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")
    
    return health


@router.post("/task")
async def send_task(request: TaskRequest, background_tasks: BackgroundTasks):
    """Send a task to an agent"""
    registry = AgentRegistry()
    ws_manager = WebSocketManager()
    
    agent = registry.get_agent(request.agent_name)
    
    if not agent:
        raise HTTPException(
            status_code=404,
            detail=f"Agent {request.agent_name} not found"
        )
    
    if not agent.is_running:
        raise HTTPException(
            status_code=400,
            detail=f"Agent {request.agent_name} is not running"
        )
    
    # Create task
    task = TaskAssignment(
        task_id=f"api-{datetime.now().timestamp()}",
        task_type=request.task_type,
        description=f"API task: {request.task_type}",
        input_data=request.input_data
    )
    
    # Create message
    message = AgentMessage(
        type=MessageType.TASK_ASSIGNED,
        source_agent="api",
        target_agent=request.agent_name,
        content=task.model_dump(),
        priority=request.priority
    )
    
    # Send to agent
    await ws_manager.send_to_agent(message)
    
    return {
        "success": True,
        "task_id": task.task_id,
        "agent": request.agent_name,
        "message": f"Task sent to {request.agent_name}"
    }


@router.post("/interrupt")
async def interrupt_agent(request: InterruptRequest):
    """Interrupt an agent or all agents"""
    registry = AgentRegistry()
    manager = registry.get_agent("manager_agent")
    
    if not manager:
        raise HTTPException(
            status_code=500,
            detail="Manager agent not available"
        )
    
    if request.agent_name:
        # Interrupt specific agent
        target = registry.get_agent(request.agent_name)
        if not target:
            raise HTTPException(
                status_code=404,
                detail=f"Agent {request.agent_name} not found"
            )
        
        await manager.interrupt_agent(request.agent_name, request.reason)
        
        return {
            "success": True,
            "interrupted": request.agent_name,
            "reason": request.reason
        }
    else:
        # Interrupt all agents
        await manager.interrupt_all_agents(request.reason)
        
        return {
            "success": True,
            "interrupted": "all",
            "reason": request.reason
        }


@router.post("/{agent_name}/start")
async def start_agent(agent_name: str):
    """Start a specific agent"""
    registry = AgentRegistry()
    
    try:
        await registry.start_agent(agent_name)
        return {
            "success": True,
            "agent": agent_name,
            "status": "started"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{agent_name}/stop")
async def stop_agent(agent_name: str):
    """Stop a specific agent"""
    registry = AgentRegistry()
    
    try:
        await registry.stop_agent(agent_name)
        return {
            "success": True,
            "agent": agent_name,
            "status": "stopped"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{agent_name}/restart")
async def restart_agent(agent_name: str):
    """Restart a specific agent"""
    registry = AgentRegistry()
    
    try:
        await registry.restart_agent(agent_name)
        return {
            "success": True,
            "agent": agent_name,
            "status": "restarted"
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/start-all")
async def start_all_agents():
    """Start all registered agents"""
    registry = AgentRegistry()
    await registry.start_all_agents()
    
    return {
        "success": True,
        "message": "All agents started",
        "agents": list(registry._agents.keys())
    }


@router.post("/stop-all")
async def stop_all_agents():
    """Stop all running agents"""
    registry = AgentRegistry()
    await registry.stop_all_agents()
    
    return {
        "success": True,
        "message": "All agents stopped"
    }


@router.get("/{agent_name}/activity")
async def get_agent_activity(agent_name: str, limit: int = 50):
    """Get agent message history and activity for demo/debugging"""
    registry = AgentRegistry()
    agent = registry.get_agent(agent_name)
    
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent {agent_name} not found")
    
    # Get message history
    history = []
    for msg in agent.message_history[-limit:]:
        history.append({
            "type": msg.type.value if hasattr(msg.type, 'value') else str(msg.type),
            "source": msg.source_agent,
            "target": msg.target_agent,
            "content": msg.content,
            "timestamp": msg.timestamp,
            "priority": msg.priority
        })
    
    return {
        "agent": agent_name,
        "status": agent.status.value if hasattr(agent.status, 'value') else str(agent.status),
        "is_running": agent.is_running,
        "current_task": agent.current_task.model_dump() if agent.current_task else None,
        "message_count": len(agent.message_history),
        "activity": history
    }


@router.get("/activity/all")
async def get_all_agents_activity(limit: int = 20):
    """Get activity from all agents for demo dashboard"""
    registry = AgentRegistry()
    all_activity = []
    
    for name, agent in registry._agents.items():
        for msg in agent.message_history[-limit:]:
            all_activity.append({
                "agent": name,
                "type": msg.type.value if hasattr(msg.type, 'value') else str(msg.type),
                "source": msg.source_agent,
                "target": msg.target_agent,
                "content": msg.content,
                "timestamp": msg.timestamp,
                "priority": msg.priority
            })
    
    # Sort by timestamp
    all_activity.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return {
        "total_messages": len(all_activity),
        "activity": all_activity[:limit * 2]  # Return up to 2x limit
    }

# ============== EventBus-based Endpoints ==============

@router.get("/status/realtime")
async def get_realtime_agent_statuses():
    """Get real-time agent statuses from EventBus"""
    if not HAS_EVENT_BUS or not event_bus:
        # Fallback to registry
        registry = AgentRegistry()
        statuses = {}
        for name, agent in registry._agents.items():
            statuses[name] = {
                "agent_name": name,
                "state": agent.status.value if hasattr(agent.status, 'value') else str(agent.status),
                "current_task": agent.current_task.task_id if agent.current_task else None,
                "message": None,
                "progress": 0
            }
        return {"source": "registry", "statuses": statuses}
    
    return {
        "source": "event_bus",
        "statuses": event_bus.get_all_agent_statuses()
    }


@router.get("/events/history")
async def get_event_history(agent_name: str = None, limit: int = 50):
    """Get event history from EventBus"""
    if not HAS_EVENT_BUS or not event_bus:
        return {"error": "EventBus not available", "history": []}
    
    history = event_bus.get_activity_history(agent_name, limit)
    return {
        "agent_name": agent_name,
        "total": len(history),
        "history": history
    }


@router.post("/interrupt/task/{task_id}")
async def interrupt_task(task_id: str, reason: str = "User requested"):
    """Request interrupt for a specific task"""
    if not HAS_EVENT_BUS or not event_bus:
        raise HTTPException(status_code=501, detail="EventBus not available")
    
    await event_bus.request_interrupt(task_id=task_id, reason=reason)
    return {
        "success": True,
        "task_id": task_id,
        "reason": reason,
        "message": "Interrupt requested. Task will stop at next checkpoint."
    }


# ============== Custom Agent CRUD ==============

class CustomAgentRequest(BaseModel):
    """Request to create or update a custom agent"""
    name: str = Field(description="Unique agent name (snake_case)")
    display_name: str = Field(description="Human-friendly name")
    role: str = Field(description="Agent role description")
    description: str = Field(default="", description="Detailed description")
    system_prompt: str = Field(default="", description="System prompt for the LLM")
    model: str = Field(default="gpt-4o-mini", description="LLM model to use")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    tools: List[str] = Field(default_factory=list, description="Tool names the agent can use")
    enabled: bool = Field(default=True)


@router.get("/custom/list")
async def list_custom_agents():
    """List all custom agents from the database"""
    conn = sqlite3.connect(CUSTOM_AGENTS_DB)
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM custom_agents ORDER BY created_at DESC").fetchall()
    conn.close()
    return {"custom_agents": [dict(r) for r in rows]}


@router.post("/custom/create")
async def create_custom_agent(request: CustomAgentRequest):
    """Create a new custom agent definition"""
    now = datetime.now().isoformat()
    try:
        conn = sqlite3.connect(CUSTOM_AGENTS_DB)
        conn.execute(
            """INSERT INTO custom_agents (name, display_name, role, description, system_prompt, model, temperature, tools, created_at, updated_at, enabled)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (request.name, request.display_name, request.role, request.description,
             request.system_prompt, request.model, request.temperature,
             json.dumps(request.tools), now, now, 1 if request.enabled else 0)
        )
        conn.commit()
        conn.close()
        return {"success": True, "agent_name": request.name, "message": f"Custom agent '{request.display_name}' created"}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail=f"Agent '{request.name}' already exists")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/custom/{agent_name}")
async def update_custom_agent(agent_name: str, request: CustomAgentRequest):
    """Update an existing custom agent"""
    now = datetime.now().isoformat()
    conn = sqlite3.connect(CUSTOM_AGENTS_DB)
    cur = conn.execute("SELECT name FROM custom_agents WHERE name = ?", (agent_name,))
    if not cur.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"Custom agent '{agent_name}' not found")
    conn.execute(
        """UPDATE custom_agents SET display_name=?, role=?, description=?, system_prompt=?, model=?, temperature=?, tools=?, updated_at=?, enabled=?
           WHERE name=?""",
        (request.display_name, request.role, request.description, request.system_prompt,
         request.model, request.temperature, json.dumps(request.tools), now,
         1 if request.enabled else 0, agent_name)
    )
    conn.commit()
    conn.close()
    return {"success": True, "agent_name": agent_name, "message": f"Custom agent '{agent_name}' updated"}


@router.delete("/custom/{agent_name}")
async def delete_custom_agent(agent_name: str):
    """Delete a custom agent"""
    conn = sqlite3.connect(CUSTOM_AGENTS_DB)
    cur = conn.execute("DELETE FROM custom_agents WHERE name = ?", (agent_name,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    if deleted == 0:
        raise HTTPException(status_code=404, detail=f"Custom agent '{agent_name}' not found")
    return {"success": True, "agent_name": agent_name, "message": f"Custom agent '{agent_name}' deleted"}