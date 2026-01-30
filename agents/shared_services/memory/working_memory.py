# -*- coding: utf-8 -*-
"""
=============================================================================
Working Memory - 工作記憶系統
=============================================================================

參考 Microsoft AI Agents 課程設計，實現工作記憶：
- 當前任務的暫存區
- 保持最相關的信息
- 動態更新和裁剪

核心概念（來自 MSFT 第13課）：
"Think of this as a piece of scratch paper an agent uses during a single, 
ongoing task or thought process. It holds immediate information needed to 
compute the next step."

=============================================================================
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import OrderedDict

logger = logging.getLogger(__name__)


@dataclass
class WorkingMemoryItem:
    """A single item in working memory"""
    key: str
    content: Any
    relevance_score: float  # 0-1, higher = more relevant
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    
    def access(self):
        """Mark item as accessed"""
        self.last_accessed = datetime.now()
        self.access_count += 1


class WorkingMemory:
    """
    Working Memory for current task context.
    
    Features:
    - Fixed capacity with LRU eviction
    - Relevance-based prioritization
    - Quick access by key
    - Automatic cleanup
    
    使用場景：
    - 當前對話的關鍵信息
    - 正在處理的任務上下文
    - 中間計算結果
    """
    
    def __init__(self, capacity: int = 20):
        """
        Initialize working memory.
        
        Args:
            capacity: Maximum items to hold (default 20)
        """
        self.capacity = capacity
        self._items: OrderedDict[str, WorkingMemoryItem] = OrderedDict()
        
        # Current task context
        self._current_task_id: Optional[str] = None
        self._task_start_time: Optional[datetime] = None
        
        logger.debug(f"WorkingMemory initialized with capacity {capacity}")
    
    def set_current_task(self, task_id: str):
        """Set the current task context"""
        if self._current_task_id != task_id:
            # Clear previous task's working memory
            self.clear()
            self._current_task_id = task_id
            self._task_start_time = datetime.now()
            logger.debug(f"Working memory: New task context {task_id}")
    
    def store(
        self,
        key: str,
        content: Any,
        relevance_score: float = 0.5
    ):
        """
        Store item in working memory.
        
        Args:
            key: Unique identifier
            content: The content to store
            relevance_score: 0-1, how relevant to current task
        """
        # Evict if at capacity
        if len(self._items) >= self.capacity and key not in self._items:
            self._evict_least_relevant()
        
        item = WorkingMemoryItem(
            key=key,
            content=content,
            relevance_score=min(1.0, max(0.0, relevance_score))
        )
        
        self._items[key] = item
        # Move to end (most recently used)
        self._items.move_to_end(key)
        
        logger.debug(f"Working memory: Stored '{key}' (relevance: {relevance_score:.2f})")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Get item from working memory.
        
        Returns None if not found.
        """
        if key in self._items:
            item = self._items[key]
            item.access()
            self._items.move_to_end(key)
            return item.content
        return None
    
    def get_all(self) -> Dict[str, Any]:
        """Get all items as a dict"""
        return {k: v.content for k, v in self._items.items()}
    
    def get_top_relevant(self, n: int = 5) -> List[Dict[str, Any]]:
        """
        Get top N most relevant items.
        
        Returns list sorted by relevance score.
        """
        sorted_items = sorted(
            self._items.values(),
            key=lambda x: x.relevance_score,
            reverse=True
        )
        
        return [
            {
                "key": item.key,
                "content": item.content,
                "relevance": item.relevance_score
            }
            for item in sorted_items[:n]
        ]
    
    def update_relevance(self, key: str, new_score: float):
        """Update relevance score for an item"""
        if key in self._items:
            self._items[key].relevance_score = min(1.0, max(0.0, new_score))
    
    def remove(self, key: str) -> bool:
        """Remove item by key"""
        if key in self._items:
            del self._items[key]
            return True
        return False
    
    def clear(self):
        """Clear all items"""
        self._items.clear()
        self._current_task_id = None
        self._task_start_time = None
        logger.debug("Working memory cleared")
    
    def _evict_least_relevant(self):
        """Evict the least relevant item"""
        if not self._items:
            return
        
        # Find item with lowest (relevance * recency) score
        min_score = float('inf')
        min_key = None
        
        now = datetime.now()
        for key, item in self._items.items():
            # Combine relevance with recency (older = lower)
            age_seconds = (now - item.last_accessed).total_seconds()
            recency_factor = 1.0 / (1.0 + age_seconds / 60.0)  # Decay over minutes
            combined_score = item.relevance_score * 0.7 + recency_factor * 0.3
            
            if combined_score < min_score:
                min_score = combined_score
                min_key = key
        
        if min_key:
            del self._items[min_key]
            logger.debug(f"Working memory: Evicted '{min_key}' (score: {min_score:.2f})")
    
    def to_context_string(self) -> str:
        """
        Convert working memory to a context string for LLM.
        
        Returns a formatted string of the most relevant items.
        """
        if not self._items:
            return ""
        
        top_items = self.get_top_relevant(10)
        
        lines = ["## Working Memory Context:"]
        for item in top_items:
            content = item['content']
            if isinstance(content, dict):
                content = str(content)[:200]
            elif isinstance(content, str) and len(content) > 200:
                content = content[:200] + "..."
            lines.append(f"- {item['key']}: {content}")
        
        return "\n".join(lines)
    
    def __len__(self) -> int:
        return len(self._items)
    
    def __contains__(self, key: str) -> bool:
        return key in self._items
    
    @property
    def is_empty(self) -> bool:
        return len(self._items) == 0
    
    @property
    def current_task_id(self) -> Optional[str]:
        return self._current_task_id


# Thread-local working memory for concurrent tasks
import threading

class ThreadLocalWorkingMemory:
    """Thread-local working memory storage"""
    
    def __init__(self, capacity: int = 20):
        self._local = threading.local()
        self._capacity = capacity
    
    @property
    def memory(self) -> WorkingMemory:
        """Get thread-local working memory"""
        if not hasattr(self._local, 'working_memory'):
            self._local.working_memory = WorkingMemory(self._capacity)
        return self._local.working_memory


# Global thread-local instance
_working_memory = ThreadLocalWorkingMemory()


def get_working_memory() -> WorkingMemory:
    """Get the thread-local working memory instance"""
    return _working_memory.memory
