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

# Cerebro Memory System
from services.cerebro_memory import get_cerebro, MemoryType, MemoryImportance
from agents.auxiliary.memory_capture_agent import process_message_for_memory, get_user_context_for_prompt

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])
config = Config()

# Get manager agent from registry
registry = AgentRegistry()


class ChatRequest(BaseModel):
    """Chat request"""
    message: str = Field(description="User message")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")
    user_id: Optional[str] = Field(default="default", description="User ID for personalization")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    use_rag: bool = Field(default=True, description="Whether to use RAG for context")
    async_mode: bool = Field(default=False, description="If True, returns task_id immediately and processes in background")
    enable_memory: bool = Field(default=True, description="Enable personalized memory capture")


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


# Import Entry Classifier
from agents.core.entry_classifier import get_entry_classifier


async def process_chat_task(
    task_id: str,
    message: str,
    conversation_id: str,
    use_rag: bool,
    context: Dict[str, Any],
    user_id: str = "default",
    enable_memory: bool = True
) -> Dict[str, Any]:
    """
    Background task handler for chat processing.
    
    架構：
    1. Entry Classifier 判斷 casual vs task
    2. Casual → Casual Chat Agent
    3. Task → Manager Agent → Planning → Execute
    
    Now integrated with SessionDB for persistent storage and recovery.
    Also integrates with Cerebro memory system for personalization.
    """
    ws_manager = WebSocketManager()
    registry = AgentRegistry()
    
    # =========== CEREBRO: Get User Context ===========
    user_context = ""
    if enable_memory:
        try:
            user_context = get_user_context_for_prompt(user_id, message)
            if user_context:
                logger.info(f"[Cerebro] Loaded user context for {user_id}: {len(user_context)} chars")
        except Exception as e:
            logger.warning(f"[Cerebro] Failed to load user context: {e}")
    # ================================================
    
    # Ensure session exists in database
    session = session_db.get_or_create_session(conversation_id, "Chat Session")
    
    # =========== LOAD CHAT HISTORY ===========
    # Get previous messages from this session for context
    previous_messages = session_db.get_session_messages(conversation_id, limit=config.MEMORY_WINDOW * 2)
    chat_history = []
    for msg in previous_messages:
        if msg.get("role") == "user":
            chat_history.append({"human": msg.get("content", "")})
        elif msg.get("role") == "assistant":
            # Attach to previous entry if exists
            if chat_history and "assistant" not in chat_history[-1]:
                chat_history[-1]["assistant"] = msg.get("content", "")
            else:
                chat_history.append({"assistant": msg.get("content", "")})
    
    # Keep only recent history (last N exchanges)
    if len(chat_history) > config.MEMORY_WINDOW:
        chat_history = chat_history[-config.MEMORY_WINDOW:]
    
    logger.info(f"[Chat] Loaded {len(chat_history)} history entries for session {conversation_id}")
    # ==========================================
    
    # Create root task in database with session-linked UID
    db_task = session_db.create_task(
        session_id=conversation_id,
        agent_name="manager_agent",
        task_type="user_query",
        description=message[:200],
        input_data={
            "query": message,
            "use_rag": use_rag,
            "context": context,
            "chat_history": chat_history,
            "user_context": user_context,  # Cerebro personalization
            "user_id": user_id
        }
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
    task_manager.update_progress(task_id, 5, "Initializing...", ["entry_classifier"])
    
    try:
        # =========== STEP 1: Entry Classification ===========
        # Determine if this is casual chat or needs manager processing
        entry_classifier = get_entry_classifier()
        classification = await entry_classifier.classify(message, user_context)
        
        logger.info(f"[Entry] Classified as: {'casual' if classification.is_casual else 'task'} ({classification.reason})")
        
        # Broadcast classification result
        await ws_manager.broadcast_agent_activity({
            "type": "entry_classification",
            "agent": "entry_classifier",
            "task_id": task_id,
            "session_id": conversation_id,
            "content": {
                "is_casual": classification.is_casual,
                "reason": classification.reason,
                "route_to": "casual_chat_agent" if classification.is_casual else "manager_agent"
            },
            "timestamp": datetime.now().isoformat()
        })
        
        task_manager.update_progress(task_id, 10, f"Routing to {'casual chat' if classification.is_casual else 'manager'}...")
        
        # =========== STEP 2: Route to Appropriate Agent ===========
        if classification.is_casual:
            # Route to Casual Chat Agent directly
            from agents.core.casual_chat_agent import get_casual_chat_agent
            casual_agent = get_casual_chat_agent()
            
            session_db.add_step(
                task_uid=task_uid,
                session_id=conversation_id,
                agent_name="casual_chat_agent",
                step_type=StepType.THINKING,
                content={"status": "Processing casual chat", "query": message[:100]}
            )
            
            await ws_manager.broadcast_agent_activity({
                "type": "agent_started",
                "agent": "casual_chat_agent",
                "task_id": task_id,
                "session_id": conversation_id,
                "content": {"query": message[:100]},
                "timestamp": datetime.now().isoformat()
            })
            
            task = TaskAssignment(
                task_id=task_uid,
                task_type="casual_response",
                description=message,
                input_data={
                    "query": message,
                    "chat_history": chat_history,
                    "user_context": user_context
                },
                priority=1
            )
            
            start_time = datetime.now()
            result = await casual_agent.process_task(task)
            processing_time = (datetime.now() - start_time).total_seconds()
            agents_involved = ["entry_classifier", "casual_chat_agent"]
            
        else:
            # Route to Manager Agent for planning-driven execution
            manager_agent = registry.get_agent("manager_agent")
            if not manager_agent:
                raise Exception("Manager agent not available")
        
            task_manager.update_progress(task_id, 15, "Manager agent creating plan...")
        
            # Add step for manager start
            session_db.add_step(
                task_uid=task_uid,
                session_id=conversation_id,
                agent_name="manager_agent",
                step_type=StepType.THINKING,
                content={"status": "Creating execution plan", "query": message[:100]}
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
            # Pass intent/handler info from classification for handler-based routing
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
                    "context": context,
                    "chat_history": chat_history,  # Include conversation history
                    "user_context": user_context,  # Cerebro personalization
                    "user_id": user_id,
                    # Intent routing info from EntryClassifier
                    "intent": classification.intent,
                    "handler": classification.handler,
                    "matched_by": classification.matched_by
                },
                priority=1
            )
        
            task_manager.update_progress(task_id, 20, "Executing plan...", ["manager_agent", "planning_agent"])
        
            # Process through manager (this takes time)
            start_time = datetime.now()
            result = await manager_agent.process_task(task)
            processing_time = (datetime.now() - start_time).total_seconds()
            agents_involved = result.get("agents_involved", ["manager_agent"])
            if "entry_classifier" not in agents_involved:
                agents_involved = ["entry_classifier"] + agents_involved
        
        task_manager.update_progress(task_id, 90, "Finalizing response...")
        
        # Extract response
        if isinstance(result, dict):
            response_text = result.get("response", result.get("content", str(result)))
            sources = result.get("sources", [])
        else:
            response_text = str(result)
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
        
        # =========== CEREBRO: Capture Memory (Background) ===========
        if enable_memory:
            try:
                # Fire-and-forget memory capture (don't block response)
                asyncio.create_task(
                    process_message_for_memory(
                        user_id=user_id,
                        session_id=conversation_id,
                        message=message,
                        response=response_text
                    )
                )
                logger.debug(f"[Cerebro] Memory capture triggered for user {user_id}")
            except Exception as mem_error:
                logger.warning(f"[Cerebro] Memory capture failed: {mem_error}")
        # ============================================================
        
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
                "context": request.context,
                "user_id": request.user_id,
                "enable_memory": request.enable_memory
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
                context=request.context,
                user_id=request.user_id,
                enable_memory=request.enable_memory
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
    # Now also persists to session_db for consistency
    # ============================================
    try:
        # Ensure session exists in database (same as async mode)
        session = session_db.get_or_create_session(conversation_id, "Chat Session")
        
        # =========== CEREBRO: Get User Context ===========
        user_context = ""
        if request.enable_memory:
            try:
                user_context = get_user_context_for_prompt(request.user_id, request.message)
                if user_context:
                    logger.info(f"[Cerebro] Loaded user context for {request.user_id}: {len(user_context)} chars")
            except Exception as e:
                logger.warning(f"[Cerebro] Failed to load user context: {e}")
        # ================================================
        
        # Load chat history from session_db
        previous_messages = session_db.get_session_messages(conversation_id, limit=config.MEMORY_WINDOW * 2)
        chat_history = []
        for msg in previous_messages:
            if msg.get("role") == "user":
                chat_history.append({"human": msg.get("content", "")})
            elif msg.get("role") == "assistant":
                if chat_history and "assistant" not in chat_history[-1]:
                    chat_history[-1]["assistant"] = msg.get("content", "")
                else:
                    chat_history.append({"assistant": msg.get("content", "")})
        if len(chat_history) > config.MEMORY_WINDOW:
            chat_history = chat_history[-config.MEMORY_WINDOW:]
        
        # Store user message in database
        task_uid = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{conversation_id}_sync"
        session_db.add_message(
            session_id=conversation_id,
            role="user",
            content=request.message,
            task_uid=task_uid
        )
        
        # === STEP 1: Entry Classification ===
        logger.info(f"[CHAT] Entry classification for: {request.message[:50]}...")
        
        entry_classifier = get_entry_classifier()
        classification = await entry_classifier.classify(request.message, user_context)
        
        logger.info(f"[Entry] Classified as: {'casual' if classification.is_casual else 'task'} ({classification.reason})")
        
        # Broadcast classification result
        await ws_manager.broadcast_agent_activity({
            "type": "entry_classification",
            "agent": "entry_classifier",
            "session_id": conversation_id,
            "content": {
                "is_casual": classification.is_casual,
                "reason": classification.reason,
                "route_to": "casual_chat_agent" if classification.is_casual else "manager_agent"
            },
            "timestamp": datetime.now().isoformat()
        })
        
        start_time = datetime.now()
        
        # === STEP 2: Route based on classification ===
        if classification.is_casual:
            # Route to Casual Chat Agent directly
            from agents.core.casual_chat_agent import get_casual_chat_agent
            casual_agent = get_casual_chat_agent()
            
            await ws_manager.broadcast_agent_activity({
                "type": "agent_started",
                "agent": "casual_chat_agent",
                "source": "entry_classifier",
                "target": "casual_chat_agent",
                "content": {"query": request.message[:100], "conversation_id": conversation_id},
                "timestamp": datetime.now().isoformat()
            })
            
            task = TaskAssignment(
                task_id=message_id,
                task_type="casual_response",
                description=request.message,
                input_data={
                    "query": request.message,
                    "chat_history": chat_history,
                    "user_context": user_context
                },
                priority=1
            )
            
            result = await casual_agent.process_task(task)
            agents_involved = ["entry_classifier", "casual_chat_agent"]
            
        else:
            # Route to Manager Agent for planning-driven execution
            manager_agent = registry.get_agent("manager_agent")
            if not manager_agent:
                raise HTTPException(status_code=500, detail="Manager agent not available")
            
            await ws_manager.broadcast_agent_activity({
                "type": "agent_started",
                "agent": "manager_agent",
                "source": "entry_classifier",
                "target": "manager_agent",
                "content": {"query": request.message[:100], "conversation_id": conversation_id},
                "timestamp": datetime.now().isoformat(),
                "priority": 1
            })
            
            task = TaskAssignment(
                task_id=message_id,
                task_type="user_query",
                description=request.message,
                input_data={
                    "query": request.message,
                    "conversation_id": conversation_id,
                    "use_rag": request.use_rag,
                    "context": request.context,
                    "user_context": user_context,
                    "user_id": request.user_id,
                    "chat_history": chat_history
                },
                priority=1
            )
            
            result = await manager_agent.process_task(task)
            agents_involved = result.get("agents_involved", ["manager_agent"])
            if "entry_classifier" not in agents_involved:
                agents_involved = ["entry_classifier"] + agents_involved
        
        processing_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"[CHAT] Completed in {processing_time:.2f}s")
        
        # Extract response from result
        if isinstance(result, dict):
            response_text = result.get("response", result.get("content", str(result)))
            sources = result.get("sources", [])
        else:
            response_text = str(result)
            sources = []
        
        # Add assistant message to in-memory history (legacy)
        conversations[conversation_id].append({
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.now().isoformat(),
            "sources": sources,
            "processing_time": processing_time
        })
        
        # Store assistant message in database (NEW - sync with async mode)
        session_db.add_message(
            session_id=conversation_id,
            role="assistant",
            content=response_text,
            task_uid=task_uid,
            agents_involved=agents_involved,
            sources=sources,
            metadata={"processing_time": processing_time}
        )
        
        # =========== CEREBRO: Capture Memory (Background) ===========
        if request.enable_memory:
            try:
                # Fire-and-forget memory capture (don't block response)
                asyncio.create_task(
                    process_message_for_memory(
                        user_id=request.user_id,
                        session_id=conversation_id,
                        message=request.message,
                        response=response_text
                    )
                )
                logger.debug(f"[Cerebro] Memory capture triggered for user {request.user_id}")
            except Exception as mem_error:
                logger.warning(f"[Cerebro] Memory capture failed: {mem_error}")
        # ============================================================
        
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
