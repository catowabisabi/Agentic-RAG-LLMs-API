# -*- coding: utf-8 -*-
"""
Memory Sub-package

Provides structured memory management following Microsoft's AI Agents design patterns:
- Working Memory: Current task context
- Episodic Memory: Workflow experience learning
- Entity Memory: Structured entity tracking
- Memory Manager: Unified interface
"""

from .working_memory import (
    WorkingMemory,
    WorkingMemoryItem,
    get_working_memory
)

from .episodic_memory import (
    Episode,
    ExecutionStep,
    EpisodeOutcome,
    TaskCategory,
    EpisodicMemoryStore,
    get_episodic_store
)

from .entity_memory import (
    Entity,
    EntityRelation,
    EntityType,
    RelationType,
    EntityMemoryStore,
    get_entity_store
)

from .memory_manager import (
    MemoryManager,
    get_memory_manager
)

__all__ = [
    # Working Memory
    'WorkingMemory',
    'WorkingMemoryItem',
    'get_working_memory',
    
    # Episodic Memory
    'Episode',
    'ExecutionStep',
    'EpisodeOutcome',
    'TaskCategory',
    'EpisodicMemoryStore',
    'get_episodic_store',
    
    # Entity Memory
    'Entity',
    'EntityRelation',
    'EntityType',
    'RelationType',
    'EntityMemoryStore',
    'get_entity_store',
    
    # Memory Manager
    'MemoryManager',
    'get_memory_manager',
]
