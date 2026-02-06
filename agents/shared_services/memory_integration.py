"""
Memory Integration Module
==========================

整合記憶系統到對話流程，提供：
1. 對話歷史記憶
2. 實體記憶（用戶提到的人、地點、概念）
3. 情節記憶（成功/失敗的經驗）
4. 工作記憶（當前對話上下文）

用於提升對話的個人化和連貫性
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """記憶類型"""
    EPISODIC = "episodic"      # 情節記憶（對話經歷）
    SEMANTIC = "semantic"      # 語義記憶（知識）
    PROCEDURAL = "procedural"  # 程序記憶（如何做某事）
    WORKING = "working"        # 工作記憶（當前上下文）


class TaskCategory(str, Enum):
    """任務類別"""
    RAG_SEARCH = "rag_search"
    CALCULATION = "calculation"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    GENERAL_CHAT = "general_chat"
    COMPLEX_REASONING = "complex_reasoning"


class EpisodeOutcome(str, Enum):
    """情節結果"""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"


class MemoryEntry(BaseModel):
    """記憶條目"""
    id: str
    type: MemoryType
    content: str
    context: Dict[str, Any] = Field(default_factory=dict)
    importance: float = Field(default=0.5, description="重要性 0-1")
    access_count: int = Field(default=0)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_accessed: str = Field(default_factory=lambda: datetime.now().isoformat())
    expires_at: Optional[str] = None
    tags: List[str] = Field(default_factory=list)


class Episode(BaseModel):
    """對話情節"""
    session_id: str
    user_id: str
    query: str
    response: str
    task_category: TaskCategory
    outcome: EpisodeOutcome
    quality_score: float
    agents_involved: List[str]
    sources_used: List[str]
    duration_ms: int
    lessons: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class EntityMention(BaseModel):
    """實體提及"""
    entity_type: str  # person, place, concept, product, etc.
    entity_name: str
    context: str
    first_mentioned: str
    mention_count: int = 1
    attributes: Dict[str, Any] = Field(default_factory=dict)


class ConversationContext(BaseModel):
    """對話上下文（工作記憶）"""
    session_id: str
    user_id: str
    current_topic: Optional[str] = None
    recent_queries: List[str] = Field(default_factory=list)
    recent_responses: List[str] = Field(default_factory=list)
    mentioned_entities: List[EntityMention] = Field(default_factory=list)
    user_preferences: Dict[str, Any] = Field(default_factory=dict)
    task_history: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class MemoryManager:
    """
    記憶管理器
    
    管理所有類型的記憶，提供存儲和檢索功能
    """
    
    def __init__(self, max_episodic: int = 500, max_working: int = 20):
        # 情節記憶存儲（長期）
        self.episodes: Dict[str, List[Episode]] = {}  # user_id -> episodes
        self.max_episodic = max_episodic
        
        # 工作記憶存儲（短期）
        self.working_memory: Dict[str, ConversationContext] = {}  # session_id -> context
        self.max_working = max_working
        
        # 實體記憶
        self.entity_memory: Dict[str, List[EntityMention]] = {}  # user_id -> entities
        
        # 用戶偏好
        self.user_preferences: Dict[str, Dict[str, Any]] = {}
        
        logger.info("MemoryManager initialized")
    
    # ============== 工作記憶（當前對話） ==============
    
    def get_or_create_context(
        self,
        session_id: str,
        user_id: str = "default"
    ) -> ConversationContext:
        """獲取或創建對話上下文"""
        if session_id not in self.working_memory:
            self.working_memory[session_id] = ConversationContext(
                session_id=session_id,
                user_id=user_id
            )
        return self.working_memory[session_id]
    
    def update_context(
        self,
        session_id: str,
        query: str = None,
        response: str = None,
        topic: str = None,
        entities: List[EntityMention] = None
    ):
        """更新對話上下文"""
        if session_id not in self.working_memory:
            return
        
        ctx = self.working_memory[session_id]
        
        if query:
            ctx.recent_queries.append(query)
            # 保持最近 N 條
            ctx.recent_queries = ctx.recent_queries[-self.max_working:]
        
        if response:
            ctx.recent_responses.append(response)
            ctx.recent_responses = ctx.recent_responses[-self.max_working:]
        
        if topic:
            ctx.current_topic = topic
        
        if entities:
            # 合併實體
            for new_entity in entities:
                existing = next(
                    (e for e in ctx.mentioned_entities 
                     if e.entity_name.lower() == new_entity.entity_name.lower()),
                    None
                )
                if existing:
                    existing.mention_count += 1
                else:
                    ctx.mentioned_entities.append(new_entity)
        
        ctx.updated_at = datetime.now().isoformat()
    
    def get_recent_context(self, session_id: str, n_turns: int = 5) -> str:
        """獲取最近的對話上下文（用於 prompt）"""
        if session_id not in self.working_memory:
            return ""
        
        ctx = self.working_memory[session_id]
        
        parts = []
        
        # 構建對話歷史
        queries = ctx.recent_queries[-n_turns:]
        responses = ctx.recent_responses[-n_turns:]
        
        for i, (q, r) in enumerate(zip(queries, responses)):
            parts.append(f"User: {q}")
            parts.append(f"Assistant: {r[:200]}...")
        
        # 添加提及的實體
        if ctx.mentioned_entities:
            entity_str = ", ".join([e.entity_name for e in ctx.mentioned_entities[-5:]])
            parts.append(f"\nRecently mentioned: {entity_str}")
        
        return "\n".join(parts)
    
    def clear_session(self, session_id: str):
        """清除會話記憶"""
        if session_id in self.working_memory:
            del self.working_memory[session_id]
    
    # ============== 情節記憶（經驗） ==============
    
    def store_episode(
        self,
        session_id: str,
        user_id: str,
        query: str,
        response: str,
        task_category: TaskCategory,
        outcome: EpisodeOutcome,
        quality_score: float,
        agents_involved: List[str] = None,
        sources_used: List[str] = None,
        duration_ms: int = 0,
        lessons: List[str] = None
    ):
        """存儲一個對話情節"""
        episode = Episode(
            session_id=session_id,
            user_id=user_id,
            query=query,
            response=response[:1000],  # 限制長度
            task_category=task_category,
            outcome=outcome,
            quality_score=quality_score,
            agents_involved=agents_involved or [],
            sources_used=sources_used or [],
            duration_ms=duration_ms,
            lessons=lessons or []
        )
        
        if user_id not in self.episodes:
            self.episodes[user_id] = []
        
        self.episodes[user_id].append(episode)
        
        # 保持數量限制
        if len(self.episodes[user_id]) > self.max_episodic:
            # 移除最舊的，但保留高質量的
            sorted_episodes = sorted(
                self.episodes[user_id],
                key=lambda e: (e.quality_score, e.created_at),
                reverse=True
            )
            self.episodes[user_id] = sorted_episodes[:self.max_episodic]
        
        logger.info(f"Stored episode for user {user_id}: {outcome.value} ({quality_score:.2f})")
    
    def recall_similar_episodes(
        self,
        user_id: str,
        query: str,
        task_category: TaskCategory = None,
        n_episodes: int = 5
    ) -> List[Episode]:
        """回憶類似的情節"""
        if user_id not in self.episodes:
            return []
        
        episodes = self.episodes[user_id]
        
        # 過濾任務類別
        if task_category:
            episodes = [e for e in episodes if e.task_category == task_category]
        
        # 簡單的關鍵詞匹配（可以改用向量相似度）
        query_words = set(query.lower().split())
        
        def similarity(episode: Episode) -> float:
            ep_words = set(episode.query.lower().split())
            if not ep_words:
                return 0
            return len(query_words & ep_words) / len(query_words | ep_words)
        
        # 按相似度和質量排序
        scored = [
            (e, similarity(e) * 0.5 + e.quality_score * 0.5)
            for e in episodes
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        
        return [e for e, _ in scored[:n_episodes]]
    
    def get_success_patterns(
        self,
        user_id: str,
        task_category: TaskCategory
    ) -> Dict[str, Any]:
        """獲取成功模式統計"""
        if user_id not in self.episodes:
            return {}
        
        category_episodes = [
            e for e in self.episodes[user_id]
            if e.task_category == task_category
        ]
        
        if not category_episodes:
            return {}
        
        successes = [e for e in category_episodes if e.outcome == EpisodeOutcome.SUCCESS]
        failures = [e for e in category_episodes if e.outcome == EpisodeOutcome.FAILURE]
        
        # 統計成功時常用的 agents
        agent_success_count: Dict[str, int] = {}
        for ep in successes:
            for agent in ep.agents_involved:
                agent_success_count[agent] = agent_success_count.get(agent, 0) + 1
        
        return {
            "total": len(category_episodes),
            "success_rate": len(successes) / len(category_episodes) if category_episodes else 0,
            "avg_quality": sum(e.quality_score for e in category_episodes) / len(category_episodes),
            "best_agents": sorted(agent_success_count.items(), key=lambda x: x[1], reverse=True)[:3],
            "common_lessons": self._extract_common_lessons(category_episodes)
        }
    
    def _extract_common_lessons(self, episodes: List[Episode]) -> List[str]:
        """提取常見教訓"""
        lesson_count: Dict[str, int] = {}
        for ep in episodes:
            for lesson in ep.lessons:
                lesson_count[lesson] = lesson_count.get(lesson, 0) + 1
        
        # 返回最常見的
        sorted_lessons = sorted(lesson_count.items(), key=lambda x: x[1], reverse=True)
        return [lesson for lesson, _ in sorted_lessons[:5]]
    
    # ============== 實體記憶 ==============
    
    def extract_and_store_entities(
        self,
        user_id: str,
        text: str,
        context: str = ""
    ) -> List[EntityMention]:
        """提取並存儲文本中的實體（簡化版，可以用 NER 替換）"""
        # 簡化的實體提取（實際應用中可以用 spaCy 或 LLM）
        entities = []
        
        # 這是一個簡化的示例，實際應該用 NER
        # 這裡只做基本的模式匹配
        import re
        
        # 查找可能的實體模式
        # 例如：大寫開頭的詞、引號中的內容等
        quoted = re.findall(r'"([^"]+)"', text)
        for q in quoted:
            entities.append(EntityMention(
                entity_type="quoted",
                entity_name=q,
                context=context[:100],
                first_mentioned=datetime.now().isoformat()
            ))
        
        if user_id not in self.entity_memory:
            self.entity_memory[user_id] = []
        
        for entity in entities:
            # 檢查是否已存在
            existing = next(
                (e for e in self.entity_memory[user_id]
                 if e.entity_name.lower() == entity.entity_name.lower()),
                None
            )
            if existing:
                existing.mention_count += 1
            else:
                self.entity_memory[user_id].append(entity)
        
        return entities
    
    def get_user_entities(
        self,
        user_id: str,
        entity_type: str = None
    ) -> List[EntityMention]:
        """獲取用戶提到的實體"""
        if user_id not in self.entity_memory:
            return []
        
        entities = self.entity_memory[user_id]
        
        if entity_type:
            entities = [e for e in entities if e.entity_type == entity_type]
        
        return sorted(entities, key=lambda e: e.mention_count, reverse=True)
    
    # ============== 用戶偏好 ==============
    
    def update_preference(
        self,
        user_id: str,
        key: str,
        value: Any
    ):
        """更新用戶偏好"""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = {}
        
        self.user_preferences[user_id][key] = value
    
    def get_preferences(self, user_id: str) -> Dict[str, Any]:
        """獲取用戶偏好"""
        return self.user_preferences.get(user_id, {})
    
    # ============== 上下文構建 ==============
    
    def build_context_prompt(
        self,
        session_id: str,
        user_id: str,
        current_query: str,
        task_category: TaskCategory = None,
        include_user_preferences: bool = True,   # 用戶偏好/習慣（跨 session）
        include_cross_session_episodes: bool = False  # 跨 session 的具體問題記憶
    ) -> str:
        """構建包含記憶的上下文 prompt
        
        記憶分離策略：
        - 用戶偏好/習慣（語言、風格、技能水平）→ 跨 session 保留 ✓
        - 具體問題/情節（上次問了什麼）→ 僅限當前 session ✗
        
        Args:
            session_id: 當前會話 ID
            user_id: 用戶 ID
            current_query: 當前查詢
            task_category: 任務類別
            include_user_preferences: 是否包含用戶偏好（默認 True，跨 session）
            include_cross_session_episodes: 是否包含跨 session 的具體問題（默認 False）
        
        Modified: 2026-02-06 - 分離偏好記憶和問題記憶
        """
        parts = []
        
        # 工作記憶：最近對話（僅限當前 session）- 永遠包含
        recent = self.get_recent_context(session_id, n_turns=3)
        if recent:
            parts.append("## Recent Conversation")
            parts.append(recent)
        
        # 用戶偏好（跨 session 保留）- 這是用戶的習慣，不是具體問題
        if include_user_preferences:
            prefs = self.get_preferences(user_id)
            if prefs:
                parts.append("\n## User Preferences")
                for k, v in list(prefs.items())[:5]:
                    parts.append(f"- {k}: {v}")
        
        # 跨 session 的具體問題記憶（默認關閉）
        # 這些是之前 session 的具體問題，不應混入新 session
        if include_cross_session_episodes:
            # 情節記憶：類似經驗
            similar = self.recall_similar_episodes(user_id, current_query, task_category, n_episodes=2)
            if similar:
                parts.append("\n## Relevant Past Experiences")
                for ep in similar:
                    parts.append(f"- Q: {ep.query[:50]}... -> {ep.outcome.value} ({ep.quality_score:.1f})")
            
            # 實體記憶（這也是具體問題相關的）
            entities = self.get_user_entities(user_id)[:5]
            if entities:
                parts.append("\n## Known Entities")
                for e in entities:
                    parts.append(f"- {e.entity_name} ({e.entity_type})")
        
        return "\n".join(parts)


# 單例
_memory_manager_instance = None


def get_memory_manager() -> MemoryManager:
    """獲取記憶管理器單例"""
    global _memory_manager_instance
    if _memory_manager_instance is None:
        _memory_manager_instance = MemoryManager()
    return _memory_manager_instance
