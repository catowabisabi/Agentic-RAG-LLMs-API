"""
Notes Agent

Creates and organizes notes from information:
- Transforms data into structured notes
- Sends notes to Memory Agent for storage
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    MessageProtocol,
    TaskAssignment,
    ValidationResult
)
from config.config import Config

logger = logging.getLogger(__name__)


class StructuredNote(BaseModel):
    """A structured note"""
    title: str = Field(description="Brief title for the note")
    summary: str = Field(description="Concise summary of the key information")
    key_points: List[str] = Field(description="List of key points extracted")
    tags: List[str] = Field(description="Relevant tags for categorization")
    importance: float = Field(
        default=0.5, 
        ge=0, 
        le=1, 
        description="Importance score"
    )


class NotesAgent(BaseAgent):
    """
    Notes Agent for the multi-agent system.
    
    Responsibilities:
    - Transform information into structured notes
    - Extract key points and summaries
    - Send notes to Memory Agent for storage
    """
    
    def __init__(self, agent_name: str = "notes_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Notes Specialist",
            agent_description="Creates and organizes notes from information"
        )
        
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.3,
            api_key=self.config.OPENAI_API_KEY
        )
        
        # Local note cache
        self.notes_cache: Dict[str, StructuredNote] = {}
        
        logger.info("NotesAgent initialized")
    
    async def process_task(self, task: TaskAssignment) -> Any:
        """Process a notes-related task"""
        task_type = task.task_type
        
        if task_type == "create_note":
            return await self._create_note(task)
        elif task_type == "search_notes":
            return await self._search_notes(task)
        elif task_type == "summarize_to_note":
            return await self._summarize_to_note(task)
        else:
            return await self._create_note(task)
    
    async def _create_note(self, task: TaskAssignment) -> Dict[str, Any]:
        """Create a structured note from content"""
        content = task.input_data.get("content", "")
        context = task.input_data.get("context", "")
        
        prompt = ChatPromptTemplate.from_template(
            """Analyze the following content and create a structured note.

Content:
{content}

Additional Context:
{context}

Create a well-organized note with:
1. A brief, descriptive title
2. A concise summary (2-3 sentences)
3. Key points (bullet points)
4. Relevant tags for categorization
5. An importance score (0-1) based on usefulness

Respond with your structured note."""
        )
        
        chain = prompt | self.llm.with_structured_output(StructuredNote)
        
        try:
            note = chain.invoke({
                "content": content,
                "context": context or "No additional context"
            })
            
            # Generate note ID
            note_id = f"note_{datetime.now().timestamp()}"
            
            # Store in cache
            self.notes_cache[note_id] = note
            
            # Send to Memory Agent
            await self._send_to_memory(note, note_id)
            
            return {
                "success": True,
                "note_id": note_id,
                "note": note.model_dump()
            }
            
        except Exception as e:
            logger.error(f"Error creating note: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _summarize_to_note(self, task: TaskAssignment) -> Dict[str, Any]:
        """Create a summary note from a longer piece of content"""
        content = task.input_data.get("content", "")
        max_length = task.input_data.get("max_length", 500)
        
        prompt = ChatPromptTemplate.from_template(
            """Create a comprehensive but concise note summarizing this content.
The summary should be no longer than {max_length} characters.

Content to summarize:
{content}

Create a structured note that captures the essential information."""
        )
        
        chain = prompt | self.llm.with_structured_output(StructuredNote)
        
        try:
            note = chain.invoke({
                "content": content,
                "max_length": max_length
            })
            
            note_id = f"summary_{datetime.now().timestamp()}"
            self.notes_cache[note_id] = note
            
            await self._send_to_memory(note, note_id)
            
            return {
                "success": True,
                "note_id": note_id,
                "note": note.model_dump()
            }
            
        except Exception as e:
            logger.error(f"Error summarizing to note: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _search_notes(self, task: TaskAssignment) -> Dict[str, Any]:
        """Search through cached notes"""
        query = task.input_data.get("query", "")
        limit = task.input_data.get("limit", 5)
        
        results = []
        query_lower = query.lower()
        
        for note_id, note in self.notes_cache.items():
            score = 0
            
            # Check title
            if query_lower in note.title.lower():
                score += 3
            
            # Check summary
            if query_lower in note.summary.lower():
                score += 2
            
            # Check key points
            for point in note.key_points:
                if query_lower in point.lower():
                    score += 1
            
            # Check tags
            for tag in note.tags:
                if query_lower in tag.lower():
                    score += 2
            
            if score > 0:
                results.append({
                    "note_id": note_id,
                    "note": note.model_dump(),
                    "relevance_score": score
                })
        
        # Sort by relevance
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        return {
            "query": query,
            "results": results[:limit],
            "count": len(results)
        }
    
    async def _send_to_memory(self, note: StructuredNote, note_id: str):
        """Send note to Memory Agent for storage"""
        note_content = f"""
Title: {note.title}
Summary: {note.summary}
Key Points:
{chr(10).join('- ' + point for point in note.key_points)}
Tags: {', '.join(note.tags)}
"""
        
        message = AgentMessage(
            type=MessageType.NOTE_CREATED,
            source_agent=self.agent_name,
            target_agent="memory_agent",
            content={
                "note": note_content,
                "type": "structured_note",
                "importance": note.importance,
                "note_id": note_id,
                "metadata": {
                    "title": note.title,
                    "tags": note.tags
                }
            }
        )
        
        await self.ws_manager.send_to_agent(message)
        
        logger.info(f"Sent note {note_id} to Memory Agent")
