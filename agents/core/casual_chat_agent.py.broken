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

[REFACTORED] Now uses Service Layer:
- llm_service: Unified LLM calls with token tracking
- prompt_manager: External prompt configuration
- broadcast: Unified WebSocket broadcasting
"""

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
    
    [REFACTORED] Uses Service Layer:
    - self.llm_service: Unified LLM calls (auto token tracking)
    - self.prompt_manager: Loads prompt from YAML
    - self.broadcast: Unified status broadcasting
    """
    
    def __init__(self, agent_name: str = "casual_chat_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Casual Chat",
            agent_description="Handles casual conversations, greetings, and simple chitchat"
        )
        
        # Load prompt template from YAML configuration
        # (System prompt is now externalized to config/prompts/casual_chat_agent.yaml)
        self.prompt_template = self.prompt_manager.get_prompt("casual_chat_agent")
        
        logger.info(f"CasualChatAgent initialized (temperature: {self.prompt_template.temperature})")
    
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
          Broadcast: Starting to generate response
        await self.broadcast.agent_status(
            self.agent_name,
            "generating",
            # Broadcast error
            await self.broadcast.error(
                self.agent_name,
                str(e),
                task_id,
                {"message": message[:100]}
            )
            
            task_id,
            {"message": "Generating casual response..."}
        )
        
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
            # === USE LLM SERVICE (Replaces direct LangChain call) ===
            # Build full prompt with history
            full_prompt = f"{history_context}{message}"
            
            # Call LLM Service (auto tracks tokens, uses cache)
            response = await self.llm_service.generate(
                prompt=full_prompt,
                system_message=self.prompt_template.system_prompt,
                temperature=self.prompt_template.temperature,
                max_tokens=self.prompt_template.max_tokens,
                session_id=task_id,
                use_cache=True
            )
            
            response_text = response.content
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            # Broadcast: Completed
            await self.broadcast.agent_status(
                self.agent_name,
                "completed",
                task_id,
                {
                    "response_preview": response_text[:100],
                    "tokens_used": response.usage.total_tokens,
                    "cost": response.usage.cost,
                    "cached": response.cached
                }
            )
            
            # Emit completion
            if HAS_EVENT_BUS and event_bus:
                await event_bus.emit(
                    EventType.LLM_CALL_END,
                    self.agent_name,
                    {
                        "response_length": len(response_text),
                        "duration_ms": duration_ms,
                        "tokens": response.usage.total_tokens,
                        "cached": response.cached
                    },
                    task_id=task_id
                )
                await event_bus.update_status(
                    self.agent_name,
                    AgentState.IDLE,
                    message="Ready"
                )
            
            logger.info(
                f"[CasualChat] Response generated in {duration_ms}ms "
                f"(tokens: {response.usage.total_tokens}, cached: {response.cached})"
            )
            
            return {
                "response": response_text,
                "agents_involved": [self.agent_name],
                "sources": [],
                "workflow": "casual_chat",
                "duration_ms": duration_ms,
                "usage": response.usage.model_dump(),
                "cached": response.cached
            "thanks", "thank you", "thx", "ty", "appreciated",
            # Simple questions about the bot
            "who are you", "what are you", "what's your name", "whats your name",
            "are you a bot", "are you ai", "are you human",
            "what can you do", "what do you do", "how can you help",
            "what are your capabilities", "what features", "your features",
            # Affirmations
            "ok", "okay", "got it", "understood", "sure", "yes", "no",
            "alright", "fine", "cool", "great", "nice", "awesome",
            # Pleasantries
            "how are you", "how's it going", "how do you do",
            "nice to meet you", "pleased to meet you",
            # Apologies
            "sorry", "my bad", "excuse me", "pardon",
            
            # === 中文 (Mandarin) ===
            # 問候
            "你好", "您好", "嗨", "哈囉", "哈喽", "早安", "午安", "晚安",
            "早上好", "下午好", "晚上好",
            # 告別
            "再見", "再见", "拜拜", "掰掰", "晚安", "保重",
            # 感謝
            "謝謝", "谢谢", "感謝", "感谢", "多謝", "多谢", "3q", "thx",
            # 關於 AI 的問題
            "你是誰", "你是谁", "你叫什麼", "你叫什么", "你的名字",
            "你是機器人", "你是机器人", "你是ai", "你是人工智慧", "你是人工智能",
            "你有什麼功能", "你有什么功能", "你能做什麼", "你能做什么",
            "你會什麼", "你会什么", "你可以做什麼", "你可以做什么",
            "你的功能", "有什麼功能", "有什么功能", "能做啥", "會做啥", "会做啥",
            # 確認
            "好", "好的", "了解", "知道了", "明白", "收到", "ok", "嗯",
            "是", "不是", "對", "对", "沒問題", "没问题",
            # 問候語
            "你好嗎", "你好吗", "最近怎樣", "最近怎样", "吃了嗎", "吃了吗",
            # 道歉
            "對不起", "对不起", "抱歉", "不好意思", "sorry",
            
            # === 粵語 (Cantonese) ===
            "你有咩功能", "你有乜功能", "你識咩", "你识乜", "你識做咩", "你识做乜",
            "你會咩", "你会乜", "你可以做咩", "你可以做乜", "做到咩", "做到乜",
            "有咩功能", "有乜功能", "咩功能", "乜功能",
            "你係邊個", "你系边个", "你叫咩名", "你叫乜名",
            "你係ai", "你系ai", "你係機械人", "你系机械人",
            "多謝", "唔該", "唔该", "拜拜", "早晨", "早抖",
            "點呀", "点呀", "點樣", "点样", "幾好", "几好",
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
