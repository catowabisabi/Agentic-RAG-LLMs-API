# -*- coding: utf-8 -*-
"""
=============================================================================
Experience Learner - 經驗學習器
=============================================================================

參考 Microsoft AI Agents 課程設計，實現經驗學習：
- 從過去任務學習
- 識別成功模式
- 避免失敗模式
- 持續改進策略

核心概念（來自 MSFT 第9課）：
"A common pattern for self-improving agents involves introducing a 
'knowledge agent' that observes the main conversation and extracts 
valuable information to store as general knowledge."

=============================================================================
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from collections import defaultdict
import json

from pydantic import BaseModel, Field

from services.llm_service import LLMService

from agents.shared_services.memory import (
    get_episodic_store,
    get_memory_manager,
    TaskCategory,
    EpisodeOutcome,
    Episode
)

logger = logging.getLogger(__name__)


class LearnedPattern(BaseModel):
    """A pattern learned from experience"""
    pattern_type: str  # "success" or "failure"
    pattern: str
    task_category: TaskCategory
    confidence: float = Field(ge=0, le=1)
    example_count: int = 1
    first_seen: str = None
    last_seen: str = None
    
    def __post_init__(self):
        if self.first_seen is None:
            self.first_seen = datetime.now().isoformat()
        if self.last_seen is None:
            self.last_seen = self.first_seen


class StrategyRecommendation(BaseModel):
    """Recommendation for task strategy"""
    recommended_agents: List[str]
    recommended_approach: str
    patterns_to_apply: List[str]
    patterns_to_avoid: List[str]
    confidence: float = Field(ge=0, le=1)
    based_on_episodes: int


class ExperienceLearner:
    """
    Experience-based learning system for AI agents.
    
    Capabilities:
    - Extract lessons from completed tasks
    - Identify success/failure patterns
    - Recommend strategies based on past experience
    - Continuously improve through feedback
    
    Based on Microsoft's Metacognition and Memory patterns.
    """
    
    def __init__(self, llm_service: Optional[LLMService] = None):
        """Initialize experience learner"""
        self.llm_service = llm_service or LLMService()
        
        self.episodic_store = get_episodic_store()
        self.memory_manager = get_memory_manager()
        
        # Pattern cache
        self._pattern_cache: Dict[TaskCategory, Dict[str, List[str]]] = {}
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl_seconds = 300  # 5 minutes
        
        self._init_prompts()
        logger.info("ExperienceLearner initialized")
    
    def _init_prompts(self):
        """Initialize learning prompts"""
        self.lesson_extraction_system = """You are an experience analyst for an AI agent system.

Analyze the completed task and extract:
1. What went well (successful patterns)
2. What could be improved (failure patterns)
3. General lessons learned

Be specific and actionable. Focus on patterns that can be applied to future similar tasks.

Respond in JSON format:
{
    "successful_patterns": [
        "Pattern description that led to success"
    ],
    "failure_patterns": [
        "Pattern description that caused issues"
    ],
    "lessons_learned": [
        "General lesson that can be applied"
    ],
    "recommended_improvements": [
        "Specific improvement for future"
    ]
}
"""
        
        self.strategy_system = """You are a strategy advisor for an AI agent system.

Based on past experiences with similar tasks, recommend the best approach.
Consider which agents worked well, what patterns led to success, and what to avoid.

Respond in JSON format:
{
    "recommended_agents": ["agent1", "agent2"],
    "recommended_approach": "Brief description of approach",
    "patterns_to_apply": ["Pattern to use"],
    "patterns_to_avoid": ["Pattern to avoid"],
    "confidence": 0.8
}
"""
    
    async def extract_lessons(self, episode: Episode) -> Dict[str, Any]:
        """
        Extract lessons from a completed episode.
        
        Args:
            episode: Completed episode to learn from
        
        Returns:
            Dict with patterns and lessons
        """
        # Build steps summary
        steps_text = "\n".join([
            f"{s.step_number}. {s.agent_name}: {s.action} ({'✓' if s.success else '✗'}) - {s.duration_ms}ms"
            for s in episode.steps[:10]  # Limit
        ])
        
        # Feedback section
        feedback_section = ""
        if episode.user_feedback:
            feedback_section = f"**User Feedback:** {episode.user_feedback}"
        if episode.user_rating:
            feedback_section += f"\n**User Rating:** {episode.user_rating}/5"
        
        try:
            prompt = f"""Analyze this completed task:

**Task Category:** {episode.task_category.value}
**Query:** {episode.task_query[:300]}
**Plan:** {episode.plan_summary[:300]}
**Agents Used:** {", ".join(episode.agents_involved)}
**Outcome:** {episode.outcome.value}
**Duration:** {episode.total_duration_ms}ms

**Steps Executed:**
{steps_text}

**Final Response (truncated):**
{episode.final_response_summary[:500]}

{feedback_section}

Extract patterns and lessons."""

            result = await self.llm_service.generate(
                prompt=prompt,
                system_message=self.lesson_extraction_system,
                temperature=0.2
            )
            lessons = json.loads(result.content)
            
            # Update episode with extracted lessons
            episode.lessons_learned = lessons.get("lessons_learned", [])
            episode.successful_patterns = lessons.get("successful_patterns", [])
            episode.failure_patterns = lessons.get("failure_patterns", [])
            
            # Store updated episode
            self.episodic_store.store_episode(episode)
            
            # Invalidate cache
            self._cache_timestamp = None
            
            logger.info(f"Extracted lessons from episode {episode.id}")
            return lessons
            
        except Exception as e:
            logger.error(f"Failed to extract lessons: {e}")
            return {
                "successful_patterns": [],
                "failure_patterns": [],
                "lessons_learned": [],
                "recommended_improvements": []
            }
    
    async def recommend_strategy(
        self,
        task_category: TaskCategory,
        query: str,
        min_episodes: int = 1
    ) -> Optional[StrategyRecommendation]:
        """
        Recommend strategy based on past experience.
        
        Args:
            task_category: Category of the new task
            query: The query to handle
            min_episodes: Minimum past episodes required
        
        Returns:
            StrategyRecommendation or None if insufficient experience
        """
        # Get similar episodes
        episodes = self.episodic_store.find_similar_episodes(
            task_category=task_category,
            task_description=query,
            only_successful=False,
            limit=10
        )
        
        if len(episodes) < min_episodes:
            logger.debug(f"Insufficient episodes ({len(episodes)}) for strategy recommendation")
            return None
        
        # Build episodes summary
        episodes_summary = []
        for ep in episodes[:5]:
            status = "✓" if ep.outcome == EpisodeOutcome.SUCCESS else "✗"
            episodes_summary.append(
                f"- {status} {ep.task_description[:50]}... "
                f"(agents: {', '.join(ep.agents_involved[:3])}, {ep.total_duration_ms}ms)"
            )
        
        # Get patterns
        patterns = self._get_cached_patterns(task_category)
        
        try:
            prompt = f"""New task to plan:
**Category:** {task_category.value}
**Query:** {query[:300]}

**Past Similar Episodes ({len(episodes)} total):**
{chr(10).join(episodes_summary)}

**Known Success Patterns:**
{chr(10).join([f"- {p}" for p in patterns["success"][:5]]) or "None recorded"}

**Known Failure Patterns:**
{chr(10).join([f"- {p}" for p in patterns["failure"][:5]]) or "None recorded"}

Recommend strategy."""

            result = await self.llm_service.generate(
                prompt=prompt,
                system_message=self.strategy_system,
                temperature=0.2
            )
            rec_data = json.loads(result.content)
            
            recommendation = StrategyRecommendation(
                recommended_agents=rec_data.get("recommended_agents", []),
                recommended_approach=rec_data.get("recommended_approach", ""),
                patterns_to_apply=rec_data.get("patterns_to_apply", []),
                patterns_to_avoid=rec_data.get("patterns_to_avoid", []),
                confidence=rec_data.get("confidence", 0.5),
                based_on_episodes=len(episodes)
            )
            
            logger.info(f"Generated strategy recommendation with confidence {recommendation.confidence:.2f}")
            return recommendation
            
        except Exception as e:
            logger.error(f"Failed to generate strategy: {e}")
            return None
    
    def _get_cached_patterns(self, task_category: TaskCategory) -> Dict[str, List[str]]:
        """Get patterns with caching"""
        now = datetime.now()
        
        # Check cache validity
        if (self._cache_timestamp and 
            (now - self._cache_timestamp).total_seconds() < self._cache_ttl_seconds and
            task_category in self._pattern_cache):
            return self._pattern_cache[task_category]
        
        # Refresh cache
        patterns = {
            "success": self.episodic_store.get_success_patterns(task_category),
            "failure": self.episodic_store.get_failure_patterns(task_category)
        }
        
        self._pattern_cache[task_category] = patterns
        self._cache_timestamp = now
        
        return patterns
    
    def get_agent_performance(self, agent_name: str, limit: int = 50) -> Dict[str, Any]:
        """
        Get performance statistics for a specific agent.
        
        Useful for understanding which agents perform well in which contexts.
        """
        stats = self.episodic_store.get_statistics()
        
        # This is a simplified version - could be enhanced with more detailed queries
        return {
            "agent": agent_name,
            "total_tasks_in_system": stats["total_episodes"],
            "overall_success_rate": stats["success_rate"],
            "note": "Detailed per-agent stats require enhanced tracking"
        }
    
    def get_improvement_summary(self) -> Dict[str, Any]:
        """Get summary of learned improvements"""
        all_patterns = {
            "by_category": {},
            "total_episodes_learned": 0
        }
        
        for category in TaskCategory:
            patterns = self._get_cached_patterns(category)
            if patterns["success"] or patterns["failure"]:
                all_patterns["by_category"][category.value] = {
                    "success_patterns": len(patterns["success"]),
                    "failure_patterns": len(patterns["failure"]),
                    "top_success": patterns["success"][:3],
                    "top_failures": patterns["failure"][:3]
                }
        
        stats = self.episodic_store.get_statistics()
        all_patterns["total_episodes_learned"] = stats["total_episodes"]
        all_patterns["overall_success_rate"] = stats["success_rate"]
        
        return all_patterns
