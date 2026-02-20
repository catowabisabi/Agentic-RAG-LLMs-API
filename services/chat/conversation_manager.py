"""
ConversationManager
===================

Extracted from ChatService — manages conversation lifecycle:
creation, retrieval, deletion, and clearing.

All state lives in the parent ChatService; sub-manager receives
references to shared objects via constructor injection.
"""

import asyncio
import uuid
import logging
from typing import Dict, List, Optional, Any, Callable

logger = logging.getLogger(__name__)


class ConversationManager:
    """
    Handles conversation-level operations for ChatService.

    Dependencies are injected so this class stays stateless
    relative to the shared conversation store.
    """

    def __init__(
        self,
        conversations: Dict[str, List[Dict]],
        conversation_lock: asyncio.Lock,
        redis_service,
        ws_manager,
        config,
        session_db,
        safe_create_task_fn: Callable,
    ):
        self.conversations = conversations
        self._conversation_lock = conversation_lock
        self.redis = redis_service
        self.ws_manager = ws_manager
        self.config = config
        self.session_db = session_db
        self._safe_create_task = safe_create_task_fn

    # ── Atomic conversation creation ─────────────────────────────────────────

    async def get_or_create_async(
        self,
        conversation_id: Optional[str] = None,
        timeout: float = 180.0,
    ) -> str:
        """
        Atomic conversation creation protected by asyncio.Lock.

        Raises TimeoutError (and broadcasts a UI event) if the lock is
        held for longer than *timeout* seconds.
        """
        try:
            async with asyncio.timeout(timeout):
                async with self._conversation_lock:
                    return self._create_internal(conversation_id)
        except TimeoutError:
            try:
                await self.ws_manager.broadcast({
                    "type": "conversation_timeout",
                    "code": "CONVERSATION_QUEUE_TIMEOUT",
                    "level": "warning",
                    "message": "Conversation creation queue exceeded 3 minutes. Continue or reset?",
                    "timeout_seconds": timeout,
                })
            except Exception:
                pass
            raise TimeoutError(
                f"Conversation creation timed out after {timeout}s. "
                "The server is under heavy load."
            )

    def get_or_create(self, conversation_id: Optional[str] = None) -> str:
        """Sync version — for backward compatibility."""
        return self._create_internal(conversation_id)

    def _create_internal(self, conversation_id: Optional[str] = None) -> str:
        """Create the conversation record (must be called under lock or sync context)."""
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())

        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []

        self.session_db.get_or_create_session(conversation_id, "Chat Session")

        if self.redis.is_connected:
            self._safe_create_task(
                self.redis.set_conversation(conversation_id, []),
                "redis-set-conversation",
            )

        return conversation_id

    # ── Read operations ───────────────────────────────────────────────────────

    def list_conversations(self) -> List[Dict[str, Any]]:
        """List all in-memory conversations with basic metadata."""
        return [
            {
                "conversation_id": conv_id,
                "message_count": len(messages),
                "last_message": messages[-1] if messages else None,
            }
            for conv_id, messages in self.conversations.items()
        ]

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Return conversation detail, or None if not found."""
        if conversation_id not in self.conversations:
            return None
        return {
            "conversation_id": conversation_id,
            "messages": self.conversations[conversation_id],
        }

    # ── Mutation operations ───────────────────────────────────────────────────

    def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation from memory and Redis."""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            if self.redis.is_connected:
                self._safe_create_task(
                    self.redis.delete_conversation(conversation_id),
                    "redis-delete-conversation",
                )
            return True
        return False

    def clear_conversation(self, conversation_id: str) -> bool:
        """Clear all messages from a conversation (keep the conversation ID)."""
        if conversation_id in self.conversations:
            self.conversations[conversation_id] = []
            if self.redis.is_connected:
                self._safe_create_task(
                    self.redis.set_conversation(conversation_id, []),
                    "redis-clear-conversation",
                )
            return True
        return False
