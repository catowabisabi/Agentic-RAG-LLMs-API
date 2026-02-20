"""
MessageManager
==============

Extracted from ChatService — manages individual message operations:
adding user/assistant messages and retrieving conversation history.
"""

import uuid
import logging
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger(__name__)


class MessageManager:
    """
    Handles per-message operations for ChatService.

    Injected with shared state so it stays stateless by itself.
    """

    def __init__(
        self,
        conversations: Dict[str, List[Dict]],
        redis_service,
        config,
        session_db,
        safe_create_task_fn: Callable,
    ):
        self.conversations = conversations
        self.redis = redis_service
        self.config = config
        self.session_db = session_db
        self._safe_create_task = safe_create_task_fn

    # ── Write ─────────────────────────────────────────────────────────────────

    def add_user_message(
        self,
        conversation_id: str,
        message: str,
        task_uid: Optional[str] = None,
    ) -> str:
        """Append a user message to the conversation and persist it."""
        from datetime import datetime

        message_id = str(uuid.uuid4())
        msg_entry = {
            "id": message_id,
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        }
        self.conversations[conversation_id].append(msg_entry)

        if self.redis.is_connected:
            self._safe_create_task(
                self.redis.append_message(conversation_id, msg_entry),
                "redis-add-user-msg",
            )

        self.session_db.add_message(
            session_id=conversation_id,
            role="user",
            content=message,
            task_uid=task_uid,
        )
        return message_id

    def add_assistant_message(
        self,
        conversation_id: str,
        message: str,
        task_uid: Optional[str] = None,
        agents_involved: Optional[List[str]] = None,
        sources: Optional[List[Dict]] = None,
    ) -> str:
        """Append an assistant message, including thinking steps, to the conversation."""
        from datetime import datetime

        message_id = str(uuid.uuid4())

        # Fetch thinking steps for this task
        thinking_steps = None
        if task_uid:
            try:
                steps = self.session_db.get_task_steps(task_uid)
                if steps:
                    thinking_steps = [
                        {
                            "step_type": s.get("step_type"),
                            "agent_name": s.get("agent_name"),
                            "content": s.get("content"),
                            "timestamp": s.get("timestamp"),
                        }
                        for s in steps
                    ]
            except Exception as e:
                logger.warning(f"Failed to get task steps: {e}")

        msg_entry = {
            "id": message_id,
            "role": "assistant",
            "content": message,
            "timestamp": datetime.now().isoformat(),
        }
        self.conversations[conversation_id].append(msg_entry)

        if self.redis.is_connected:
            self._safe_create_task(
                self.redis.append_message(conversation_id, msg_entry),
                "redis-add-assistant-msg",
            )

        self.session_db.add_message(
            session_id=conversation_id,
            role="assistant",
            content=message,
            task_uid=task_uid,
            agents_involved=agents_involved,
            sources=sources,
            thinking_steps=thinking_steps,
        )
        return message_id

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_conversation_history(
        self,
        conversation_id: str,
        limit: Optional[int] = None,
    ) -> List[Dict]:
        """
        Return conversation history as a list of {human, assistant} dicts,
        fetched from the persistent SessionDB.
        """
        if limit is None:
            limit = self.config.MEMORY_WINDOW * 2

        previous_messages = self.session_db.get_session_messages(
            conversation_id, limit=limit
        )

        chat_history: List[Dict[str, Any]] = []
        for msg in previous_messages:
            if msg.get("role") == "user":
                chat_history.append({"human": msg.get("content", "")})
            elif msg.get("role") == "assistant":
                if chat_history and "assistant" not in chat_history[-1]:
                    chat_history[-1]["assistant"] = msg.get("content", "")
        return chat_history
