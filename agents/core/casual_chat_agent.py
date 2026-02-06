"""
Casual Chat Agent

Handles simple conversational queries that don't require:
- RAG retrieval
- Complex planning
- Multi-step reasoning

Examples:
- "Hello", "Hi there"
- "How are you?"
- "What's your name?"
- "Thanks!", "Goodbye"
- Simple chitchat

This agent provides fast, direct responses for casual conversations.
"""

import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime

from pydantic import BaseModel, Field

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import TaskAssignment

try:
    from services.event_bus import event_bus, EventType, AgentState
    HAS_EVENT_BUS = True
except ImportError:
    HAS_EVENT_BUS = False
    event_bus = None

logger = logging.getLogger(__name__)


class CapabilityCheck(BaseModel):
    """Result of checking if the query is within casual chat capabilities."""
    can_handle: bool = Field(description="True if this is chitchat/persona/social. False if it requires factual lookup/tools/technical reasoning.")
    reason: str = Field(description="Brief reason for the decision.")


class CasualChatAgent(BaseAgent):
    """
    Agent for handling casual/social conversations.
    
    Fast, lightweight responses without RAG or complex reasoning.
    """
    
    def __init__(self, agent_name: str = "casual_chat_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Casual Chat",
            agent_description="Handles casual conversations, greetings, and simple chitchat"
        )
        
        # System prompt for casual conversation
        self.system_prompt = """You are a friendly AI assistant having a casual conversation.

## CRITICAL LANGUAGE RULE (MUST FOLLOW):
You MUST respond in the SAME LANGUAGE as the user's message:
- Chinese (中文/廣東話) input → Chinese response
- English input → English response  
- Mixed → Use user's dominant language

Examples of language matching:
- 用戶：「你好」→ 你要用中文回答
- 用戶：「你有咩功能」→ 用中文回答功能列表
- User: "Hello" → Respond in English

## Guidelines:
- Be warm, friendly, and conversational
- Keep responses brief and natural (1-3 sentences usually)
- Don't over-explain or be overly formal
- Take into account the conversation history if provided

## Capabilities (answer in user's language):
When asked about capabilities, explain that you can:
- 回答問題和對話 / Answer questions and chat
- 搜索知識庫 / Search knowledge bases  
- 規劃和分析 / Planning and analysis
- 翻譯、總結、計算 / Translate, summarize, calculate
- 記住用戶偏好 / Remember preferences

## Examples:
User: "Hello!"
→ Hey there! How can I help you today?

User: "你好"  
→ 你好！有什麼可以幫到你？

User: "你有咩功能"
→ 我可以幫你：回答問題、搜索知識庫、規劃分析、翻譯、總結文件，同埋記住你嘅偏好。有咩需要？

User: "What can you do?"
→ I can help with many things! Answer questions, search knowledge bases, help with planning, translate, summarize, and remember your preferences.
"""
        
        logger.info("CasualChatAgent initialized")
    
    async def _check_capabilities(self, query: str) -> CapabilityCheck:
        """
        Ask the Classifier Agent if this query fits the 'Casual Agent' persona.
        
        Architecture V2 Design:
        - LLM is the primary decision maker
        - NO FALLBACK: errors propagate for testing visibility
        """
        from agents.auxiliary.classifier_agent import ClassifierAgent
        
        classifier = ClassifierAgent()
        
        # Clear criterion with explicit examples including short messages
        criterion = f"""
        Determine if this user message is 'Casual Chat'.
        
        USER MESSAGE: "{query}"
        
        Return TRUE (is casual chat) if:
        - Greetings: "Hi", "Hello!", "Hey", "你好", "早安"
        - Farewells: "Bye", "See you", "再見"
        - Thanks: "Thanks!", "Thank you", "謝謝"
        - Social: "How are you?", "What's up?", "I'm happy"
        - Identity questions: "Who are you?", "What's your name?"
        - Simple acknowledgments: "OK", "Sure", "Yes", "好"
        
        Return FALSE (NOT casual chat, needs specialist) if:
        - Technical questions: "How do I use Python?"
        - Data requests: "What data do you have?"
        - Task requests: "Search for X", "Analyze this"
        - Complex queries requiring knowledge lookup
        
        IMPORTANT: Short messages like "Hello!" or "Hi" ARE casual chat, not empty content.
        """
        
        # NOTE: No try-catch - errors MUST propagate for testing visibility
        result = await classifier.classify(
            content=query,
            criterion=criterion,
            context=f"The user sent: '{query}'. Determine if this is casual chat or needs specialist handling."
        )
        
        return CapabilityCheck(
            can_handle=result.get("decision", False),
            reason=result.get("reason", "Classifier decision")
        )

    async def process_task(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        Process a casual chat message.
        
        Args:
            task: TaskAssignment with the user's message
            
        Returns:
            Dict with response and metadata
        """
        task_id = task.task_id
        message = task.input_data.get("query", task.description)
        chat_history = task.input_data.get("chat_history", [])
        
        logger.info(f"[CasualChat] Processing: {message[:50]}... (history: {len(chat_history)} entries)")

        # --- STEP 1: Capability Check ---
        # ALL decisions are made by LLM - no heuristics or pattern matching
        # This ensures consistent, intelligent classification
        capability = await self._check_capabilities(message)
        
        if not capability.can_handle:
            logger.info(f"[CasualChat] Escalating: {capability.reason}")
            return {
                "status": "escalate",
                "reason": capability.reason,
                "original_query": message,
                "agents_involved": [self.agent_name],
                "workflow": "casual_chat_escalation"
            }
        # --------------------------------
        
        # Format chat history for context
        history_context = ""
        if chat_history:
            history_parts = []
            for exchange in chat_history[-3:]:  # Last 3 exchanges for casual chat
                if "human" in exchange:
                    history_parts.append(f"User: {exchange['human']}")
                if "assistant" in exchange:
                    history_parts.append(f"Assistant: {exchange['assistant']}")
            if history_parts:
                history_context = "[Previous conversation]\n" + "\n".join(history_parts) + "\n[Current message]\n"
        
        start_time = datetime.now()
        
        # Emit start event
        if HAS_EVENT_BUS and event_bus:
            await event_bus.update_status(
                self.agent_name,
                AgentState.CALLING_LLM,
                task_id=task_id,
                message="Generating response..."
            )
            await event_bus.emit(
                EventType.LLM_CALL_START,
                self.agent_name,
                {"message_length": len(message)},
                task_id=task_id
            )
        
        try:
            # Generate response using Service Layer
            user_message = f"{history_context}{message}"
            response = await self.llm_service.generate(
                prompt=user_message,
                system_message=self.system_prompt,
                temperature=0.7
            )
            response_text = response.content
            
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Emit completion
            if HAS_EVENT_BUS and event_bus:
                await event_bus.emit(
                    EventType.LLM_CALL_END,
                    self.agent_name,
                    {"response_length": len(response_text), "duration_ms": duration_ms},
                    task_id=task_id
                )
                await event_bus.update_status(
                    self.agent_name,
                    AgentState.IDLE,
                    message="Ready"
                )
            
            logger.info(f"[CasualChat] Response generated in {duration_ms}ms")
            
            return {
                "response": response_text,
                "agents_involved": [self.agent_name],
                "sources": [],
                "workflow": "casual_chat",
                "duration_ms": duration_ms
            }
            
        except Exception as e:
            logger.error(f"[CasualChat] Error: {e}")
            
            if HAS_EVENT_BUS and event_bus:
                await event_bus.update_status(
                    self.agent_name,
                    AgentState.ERROR,
                    task_id=task_id,
                    message=str(e)
                )
            
            return {
                "response": "I'm having trouble responding right now. Could you try again?",
                "error": str(e),
                "agents_involved": [self.agent_name],
                "sources": [],
                "workflow": "casual_chat"
            }
    
    @staticmethod
    def is_casual_message(message: str) -> bool:
        """
        [DEPRECATED] This method has been disabled to enforce LLM-only decision making.
        
        In Agentic Architecture V2, ALL classification decisions MUST be made by LLM.
        Pattern matching is removed to ensure consistent, intelligent decision making.
        
        Args:
            message: The user's message
            
        Returns:
            Always returns False to force LLM classification
        """
        # [REMOVED] All pattern matching logic
        # LLM is the ONLY decision maker in Agentic Architecture V2
        # 
        # The original patterns have been commented out for reference,
        # but they should NEVER be used for routing decisions.
        #
        # casual_patterns = [
        #     "hello", "hi", "hey", ...
        # ]
        #
        # for pattern in casual_patterns:
        #     if message_lower == pattern ...:
        #         return True
        
        return False  # Always return False to force LLM classification


# Singleton instance
_casual_chat_agent: Optional[CasualChatAgent] = None


def get_casual_chat_agent() -> CasualChatAgent:
    """Get or create the casual chat agent singleton"""
    global _casual_chat_agent
    if _casual_chat_agent is None:
        _casual_chat_agent = CasualChatAgent()
    return _casual_chat_agent
