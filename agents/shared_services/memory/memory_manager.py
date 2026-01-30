# -*- coding: utf-8 -*-
"""
=============================================================================
Memory Manager - 統一記憶管理器
=============================================================================

整合所有記憶類型，提供統一的記憶管理介面。

參考 Microsoft AI Agents 課程設計的記憶架構：
- Working Memory: 當前任務上下文
- Short-term Memory: 會話記憶
- Long-term Memory: 持久化偏好和事實
- Episodic Memory: 工作流程經驗
- Entity Memory: 結構化實體

=============================================================================
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import hashlib

from .working_memory import WorkingMemory, get_working_memory
from .episodic_memory import (
    EpisodicMemoryStore, Episode, ExecutionStep,
    EpisodeOutcome, TaskCategory, get_episodic_store
)
from .entity_memory import (
    EntityMemoryStore, Entity, EntityRelation,
    EntityType, RelationType, get_entity_store
)

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Unified Memory Manager.
    
    Provides a single interface for all memory operations:
    - store/retrieve working memory
    - store/retrieve episodes
    - store/retrieve entities
    - generate context for LLM
    """
    
    def __init__(self):
        # Initialize all memory stores
        self.working_memory = get_working_memory()
        self.episodic_store = get_episodic_store()
        self.entity_store = get_entity_store()
        
        logger.info("MemoryManager initialized with all memory stores")
    
    # ============== Working Memory Operations ==============
    
    def set_task_context(self, task_id: str):
        """Set current task context"""
        self.working_memory.set_current_task(task_id)
    
    def store_working(self, key: str, content: Any, relevance: float = 0.5):
        """Store in working memory"""
        self.working_memory.store(key, content, relevance)
    
    def get_working(self, key: str) -> Optional[Any]:
        """Get from working memory"""
        return self.working_memory.get(key)
    
    def get_working_context(self) -> str:
        """Get working memory as context string"""
        return self.working_memory.to_context_string()
    
    # ============== Episodic Memory Operations ==============
    
    def start_episode(
        self,
        task_id: str,
        user_id: str,
        session_id: str,
        task_category: TaskCategory,
        task_description: str,
        query: str
    ) -> Episode:
        """Start tracking a new episode"""
        episode = Episode(
            id=task_id,
            user_id=user_id,
            session_id=session_id,
            task_category=task_category,
            task_description=task_description,
            task_query=query,
            plan_summary="",
            agents_involved=[],
            steps=[],
            outcome=EpisodeOutcome.SUCCESS,  # Default, update later
            final_response_summary=""
        )
        return episode
    
    def add_episode_step(
        self,
        episode: Episode,
        step_number: int,
        agent_name: str,
        action: str,
        input_summary: str,
        output_summary: str,
        duration_ms: int,
        success: bool,
        error_message: Optional[str] = None
    ):
        """Add a step to the episode"""
        step = ExecutionStep(
            step_number=step_number,
            agent_name=agent_name,
            action=action,
            input_summary=input_summary[:500],  # Limit size
            output_summary=output_summary[:500],
            duration_ms=duration_ms,
            success=success,
            error_message=error_message
        )
        episode.steps.append(step)
        
        if agent_name not in episode.agents_involved:
            episode.agents_involved.append(agent_name)
    
    def complete_episode(
        self,
        episode: Episode,
        outcome: EpisodeOutcome,
        final_response: str,
        lessons_learned: Optional[List[str]] = None,
        successful_patterns: Optional[List[str]] = None,
        failure_patterns: Optional[List[str]] = None
    ):
        """Complete and store the episode"""
        episode.outcome = outcome
        episode.final_response_summary = final_response[:500]
        
        if lessons_learned:
            episode.lessons_learned = lessons_learned
        if successful_patterns:
            episode.successful_patterns = successful_patterns
        if failure_patterns:
            episode.failure_patterns = failure_patterns
        
        # Calculate total duration
        episode.total_duration_ms = sum(s.duration_ms for s in episode.steps)
        
        # Store
        self.episodic_store.store_episode(episode)
        logger.info(f"Episode completed: {episode.id} ({outcome.value})")
    
    def get_similar_episodes(
        self,
        task_category: TaskCategory,
        description: str,
        only_successful: bool = True,
        limit: int = 3
    ) -> List[Episode]:
        """Find similar past episodes"""
        return self.episodic_store.find_similar_episodes(
            task_category=task_category,
            task_description=description,
            only_successful=only_successful,
            limit=limit
        )
    
    def get_learned_patterns(self, task_category: TaskCategory) -> Dict[str, List[str]]:
        """Get success and failure patterns for a task category"""
        return {
            "success": self.episodic_store.get_success_patterns(task_category),
            "failure": self.episodic_store.get_failure_patterns(task_category)
        }
    
    # ============== Entity Memory Operations ==============
    
    def extract_and_store_entity(
        self,
        name: str,
        entity_type: EntityType,
        user_id: str,
        session_id: str,
        attributes: Optional[Dict[str, Any]] = None
    ) -> Entity:
        """Extract and store an entity"""
        entity_id = self._generate_entity_id(name, entity_type, user_id)
        
        entity = Entity(
            id=entity_id,
            name=name,
            entity_type=entity_type,
            user_id=user_id,
            attributes=attributes or {},
            source_sessions=[session_id]
        )
        
        self.entity_store.store_entity(entity)
        return entity
    
    def add_entity_relation(
        self,
        source_entity_id: str,
        target_entity_id: str,
        relation_type: RelationType,
        context: Optional[str] = None
    ) -> EntityRelation:
        """Add a relationship between entities"""
        relation_id = hashlib.md5(
            f"{source_entity_id}:{target_entity_id}:{relation_type.value}".encode()
        ).hexdigest()[:16]
        
        relation = EntityRelation(
            id=relation_id,
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            relation_type=relation_type,
            context=context
        )
        
        self.entity_store.store_relation(relation)
        return relation
    
    def find_entity(self, name: str, entity_type: Optional[EntityType] = None) -> Optional[Entity]:
        """Find an entity by name"""
        return self.entity_store.find_entity(name, entity_type)
    
    def get_user_entities(self, user_id: str, limit: int = 50) -> List[Entity]:
        """Get all entities for a user"""
        return self.entity_store.get_user_entities(user_id, limit=limit)
    
    def get_entity_context(self, user_id: str, limit: int = 10) -> str:
        """Get entity memory as context string"""
        return self.entity_store.to_context_string(user_id, limit)
    
    # ============== Combined Context Generation ==============
    
    def generate_full_context(
        self,
        user_id: str,
        task_category: Optional[TaskCategory] = None,
        include_working: bool = True,
        include_entities: bool = True,
        include_patterns: bool = True
    ) -> str:
        """
        Generate comprehensive context for LLM.
        
        Combines:
        - Working memory (current task context)
        - Entity memory (known facts about user)
        - Learned patterns (from past episodes)
        """
        parts = []
        
        # Working Memory
        if include_working:
            working_ctx = self.working_memory.to_context_string()
            if working_ctx:
                parts.append(working_ctx)
        
        # Entity Memory
        if include_entities:
            entity_ctx = self.entity_store.to_context_string(user_id, limit=10)
            if entity_ctx:
                parts.append(entity_ctx)
        
        # Learned Patterns
        if include_patterns and task_category:
            patterns = self.get_learned_patterns(task_category)
            
            if patterns["success"]:
                parts.append("## Successful Patterns:")
                for p in patterns["success"][:5]:
                    parts.append(f"- ✓ {p}")
            
            if patterns["failure"]:
                parts.append("## Patterns to Avoid:")
                for p in patterns["failure"][:3]:
                    parts.append(f"- ✗ {p}")
        
        return "\n\n".join(parts) if parts else ""
    
    def _generate_entity_id(self, name: str, entity_type: EntityType, user_id: str) -> str:
        """Generate deterministic entity ID"""
        key = f"{entity_type.value}:{name.lower()}:{user_id}"
        return hashlib.md5(key.encode()).hexdigest()[:16]
    
    # ============== Statistics ==============
    
    def get_statistics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get memory system statistics"""
        return {
            "working_memory_items": len(self.working_memory),
            "episodic_stats": self.episodic_store.get_statistics(user_id),
            "entity_count": len(self.get_user_entities(user_id)) if user_id else 0
        }


# Singleton instance
_memory_manager: Optional[MemoryManager] = None


def get_memory_manager() -> MemoryManager:
    """Get the singleton memory manager"""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
