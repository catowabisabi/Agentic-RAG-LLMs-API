import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import TaskAssignment

logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)

class ClassificationResult(BaseModel):
    """Result of a binary classification."""
    decision: bool = Field(description="The binary decision result (True for Yes, False for No)")
    reason: str = Field(description="The reasoning behind the decision")
    confidence: float = Field(description="Confidence score between 0.0 and 1.0")

class ClassifierAgent(BaseAgent):
    """
    通用分類代理 (Utility Agent).
    
    Responsibilities:
    - 根據上下文 (Context)、內容 (Content) 和 目標 (Determination) 進行二元分類 (Yes/No)。
    """
    
    def __init__(self, agent_name: str = "classifier_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Binary Classifier",
            agent_description="Performs binary classification based on context and criteria"
        )
        
        # Load prompt configuration
        self.prompt_template = self.prompt_manager.get_prompt("classifier_agent")
        
        logger.info("ClassifierAgent initialized")

    async def process_task(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        Process a classification task.
        
        Input Data Keys:
        - content: The core content to analyze (e.g., user query)
        - criterion: The question to answer or condition to check (e.g., "Is this casual chat?")
        - context: (Optional) Background context
        """
        content = task.input_data.get("content", "")
        criterion = task.input_data.get("criterion", "")
        context = task.input_data.get("context", "")
        
        return await self.classify(content, criterion, context)

    async def classify(self, content: str, criterion: str, context: str = "") -> Dict[str, Any]:
        """
        執行分類邏輯
        
        Args:
            content: 要分類的內容
            criterion: 判斷標準 (Determination)
            context: 上下文
            
        Returns:
            Dict containing 'decision' (bool), 'reason' (str)
        """
        # [NO FALLBACK] Errors propagate for testing visibility
        
        # Build the prompt explicitly
        prompt = f"""You are a binary classifier. Make a YES/NO decision based on the criterion.

Context: {context if context else "No specific context provided."}

Content to analyze: "{content}"

Criterion (what to determine):
{criterion}

Based on the criterion above, determine:
- decision: true if the content matches the criterion, false otherwise
- reason: brief explanation for your decision
- confidence: your confidence level (0.0 to 1.0)

IMPORTANT: 
- "{content}" is the actual user message to analyze
- Short messages like "Hello!" or "Hi" are valid content, NOT empty
- Make decision based on the ACTUAL content provided
"""
        
        result = await self.llm_service.generate_with_structured_output(
            prompt_key="classifier_agent",
            output_schema=ClassificationResult,
            user_input=prompt,
            temperature=0.2
        )
        
        return {
            "decision": result.decision,
            "reason": result.reason,
            "confidence": result.confidence,
            "meta": {
                "agent": self.agent_name,
                "criterion": criterion
            }
        }
