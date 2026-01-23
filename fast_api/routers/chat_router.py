"""
Chat Router

REST API endpoints for chat operations:
- Process queries through the agent system
- Get conversation history
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from agents.shared_services.agent_registry import AgentRegistry
from agents.shared_services.websocket_manager import WebSocketManager
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    TaskAssignment
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    """Chat request"""
    message: str = Field(description="User message")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


class ChatResponse(BaseModel):
    """Chat response"""
    message_id: str
    response: str
    conversation_id: str
    agents_involved: List[str]
    timestamp: str


# In-memory conversation storage (use Redis in production)
conversations: Dict[str, List[Dict]] = {}


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Send a message and get response"""
    registry = AgentRegistry()
    ws_manager = WebSocketManager()
    
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
    
    # Get manager agent
    manager = registry.get_agent("manager_agent")
    
    if not manager:
        raise HTTPException(
            status_code=500,
            detail="Manager agent not available"
        )
    
    # Create task
    task = TaskAssignment(
        task_id=message_id,
        task_type="process_query",
        input_data={
            "query": request.message,
            "context": request.context,
            "conversation_id": conversation_id,
            "history": conversations[conversation_id][-10:]  # Last 10 messages
        },
        context=request.message,
        priority=1
    )
    
    # Send to manager
    message = AgentMessage(
        type=MessageType.TASK_ASSIGNED,
        source_agent="api",
        target_agent="manager_agent",
        content=task.model_dump(),
        priority=1
    )
    
    await ws_manager.send_to_agent(message)
    
    # Wait for response (with timeout)
    # In production, use proper async message queue
    import asyncio
    
    try:
        # Simple polling for demonstration
        # In production, use proper async patterns
        for _ in range(30):  # 30 second timeout
            await asyncio.sleep(1)
            
            # Check for response in manager's history
            for hist in manager.message_history[-10:]:
                if (hist.type == MessageType.AGENT_COMPLETED and
                    hist.content.get("task_id") == message_id):
                    
                    response = hist.content.get("result", {})
                    response_text = response.get("response", "No response")
                    
                    # Add assistant message to history
                    conversations[conversation_id].append({
                        "id": str(uuid.uuid4()),
                        "role": "assistant",
                        "content": response_text,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    return ChatResponse(
                        message_id=message_id,
                        response=response_text,
                        conversation_id=conversation_id,
                        agents_involved=response.get("agents", []),
                        timestamp=datetime.now().isoformat()
                    )
        
        # Timeout
        raise HTTPException(
            status_code=408,
            detail="Request timed out"
        )
        
    except Exception as e:
        logger.error(f"Chat error: {e}")
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
