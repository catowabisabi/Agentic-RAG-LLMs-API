# -*- coding: utf-8 -*-
"""
=============================================================================
Self Evaluator - 自我評估器
=============================================================================

參考 Microsoft AI Agents 課程第9課 Metacognition 設計：
- 評估自己的表現
- 識別改進空間
- 提供質量保證

核心概念（來自 MSFT 第9課）：
"Metacognition empowers agents to evaluate and adapt their strategies 
and actions, leading to improved problem-solving and decision-making."

=============================================================================
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EvaluationDimension(str, Enum):
    """Dimensions of self-evaluation"""
    ACCURACY = "accuracy"           # 回答是否正確
    COMPLETENESS = "completeness"   # 回答是否完整
    RELEVANCE = "relevance"         # 回答是否相關
    CLARITY = "clarity"             # 回答是否清晰
    EFFICIENCY = "efficiency"       # 執行是否高效
    USER_ALIGNMENT = "user_alignment"  # 是否符合用戶需求


class EvaluationResult(BaseModel):
    """Result of self-evaluation"""
    overall_score: float = Field(ge=0, le=1, description="Overall score 0-1")
    dimension_scores: Dict[str, float] = Field(default_factory=dict)
    
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    improvement_suggestions: List[str] = Field(default_factory=list)
    
    # Patterns identified
    successful_patterns: List[str] = Field(default_factory=list)
    failure_patterns: List[str] = Field(default_factory=list)
    
    # Metadata
    confidence: float = Field(default=0.8, ge=0, le=1)
    evaluation_time_ms: int = 0


class SelfEvaluator:
    """
    Self-evaluation capability for AI agents.
    
    Enables agents to:
    - Assess their own performance
    - Identify patterns in success/failure
    - Suggest improvements
    
    Based on Microsoft's Metacognition design pattern.
    """
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """
        Initialize self-evaluator.
        
        Args:
            llm: LLM to use for evaluation. If None, uses default.
        """
        if llm is None:
            from config.config import Config
            config = Config()
            self.llm = ChatOpenAI(
                model=config.DEFAULT_MODEL,
                temperature=0.1,  # Low temp for consistent evaluation
                api_key=config.OPENAI_API_KEY,
                max_tokens=1000
            )
        else:
            self.llm = llm
        
        self._init_prompts()
        logger.info("SelfEvaluator initialized")
    
    def _init_prompts(self):
        """Initialize evaluation prompts"""
        self.evaluation_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a quality evaluator for AI agent responses.

Evaluate the given task execution and response on these dimensions:
1. Accuracy: Is the information correct?
2. Completeness: Does it fully address the query?
3. Relevance: Is everything relevant to the question?
4. Clarity: Is it easy to understand?
5. Efficiency: Was the approach efficient?
6. User Alignment: Does it match what the user wanted?

Score each dimension from 0.0 to 1.0.
Identify specific strengths, weaknesses, and patterns.

Respond in JSON format:
{{
    "overall_score": 0.85,
    "dimension_scores": {{
        "accuracy": 0.9,
        "completeness": 0.8,
        "relevance": 0.85,
        "clarity": 0.9,
        "efficiency": 0.8,
        "user_alignment": 0.85
    }},
    "strengths": ["Clear explanation", "Accurate data"],
    "weaknesses": ["Could be more concise"],
    "improvement_suggestions": ["Add examples next time"],
    "successful_patterns": ["Breaking down complex topics"],
    "failure_patterns": [],
    "confidence": 0.8
}}
"""),
            ("human", """Evaluate this task execution:

**Original Query:**
{query}

**Execution Plan:**
{plan}

**Agents Involved:**
{agents}

**Final Response:**
{response}

**Execution Time:** {duration_ms}ms

Provide your evaluation in JSON format.""")
        ])
        
        self.quick_eval_prompt = ChatPromptTemplate.from_messages([
            ("system", """Rate this response on a scale of 0-1 for quality.
Consider: accuracy, completeness, clarity, relevance.
Respond with just a number between 0.0 and 1.0."""),
            ("human", """Query: {query}
Response: {response}
Rating:""")
        ])
    
    async def evaluate(
        self,
        query: str,
        response: str,
        plan: Optional[str] = None,
        agents_involved: Optional[List[str]] = None,
        duration_ms: int = 0,
        user_feedback: Optional[str] = None
    ) -> EvaluationResult:
        """
        Perform full self-evaluation.
        
        Args:
            query: Original user query
            response: Final response given
            plan: Execution plan used
            agents_involved: List of agents that participated
            duration_ms: Execution time
            user_feedback: Optional user feedback
        
        Returns:
            EvaluationResult with scores and insights
        """
        import time
        import json
        
        start_time = time.time()
        
        try:
            # Build prompt
            formatted = self.evaluation_prompt.format_messages(
                query=query[:500],
                plan=plan or "No plan recorded",
                agents=", ".join(agents_involved or ["unknown"]),
                response=response[:1500],
                duration_ms=duration_ms
            )
            
            # Get evaluation
            result = await self.llm.ainvoke(formatted)
            
            # Parse JSON response
            eval_data = json.loads(result.content)
            
            eval_result = EvaluationResult(
                overall_score=eval_data.get("overall_score", 0.5),
                dimension_scores=eval_data.get("dimension_scores", {}),
                strengths=eval_data.get("strengths", []),
                weaknesses=eval_data.get("weaknesses", []),
                improvement_suggestions=eval_data.get("improvement_suggestions", []),
                successful_patterns=eval_data.get("successful_patterns", []),
                failure_patterns=eval_data.get("failure_patterns", []),
                confidence=eval_data.get("confidence", 0.8),
                evaluation_time_ms=int((time.time() - start_time) * 1000)
            )
            
            logger.info(f"Self-evaluation complete: score={eval_result.overall_score:.2f}")
            return eval_result
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse evaluation JSON: {e}")
            return self._fallback_evaluation(query, response)
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return self._fallback_evaluation(query, response)
    
    async def quick_evaluate(self, query: str, response: str) -> float:
        """
        Perform quick quality check.
        
        Returns a single score 0-1.
        """
        try:
            formatted = self.quick_eval_prompt.format_messages(
                query=query[:200],
                response=response[:500]
            )
            
            result = await self.llm.ainvoke(formatted)
            score = float(result.content.strip())
            return max(0.0, min(1.0, score))
            
        except Exception as e:
            logger.warning(f"Quick evaluation failed: {e}")
            return 0.5  # Default neutral score
    
    def _fallback_evaluation(self, query: str, response: str) -> EvaluationResult:
        """Fallback evaluation when LLM fails"""
        # Basic heuristics
        has_content = len(response) > 50
        is_relevant = any(
            word.lower() in response.lower() 
            for word in query.split()[:5] if len(word) > 3
        )
        
        score = 0.3
        if has_content:
            score += 0.2
        if is_relevant:
            score += 0.2
        
        return EvaluationResult(
            overall_score=score,
            dimension_scores={},
            weaknesses=["Evaluation incomplete due to error"],
            confidence=0.3
        )
    
    def should_retry(self, result: EvaluationResult) -> bool:
        """Determine if task should be retried based on evaluation"""
        return result.overall_score < 0.4 and result.confidence > 0.6


class AdaptiveEvaluator(SelfEvaluator):
    """
    Adaptive evaluator that learns from feedback.
    
    Tracks evaluation accuracy and adjusts criteria based on
    user feedback patterns.
    """
    
    def __init__(self, llm: Optional[ChatOpenAI] = None):
        super().__init__(llm)
        
        # Track calibration
        self.feedback_history: List[Dict[str, Any]] = []
        self.calibration_offset: float = 0.0
    
    def record_feedback(
        self,
        evaluation: EvaluationResult,
        user_rating: int,  # 1-5
        feedback_text: Optional[str] = None
    ):
        """Record user feedback to calibrate evaluations"""
        # Convert user rating to 0-1 scale
        user_score = (user_rating - 1) / 4.0
        
        # Record discrepancy
        discrepancy = user_score - evaluation.overall_score
        
        self.feedback_history.append({
            "eval_score": evaluation.overall_score,
            "user_score": user_score,
            "discrepancy": discrepancy,
            "feedback": feedback_text,
            "timestamp": datetime.now().isoformat()
        })
        
        # Update calibration (simple moving average)
        if len(self.feedback_history) > 5:
            recent = self.feedback_history[-10:]
            self.calibration_offset = sum(f["discrepancy"] for f in recent) / len(recent)
            logger.info(f"Updated calibration offset: {self.calibration_offset:.2f}")
    
    async def calibrated_evaluate(
        self,
        query: str,
        response: str,
        **kwargs
    ) -> EvaluationResult:
        """Evaluate with calibration applied"""
        result = await self.evaluate(query, response, **kwargs)
        
        # Apply calibration
        result.overall_score = max(0.0, min(1.0, 
            result.overall_score + self.calibration_offset
        ))
        
        return result
