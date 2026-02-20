"""
QueryClassifier
===============

Extracted from ManagerAgent — classifies user queries to determine
the appropriate workflow/agent routing.

All classification is performed via LLM; no heuristic fast-paths.
"""

import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class QueryClassification(BaseModel):
    """Classification result for a user query."""

    query_type: str = Field(
        description=(
            "One of: casual_chat, general_knowledge, knowledge_rag, "
            "calculation, translation, summarization, solidworks_api, "
            "complex_planning"
        )
    )
    reasoning: str = Field(description="Brief explanation for this classification")
    confidence: float = Field(default=0.8, description="Confidence score (0-1)")


_VALID_TYPES = [
    "casual_chat",
    "general_knowledge",
    "knowledge_rag",
    "calculation",
    "translation",
    "summarization",
    "solidworks_api",
    "complex_planning",
]


class QueryClassifier:
    """
    Classifies user queries using an LLM.

    Injected with `llm_service` and optional `debug_service`.
    """

    def __init__(self, llm_service, debug_service=None):
        self.llm_service = llm_service
        self._debug = debug_service

    async def classify(self, query: str, task_id: str) -> QueryClassification:
        """
        Classify a user query to determine the appropriate workflow.

        Returns a QueryClassification whose ``query_type`` is one of the
        VALID_TYPES above.  Raises ValueError if the LLM returns an
        unrecognised type.
        """
        # Fetch available knowledge bases to inform classification
        available_kb_names = []
        try:
            from services.vectordb_manager import vectordb_manager

            databases = vectordb_manager.list_databases()
            available_kb_names = [db.get("name", "") for db in databases if db.get("name")]
        except Exception as e:
            logger.debug(f"Could not fetch knowledge bases for classification: {e}")

        kb_list_str = ", ".join(available_kb_names) if available_kb_names else "None"

        classification_prompt = f"""You are a query router. Classify this user query into ONE category:

1. casual_chat: Greetings, small talk, thanks, farewells, questions about AI capabilities
   Examples: "Hello", "Thanks!", "What can you do?", "你有什麼功能", "Who are you?"
   
2. general_knowledge: General questions that an LLM can answer from training data AND no relevant knowledge base exists
   Examples: "What is machine learning?", "How do I write a for loop in Java?"
   NOTE: Only use this if none of the available knowledge bases are relevant to the query topic

3. knowledge_rag: Questions where we have a relevant knowledge base that can provide better/more specific answers
   NOTE: If the query topic matches ANY available knowledge base below, classify as knowledge_rag.
   Even general programming/coding questions should use knowledge_rag if a matching KB exists.

4. calculation: Math problems, data analysis, numerical computations
5. translation: Language translation requests
6. summarization: Summarize content, create summaries
7. solidworks_api: SolidWorks API, CAD, modeling, technical queries
8. complex_planning: Multi-step tasks requiring planning, comparison, or combining multiple sources

Available knowledge bases: [{kb_list_str}]

User query: "{query}"

Respond with ONLY the category name and a brief reason.
Format: category|reason"""

        result = await self.llm_service.generate(
            prompt=classification_prompt, temperature=0.1
        )
        response = result.content if hasattr(result, "content") else str(result)

        if self._debug:
            self._debug.record_llm_request(
                agent_name="manager_agent",
                task_id=task_id,
                prompt=f"[Classification] KB list: [{kb_list_str[:200]}] Query: {query[:200]}",
                session_id="",
            )
            self._debug.record_llm_response(
                agent_name="manager_agent",
                task_id=task_id,
                response=response,
                session_id="",
            )

        parts = response.strip().split("|", 1)
        query_type = parts[0].strip().lower()
        reasoning = parts[1].strip() if len(parts) > 1 else "LLM classification"

        if query_type not in _VALID_TYPES:
            raise ValueError(
                f"LLM returned invalid query type: '{query_type}'. "
                f"Valid types: {_VALID_TYPES}"
            )

        return QueryClassification(
            query_type=query_type,
            reasoning=reasoning,
            confidence=0.85,
        )
