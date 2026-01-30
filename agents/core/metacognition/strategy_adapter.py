# -*- coding: utf-8 -*-
"""
=============================================================================
Strategy Adapter - 策略調整器
=============================================================================

參考 Microsoft AI Agents 課程設計，實現動態策略調整：
- 根據上下文調整執行策略
- 基於經驗優化代理選擇
- 自適應任務分解

核心概念（來自 MSFT 第9課）：
"Agents can modify their strategies based on past experiences 
and changing environments."

=============================================================================
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from agents.shared_services.memory import (
    TaskCategory,
    get_memory_manager
)
from .experience_learner import ExperienceLearner, StrategyRecommendation

logger = logging.getLogger(__name__)


class ExecutionMode(str, Enum):
    """Different execution modes"""
    FAST = "fast"           # Quick response, minimal processing
    STANDARD = "standard"   # Normal processing
    THOROUGH = "thorough"   # Deep analysis, more agents
    CAUTIOUS = "cautious"   # Extra validation steps


class AdaptedStrategy(BaseModel):
    """Strategy adapted to current context"""
    execution_mode: ExecutionMode
    primary_agent: str
    supporting_agents: List[str]
    skip_agents: List[str]
    
    # Planning adjustments
    decompose_task: bool = True
    max_steps: int = 5
    require_validation: bool = True
    
    # Patterns to apply
    apply_patterns: List[str] = Field(default_factory=list)
    avoid_patterns: List[str] = Field(default_factory=list)
    
    # Reasoning
    adaptation_reason: str = ""
    confidence: float = 0.7


class StrategyAdapter:
    """
    Dynamic strategy adaptation based on context and experience.
    
    Capabilities:
    - Select execution mode based on task complexity
    - Choose optimal agents based on past performance
    - Adjust strategy in real-time
    - Apply learned patterns
    
    Based on Microsoft's Metacognition pattern.
    """
    
    # Default agent capabilities and specializations
    AGENT_CAPABILITIES = {
        "casual_chat_agent": {
            "categories": [TaskCategory.SIMPLE_CHAT],
            "strength": "fast_response",
            "complexity_limit": "low"
        },
        "rag_agent": {
            "categories": [TaskCategory.RAG_SEARCH],
            "strength": "knowledge_retrieval",
            "complexity_limit": "medium"
        },
        "thinking_agent": {
            "categories": [TaskCategory.ANALYSIS, TaskCategory.PLANNING],
            "strength": "deep_reasoning",
            "complexity_limit": "high"
        },
        "calculation_agent": {
            "categories": [TaskCategory.CALCULATION],
            "strength": "precision",
            "complexity_limit": "medium"
        },
        "translate_agent": {
            "categories": [TaskCategory.TRANSLATION],
            "strength": "language",
            "complexity_limit": "medium"
        },
        "summarize_agent": {
            "categories": [TaskCategory.SUMMARIZATION],
            "strength": "condensing",
            "complexity_limit": "medium"
        },
        "validation_agent": {
            "categories": [],
            "strength": "verification",
            "complexity_limit": "medium"
        }
    }
    
    # Complexity indicators
    COMPLEXITY_KEYWORDS = {
        "high": ["analyze", "compare", "evaluate", "plan", "design", "complex", "multiple"],
        "medium": ["explain", "describe", "calculate", "translate", "summarize"],
        "low": ["hello", "hi", "thanks", "what", "who", "when"]
    }
    
    def __init__(self):
        """Initialize strategy adapter"""
        self.experience_learner = ExperienceLearner()
        self.memory_manager = get_memory_manager()
        
        # Track runtime adjustments
        self._runtime_adjustments: List[Dict[str, Any]] = []
        
        logger.info("StrategyAdapter initialized")
    
    async def adapt_strategy(
        self,
        query: str,
        task_category: TaskCategory,
        user_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> AdaptedStrategy:
        """
        Adapt strategy based on query, category, and experience.
        
        Args:
            query: User's query
            task_category: Detected task category
            user_id: User identifier for personalization
            context: Additional context
        
        Returns:
            AdaptedStrategy with adapted parameters
        """
        # Step 1: Assess complexity
        complexity = self._assess_complexity(query, context)
        
        # Step 2: Get experience-based recommendation
        experience_rec = await self.experience_learner.recommend_strategy(
            task_category=task_category,
            query=query,
            min_episodes=2
        )
        
        # Step 3: Select execution mode
        execution_mode = self._select_execution_mode(complexity, task_category)
        
        # Step 4: Select agents
        primary_agent, supporting_agents = self._select_agents(
            task_category=task_category,
            complexity=complexity,
            experience=experience_rec
        )
        
        # Step 5: Determine skipped agents
        skip_agents = self._determine_skip_agents(execution_mode, task_category)
        
        # Step 6: Get patterns to apply/avoid
        if experience_rec:
            apply_patterns = experience_rec.patterns_to_apply
            avoid_patterns = experience_rec.patterns_to_avoid
        else:
            apply_patterns = []
            avoid_patterns = []
        
        # Step 7: Build adapted strategy
        strategy = AdaptedStrategy(
            execution_mode=execution_mode,
            primary_agent=primary_agent,
            supporting_agents=supporting_agents,
            skip_agents=skip_agents,
            decompose_task=complexity in ["high", "medium"],
            max_steps=self._get_max_steps(execution_mode, complexity),
            require_validation=complexity == "high" or execution_mode == ExecutionMode.CAUTIOUS,
            apply_patterns=apply_patterns,
            avoid_patterns=avoid_patterns,
            adaptation_reason=self._build_reason(complexity, execution_mode, experience_rec),
            confidence=experience_rec.confidence if experience_rec else 0.5
        )
        
        logger.info(f"Adapted strategy: mode={execution_mode.value}, primary={primary_agent}")
        return strategy
    
    def _assess_complexity(
        self,
        query: str,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Assess task complexity"""
        query_lower = query.lower()
        
        # Check for high complexity indicators
        for keyword in self.COMPLEXITY_KEYWORDS["high"]:
            if keyword in query_lower:
                return "high"
        
        # Check for medium complexity
        for keyword in self.COMPLEXITY_KEYWORDS["medium"]:
            if keyword in query_lower:
                return "medium"
        
        # Check for low complexity
        for keyword in self.COMPLEXITY_KEYWORDS["low"]:
            if keyword in query_lower:
                return "low"
        
        # Consider context
        if context:
            if context.get("has_documents"):
                return "medium"
            if context.get("multi_step"):
                return "high"
        
        # Default to medium
        return "medium"
    
    def _select_execution_mode(
        self,
        complexity: str,
        task_category: TaskCategory
    ) -> ExecutionMode:
        """Select appropriate execution mode"""
        if task_category == TaskCategory.SIMPLE_CHAT:
            return ExecutionMode.FAST
        
        if complexity == "high":
            return ExecutionMode.THOROUGH
        elif complexity == "low":
            return ExecutionMode.FAST
        else:
            return ExecutionMode.STANDARD
    
    def _select_agents(
        self,
        task_category: TaskCategory,
        complexity: str,
        experience: Optional[StrategyRecommendation]
    ) -> Tuple[str, List[str]]:
        """Select primary and supporting agents"""
        # Use experience if available
        if experience and experience.recommended_agents:
            primary = experience.recommended_agents[0]
            supporting = experience.recommended_agents[1:]
            return primary, supporting
        
        # Default selection based on category
        category_agents = {
            TaskCategory.SIMPLE_CHAT: ("casual_chat_agent", []),
            TaskCategory.RAG_SEARCH: ("rag_agent", ["thinking_agent"]),
            TaskCategory.CALCULATION: ("calculation_agent", ["validation_agent"]),
            TaskCategory.TRANSLATION: ("translate_agent", []),
            TaskCategory.SUMMARIZATION: ("summarize_agent", []),
            TaskCategory.ANALYSIS: ("thinking_agent", ["rag_agent"]),
            TaskCategory.PLANNING: ("planning_agent", ["thinking_agent"]),
            TaskCategory.CREATIVE: ("thinking_agent", []),
            TaskCategory.MULTI_STEP: ("planning_agent", ["thinking_agent", "rag_agent"]),
            TaskCategory.TOOL_USE: ("tool_agent", []),
        }
        
        default = ("thinking_agent", [])
        result = category_agents.get(task_category, default)
        
        # Add validation for complex tasks
        if complexity == "high" and "validation_agent" not in result[1]:
            supporting = list(result[1]) + ["validation_agent"]
            return result[0], supporting
        
        return result
    
    def _determine_skip_agents(
        self,
        execution_mode: ExecutionMode,
        task_category: TaskCategory
    ) -> List[str]:
        """Determine which agents to skip"""
        skip = []
        
        if execution_mode == ExecutionMode.FAST:
            # Skip heavy agents in fast mode
            skip.extend(["thinking_agent", "validation_agent"])
        
        # Don't use RAG for non-knowledge tasks
        if task_category in [TaskCategory.SIMPLE_CHAT, TaskCategory.CALCULATION]:
            skip.append("rag_agent")
        
        return skip
    
    def _get_max_steps(self, mode: ExecutionMode, complexity: str) -> int:
        """Get maximum steps based on mode"""
        mode_limits = {
            ExecutionMode.FAST: 2,
            ExecutionMode.STANDARD: 5,
            ExecutionMode.THOROUGH: 10,
            ExecutionMode.CAUTIOUS: 8
        }
        
        base = mode_limits.get(mode, 5)
        
        # Adjust for complexity
        if complexity == "high":
            return base + 2
        elif complexity == "low":
            return max(1, base - 2)
        
        return base
    
    def _build_reason(
        self,
        complexity: str,
        mode: ExecutionMode,
        experience: Optional[StrategyRecommendation]
    ) -> str:
        """Build explanation for the adaptation"""
        parts = [f"Complexity: {complexity}", f"Mode: {mode.value}"]
        
        if experience:
            parts.append(f"Based on {experience.based_on_episodes} similar past tasks")
            if experience.confidence > 0.7:
                parts.append("High confidence from experience")
        else:
            parts.append("No prior experience available")
        
        return "; ".join(parts)
    
    def record_runtime_adjustment(
        self,
        task_id: str,
        adjustment: str,
        reason: str
    ):
        """Record a runtime strategy adjustment"""
        self._runtime_adjustments.append({
            "task_id": task_id,
            "adjustment": adjustment,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only recent adjustments
        if len(self._runtime_adjustments) > 100:
            self._runtime_adjustments = self._runtime_adjustments[-50:]
        
        logger.debug(f"Recorded runtime adjustment: {adjustment}")
    
    def get_runtime_adjustments(self, task_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recorded runtime adjustments"""
        if task_id:
            return [a for a in self._runtime_adjustments if a["task_id"] == task_id]
        return self._runtime_adjustments[-20:]
