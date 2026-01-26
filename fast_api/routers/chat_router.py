"""
Chat Router

REST API endpoints for chat operations:
- Process queries through the agent system with RAG
- Get conversation history
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
        # Query all databases
        results = await vectordb_manager.query_all_databases(query, n_results=3)
        
        context_parts = []
        sources = []
        
        for db_name, db_results in results.get("results", {}).items():
            if isinstance(db_results, list) and db_results:
                for result in db_results:
                    if isinstance(result, dict) and result.get("content"):
                        content = result["content"]
                        metadata = result.get("metadata", {})
                        distance = result.get("distance", 1.0)
                        
                        # Only include relevant results (distance < 1.5)
                        if distance < 1.5:
                            context_parts.append(f"[From {db_name}]: {content[:500]}...")
                            sources.append({
                                "database": db_name,
                                "title": metadata.get("title", metadata.get("source", "Unknown")),
                                "relevance": round(1 - distance, 2) if distance else 0
                            })
        
        context = "\n\n".join(context_parts) if context_parts else ""
        return context, sources
        
    except Exception as e:
        logger.error(f"RAG query error: {e}")
        return "", []


@router.post("/message", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Send a message and get response using RAG-enhanced LLM processing"""
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
    
    try:
        # Get RAG context if enabled
        rag_context = ""
        sources = []
        agents_involved = ["chat_agent"]
        
        if request.use_rag:
            # Notify frontend about RAG query
            await ws_manager.broadcast_to_clients({
                "type": "chat_rag_query",
                "message_id": message_id,
                "timestamp": datetime.now().isoformat()
            })
            
            rag_context, sources = await get_rag_context(request.message)
            if rag_context:
                agents_involved.append("rag_agent")
        
        # Initialize LLM
        llm = ChatOpenAI(
            model=config.DEFAULT_MODEL,
            temperature=0.7,
            api_key=config.OPENAI_API_KEY
        )
        
        # Build conversation context
        history_messages = []
        for msg in conversations[conversation_id][-10:]:
            if msg["role"] == "user":
                history_messages.append(f"User: {msg['content']}")
            else:
                history_messages.append(f"Assistant: {msg['content']}")
        
        history_text = "\n".join(history_messages[:-1])  # Exclude current message
        
        # Create prompt with RAG context
        if rag_context:
            prompt = ChatPromptTemplate.from_template(
                """You are a helpful AI assistant with access to a knowledge base. Use the following context from the knowledge base to help answer the user's question. If the context is relevant, incorporate it into your answer. If not relevant, you can answer from your general knowledge.

=== Knowledge Base Context ===
{rag_context}
=== End Context ===

{history}

User: {message}

Provide a helpful, accurate, and informative response based on the available context and your knowledge."""
            )
        else:
            prompt = ChatPromptTemplate.from_template(
                """You are a helpful AI assistant. Answer the user's question clearly and concisely.

{history}

User: {message}

Provide a helpful and informative response."""
            )
        
        chain = prompt | llm
        
        # Notify frontend about processing
        await ws_manager.broadcast_to_clients({
            "type": "chat_processing",
            "message_id": message_id,
            "has_rag_context": bool(rag_context),
            "timestamp": datetime.now().isoformat()
        })
        
        # Get response from LLM
        invoke_params = {
            "history": history_text if history_text else "No previous conversation.",
            "message": request.message
        }
        if rag_context:
            invoke_params["rag_context"] = rag_context
            
        result = await chain.ainvoke(invoke_params)
        
        response_text = result.content
        
        # Add assistant message to history
        conversations[conversation_id].append({
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": response_text,
            "timestamp": datetime.now().isoformat(),
            "sources": sources
        })
        
        # Notify frontend about completion
        await ws_manager.broadcast_to_clients({
            "type": "chat_completed",
            "message_id": message_id,
            "timestamp": datetime.now().isoformat()
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
