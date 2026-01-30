# -*- coding: utf-8 -*-
"""
=============================================================================
Episodic Memory - 情節記憶系統
=============================================================================

參考 Microsoft AI Agents 課程設計，實現工作流程/情節記憶：
- 記錄任務執行經驗（成功/失敗）
- 學習哪些策略有效
- 用於未來任務優化

核心概念（來自 MSFT 第13課）：
"Episodic memory stores the sequence of steps an agent takes during 
a complex task, including successes and failures. It's like remembering 
specific 'episodes' or past experiences to learn from them."

=============================================================================
"""

import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict, field
from enum import Enum
import sqlite3
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class EpisodeOutcome(str, Enum):
    """Episode execution outcomes"""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    USER_CANCELLED = "user_cancelled"


class TaskCategory(str, Enum):
    """Categories of tasks for pattern matching"""
    RAG_SEARCH = "rag_search"
    CALCULATION = "calculation"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"
    PLANNING = "planning"
    ANALYSIS = "analysis"
    CREATIVE = "creative"
    MULTI_STEP = "multi_step"
    SIMPLE_CHAT = "simple_chat"
    TOOL_USE = "tool_use"


@dataclass
class ExecutionStep:
    """A single step in an episode"""
    step_number: int
    agent_name: str
    action: str
    input_summary: str
    output_summary: str
    duration_ms: int
    success: bool
    error_message: Optional[str] = None


@dataclass
class Episode:
    """
    A complete episode record.
    
    Records the full execution of a task, including:
    - What was the task
    - What plan was used
    - What steps were taken
    - What was the outcome
    - What can be learned
    """
    id: str
    user_id: str
    session_id: str
    
    # Task Information
    task_category: TaskCategory
    task_description: str
    task_query: str
    
    # Execution Details
    plan_summary: str
    agents_involved: List[str]
    steps: List[ExecutionStep]
    
    # Outcome
    outcome: EpisodeOutcome
    final_response_summary: str
    user_feedback: Optional[str] = None
    user_rating: Optional[int] = None  # 1-5
    
    # Learning
    lessons_learned: List[str] = field(default_factory=list)
    successful_patterns: List[str] = field(default_factory=list)
    failure_patterns: List[str] = field(default_factory=list)
    
    # Metadata
    total_duration_ms: int = 0
    tokens_used: int = 0
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['task_category'] = self.task_category.value if isinstance(self.task_category, TaskCategory) else self.task_category
        d['outcome'] = self.outcome.value if isinstance(self.outcome, EpisodeOutcome) else self.outcome
        d['steps'] = [asdict(s) for s in self.steps]
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Episode':
        data['task_category'] = TaskCategory(data['task_category'])
        data['outcome'] = EpisodeOutcome(data['outcome'])
        data['steps'] = [ExecutionStep(**s) for s in data.get('steps', [])]
        return cls(**data)


class EpisodicMemoryStore:
    """
    Episodic Memory Storage and Retrieval.
    
    Features:
    - SQLite persistence
    - Pattern matching for similar past episodes
    - Success/failure analysis
    - Experience-based recommendations
    """
    
    def __init__(self, db_path: str = "data/episodic_memory.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()
        logger.info(f"EpisodicMemoryStore initialized at {db_path}")
    
    @contextmanager
    def _get_connection(self):
        """Thread-safe connection management"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
        try:
            yield self._local.connection
        except Exception as e:
            self._local.connection.rollback()
            raise
    
    def _init_db(self):
        """Initialize database schema"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Episodes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episodes (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    task_category TEXT NOT NULL,
                    task_description TEXT NOT NULL,
                    task_query TEXT NOT NULL,
                    plan_summary TEXT,
                    agents_involved TEXT,
                    outcome TEXT NOT NULL,
                    final_response_summary TEXT,
                    user_feedback TEXT,
                    user_rating INTEGER,
                    lessons_learned TEXT,
                    successful_patterns TEXT,
                    failure_patterns TEXT,
                    total_duration_ms INTEGER,
                    tokens_used INTEGER,
                    created_at TEXT NOT NULL
                )
            """)
            
            # Steps table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS episode_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    episode_id TEXT NOT NULL,
                    step_number INTEGER NOT NULL,
                    agent_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    input_summary TEXT,
                    output_summary TEXT,
                    duration_ms INTEGER,
                    success INTEGER,
                    error_message TEXT,
                    FOREIGN KEY (episode_id) REFERENCES episodes(id)
                )
            """)
            
            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodes_user 
                ON episodes(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodes_category 
                ON episodes(task_category)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_episodes_outcome 
                ON episodes(outcome)
            """)
            
            conn.commit()
    
    def store_episode(self, episode: Episode) -> str:
        """Store an episode"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Insert episode
            cursor.execute("""
                INSERT INTO episodes (
                    id, user_id, session_id, task_category, task_description,
                    task_query, plan_summary, agents_involved, outcome,
                    final_response_summary, user_feedback, user_rating,
                    lessons_learned, successful_patterns, failure_patterns,
                    total_duration_ms, tokens_used, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                episode.id,
                episode.user_id,
                episode.session_id,
                episode.task_category.value,
                episode.task_description,
                episode.task_query,
                episode.plan_summary,
                json.dumps(episode.agents_involved),
                episode.outcome.value,
                episode.final_response_summary,
                episode.user_feedback,
                episode.user_rating,
                json.dumps(episode.lessons_learned),
                json.dumps(episode.successful_patterns),
                json.dumps(episode.failure_patterns),
                episode.total_duration_ms,
                episode.tokens_used,
                episode.created_at
            ))
            
            # Insert steps
            for step in episode.steps:
                cursor.execute("""
                    INSERT INTO episode_steps (
                        episode_id, step_number, agent_name, action,
                        input_summary, output_summary, duration_ms,
                        success, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    episode.id,
                    step.step_number,
                    step.agent_name,
                    step.action,
                    step.input_summary,
                    step.output_summary,
                    step.duration_ms,
                    1 if step.success else 0,
                    step.error_message
                ))
            
            conn.commit()
            logger.info(f"Stored episode: {episode.id}")
            return episode.id
    
    def find_similar_episodes(
        self,
        task_category: TaskCategory,
        task_description: str,
        limit: int = 5,
        only_successful: bool = False
    ) -> List[Episode]:
        """
        Find similar past episodes for learning.
        
        Uses task category and keyword matching.
        Future: Add semantic similarity.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Build query
            query = """
                SELECT * FROM episodes
                WHERE task_category = ?
            """
            params = [task_category.value]
            
            if only_successful:
                query += " AND outcome = 'success'"
            
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            episodes = []
            for row in rows:
                episode_dict = dict(row)
                
                # Parse JSON fields
                episode_dict['agents_involved'] = json.loads(episode_dict['agents_involved'] or '[]')
                episode_dict['lessons_learned'] = json.loads(episode_dict['lessons_learned'] or '[]')
                episode_dict['successful_patterns'] = json.loads(episode_dict['successful_patterns'] or '[]')
                episode_dict['failure_patterns'] = json.loads(episode_dict['failure_patterns'] or '[]')
                
                # Get steps
                cursor.execute("""
                    SELECT * FROM episode_steps WHERE episode_id = ?
                    ORDER BY step_number
                """, (episode_dict['id'],))
                step_rows = cursor.fetchall()
                
                steps = []
                for step_row in step_rows:
                    step_dict = dict(step_row)
                    step_dict['success'] = bool(step_dict['success'])
                    del step_dict['id']
                    del step_dict['episode_id']
                    steps.append(ExecutionStep(**step_dict))
                
                episode_dict['steps'] = steps
                episodes.append(Episode.from_dict(episode_dict))
            
            return episodes
    
    def get_success_patterns(
        self,
        task_category: TaskCategory,
        limit: int = 10
    ) -> List[str]:
        """Extract successful patterns for a task category"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT successful_patterns FROM episodes
                WHERE task_category = ? AND outcome = 'success'
                ORDER BY created_at DESC
                LIMIT ?
            """, (task_category.value, limit))
            
            rows = cursor.fetchall()
            patterns = []
            for row in rows:
                patterns.extend(json.loads(row['successful_patterns'] or '[]'))
            
            return list(set(patterns))  # Deduplicate
    
    def get_failure_patterns(
        self,
        task_category: TaskCategory,
        limit: int = 10
    ) -> List[str]:
        """Extract failure patterns to avoid"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT failure_patterns FROM episodes
                WHERE task_category = ? AND outcome IN ('failure', 'partial_success')
                ORDER BY created_at DESC
                LIMIT ?
            """, (task_category.value, limit))
            
            rows = cursor.fetchall()
            patterns = []
            for row in rows:
                patterns.extend(json.loads(row['failure_patterns'] or '[]'))
            
            return list(set(patterns))
    
    def get_statistics(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get episode statistics"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            where_clause = "WHERE user_id = ?" if user_id else ""
            params = [user_id] if user_id else []
            
            # Total episodes
            cursor.execute(f"SELECT COUNT(*) FROM episodes {where_clause}", params)
            total = cursor.fetchone()[0]
            
            # By outcome
            cursor.execute(f"""
                SELECT outcome, COUNT(*) as count
                FROM episodes {where_clause}
                GROUP BY outcome
            """, params)
            by_outcome = {row['outcome']: row['count'] for row in cursor.fetchall()}
            
            # By category
            cursor.execute(f"""
                SELECT task_category, COUNT(*) as count
                FROM episodes {where_clause}
                GROUP BY task_category
            """, params)
            by_category = {row['task_category']: row['count'] for row in cursor.fetchall()}
            
            # Average duration
            cursor.execute(f"""
                SELECT AVG(total_duration_ms) as avg_duration
                FROM episodes {where_clause}
            """, params)
            avg_duration = cursor.fetchone()['avg_duration'] or 0
            
            return {
                "total_episodes": total,
                "by_outcome": by_outcome,
                "by_category": by_category,
                "average_duration_ms": avg_duration,
                "success_rate": by_outcome.get('success', 0) / total if total > 0 else 0
            }
    
    def update_user_feedback(
        self,
        episode_id: str,
        feedback: str,
        rating: int
    ) -> bool:
        """Update user feedback for an episode"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE episodes
                SET user_feedback = ?, user_rating = ?
                WHERE id = ?
            """, (feedback, rating, episode_id))
            
            conn.commit()
            return cursor.rowcount > 0


import threading  # Add at top

# Singleton instance
_episodic_store: Optional[EpisodicMemoryStore] = None


def get_episodic_store() -> EpisodicMemoryStore:
    """Get the singleton episodic memory store"""
    global _episodic_store
    if _episodic_store is None:
        _episodic_store = EpisodicMemoryStore()
    return _episodic_store
