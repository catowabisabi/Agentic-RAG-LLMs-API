# -*- coding: utf-8 -*-
"""
=============================================================================
Memory Capture Agent - 記憶擷取代理
=============================================================================

功能說明：
-----------
使用 LLM 智能判斷對話中哪些內容值得記住，並結構化提取記憶。

Pipeline:
-----------
1. 分析對話 → 判斷是否值得記住
2. 如果值得 → 提取結構化記憶
3. 存入 Cerebro 記憶系統

=============================================================================
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import TaskAssignment
from services.cerebro_memory import (
    get_cerebro, CerebroMemory,
    MemoryType, MemoryImportance, Observation
)

logger = logging.getLogger(__name__)


class MemoryCaptureAgent(BaseAgent):
    """
    Agent responsible for capturing and storing user memories.
    
    Analyzes conversations to identify:
    - User preferences
    - Facts about the user
    - Important decisions
    - Style preferences
    """
    
    def __init__(self, agent_name: str = "memory_capture_agent"):
        super().__init__(agent_name, agent_role="Memory Capture Specialist")
        self.cerebro: CerebroMemory = get_cerebro()
        
        # Capabilities
        self.capabilities = [
            "analyze_for_memory",
            "extract_memory",
            "store_memory",
            "get_user_context"
        ]
        
        logger.info(f"MemoryCaptureAgent initialized")
    
    async def process_task(self, task: TaskAssignment) -> Any:
        """Process memory-related tasks"""
        
        task_type = task.task_type
        
        if task_type == "analyze_for_memory":
            return await self._analyze_for_memory(task)
        elif task_type == "extract_and_store":
            return await self._extract_and_store(task)
        elif task_type == "get_user_context":
            return await self._get_user_context(task)
        elif task_type == "update_user_profile":
            return await self._update_user_profile(task)
        else:
            logger.warning(f"Unknown task type: {task_type}")
            return {"error": f"Unknown task type: {task_type}"}
    
    async def _analyze_for_memory(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        Analyze a message to determine if it contains memorable content.
        Uses LLM for intelligent analysis.
        """
        
        message = task.input_data.get("message", "")
        response = task.input_data.get("response", "")
        user_id = task.input_data.get("user_id", "default")
        
        if not message:
            return {"should_remember": False, "reason": "Empty message"}
        
        # First, quick heuristic check
        should_capture, memory_type, reason = self.cerebro.should_capture(message, response)
        
        if not should_capture:
            # Use LLM for deeper analysis
            analysis = await self._llm_analyze_memory(message, response)
            should_capture = analysis.get("should_remember", False)
            memory_type = analysis.get("memory_type")
            reason = analysis.get("reason", "LLM analysis")
        
        return {
            "should_remember": should_capture,
            "memory_type": memory_type.value if memory_type else None,
            "reason": reason,
            "message": message[:200]  # Truncate for logging
        }
    
    async def _llm_analyze_memory(
        self,
        message: str,
        response: str = None
    ) -> Dict[str, Any]:
        """Use LLM to analyze if message contains memorable content"""
        
        prompt = f"""Analyze this conversation to determine if it contains information worth remembering about the user.

User message: "{message}"
{f'Assistant response: "{response}"' if response else ''}

Look for:
1. **Preferences**: What the user likes/dislikes, preferred formats, styles
2. **Facts**: Information about the user (profession, skills, projects)
3. **Decisions**: Important choices the user made
4. **Style**: How the user prefers to communicate

Respond in JSON format:
{{
    "should_remember": true/false,
    "memory_type": "preference" | "fact" | "decision" | "style" | null,
    "title": "Short summary of what to remember",
    "facts": ["fact1", "fact2"],
    "importance": "critical" | "high" | "medium" | "low",
    "reason": "Why this is worth remembering"
}}

If nothing worth remembering, respond:
{{"should_remember": false, "reason": "explanation"}}
"""
        
        try:
            from langchain_openai import ChatOpenAI
            from config.config import Config
            config = Config()
            llm = ChatOpenAI(
                model=config.DEFAULT_MODEL,
                temperature=0.3,
                api_key=config.OPENAI_API_KEY
            )
            
            result = await llm.ainvoke(prompt)
            content = result.content if hasattr(result, 'content') else str(result)
            
            # Parse JSON from response
            import json
            import re
            
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                data = json.loads(json_match.group())
                
                # Convert memory_type string to enum
                if data.get("memory_type"):
                    type_map = {
                        "preference": MemoryType.PREFERENCE,
                        "fact": MemoryType.FACT,
                        "decision": MemoryType.DECISION,
                        "style": MemoryType.STYLE,
                        "discovery": MemoryType.DISCOVERY,
                        "context": MemoryType.CONTEXT
                    }
                    data["memory_type"] = type_map.get(data["memory_type"].lower())
                
                return data
            
            return {"should_remember": False, "reason": "Could not parse LLM response"}
            
        except Exception as e:
            logger.error(f"Error in LLM memory analysis: {e}")
            return {"should_remember": False, "reason": str(e)}
    
    async def _extract_and_store(self, task: TaskAssignment) -> Dict[str, Any]:
        """Extract memory from message and store it"""
        
        message = task.input_data.get("message", "")
        response = task.input_data.get("response", "")
        user_id = task.input_data.get("user_id", "default")
        session_id = task.input_data.get("session_id", "unknown")
        
        # Analyze what to remember
        analysis = await self._llm_analyze_memory(message, response)
        
        if not analysis.get("should_remember", False):
            return {
                "stored": False,
                "reason": analysis.get("reason", "Nothing to remember")
            }
        
        # Map importance
        importance_map = {
            "critical": MemoryImportance.CRITICAL,
            "high": MemoryImportance.HIGH,
            "medium": MemoryImportance.MEDIUM,
            "low": MemoryImportance.LOW
        }
        importance = importance_map.get(
            analysis.get("importance", "medium").lower(),
            MemoryImportance.MEDIUM
        )
        
        # Store the observation
        observation = self.cerebro.store_observation(
            user_id=user_id,
            session_id=session_id,
            memory_type=analysis.get("memory_type", MemoryType.FACT),
            title=analysis.get("title", message[:100]),
            importance=importance,
            facts=analysis.get("facts", []),
            source_message=message,
            confidence=0.8
        )
        
        logger.info(f"Stored memory: {observation.title} for user {user_id}")
        
        return {
            "stored": True,
            "observation_id": observation.id,
            "title": observation.title,
            "memory_type": observation.memory_type.value,
            "importance": observation.importance.value
        }
    
    async def _get_user_context(self, task: TaskAssignment) -> Dict[str, Any]:
        """Get user context for prompt injection"""
        
        user_id = task.input_data.get("user_id", "default")
        query = task.input_data.get("query", None)
        max_observations = task.input_data.get("max_observations", 10)
        
        # Get formatted context
        context = self.cerebro.get_context_for_prompt(
            user_id=user_id,
            query=query,
            max_observations=max_observations
        )
        
        # Also get user profile
        profile = self.cerebro.get_or_create_user(user_id)
        
        return {
            "context_text": context,
            "user_profile": profile.to_dict(),
            "has_memories": bool(context and len(context) > 20)
        }
    
    async def _update_user_profile(self, task: TaskAssignment) -> Dict[str, Any]:
        """Update user profile with new information"""
        
        user_id = task.input_data.get("user_id", "default")
        updates = task.input_data.get("updates", {})
        
        if not updates:
            return {"success": False, "error": "No updates provided"}
        
        profile = self.cerebro.update_user_profile(user_id, updates)
        
        return {
            "success": True,
            "user_id": user_id,
            "updated_fields": list(updates.keys()),
            "profile": profile.to_dict()
        }


# ============== Integration Helper ==============

async def process_message_for_memory(
    user_id: str,
    session_id: str,
    message: str,
    response: str = None
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to process a message for memory capture.
    Call this after each user message to potentially store memories.
    
    Returns: Dict with stored memory info, or None if nothing stored
    """
    
    agent = MemoryCaptureAgent()
    
    task = TaskAssignment(
        task_type="extract_and_store",
        description="Extract and store memory from message",
        input_data={
            "user_id": user_id,
            "session_id": session_id,
            "message": message,
            "response": response
        }
    )
    
    result = await agent._extract_and_store(task)
    
    if result.get("stored"):
        return result
    return None


def get_user_context_for_prompt(user_id: str, query: str = None) -> str:
    """
    Convenience function to get user context for prompt injection.
    Call this when building prompts to personalize responses.
    
    Returns: Formatted context string
    """
    
    cerebro = get_cerebro()
    return cerebro.get_context_for_prompt(user_id, query)
