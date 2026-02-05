"""
Memory Agent

Manages conversation memory and context persistence:
- Stores and retrieves conversation history
- Maintains long-term memory
- Receives notes from Notes Agent
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import json

from langchain_community.vectorstores import Chroma
from pydantic import BaseModel, Field

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    TaskAssignment,
    ValidationResult
)

logger = logging.getLogger(__name__)


class MemoryEntry(BaseModel):
    """A memory entry"""
    id: str
    content: str
    memory_type: str  # "conversation", "note", "fact", "preference"
    source_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    importance: float = Field(default=0.5, ge=0, le=1)


class MemoryAgent(BaseAgent):
    """
    Memory Agent for the multi-agent system.
    
    Responsibilities:
    - Store conversation history
    - Maintain long-term memories
    - Receive and store notes from Notes Agent
    - Provide memory context to other agents
    """
    
    def __init__(self, agent_name: str = "memory_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Memory Specialist",
            agent_description="Manages conversation memory and long-term context"
        )
        
        # Load prompt configuration
        self.prompt_template = self.prompt_manager.get_prompt("memory_agent")
        
        # Import config for memory paths
        from config.config import Config
        self.config = Config()
        
        # Memory stores
        self.short_term_memory: List[MemoryEntry] = []
        self.memory_window = 10  # Use default instead of config
        
        # Embeddings for vector store (still needed for memory storage)
        from langchain_openai import OpenAIEmbeddings
        self.embeddings = OpenAIEmbeddings(
            model=self.config.EMBEDDING_MODEL,
            api_key=self.config.OPENAI_API_KEY
        )
        
        # Vector store for long-term memory
        self._init_memory_store()
        
        # Add custom message handlers
        self._message_handlers[MessageType.NOTE_CREATED] = self._handle_note_received
        self._message_handlers[MessageType.MEMORY_STORED] = self._handle_memory_stored
        
        logger.info("MemoryAgent initialized")
    
    def _init_memory_store(self):
        """Initialize the memory vector store"""
        try:
            memory_path = f"{self.config.CHROMA_DB_PATH}/memory"
            self.memory_store = Chroma(
                persist_directory=memory_path,
                embedding_function=self.embeddings,
                collection_name="agent_memory"
            )
            logger.info(f"Memory store initialized at {memory_path}")
        except Exception as e:
            logger.error(f"Error initializing memory store: {e}")
            self.memory_store = None
    
    async def process_task(self, task: TaskAssignment) -> Any:
        """Process a memory-related task"""
        task_type = task.task_type
        
        if task_type == "store_memory":
            return await self._store_memory(task)
        elif task_type == "retrieve_memory":
            return await self._retrieve_memory(task)
        elif task_type == "store_conversation":
            return await self._store_conversation(task)
        elif task_type == "get_context":
            return await self._get_context(task)
        elif task_type == "clear_memory":
            return await self._clear_memory(task)
        else:
            return await self._retrieve_memory(task)
    
    async def _store_memory(self, task: TaskAssignment) -> Dict[str, Any]:
        """Store a memory entry"""
        content = task.input_data.get("content", "")
        memory_type = task.input_data.get("memory_type", "fact")
        importance = task.input_data.get("importance", 0.5)
        metadata = task.input_data.get("metadata", {})
        
        entry = MemoryEntry(
            id=f"mem_{datetime.now().timestamp()}",
            content=content,
            memory_type=memory_type,
            source_agent=task.input_data.get("source_agent"),
            importance=importance,
            metadata=metadata
        )
        
        # Store in short-term memory
        self.short_term_memory.append(entry)
        
        # Trim short-term memory if needed
        if len(self.short_term_memory) > self.memory_window * 2:
            # Move important memories to long-term
            await self._consolidate_memory()
        
        # Store important memories immediately in vector store
        if importance >= 0.7 and self.memory_store:
            try:
                self.memory_store.add_texts(
                    texts=[content],
                    metadatas=[{
                        "id": entry.id,
                        "memory_type": memory_type,
                        "importance": importance,
                        "created_at": entry.created_at.isoformat(),
                        **metadata
                    }]
                )
            except Exception as e:
                logger.error(f"Error storing in vector store: {e}")
        
        return {
            "success": True,
            "memory_id": entry.id,
            "stored_in_long_term": importance >= 0.7
        }
    
    async def _retrieve_memory(self, task: TaskAssignment) -> Dict[str, Any]:
        """Retrieve relevant memories"""
        query = task.input_data.get("query", "")
        limit = task.input_data.get("limit", 5)
        memory_type = task.input_data.get("memory_type")
        
        results = []
        
        # Search short-term memory first
        for entry in reversed(self.short_term_memory):
            if memory_type and entry.memory_type != memory_type:
                continue
            
            # Simple keyword matching for short-term
            if query.lower() in entry.content.lower():
                results.append({
                    "content": entry.content,
                    "memory_type": entry.memory_type,
                    "importance": entry.importance,
                    "created_at": entry.created_at.isoformat(),
                    "source": "short_term"
                })
        
        # Search long-term memory
        if self.memory_store and len(results) < limit:
            try:
                docs = self.memory_store.similarity_search(
                    query, 
                    k=limit - len(results)
                )
                
                for doc in docs:
                    results.append({
                        "content": doc.page_content,
                        "memory_type": doc.metadata.get("memory_type", "unknown"),
                        "importance": doc.metadata.get("importance", 0.5),
                        "created_at": doc.metadata.get("created_at"),
                        "source": "long_term"
                    })
                    
            except Exception as e:
                logger.error(f"Error searching long-term memory: {e}")
        
        return {
            "query": query,
            "memories": results[:limit],
            "count": len(results)
        }
    
    async def _store_conversation(self, task: TaskAssignment) -> Dict[str, Any]:
        """Store a conversation exchange"""
        human_input = task.input_data.get("human", "")
        assistant_response = task.input_data.get("assistant", "")
        
        # Create memory entry for the exchange
        content = f"Human: {human_input}\nAssistant: {assistant_response}"
        
        entry = MemoryEntry(
            id=f"conv_{datetime.now().timestamp()}",
            content=content,
            memory_type="conversation",
            importance=0.4,  # Conversations start with medium-low importance
            metadata={
                "human_input": human_input,
                "assistant_response": assistant_response[:200]
            }
        )
        
        self.short_term_memory.append(entry)
        
        return {
            "success": True,
            "memory_id": entry.id
        }
    
    async def _get_context(self, task: TaskAssignment) -> Dict[str, Any]:
        """Get recent context for a query"""
        query = task.input_data.get("query", "")
        include_long_term = task.input_data.get("include_long_term", True)
        
        context_parts = []
        
        # Get recent short-term memories
        recent = self.short_term_memory[-self.memory_window:]
        for entry in recent:
            context_parts.append({
                "content": entry.content,
                "type": entry.memory_type,
                "recency": "recent"
            })
        
        # Get relevant long-term memories
        if include_long_term:
            long_term_result = await self._retrieve_memory(TaskAssignment(
                task_type="retrieve",
                description="Get long-term context",
                input_data={"query": query, "limit": 3}
            ))
            
            for memory in long_term_result.get("memories", []):
                if memory.get("source") == "long_term":
                    context_parts.append({
                        "content": memory["content"],
                        "type": memory["memory_type"],
                        "recency": "historical"
                    })
        
        return {
            "context": context_parts,
            "short_term_count": len(recent),
            "total_count": len(context_parts)
        }
    
    async def _clear_memory(self, task: TaskAssignment) -> Dict[str, Any]:
        """Clear memory (short-term or all)"""
        clear_long_term = task.input_data.get("clear_long_term", False)
        
        self.short_term_memory.clear()
        
        if clear_long_term and self.memory_store:
            # Reinitialize the store
            self._init_memory_store()
        
        return {
            "success": True,
            "cleared_long_term": clear_long_term
        }
    
    async def _consolidate_memory(self):
        """Consolidate short-term memories to long-term"""
        if not self.memory_store:
            return
        
        # Get memories to consolidate (older, less important ones)
        to_consolidate = self.short_term_memory[:-self.memory_window]
        
        for entry in to_consolidate:
            if entry.importance >= 0.5:  # Only keep somewhat important memories
                try:
                    self.memory_store.add_texts(
                        texts=[entry.content],
                        metadatas=[{
                            "id": entry.id,
                            "memory_type": entry.memory_type,
                            "importance": entry.importance,
                            "created_at": entry.created_at.isoformat(),
                            "consolidated": True
                        }]
                    )
                except Exception as e:
                    logger.error(f"Error consolidating memory: {e}")
        
        # Keep only recent memories
        self.short_term_memory = self.short_term_memory[-self.memory_window:]
        
        logger.info(f"Consolidated {len(to_consolidate)} memories")
    
    async def _handle_note_received(self, message: AgentMessage):
        """Handle notes received from Notes Agent"""
        note_content = message.content.get("note", "")
        note_type = message.content.get("type", "note")
        importance = message.content.get("importance", 0.6)
        
        task = TaskAssignment(
            task_type="store_memory",
            description="Store note from Notes Agent",
            input_data={
                "content": note_content,
                "memory_type": "note",
                "importance": importance,
                "source_agent": message.source_agent,
                "metadata": {"note_type": note_type}
            }
        )
        
        result = await self._store_memory(task)
        
        logger.info(f"Stored note from {message.source_agent}: {result}")
    
    async def _handle_memory_stored(self, message: AgentMessage):
        """Handle confirmation of memory storage"""
        logger.debug(f"Memory stored confirmation: {message.content}")
