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

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import TaskAssignment

try:
    from services.event_bus import event_bus, EventType, AgentState
    HAS_EVENT_BUS = True
except ImportError:
    HAS_EVENT_BUS = False
    event_bus = None

from config.config import Config

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
        
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.7,  # More creative for casual chat
            api_key=self.config.OPENAI_API_KEY,
            max_tokens=256  # Keep responses concise
        )
        
        # System prompt for casual conversation
        self.system_prompt = """You are a friendly AI assistant having a casual conversation.

Guidelines:
- Be warm, friendly, and conversational
- Keep responses brief and natural (1-3 sentences usually)
- Don't over-explain or be overly formal
- Match the user's energy and tone
- If asked about yourself, you're an AI assistant that helps with knowledge and tasks
- Don't redirect to other topics unless asked
- Take into account the conversation history if provided

Examples:
User: "Hello!"
Assistant: "Hey there! How can I help you today?"

User: "Thanks for your help!"
Assistant: "You're welcome! Feel free to ask if you need anything else."
"""
        
        self.chat_prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            ("human", "{history_context}{message}")
        ])
        
        logger.info("CasualChatAgent initialized")
    
    async def _check_capabilities(self, query: str) -> CapabilityCheck:
        """
        Ask the Classifier Agent if this query fits the 'Casual Agent' persona.
        """
        # Use the centralized Classifier Agent
        from agents.auxiliary.classifier_agent import ClassifierAgent
        
        classifier = ClassifierAgent()
        
        criterion = """
        Is this query purely 'Casual Chat' (chitchat, greetings, social, emotional connection)?
        
        YES criteria (Return True):
        - Greetings ("Hi", "How are you?")
        - Social interactions ("You are funny", "I'm sad")
        - Simple identity questions ("Who are you?")
        
        NO criteria (Return False - Technical/Knowledge/Task):
        - "What data do you have?"
        - "Can you analyze this?"
        - "How do I use python?"
        - "Search for X"
        - "Plan a trip"
        - Requests to perform specific tasks or look up info.
        """
        
        try:
            # Use the shared classifier
            result = await classifier.classify(
                content=query,
                criterion=criterion,
                context="User is interacting with a Casual Chat Agent. We need to decide if we should handle it or escalate to a specialist."
            )
            
            return CapabilityCheck(
                can_handle=result.get("decision", False),
                reason=result.get("reason", "Classifier decision")
            )
        except Exception as e:
            logger.error(f"Capability check with ClassifierAgent failed: {e}")
            return CapabilityCheck(can_handle=False, reason=f"Check failed: {e}")

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
        # Only check if it's not obviously trivial (heuristic fallback or override can go here)
        # For now, we trust the LLM check.
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
            # Generate response
            chain = self.chat_prompt | self.llm
            result = await chain.ainvoke({"message": message, "history_context": history_context})
            response_text = result.content if hasattr(result, 'content') else str(result)
            
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
        Quick heuristic check if a message is likely casual.
        Used for fast-path routing before LLM classification.
        
        Args:
            message: The user's message
            
        Returns:
            True if message appears to be casual chat
        """
        message_lower = message.lower().strip()
        
        # Common casual patterns
        casual_patterns = [
            # Greetings
            "hello", "hi", "hey", "hi there", "hello there", "howdy",
            "good morning", "good afternoon", "good evening", "good night",
            "what's up", "whats up", "sup", "yo",
            # Farewells
            "bye", "goodbye", "see you", "see ya", "later", "take care",
            "good bye", "farewell",
            # Thanks
            "thanks", "thank you", "thx", "ty", "appreciated",
            # Simple questions about the bot
            "who are you", "what are you", "what's your name", "whats your name",
            "are you a bot", "are you ai", "are you human",
            # Affirmations
            "ok", "okay", "got it", "understood", "sure", "yes", "no",
            "alright", "fine", "cool", "great", "nice", "awesome",
            # Pleasantries
            "how are you", "how's it going", "how do you do",
            "nice to meet you", "pleased to meet you",
            # Apologies
            "sorry", "my bad", "excuse me", "pardon",
        ]
        
        # Check if message matches or starts with casual pattern
        for pattern in casual_patterns:
            if message_lower == pattern or message_lower.startswith(pattern + " ") or message_lower.startswith(pattern + "!") or message_lower.startswith(pattern + "?") or message_lower.startswith(pattern + ",") or message_lower.startswith(pattern + "."):
                return True
        
        # NOTE: Removed length-based heuristic as it causes false positives for short queries 
        # (especially in non-English languages or specific technical terms like "rag status")
        
        return False


# Singleton instance
_casual_chat_agent: Optional[CasualChatAgent] = None


def get_casual_chat_agent() -> CasualChatAgent:
    """Get or create the casual chat agent singleton"""
    global _casual_chat_agent
    if _casual_chat_agent is None:
        _casual_chat_agent = CasualChatAgent()
    return _casual_chat_agent
