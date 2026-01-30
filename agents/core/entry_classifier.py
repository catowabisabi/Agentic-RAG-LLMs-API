# -*- coding: utf-8 -*-
"""
=============================================================================
Entry Classifier - 入口分類器
=============================================================================

這是系統的第一層分類器，只做一個決定：
- Casual Chat → 直接發送給 Casual Chat Agent
- Other → 發送給 Manager Agent 進行進一步規劃

=============================================================================
"""

import logging
from typing import Dict, Any, Tuple
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import TaskAssignment
from config.config import Config

logger = logging.getLogger(__name__)


class EntryClassification(BaseModel):
    """Entry classification result"""
    is_casual: bool = Field(description="True if this is casual chat, False if needs manager")
    reason: str = Field(description="Brief reason for classification")
    confidence: float = Field(default=0.9, description="Confidence 0-1")


class EntryClassifier(BaseAgent):
    """
    入口分類器 - 系統的第一道門
    
    職責：
    - 快速判斷用戶消息是否為閒聊
    - 如果是閒聊 → Casual Chat Agent
    - 如果不是 → Manager Agent (進行規劃和分派)
    """
    
    def __init__(self, agent_name: str = "entry_classifier"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Entry Classifier",
            agent_description="First-line classifier to route casual vs task queries"
        )
        
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.0,
            api_key=self.config.OPENAI_API_KEY,
            max_tokens=100
        )
        
        # Casual patterns for fast-path (heuristic)
        self.casual_patterns = self._load_casual_patterns()
        
        logger.info("EntryClassifier initialized")
    
    def _load_casual_patterns(self) -> set:
        """Load casual chat patterns for fast-path matching"""
        patterns = {
            # === English ===
            "hello", "hi", "hey", "hi there", "hello there", "howdy",
            "good morning", "good afternoon", "good evening", "good night",
            "what's up", "whats up", "sup", "yo",
            "bye", "goodbye", "see you", "see ya", "later", "take care",
            "thanks", "thank you", "thx", "ty", "appreciated",
            "who are you", "what are you", "what's your name",
            "what can you do", "what do you do", "how can you help",
            "ok", "okay", "got it", "understood", "sure", "yes", "no",
            "how are you", "how's it going", "nice to meet you",
            "sorry", "my bad", "excuse me",
            
            # === 中文 (Mandarin) ===
            "你好", "您好", "嗨", "哈囉", "早安", "午安", "晚安",
            "再見", "再见", "拜拜", "保重",
            "謝謝", "谢谢", "感謝", "多謝",
            "你是誰", "你是谁", "你叫什麼", "你的名字",
            "你有什麼功能", "你有什么功能", "你能做什麼", "你能做什么",
            "你會什麼", "你会什么", "你可以做什麼",
            "好", "好的", "了解", "知道了", "明白", "收到",
            "你好嗎", "你好吗", "最近怎樣",
            
            # === 粵語 (Cantonese) ===
            "你有咩功能", "你識咩", "你識做咩", "你會咩",
            "你係邊個", "你叫咩名",
            "多謝", "唔該", "拜拜", "早晨",
            "點呀", "點樣", "幾好",
        }
        return patterns
    
    def _quick_check_casual(self, message: str) -> bool:
        """Fast heuristic check for casual messages"""
        msg_lower = message.lower().strip()
        
        # Direct pattern match
        if msg_lower in self.casual_patterns:
            return True
        
        # Prefix match
        for pattern in self.casual_patterns:
            if msg_lower.startswith(pattern + " ") or \
               msg_lower.startswith(pattern + "!") or \
               msg_lower.startswith(pattern + "?") or \
               msg_lower.startswith(pattern + ","):
                return True
        
        return False
    
    async def classify(self, message: str, context: str = "") -> EntryClassification:
        """
        Classify a message as casual or task-oriented.
        
        Args:
            message: User's message
            context: Optional context (chat history, user info)
            
        Returns:
            EntryClassification with is_casual flag
        """
        # Fast path: heuristic check
        if self._quick_check_casual(message):
            return EntryClassification(
                is_casual=True,
                reason="Matches casual conversation pattern",
                confidence=0.95
            )
        
        # LLM classification for ambiguous cases
        prompt = ChatPromptTemplate.from_template(
            """Classify this message as either CASUAL or TASK:

CASUAL (return true):
- Greetings, farewells, thanks
- Questions about the AI itself ("what can you do", "who are you")
- Simple chitchat, emotional expressions
- Short confirmations or responses

TASK (return false):
- Questions requiring knowledge lookup
- Requests to perform actions (calculate, translate, search, analyze)
- Complex multi-step requests
- Technical or domain-specific questions

Message: "{message}"
{context_section}

Is this CASUAL chat? (true/false)"""
        )
        
        context_section = f"\nContext: {context}" if context else ""
        
        try:
            chain = prompt | self.llm.with_structured_output(EntryClassification)
            result = await chain.ainvoke({
                "message": message,
                "context_section": context_section
            })
            return result
        except Exception as e:
            logger.warning(f"Classification failed: {e}, defaulting to task")
            return EntryClassification(
                is_casual=False,
                reason=f"Classification error: {e}",
                confidence=0.5
            )
    
    async def process_task(self, task: TaskAssignment) -> Dict[str, Any]:
        """Process a classification task"""
        message = task.input_data.get("message", task.description)
        context = task.input_data.get("context", "")
        
        result = await self.classify(message, context)
        
        return {
            "is_casual": result.is_casual,
            "reason": result.reason,
            "confidence": result.confidence,
            "route_to": "casual_chat_agent" if result.is_casual else "manager_agent"
        }


# Singleton
_entry_classifier = None

def get_entry_classifier() -> EntryClassifier:
    global _entry_classifier
    if _entry_classifier is None:
        _entry_classifier = EntryClassifier()
    return _entry_classifier
