import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import TaskAssignment
from config.config import Config

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
        
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.0,  # 使用低溫度以確保邏輯一致性
            api_key=self.config.OPENAI_API_KEY
        )
        
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
        prompt = ChatPromptTemplate.from_template(
            """You are a precise binary classifier logic unit.
Your goal is to Determine if the [Content] meets the [Criterion] based on the [Context].

[Context]
{context}

[Content]
{content}

[Criterion (Determination Goal)]
{criterion}

Instructions:
1. Analyze the Content strictly against the Criterion.
2. Return 'decision': true if the Criterion is met (Yes), false otherwise (No).
3. Provide a concise 'reason'.
"""
        )
        
        chain = prompt | self.llm.with_structured_output(ClassificationResult)
        
        try:
            result = await chain.ainvoke({
                "context": context if context else "No specific context provided.",
                "content": content,
                "criterion": criterion
            })
            
            return {
                "decision": result.decision,
                "reason": result.reason,
                "confidence": result.confidence,
                "meta": {
                    "agent": self.agent_name,
                    "criterion": criterion
                }
            }
            
        except Exception as e:
            logger.error(f"[ClassifierAgent] Error: {e}")
            return {
                "decision": False,
                "reason": f"Classification error: {str(e)}",
                "confidence": 0.0,
                "meta": {"error": True}
            }
