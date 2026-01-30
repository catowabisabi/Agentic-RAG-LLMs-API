# -*- coding: utf-8 -*-
"""
=============================================================================
Entry Classifier - 配置驅動的入口分類器
=============================================================================

從 config/intents.yaml 載入意圖配置，動態路由請求。
不需要改代碼就可以添加新意圖！

=============================================================================
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from pydantic import BaseModel, Field

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import TaskAssignment
from agents.shared_services.intent_router import get_intent_router, IntentMatch
from agents.shared_services.standard_response import AgentResponse, ResponseStatus

logger = logging.getLogger(__name__)


class EntryClassification(BaseModel):
    """Entry classification result"""
    is_casual: bool = Field(description="True if routes to casual_chat_agent")
    intent: str = Field(description="Identified intent name")
    route_to: str = Field(description="Target agent")
    handler: Optional[str] = Field(default=None, description="Specific handler method")
    reason: str = Field(description="Brief reason for classification")
    confidence: float = Field(default=0.9, description="Confidence 0-1")
    matched_by: str = Field(default="pattern", description="pattern | llm | default")


class EntryClassifier(BaseAgent):
    """
    配置驅動的入口分類器
    
    職責：
    - 從 config/intents.yaml 載入意圖配置
    - 使用模式匹配 + LLM 動態理解
    - 路由到適當的 Agent
    - 支持熱重載配置（不重啟服務）
    """
    
    def __init__(self, agent_name: str = "entry_classifier"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Entry Classifier",
            agent_description="Configuration-driven intent classifier and router"
        )
        
        # Use the shared intent router
        self.router = get_intent_router()
        logger.info(f"EntryClassifier initialized with {len(self.router.intents)} intents")
    
    async def classify(self, message: str, context: str = "") -> EntryClassification:
        """
        Classify a message using configuration-driven routing.
        
        Args:
            message: User's message
            context: Optional context (chat history, user info)
            
        Returns:
            EntryClassification with routing info
        """
        # Use the intent router
        match: IntentMatch = self.router.match(message, context)
        
        # Determine if it's casual
        is_casual = match.route_to == "casual_chat_agent"
        
        logger.info(f"[Entry] Intent: {match.intent} -> {match.route_to} (by {match.matched_by})")
        
        return EntryClassification(
            is_casual=is_casual,
            intent=match.intent,
            route_to=match.route_to,
            handler=match.handler,
            reason=f"Matched intent '{match.intent}' via {match.matched_by}",
            confidence=match.confidence,
            matched_by=match.matched_by
        )
    
    async def process_task(self, task: TaskAssignment) -> Dict[str, Any]:
        """Process a classification task"""
        message = task.input_data.get("message", task.description)
        context = task.input_data.get("context", "")
        
        result = await self.classify(message, context)
        
        return {
            "is_casual": result.is_casual,
            "intent": result.intent,
            "route_to": result.route_to,
            "handler": result.handler,
            "reason": result.reason,
            "confidence": result.confidence,
            "matched_by": result.matched_by
        }
    
    def reload_config(self) -> bool:
        """Reload intent configuration without restart"""
        return self.router.reload()
    
    def add_intent(self, name: str, config: Dict[str, Any]) -> bool:
        """
        Add a new intent dynamically.
        
        Example:
            classifier.add_intent("weather", {
                "description": "Weather queries",
                "route_to": "manager_agent",
                "handler": "weather_lookup",
                "patterns": ["天氣", "weather"]
            })
        """
        return self.router.add_intent(name, config)


# Singleton
_entry_classifier = None

def get_entry_classifier() -> EntryClassifier:
    global _entry_classifier
    if _entry_classifier is None:
        _entry_classifier = EntryClassifier()
    return _entry_classifier
