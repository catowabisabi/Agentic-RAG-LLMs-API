"""
Metacognition System (Enhanced with Self-Model)
================================================

自我監控和反思系統，讓 Agent 能夠：
1. 評估自己的回答品質
2. 識別知識不足
3. 決定是否需要重試或使用不同策略
4. 從過往經驗學習
5. 自我評估能力邊界 (Self-Model)
6. 選擇最佳處理策略

參考: 
- app_docs/Agentic-Rag-Examples/09_metacognition
- app_docs/Agentic-Rag-Examples/17_reflexive_metacognitive.ipynb
- example/01/09-metacognition/README.md
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from services.llm_service import LLMService

logger = logging.getLogger(__name__)


class ConfidenceLevel(str, Enum):
    """回答信心等級"""
    HIGH = "high"           # > 0.8
    MEDIUM = "medium"       # 0.5 - 0.8
    LOW = "low"             # 0.3 - 0.5
    VERY_LOW = "very_low"   # < 0.3


class EvaluationResult(BaseModel):
    """自我評估結果"""
    score: float = Field(description="評分 0-1")
    confidence: ConfidenceLevel = Field(description="信心等級")
    reasoning: str = Field(description="評估理由")
    issues: List[str] = Field(default_factory=list, description="發現的問題")
    suggestions: List[str] = Field(default_factory=list, description="改進建議")
    should_retry: bool = Field(default=False, description="是否應該重試")
    retry_strategy: Optional[str] = Field(default=None, description="重試策略")


class ResponseQuality(BaseModel):
    """回答品質評估"""
    relevance: float = Field(description="相關性 0-1")
    completeness: float = Field(description="完整性 0-1")
    accuracy: float = Field(description="準確性 0-1")
    clarity: float = Field(description="清晰度 0-1")
    overall: float = Field(description="總體評分 0-1")


class ExperienceRecord(BaseModel):
    """經驗記錄"""
    query_pattern: str = Field(description="問題模式")
    strategy_used: str = Field(description="使用的策略")
    success: bool = Field(description="是否成功")
    quality_score: float = Field(description="品質評分")
    lessons: List[str] = Field(default_factory=list, description="學到的教訓")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class AgentCapability(BaseModel):
    """
    Agent 能力定義
    
    參考: 17_reflexive_metacognitive.ipynb 的 AgentSelfModel
    """
    domain: str = Field(description="能力領域")
    confidence_level: float = Field(default=0.7, description="在此領域的信心水平 0-1")
    requires_tool: Optional[str] = Field(default=None, description="需要的工具")
    limitations: List[str] = Field(default_factory=list, description="限制")


class MetacognitiveSelfModel(BaseModel):
    """
    Agent 自我模型 (Metacognitive Self-Model)
    
    這是 Metacognition 的核心 - Agent 對自己能力的認知
    """
    name: str = Field(default="AgenticRAG-Agent")
    role: str = Field(default="Intelligent assistant with document retrieval capabilities")
    
    # 能力清單
    capabilities: List[AgentCapability] = Field(
        default_factory=lambda: [
            AgentCapability(
                domain="general_conversation",
                confidence_level=0.9,
                requires_tool=None,
                limitations=["Cannot access real-time information"]
            ),
            AgentCapability(
                domain="document_search",
                confidence_level=0.8,
                requires_tool="rag_search",
                limitations=["Limited to uploaded documents", "May miss context"]
            ),
            AgentCapability(
                domain="calculation",
                confidence_level=0.7,
                requires_tool="calculator",
                limitations=["Complex calculations may need verification"]
            ),
            AgentCapability(
                domain="analysis",
                confidence_level=0.75,
                requires_tool="thinking_agent",
                limitations=["May require multiple iterations for complex analysis"]
            )
        ]
    )
    
    # 知識邊界
    knowledge_boundaries: List[str] = Field(
        default_factory=lambda: [
            "No access to real-time internet data",
            "Cannot provide medical/legal/financial advice",
            "Limited to uploaded document content",
            "May have training data cutoff limitations"
        ]
    )
    
    # 高風險主題 (需要特別謹慎或拒絕回答)
    high_risk_topics: List[str] = Field(
        default_factory=lambda: [
            "medical_diagnosis",
            "legal_advice", 
            "financial_investment",
            "safety_critical"
        ]
    )
    
    # 動態學習的經驗
    learned_patterns: Dict[str, str] = Field(
        default_factory=dict,
        description="從經驗中學到的模式：query_pattern -> best_strategy"
    )
    
    def get_capability_for_domain(self, domain: str) -> Optional[AgentCapability]:
        """獲取特定領域的能力"""
        for cap in self.capabilities:
            if cap.domain == domain:
                return cap
        return None
    
    def is_within_boundaries(self, topic: str) -> bool:
        """檢查主題是否在能力邊界內"""
        topic_lower = topic.lower()
        for boundary in self.knowledge_boundaries:
            if any(word in topic_lower for word in ["real-time", "live", "current price"]):
                return False
        for risk_topic in self.high_risk_topics:
            if risk_topic.replace("_", " ") in topic_lower:
                return False
        return True


class SelfEvaluator:
    """
    自我評估器
    
    評估 Agent 回答的品質，決定是否需要改進
    """
    
    def __init__(self):
        self.llm_service = LLMService()
        
        # 評估閾值
        self.retry_threshold = 0.6  # 低於此分數需要重試
        self.quality_threshold = 0.7  # 品質合格線
    
    async def evaluate_response(
        self,
        query: str,
        response: str,
        context: str = "",
        sources: List[Dict] = None
    ) -> EvaluationResult:
        """
        評估回答品質
        """
        sources = sources or []
        
        system_message = "You are a strict quality evaluator. Evaluate responses objectively."
        
        prompt = f"""Evaluate this response objectively.

Original Question: {query}

Response to Evaluate: {response[:2000]}

Available Context Used: {context[:2000] if context else "No context provided"}

Sources Referenced: {len(sources)} sources

Evaluate based on these criteria:
1. Relevance (0-1): Does the response directly address the question?
2. Completeness (0-1): Does it fully answer all parts of the question?
3. Accuracy (0-1): Is the information correct based on the context?
4. Clarity (0-1): Is the response clear and well-structured?

Consider:
- If the response says "I don't know" or "I couldn't find information", that's honest but scores lower on completeness
- If the response contradicts the context, that's a major accuracy issue
- If the response goes off-topic, that's a relevance issue

Respond in this exact JSON format:
{{
    "relevance": 0.0-1.0,
    "completeness": 0.0-1.0,
    "accuracy": 0.0-1.0,
    "clarity": 0.0-1.0,
    "issues": ["issue1", "issue2"],
    "suggestions": ["suggestion1", "suggestion2"],
    "reasoning": "Brief explanation of the evaluation"
}}
"""
        
        try:
            result = await self.llm_service.generate(
                prompt=prompt,
                system_message=system_message,
                temperature=0.1
            )
            
            response_text = result.content
            
            # 解析 JSON
            import json
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            data = json.loads(response_text.strip())
            
            # 計算總分
            scores = [
                data.get("relevance", 0.5),
                data.get("completeness", 0.5),
                data.get("accuracy", 0.5),
                data.get("clarity", 0.5)
            ]
            overall_score = sum(scores) / len(scores)
            
            # 決定信心等級
            if overall_score > 0.8:
                confidence = ConfidenceLevel.HIGH
            elif overall_score > 0.5:
                confidence = ConfidenceLevel.MEDIUM
            elif overall_score > 0.3:
                confidence = ConfidenceLevel.LOW
            else:
                confidence = ConfidenceLevel.VERY_LOW
            
            # 決定是否需要重試
            should_retry = overall_score < self.retry_threshold
            retry_strategy = None
            
            if should_retry:
                issues = data.get("issues", [])
                if "accuracy" in str(issues).lower() or data.get("accuracy", 1) < 0.5:
                    retry_strategy = "verify_with_additional_sources"
                elif "completeness" in str(issues).lower() or data.get("completeness", 1) < 0.5:
                    retry_strategy = "search_for_more_details"
                elif "relevance" in str(issues).lower() or data.get("relevance", 1) < 0.5:
                    retry_strategy = "reformulate_query"
                else:
                    retry_strategy = "general_retry"
            
            return EvaluationResult(
                score=overall_score,
                confidence=confidence,
                reasoning=data.get("reasoning", ""),
                issues=data.get("issues", []),
                suggestions=data.get("suggestions", []),
                should_retry=should_retry,
                retry_strategy=retry_strategy
            )
            
        except Exception as e:
            logger.error(f"Evaluation error: {e}")
            return EvaluationResult(
                score=0.5,
                confidence=ConfidenceLevel.MEDIUM,
                reasoning=f"Evaluation failed: {str(e)}",
                issues=["Evaluation system error"],
                suggestions=["Manual review recommended"],
                should_retry=False,
                retry_strategy=None
            )
    
    async def quick_evaluate(
        self,
        query: str,
        response: str
    ) -> Tuple[float, bool]:
        """
        快速評估（用於決定是否需要完整評估）
        
        Returns:
            (score, needs_full_evaluation)
        """
        # 簡單啟發式檢查
        response_lower = response.lower()
        
        # 明顯失敗的回答
        failure_indicators = [
            "i don't know",
            "i couldn't find",
            "no information available",
            "error occurred",
            "unable to",
            "抱歉",
            "無法找到",
            "沒有相關"
        ]
        
        for indicator in failure_indicators:
            if indicator in response_lower:
                return 0.4, True  # 需要完整評估
        
        # 回答太短
        if len(response) < 50:
            return 0.5, True
        
        # 回答太長（可能是 dump 了太多無關內容）
        if len(response) > 3000:
            return 0.6, True
        
        # 看起來還行
        return 0.75, False


class ExperienceLearner:
    """
    經驗學習器
    
    記錄和學習過往經驗，用於改進未來決策
    """
    
    def __init__(self, max_experiences: int = 100):
        self.experiences: List[ExperienceRecord] = []
        self.max_experiences = max_experiences
        self.strategy_success_rates: Dict[str, Dict] = {}
    
    def record_experience(
        self,
        query: str,
        strategy: str,
        success: bool,
        quality_score: float,
        lessons: List[str] = None
    ):
        """記錄一次經驗"""
        # 提取問題模式（簡化處理）
        query_pattern = self._extract_pattern(query)
        
        experience = ExperienceRecord(
            query_pattern=query_pattern,
            strategy_used=strategy,
            success=success,
            quality_score=quality_score,
            lessons=lessons or []
        )
        
        self.experiences.append(experience)
        
        # 保持經驗數量限制
        if len(self.experiences) > self.max_experiences:
            self.experiences = self.experiences[-self.max_experiences:]
        
        # 更新策略成功率
        self._update_strategy_stats(strategy, success, quality_score)
        
        logger.info(f"Recorded experience: {strategy} -> {'✓' if success else '✗'} ({quality_score:.2f})")
    
    def _extract_pattern(self, query: str) -> str:
        """提取問題模式"""
        query_lower = query.lower()
        
        if any(w in query_lower for w in ["what is", "什麼是", "define"]):
            return "definition"
        elif any(w in query_lower for w in ["how to", "how do", "怎麼", "如何"]):
            return "how_to"
        elif any(w in query_lower for w in ["why", "為什麼", "原因"]):
            return "explanation"
        elif any(w in query_lower for w in ["compare", "difference", "比較", "區別"]):
            return "comparison"
        elif any(w in query_lower for w in ["list", "what are", "列出", "有哪些"]):
            return "enumeration"
        else:
            return "general"
    
    def _update_strategy_stats(self, strategy: str, success: bool, score: float):
        """更新策略統計"""
        if strategy not in self.strategy_success_rates:
            self.strategy_success_rates[strategy] = {
                "total": 0,
                "successes": 0,
                "avg_score": 0.0,
                "scores": []
            }
        
        stats = self.strategy_success_rates[strategy]
        stats["total"] += 1
        if success:
            stats["successes"] += 1
        stats["scores"].append(score)
        stats["avg_score"] = sum(stats["scores"]) / len(stats["scores"])
    
    def get_best_strategy(self, query_pattern: str) -> Optional[str]:
        """根據問題模式獲取最佳策略"""
        # 找到與此模式相關的成功經驗
        relevant = [
            e for e in self.experiences
            if e.query_pattern == query_pattern and e.success
        ]
        
        if not relevant:
            return None
        
        # 統計策略成功率
        strategy_scores: Dict[str, List[float]] = {}
        for exp in relevant:
            if exp.strategy_used not in strategy_scores:
                strategy_scores[exp.strategy_used] = []
            strategy_scores[exp.strategy_used].append(exp.quality_score)
        
        # 返回平均分最高的策略
        best_strategy = max(
            strategy_scores.keys(),
            key=lambda s: sum(strategy_scores[s]) / len(strategy_scores[s])
        )
        
        return best_strategy
    
    def get_lessons_for_pattern(self, query_pattern: str) -> List[str]:
        """獲取特定模式的經驗教訓"""
        lessons = []
        for exp in self.experiences:
            if exp.query_pattern == query_pattern:
                lessons.extend(exp.lessons)
        
        # 去重
        return list(set(lessons))


class StrategyAdapter:
    """
    策略適配器
    
    根據評估結果和經驗學習調整策略
    """
    
    def __init__(self):
        self.evaluator = SelfEvaluator()
        self.learner = ExperienceLearner()
    
    async def adapt_strategy(
        self,
        current_strategy: str,
        evaluation: EvaluationResult,
        query: str
    ) -> str:
        """
        根據評估結果調整策略
        """
        # 如果評估分數足夠高，保持當前策略
        if evaluation.score >= 0.7:
            return current_strategy
        
        # 根據評估建議的重試策略
        if evaluation.retry_strategy:
            return evaluation.retry_strategy
        
        # 從經驗中學習
        query_pattern = self.learner._extract_pattern(query)
        best_strategy = self.learner.get_best_strategy(query_pattern)
        
        if best_strategy and best_strategy != current_strategy:
            return best_strategy
        
        # 默認策略輪換
        strategy_rotation = {
            "simple_rag": "react_loop",
            "react_loop": "multi_source_rag",
            "multi_source_rag": "deep_thinking",
            "deep_thinking": "simple_rag"
        }
        
        return strategy_rotation.get(current_strategy, "react_loop")
    
    def record_outcome(
        self,
        query: str,
        strategy: str,
        evaluation: EvaluationResult
    ):
        """記錄策略結果"""
        self.learner.record_experience(
            query=query,
            strategy=strategy,
            success=evaluation.score >= 0.7,
            quality_score=evaluation.score,
            lessons=evaluation.suggestions
        )


# 單例獲取
_evaluator_instance = None
_learner_instance = None
_adapter_instance = None


def get_self_evaluator() -> SelfEvaluator:
    """獲取自我評估器單例"""
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = SelfEvaluator()
    return _evaluator_instance


def get_experience_learner() -> ExperienceLearner:
    """獲取經驗學習器單例"""
    global _learner_instance
    if _learner_instance is None:
        _learner_instance = ExperienceLearner()
    return _learner_instance


def get_strategy_adapter() -> StrategyAdapter:
    """獲取策略適配器單例"""
    global _adapter_instance
    if _adapter_instance is None:
        _adapter_instance = StrategyAdapter()
    return _adapter_instance


# 自我模型單例
_self_model_instance = None


def get_metacognitive_self_model() -> MetacognitiveSelfModel:
    """獲取 Metacognitive Self Model 單例"""
    global _self_model_instance
    if _self_model_instance is None:
        _self_model_instance = MetacognitiveSelfModel()
    return _self_model_instance


def update_self_model_from_experience(
    query_pattern: str,
    strategy: str,
    success: bool
):
    """從經驗更新 Self Model"""
    model = get_metacognitive_self_model()
    if success:
        model.learned_patterns[query_pattern] = strategy
        logger.info(f"[Metacognition] Learned: {query_pattern} -> {strategy}")


class MetacognitionEngine:
    """
    Metacognition 引擎
    
    整合自我評估、經驗學習、策略適配的完整系統
    """
    
    def __init__(self):
        self.llm_service = LLMService()
        self.self_model = get_metacognitive_self_model()
        self.evaluator = get_self_evaluator()
        self.learner = get_experience_learner()
        self.adapter = get_strategy_adapter()
    
    async def assess_capability(
        self,
        query: str
    ) -> Dict[str, Any]:
        """
        評估處理此查詢的能力
        
        參考: 17_reflexive_metacognitive.ipynb 的 metacognitive_analysis_node
        """
        prompt = ChatPromptTemplate.from_template(
            """You are a metacognitive reasoning engine. Assess whether you can handle this query.

**Your Capabilities:**
{capabilities}

**Your Knowledge Boundaries:**
{boundaries}

**High-Risk Topics (require caution):**
{high_risk}

**Query:** {query}

Assess:
1. Is this query within my capabilities?
2. What domain does this query fall under?
3. Do I need any specific tools?
4. What is my confidence level for this query?
5. Are there any risks or limitations I should be aware of?

Respond in JSON:
{{
    "can_handle": true/false,
    "domain": "the domain this falls under",
    "requires_tools": ["list", "of", "tools"],
    "confidence": 0.0-1.0,
    "risks": ["any risks"],
    "recommended_strategy": "direct|rag|react|escalate",
    "reasoning": "brief explanation"
}}
"""
        )
        
        capabilities_str = "\n".join([
            f"- {cap.domain}: confidence={cap.confidence_level}, tool={cap.requires_tool}"
            for cap in self.self_model.capabilities
        ])
        
        system_message = "You are a metacognitive reasoning engine. Assess queries and provide structured analysis."
        
        prompt = f"""Assess whether you can handle this query.

**Your Capabilities:**
{capabilities_str}

**Your Knowledge Boundaries:**
{chr(10).join(self.self_model.knowledge_boundaries)}

**High-Risk Topics (require caution):**
{", ".join(self.self_model.high_risk_topics)}

**Query:** {query}

Assess:
1. Is this query within my capabilities?
2. What domain does this query fall under?
3. Do I need any specific tools?
4. What is my confidence level for this query?
5. Are there any risks or limitations I should be aware of?

Respond in JSON:
{{
    "can_handle": true/false,
    "domain": "the domain this falls under",
    "requires_tools": ["list", "of", "tools"],
    "confidence": 0.0-1.0,
    "risks": ["any risks"],
    "recommended_strategy": "direct|rag|react|escalate",
    "reasoning": "brief explanation"
}}
"""
        
        try:
            result = await self.llm_service.generate(
                prompt=prompt,
                system_message=system_message,
                temperature=0.1
            )
            
            response = result.content
            
            import json
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            data = json.loads(response.strip())
            
            logger.info(
                f"[Metacognition] Capability assessment: "
                f"can_handle={data.get('can_handle')}, "
                f"strategy={data.get('recommended_strategy')}, "
                f"confidence={data.get('confidence')}"
            )
            
            return data
            
        except Exception as e:
            logger.error(f"Capability assessment error: {e}")
            return {
                "can_handle": True,
                "domain": "unknown",
                "requires_tools": [],
                "confidence": 0.5,
                "risks": [str(e)],
                "recommended_strategy": "rag",
                "reasoning": f"Error during assessment: {e}"
            }
    
    async def reflect_on_response(
        self,
        query: str,
        response: str,
        strategy_used: str,
        context: str = ""
    ) -> Dict[str, Any]:
        """
        對回答進行反思
        
        這是完整的 Metacognition 循環：
        1. 評估回答品質
        2. 識別問題
        3. 決定是否需要改進
        4. 記錄經驗
        """
        # Step 1: 評估回答
        evaluation = await self.evaluator.evaluate_response(
            query=query,
            response=response,
            context=context
        )
        
        # Step 2: 根據評估調整策略
        adapted_strategy = await self.adapter.adapt_strategy(
            current_strategy=strategy_used,
            evaluation=evaluation,
            query=query
        )
        
        # Step 3: 記錄經驗
        self.adapter.record_outcome(
            query=query,
            strategy=strategy_used,
            evaluation=evaluation
        )
        
        # Step 4: 更新 self-model
        query_pattern = self.learner._extract_pattern(query)
        if evaluation.score >= 0.7:
            update_self_model_from_experience(
                query_pattern=query_pattern,
                strategy=strategy_used,
                success=True
            )
        
        return {
            "evaluation": evaluation.model_dump(),
            "should_retry": evaluation.should_retry,
            "adapted_strategy": adapted_strategy,
            "lessons_learned": evaluation.suggestions,
            "query_pattern": query_pattern
        }
    
    def get_recommended_strategy(self, query: str) -> Optional[str]:
        """
        根據過往經驗獲取推薦策略
        """
        query_pattern = self.learner._extract_pattern(query)
        
        # 首先檢查 self-model 的學習記錄
        if query_pattern in self.self_model.learned_patterns:
            return self.self_model.learned_patterns[query_pattern]
        
        # 然後檢查經驗學習器
        return self.learner.get_best_strategy(query_pattern)


# Metacognition Engine 單例
_engine_instance = None


def get_metacognition_engine() -> MetacognitionEngine:
    """獲取 Metacognition Engine 單例"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = MetacognitionEngine()
    return _engine_instance
