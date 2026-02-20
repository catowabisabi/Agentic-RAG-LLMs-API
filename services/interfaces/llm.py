"""
ILLMService — Language-Model Service Interface
===============================================

Any object that implements these methods satisfies ILLMService.
Because this is a ``typing.Protocol``, no inheritance is required.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, Union, runtime_checkable


@runtime_checkable
class ILLMService(Protocol):
    """
    Structural interface for the unified LLM service.

    Concrete implementations: ``services.llm_service.LLMService``
    Test doubles: any object that implements the same method signatures.
    """

    async def generate(
        self,
        prompt: Union[str, List[Dict[str, str]]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        system_message: Optional[str] = None,
        session_id: str = "default",
        use_cache: bool = True,
    ) -> Any:
        """
        Generate a complete LLM response.

        Returns an object with at minimum a ``.content: str`` attribute
        (``LLMResponse`` in the concrete implementation).
        """
        ...

    async def astream(
        self,
        prompt: Union[str, List[Dict[str, str]]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        system_message: Optional[str] = None,
        session_id: str = "default",
    ) -> AsyncIterator[str]:
        """Stream response tokens one-by-one."""
        ...

    def get_usage_stats(self) -> Dict[str, Any]:
        """Return current token-usage and cost statistics."""
        ...

    def clear_cache(self) -> None:
        """Invalidate the response cache."""
        ...
