"""
Chat Router

REST API endpoints for chat operations:
- Process queries through the agent system with RAG
- Uses Manager Agent for coordinated multi-agent processing
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import asyncio

from fastapi import APIRouter, HTTPException
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


class ChatResponse(BaseModel):
    """Chat response"""
    message_id: str
    response: str
    conversation_id: str
    agents_involved: List[str]
    sources: List[Dict[str, Any]] = []
    timestamp: str


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


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """
    Send a message and get response using TRUE multi-agent coordination.
    
    Flow:
    1. User query → Manager Agent
    2. Manager Agent → Planning Agent (creates execution plan)
    3. Planning Agent → RAG Agent (if needed) + Thinking Agent
    4. RAG Agent queries vector databases
    5. Thinking Agent performs reasoning with RAG context
    6. Validation Agent checks response quality
    7. Manager Agent returns final response
    
    This is a REAL agent workflow with actual waiting time (10-20 seconds typical).
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
