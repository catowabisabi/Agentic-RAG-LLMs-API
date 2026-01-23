"""
Summarize Agent

Creates summaries and condensed information:
- Text summarization
- Key point extraction
- Abstractive and extractive summaries
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
    TaskAssignment
)
from config.config import Config

logger = logging.getLogger(__name__)


class Summary(BaseModel):
    """A summary result"""
    title: str = Field(description="Title for the summary")
    summary: str = Field(description="The main summary text")
    key_points: List[str] = Field(description="Key points from the content")
    word_count: int = Field(description="Word count of the summary")


class SummarizeAgent(BaseAgent):
    """
    Summarize Agent for the multi-agent system.
    
    Responsibilities:
    - Create concise summaries of content
    - Extract key points
    - Generate different types of summaries
    """
    
    def __init__(self, agent_name: str = "summarize_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Summary Specialist",
            agent_description="Creates summaries and condensed information"
        )
        
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.3,
            api_key=self.config.OPENAI_API_KEY
        )
        
        logger.info("SummarizeAgent initialized")
    
    async def process_task(self, task: TaskAssignment) -> Any:
        """Process a summarization task"""
        task_type = task.task_type
        
        if task_type == "summarize":
            return await self._summarize(task)
        elif task_type == "key_points":
            return await self._extract_key_points(task)
        elif task_type == "abstractive":
            return await self._abstractive_summary(task)
        elif task_type == "extractive":
            return await self._extractive_summary(task)
        elif task_type == "bullet_points":
            return await self._bullet_points(task)
        else:
            return await self._summarize(task)
    
    async def _summarize(self, task: TaskAssignment) -> Dict[str, Any]:
        """Create a comprehensive summary"""
        content = task.input_data.get("content", task.context)
        max_length = task.input_data.get("max_length", 200)
        style = task.input_data.get("style", "concise")
        
        prompt = ChatPromptTemplate.from_template(
            """Create a {style} summary of the following content.
Keep the summary under {max_length} words.

Content:
{content}

Provide:
1. A brief title
2. The main summary
3. 3-5 key points"""
        )
        
        chain = prompt | self.llm.with_structured_output(Summary)
        
        try:
            result = chain.invoke({
                "content": content,
                "max_length": max_length,
                "style": style
            })
            
            return {
                "success": True,
                "summary": result.model_dump()
            }
        except Exception as e:
            # Fallback to unstructured
            chain = prompt | self.llm
            result = chain.invoke({
                "content": content,
                "max_length": max_length,
                "style": style
            })
            
            return {
                "success": True,
                "summary": {
                    "title": "Summary",
                    "summary": result.content,
                    "key_points": [],
                    "word_count": len(result.content.split())
                }
            }
    
    async def _extract_key_points(self, task: TaskAssignment) -> Dict[str, Any]:
        """Extract key points from content"""
        content = task.input_data.get("content", task.context)
        num_points = task.input_data.get("num_points", 5)
        
        prompt = ChatPromptTemplate.from_template(
            """Extract the {num_points} most important key points from this content.

Content:
{content}

Return only the key points as a numbered list."""
        )
        
        chain = prompt | self.llm
        
        result = chain.invoke({
            "content": content,
            "num_points": num_points
        })
        
        # Parse the points
        lines = result.content.strip().split("\n")
        key_points = []
        for line in lines:
            # Remove numbering
            point = line.strip()
            if point and point[0].isdigit():
                point = point.lstrip("0123456789.)-: ")
            if point:
                key_points.append(point)
        
        return {
            "success": True,
            "key_points": key_points[:num_points],
            "count": len(key_points[:num_points])
        }
    
    async def _abstractive_summary(self, task: TaskAssignment) -> Dict[str, Any]:
        """Create an abstractive (rewritten) summary"""
        content = task.input_data.get("content", task.context)
        length = task.input_data.get("length", "medium")
        
        length_guide = {
            "short": "1-2 sentences",
            "medium": "1 paragraph (3-5 sentences)",
            "long": "2-3 paragraphs"
        }
        
        prompt = ChatPromptTemplate.from_template(
            """Write a new summary that captures the essence of the content.
Do not copy sentences directly - rephrase in your own words.
Length: {length_guide}

Content:
{content}

Summary:"""
        )
        
        chain = prompt | self.llm
        
        result = chain.invoke({
            "content": content,
            "length_guide": length_guide.get(length, "1 paragraph")
        })
        
        return {
            "success": True,
            "summary": result.content,
            "type": "abstractive",
            "length": length
        }
    
    async def _extractive_summary(self, task: TaskAssignment) -> Dict[str, Any]:
        """Create an extractive (key sentences) summary"""
        content = task.input_data.get("content", task.context)
        num_sentences = task.input_data.get("num_sentences", 3)
        
        prompt = ChatPromptTemplate.from_template(
            """Identify the {num_sentences} most important sentences from this content.
Return only the exact sentences from the original text.

Content:
{content}

Most important sentences:"""
        )
        
        chain = prompt | self.llm
        
        result = chain.invoke({
            "content": content,
            "num_sentences": num_sentences
        })
        
        # Parse sentences
        sentences = [s.strip() for s in result.content.split("\n") if s.strip()]
        
        return {
            "success": True,
            "sentences": sentences,
            "type": "extractive",
            "count": len(sentences)
        }
    
    async def _bullet_points(self, task: TaskAssignment) -> Dict[str, Any]:
        """Convert content to bullet points"""
        content = task.input_data.get("content", task.context)
        max_points = task.input_data.get("max_points", 10)
        
        prompt = ChatPromptTemplate.from_template(
            """Convert this content into clear bullet points.
Maximum {max_points} points.
Each point should be concise and actionable.

Content:
{content}

Bullet points:"""
        )
        
        chain = prompt | self.llm
        
        result = chain.invoke({
            "content": content,
            "max_points": max_points
        })
        
        # Parse bullet points
        lines = result.content.strip().split("\n")
        bullets = []
        for line in lines:
            point = line.strip().lstrip("-•* ")
            if point:
                bullets.append(point)
        
        return {
            "success": True,
            "bullet_points": bullets[:max_points],
            "count": len(bullets[:max_points])
        }
