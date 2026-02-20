"""
QualityController
=================

Extracted from ManagerAgent — LLM-based response quality validation
and retry-with-feedback logic.

The controller acts as the final quality gate before a response
is returned to the user.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class QualityController:
    """
    Validates agent responses and retries with targeted feedback when needed.

    Injected with ``llm_service``, an optional ``debug_service``, and a
    ``broadcast_thinking_fn`` coroutine so it can emit thinking events
    without depending on the full ManagerAgent.
    """

    def __init__(
        self,
        llm_service,
        debug_service=None,
        broadcast_thinking_fn: Optional[Callable] = None,
    ):
        self.llm_service = llm_service
        self._debug = debug_service
        self._broadcast_thinking = broadcast_thinking_fn or self._noop_broadcast

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    async def _noop_broadcast(*args, **kwargs):
        """No-op broadcast when no ws_manager is available."""

    # ── Public API ────────────────────────────────────────────────────────────

    async def validate_response(
        self,
        query: str,
        response_text: str,
        sources: Optional[List] = None,
        workflow: str = "unknown",
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        LLM-based quality validation.

        Returns a dict with:
            passed, quality_score, issues, suggestions,
            reasoning, should_retry, retry_hint
        """
        try:
            await self._broadcast_thinking(
                session_id,
                {"status": "Manager double-checking response quality...", "workflow": workflow},
                task_id,
            )

            validation_prompt = f"""You are a strict quality control manager. Evaluate whether this response is ready to send to the user.

User Question: {query}

Agent Response:
{response_text[:3000]}

Sources Available: {len(sources) if sources else 0}
Workflow: {workflow}

Evaluate these aspects (score 0-1 each):
1. RELEVANCE: Does the response actually address what the user asked?
2. COMPLETENESS: Is it sufficiently detailed? (not too vague or empty)
3. ACCURACY_SIGNALS: Does it avoid contradictions, hedging, or hallucination signals?
4. LANGUAGE_MATCH: Does it respond in the same language the user asked in?
5. HARMFUL_CONTENT: Is it free from any inappropriate/harmful content?

Score STRICTLY. Common failure modes:
- Response says "I don't know" when sources were available → low relevance
- Response repeats the question without answering → low completeness
- Response is in English when user asked in Chinese (or vice versa) → low language match
- Response contains "error" or system messages → fail

Respond in JSON only:
{{
    "relevance": 0.0-1.0,
    "completeness": 0.0-1.0,
    "accuracy_signals": 0.0-1.0,
    "language_match": 0.0-1.0,
    "harmful_content_free": 0.0-1.0,
    "overall": 0.0-1.0,
    "passed": true/false,
    "issues": ["issue1", ...],
    "suggestions": ["how to fix1", ...],
    "reasoning": "brief explanation",
    "retry_hint": "specific instruction for retry if failed, null if passed"
}}"""

            result = await self.llm_service.generate(
                prompt=validation_prompt,
                system_message="You are a quality control evaluator. Return JSON only.",
                temperature=0.1,
            )

            import json as json_mod

            response = result.content.strip()
            if response.startswith("```"):
                response = response.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            data = json_mod.loads(response)
            overall = data.get("overall", 0.5)
            passed = data.get("passed", overall >= 0.6)

            logger.info(
                f"[Manager QC] {workflow} validation: score={overall:.2f}, passed={passed}"
            )

            if self._debug:
                self._debug.record_agent_output(
                    agent_name="manager_validation",
                    task_id=task_id or "",
                    output_data={
                        "score": overall,
                        "passed": passed,
                        "issues": data.get("issues", []),
                        "workflow": workflow,
                    },
                    session_id=session_id or "",
                )

            return {
                "passed": passed,
                "quality_score": overall,
                "issues": data.get("issues", []),
                "suggestions": data.get("suggestions", []),
                "reasoning": data.get("reasoning", ""),
                "should_retry": not passed and overall < 0.6,
                "retry_hint": data.get("retry_hint"),
            }

        except Exception as e:
            logger.warning(f"[Manager QC] Validation failed: {e}, allowing response through")
            return {
                "passed": True,
                "quality_score": 0.7,
                "issues": [f"Validation error: {str(e)}"],
                "suggestions": [],
                "reasoning": "Validation system error — defaulting to pass",
                "should_retry": False,
                "retry_hint": None,
            }

    async def retry_with_feedback(
        self,
        query: str,
        original_response: str,
        validation_result: Dict[str, Any],
        context: str = "",
        sources: Optional[List] = None,
        session_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """
        Re-generate a response using LLM + validation feedback.

        Does NOT re-run the full pipeline — uses targeted prompting to
        fix the specific issues identified by ``validate_response``.
        """
        try:
            issues = validation_result.get("issues", [])
            retry_hint = validation_result.get("retry_hint", "")
            suggestions = validation_result.get("suggestions", [])

            await self._broadcast_thinking(
                session_id,
                {
                    "status": f"Manager retrying: fixing {len(issues)} issues...",
                    "issues": issues[:3],
                },
                task_id,
            )

            logger.info(f"[Manager Retry] Issues: {issues}, Hint: {retry_hint}")

            # Build source context string
            source_context = ""
            if sources:
                source_parts = []
                for i, s in enumerate(sources[:5]):
                    content = s.get("content", s.get("snippet", ""))
                    title = s.get("title", f"Source {i+1}")
                    if content:
                        source_parts.append(f"[{title}]: {content[:500]}")
                if source_parts:
                    source_context = "\n\nAvailable Sources:\n" + "\n".join(source_parts)

            retry_prompt = f"""The previous response to this question was rejected by quality control.

Question: {query}

Previous Response (REJECTED):
{original_response[:2000]}

Quality Control Feedback:
- Issues Found: {', '.join(issues) if issues else 'None specified'}
- Specific Fix Needed: {retry_hint or 'General improvement needed'}
- Suggestions: {', '.join(suggestions) if suggestions else 'None'}

{source_context}

{context[:2000] if context else ""}

Please provide an IMPROVED response that:
1. Directly addresses the user's question
2. Fixes ALL the issues identified above
3. Matches the language of the user's question
4. Is clear, complete, and accurate
5. References source material when available

Improved Response:"""

            result = await self.llm_service.generate(
                prompt=retry_prompt,
                system_message=(
                    "You are a helpful assistant. Provide an improved, high-quality "
                    "response that fixes all identified issues."
                ),
                temperature=0.3,
            )

            improved = result.content if hasattr(result, "content") else str(result)
            logger.info(f"[Manager Retry] Improved response: {len(improved)} chars")
            return improved

        except Exception as e:
            logger.warning(f"[Manager Retry] Failed: {e}, returning original")
            return original_response
