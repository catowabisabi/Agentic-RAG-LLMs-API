"""
Chat Router

REST API endpoints for chat operations:
- Process queries through the agent system with RAG
- Uses Manager Agent for coordinated multi-agent processing
- Supports both sync and async (background) processing modes
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import asyncio

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from agents.shared_services.agent_registry import AgentRegistry
from agents.shared_services.websocket_manager import WebSocketManager
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    TaskAssignment
)
from config.config import Config
from services.vectordb_manager import vectordb_manager
from services.task_manager import task_manager, TaskStatus
from services.session_db import session_db, TaskStatus as DBTaskStatus, StepType

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])
config = Config()

# Get manager agent from registry
registry = AgentRegistry()


class ChatRequest(BaseModel):
    """Chat request"""
    message: str = Field(description="User message")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    use_rag: bool = Field(default=True, description="Whether to use RAG for context")
    async_mode: bool = Field(default=False, description="If True, returns task_id immediately and processes in background")


class ChatResponse(BaseModel):
    """Chat response"""
    message_id: str
    response: str
    conversation_id: str
    agents_involved: List[str]
    sources: List[Dict[str, Any]] = []
    timestamp: str


class AsyncChatResponse(BaseModel):
    """Response for async mode - returns immediately with task_id"""
    task_id: str
    conversation_id: str
    status: str = "pending"
    message: str = "Task submitted. Poll /chat/task/{task_id} for status or wait for WebSocket updates."


class TaskStatusResponse(BaseModel):
    """Task status response"""
    task_id: str
    status: str
    progress: float
    current_step: str
    agents_involved: List[str]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


# In-memory conversation storage (use Redis in production)
conversations: Dict[str, List[Dict]] = {}


async def get_rag_context(query: str) -> tuple[str, List[Dict]]:
    """Query all RAG databases and return relevant context"""
    try:
        # Get database list and filter to only non-empty databases
        db_list = vectordb_manager.list_databases()
        active_dbs = [db["name"] for db in db_list if db.get("document_count", 0) > 0]
        
        if not active_dbs:
            logger.warning("No non-empty databases found for RAG query")
            return "", []
        
        context_parts = []
        sources = []
        
        # Query each database individually to handle errors gracefully
        for db_name in active_dbs:
            try:
                result = await vectordb_manager.query(query, db_name, n_results=3)
                db_results = result.get("results", [])
                
                if isinstance(db_results, list) and db_results:
                    for item in db_results:
                        if isinstance(item, dict) and item.get("content"):
                            content = item["content"]
                            metadata = item.get("metadata", {})
                            distance = item.get("distance", 999)
                            
                            # Convert distance to similarity (0-1 scale)
                            # Lower distance = higher similarity
                            # Typical distance range is 0-2, so we use max(0, 1 - distance/2)
                            similarity = max(0, min(1, 1 - (distance / 2)))
                            
                            # Only include if similarity > 0.3 (distance < 1.4)
                            if similarity > 0.3:
                                context_parts.append(f"[From {db_name}]: {content[:500]}")
                                sources.append({
                                    "database": db_name,
                                    "title": metadata.get("title", metadata.get("source", "Unknown")),
                                    "relevance": round(similarity, 2)
                                })
            except Exception as db_error:
                # Skip databases with errors (e.g., embedding dimension mismatch)
                logger.warning(f"Skipping {db_name} due to error: {db_error}")
                continue
        
        context = "\n\n".join(context_parts) if context_parts else ""
        return context, sources
        
    except Exception as e:
        logger.error(f"RAG query error: {e}")
        return "", []


async def process_chat_task(
    task_id: str,
    message: str,
    conversation_id: str,
    use_rag: bool,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Background task handler for chat processing.
    This runs independently of the frontend connection.
    
    Now integrated with SessionDB for persistent storage and recovery.
    """
    ws_manager = WebSocketManager()
    registry = AgentRegistry()
    
    # Ensure session exists in database
    session = session_db.get_or_create_session(conversation_id, "Chat Session")
    
    # Create root task in database with session-linked UID
    db_task = session_db.create_task(
        session_id=conversation_id,
        agent_name="manager_agent",
        task_type="user_query",
        description=message[:200],
        input_data={"query": message, "use_rag": use_rag, "context": context}
    )
    task_uid = db_task.task_uid
    
    # Store user message in database
    session_db.add_message(
        session_id=conversation_id,
        role="user",
        content=message,
        task_uid=task_uid
    )
    
    # Update task status to running
    session_db.update_task_status(task_uid, DBTaskStatus.RUNNING)
    
    # Add initialization step
    session_db.add_step(
        task_uid=task_uid,
        session_id=conversation_id,
        agent_name="system",
        step_type=StepType.THINKING,
        content={"status": "Initializing task", "task_id": task_id, "task_uid": task_uid}
    )
    
    # Update progress (legacy task_manager for polling)
    task_manager.update_progress(task_id, 5, "Initializing...", ["manager_agent"])
    
    try:
        # Get manager agent
        manager_agent = registry.get_agent("manager_agent")
        if not manager_agent:
            raise Exception("Manager agent not available")
        
        task_manager.update_progress(task_id, 10, "Manager agent analyzing query...")
        
        # Add step for manager start
        session_db.add_step(
            task_uid=task_uid,
            session_id=conversation_id,
            agent_name="manager_agent",
            step_type=StepType.THINKING,
            content={"status": "Analyzing query", "query": message[:100]}
        )
        
        # Broadcast start via WebSocket (with task_uid for session linking)
        await ws_manager.broadcast_agent_activity({
            "type": "agent_started",
            "agent": "manager_agent",
            "task_id": task_id,
            "task_uid": task_uid,
            "session_id": conversation_id,
            "content": {"query": message[:100], "conversation_id": conversation_id},
            "timestamp": datetime.now().isoformat()
        })
        
        # Create task assignment (use task_uid for session linking)
        task = TaskAssignment(
            task_id=task_uid,  # Use session-linked UID
            task_type="user_query",
            description=message,
            input_data={
                "query": message,
                "conversation_id": conversation_id,
                "session_id": conversation_id,
                "task_uid": task_uid,
                "use_rag": use_rag,
                "context": context
            },
            priority=1
        )
        
        task_manager.update_progress(task_id, 20, "Processing with agents...", ["manager_agent", "planning_agent"])
        
        # Process through manager (this takes time)
        start_time = datetime.now()
        result = await manager_agent.process_task(task)
        processing_time = (datetime.now() - start_time).total_seconds()
        
        task_manager.update_progress(task_id, 90, "Finalizing response...")
        
        # Extract response
        if isinstance(result, dict):
            response_text = result.get("response", result.get("content", str(result)))
            agents_involved = result.get("agents_involved", ["manager_agent"])
            sources = result.get("sources", [])
        else:
            response_text = str(result)
            agents_involved = ["manager_agent"]
            sources = []
        
        # Store in conversation history (legacy)
        if conversation_id in conversations:
            conversations[conversation_id].append({
                "id": task_id,
                "role": "assistant",
                "content": response_text,
                "timestamp": datetime.now().isoformat(),
                "sources": sources,
                "processing_time": processing_time
            })
        
        # Store assistant message in database
        session_db.add_message(
            session_id=conversation_id,
            role="assistant",
            content=response_text,
            task_uid=task_uid,
            agents_involved=agents_involved,
            sources=sources,
            metadata={"processing_time": processing_time}
        )
        
        # Update task as completed in database
        session_db.update_task_status(
            task_uid,
            DBTaskStatus.COMPLETED,
            result={
                "response": response_text,
                "agents_involved": agents_involved,
                "sources": sources,
                "processing_time": processing_time
            }
        )
        
        # Add completion step
        session_db.add_step(
            task_uid=task_uid,
            session_id=conversation_id,
            agent_name="manager_agent",
            step_type=StepType.LLM_RESPONSE,
            content={
                "status": "completed",
                "response_preview": response_text[:200] + "..." if len(response_text) > 200 else response_text,
                "agents": agents_involved,
                "processing_time": processing_time
            },
            duration_ms=int(processing_time * 1000)
        )
        
        # Broadcast completion (with session info)
        await ws_manager.broadcast_agent_activity({
            "type": "task_completed",
            "task_id": task_id,
            "task_uid": task_uid,
            "session_id": conversation_id,
            "agent": "manager_agent",
            "content": {
                "response": response_text[:200] + "..." if len(response_text) > 200 else response_text,
                "sources_count": len(sources),
                "agents": agents_involved,
                "processing_time": processing_time
            },
            "timestamp": datetime.now().isoformat()
        })
        
        return {
            "response": response_text,
            "agents_involved": agents_involved,
            "sources": sources,
            "processing_time": processing_time,
            "conversation_id": conversation_id,
            "task_uid": task_uid
        }
        
    except Exception as e:
        logger.error(f"Background task error: {e}", exc_info=True)
        
        # Update task as failed in database
        session_db.update_task_status(task_uid, DBTaskStatus.FAILED, error=str(e))
        
        # Add error step
        session_db.add_step(
            task_uid=task_uid,
            session_id=conversation_id,
            agent_name="system",
            step_type=StepType.ERROR,
            content={"error": str(e)}
        )
        
        await ws_manager.broadcast_agent_activity({
            "type": "task_error",
            "task_id": task_id,
            "task_uid": task_uid,
            "session_id": conversation_id,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        })
        raise


@router.post("/message")
async def send_message(request: ChatRequest):
    """
    Send a message and get response using TRUE multi-agent coordination.
    
    Modes:
    - async_mode=False (default): Wait for response (may take 20-60 seconds)
    - async_mode=True: Return task_id immediately, process in background
    
    For async_mode, poll /chat/task/{task_id} for status, or listen on WebSocket.
    """
    ws_manager = WebSocketManager()
    registry = AgentRegistry()
    
    # Get or create conversation
    conversation_id = request.conversation_id or str(uuid.uuid4())
    
    if conversation_id not in conversations:
        conversations[conversation_id] = []
    
    # Add user message to history
    message_id = str(uuid.uuid4())
    conversations[conversation_id].append({
        "id": message_id,
        "role": "user",
        "content": request.message,
        "timestamp": datetime.now().isoformat()
    })
    
    # ============================================
    # ASYNC MODE: Return immediately, process in background
    # ============================================
    if request.async_mode:
        # Create background task
        task_id = task_manager.create_task(
            task_type="chat",
            input_data={
                "message": request.message,
                "conversation_id": conversation_id,
                "use_rag": request.use_rag,
                "context": request.context
            }
        )
        
        # Start background processing (fire-and-forget)
        asyncio.create_task(
            task_manager.run_task(
                task_id,
                process_chat_task,
                message=request.message,
                conversation_id=conversation_id,
                use_rag=request.use_rag,
                context=request.context
            )
        )
        
        logger.info(f"[CHAT] Async task {task_id} created for conversation {conversation_id}")
        
        return AsyncChatResponse(
            task_id=task_id,
            conversation_id=conversation_id,
            status="pending",
            message="Task submitted. Poll /chat/task/{task_id} for status or wait for WebSocket updates."
        )
    
    # ============================================
    # SYNC MODE: Wait for response (original behavior)
    # ============================================
    try:
        # === STEP 1: Send query to Manager Agent ===
        logger.info(f"[CHAT] Sending query to Manager Agent: {request.message[:50]}...")
        
        # Get manager agent from registry
        manager_agent = registry.get_agent("manager_agent")
        if not manager_agent:
            raise HTTPException(status_code=500, detail="Manager agent not available")
        
        # Broadcast start
        await ws_manager.broadcast_agent_activity({
            "type": "agent_started",
            "agent": "manager_agent",
            "source": "user",
            "target": "manager_agent",
            "content": {"query": request.message[:100], "conversation_id": conversation_id},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        # Create task for manager
        task = TaskAssignment(
            task_id=message_id,
            task_type="user_query",
            description=request.message,
            input_data={
                "query": request.message,
                "conversation_id": conversation_id,
                "use_rag": request.use_rag,
                "context": request.context
            },
            priority=1
        )
        
        # Broadcast thinking
        await ws_manager.broadcast_agent_activity({
            "type": "thinking",
            "agent": "manager_agent",
            "source": "manager_agent",
            "target": "planning_agent",
            "content": {"status": "Analyzing query and routing to appropriate agents..."},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        # === STEP 2: Manager processes and routes task ===
        # This will internally trigger planning, RAG, thinking, and validation agents
        logger.info("[CHAT] Manager agent processing task...")
        start_time = datetime.now()
        
        # Process through manager (this is async and will take time)
        result = await manager_agent.process_task(task)
        
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"[CHAT] Manager agent completed in {processing_time:.2f}s")
        
        # Extract response from result
        if isinstance(result, dict):
            response_text = result.get("response", result.get("content", str(result)))
            agents_involved = result.get("agents_involved", ["manager_agent"])
            sources = result.get("sources", [])
        else:
            response_text = str(result)
            agents_involved = ["manager_agent"]
            sources = []
        
        # Add assistant message to history
        conversations[conversation_id].append({
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.now().isoformat(),
            "sources": sources,
            "processing_time": processing_time
        })
        
        # Broadcast completion
        await ws_manager.broadcast_agent_activity({
            "type": "agent_completed",
            "agent": "manager_agent",
            "source": "manager_agent",
            "target": "user",
            "content": {
                "response_length": len(response_text),
                "sources_used": len(sources),
                "agents_coordinated": agents_involved,
                "processing_time_seconds": processing_time
            },
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        return ChatResponse(
            message_id=message_id,
            response=response_text,
            conversation_id=conversation_id,
            agents_involved=agents_involved,
            sources=sources,
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"[CHAT] Error: {e}", exc_info=True)
        # Notify about error
        await ws_manager.broadcast_agent_activity({
            "type": "agent_error",
            "agent": "manager_agent",
            "source": "manager_agent",
            "target": "user",
            "content": {"error": str(e)},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations")
async def list_conversations():
    """List all conversations"""
    return {
        "conversations": [
            {
                "id": conv_id,
                "message_count": len(messages),
                "last_message": messages[-1] if messages else None
            }
            for conv_id, messages in conversations.items()
        ]
    }


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """Get conversation history"""
    if conversation_id not in conversations:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found"
        )
    
    return {
        "conversation_id": conversation_id,
        "messages": conversations[conversation_id]
    }


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a conversation"""
    if conversation_id not in conversations:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found"
        )
    
    del conversations[conversation_id]
    
    return {
        "success": True,
        "deleted": conversation_id
    }


@router.post("/conversations/{conversation_id}/clear")
async def clear_conversation(conversation_id: str):
    """Clear conversation history"""
    if conversation_id not in conversations:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation {conversation_id} not found"
        )
    
    conversations[conversation_id] = []
    
    return {
        "success": True,
        "cleared": conversation_id
    }


# ============================================
# BACKGROUND TASK ENDPOINTS
# ============================================

@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Get the status of a background chat task.
    
    Poll this endpoint to check if your async task has completed.
    Returns progress, status, and result when done.
    """
    task = task_manager.get_task_status(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return TaskStatusResponse(
        task_id=task["task_id"],
        status=task["status"],
        progress=task["progress"],
        current_step=task["current_step"],
        agents_involved=task["agents_involved"],
        result=task.get("result"),
        error=task.get("error"),
        created_at=task["created_at"],
        completed_at=task.get("completed_at")
    )


@router.get("/task/{task_id}/result")
async def get_task_result(task_id: str):
    """
    Get the full result of a completed task.
    
    Returns the complete response once the task is done.
    Returns 202 if still processing.
    """
    task = task_manager.get_task_status(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    status = task["status"]
    
    if status == "pending" or status == "running":
        return {
            "status": status,
            "progress": task["progress"],
            "current_step": task["current_step"],
            "message": "Task still processing. Please wait."
        }
    
    if status == "failed":
        raise HTTPException(status_code=500, detail=task.get("error", "Task failed"))
    
    if status == "cancelled":
        raise HTTPException(status_code=410, detail="Task was cancelled")
    
    # Completed
    return {
        "status": "completed",
        "result": task.get("result", {}),
        "agents_involved": task["agents_involved"],
        "completed_at": task.get("completed_at")
    }


@router.post("/task/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running task"""
    success = task_manager.cancel_task(task_id)
    
    if not success:
        task = task_manager.get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        return {"success": False, "message": "Task is not running or already completed"}
    
    return {"success": True, "message": f"Task {task_id} cancellation requested"}


@router.get("/tasks")
async def list_tasks(status: Optional[str] = None, limit: int = 50):
    """
    List all background tasks.
    
    Optionally filter by status: pending, running, completed, failed, cancelled
    """
    task_status = None
    if status:
        try:
            task_status = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    tasks = task_manager.list_tasks(status=task_status, limit=limit)
    
    return {
        "tasks": tasks,
        "count": len(tasks)
    }
