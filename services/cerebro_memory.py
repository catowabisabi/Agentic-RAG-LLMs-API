# -*- coding: utf-8 -*-
"""
=============================================================================
Cerebro 個性化記憶系統 (Personalized Memory System)
=============================================================================

功能說明：
-----------
參考 claude-mem 設計的個性化記憶系統，用於記住用戶偏好、重要事實和決策。

核心功能：
-----------
1. Memory Capture - 判斷什麼值得記住
2. Memory Store - 結構化存儲記憶
3. Memory Summarization - LLM 壓縮摘要
4. Memory Retrieval - 語義搜索 + top-k

資料模型：
-----------
    ┌─────────────────────────────────────────────────────────────────────┐
    │                         Cerebro Memory                               │
    │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                │
    │  │ Observation  │ │ UserProfile  │ │SessionSummary│                │
    │  │  - id        │ │  - user_id   │ │  - session_id│                │
    │  │  - type      │ │  - prefs     │ │  - request   │                │
    │  │  - title     │ │  - facts     │ │  - learned   │                │
    │  │  - facts     │ │  - style     │ │  - completed │                │
    │  └──────────────┘ └──────────────┘ └──────────────┘                │
    └─────────────────────────────────────────────────────────────────────┘

記憶類型：
-----------
- preference: 用戶偏好（喜歡簡潔回答、偏好中文...）
- fact: 用戶事實（職業、專長、常用工具...）
- decision: 重要決策（選擇了某技術棧...）
- discovery: 發現（用戶的使用習慣...）

=============================================================================
"""

import sqlite3
import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, asdict, field
from enum import Enum
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class MemoryType(str, Enum):
    """Types of memories we can store"""
    PREFERENCE = "preference"   # User preferences (e.g., "prefers concise answers")
    FACT = "fact"              # Facts about user (e.g., "is a Python developer")
    DECISION = "decision"      # Important decisions made
    DISCOVERY = "discovery"    # Discovered patterns/habits
    CONTEXT = "context"        # Contextual information
    STYLE = "style"           # Communication style preferences


class MemoryImportance(str, Enum):
    """Importance levels for memories"""
    CRITICAL = "critical"   # Must always inject (e.g., language preference)
    HIGH = "high"          # Inject when relevant
    MEDIUM = "medium"      # Inject if space allows
    LOW = "low"           # Archive, rarely inject


@dataclass
class Observation:
    """
    A single observation/memory captured from conversation.
    Similar to claude-mem's observation structure.
    """
    id: str
    user_id: str
    session_id: str
    memory_type: MemoryType
    importance: MemoryImportance
    
    # Structured content
    title: str                          # Short summary (e.g., "Prefers Python")
    subtitle: Optional[str] = None      # Additional context
    facts: List[str] = field(default_factory=list)  # Key facts extracted
    narrative: Optional[str] = None     # Full narrative if needed
    concepts: List[str] = field(default_factory=list)  # Related concepts/tags
    
    # Metadata
    source_message: Optional[str] = None  # Original message that triggered this
    confidence: float = 0.8              # How confident we are (0-1)
    created_at: str = None
    last_accessed: str = None
    access_count: int = 0
    decay_factor: float = 1.0           # For memory decay (1.0 = no decay)
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if self.last_accessed is None:
            self.last_accessed = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['memory_type'] = self.memory_type.value if isinstance(self.memory_type, MemoryType) else self.memory_type
        d['importance'] = self.importance.value if isinstance(self.importance, MemoryImportance) else self.importance
        return d
    
    def to_prompt_text(self) -> str:
        """Convert to text suitable for prompt injection"""
        parts = [f"• {self.title}"]
        if self.subtitle:
            parts.append(f"  ({self.subtitle})")
        if self.facts:
            for fact in self.facts[:3]:  # Limit facts
                parts.append(f"  - {fact}")
        return "\n".join(parts)


@dataclass
class UserProfile:
    """Aggregated user profile from all observations"""
    user_id: str
    display_name: Optional[str] = None
    
    # Aggregated preferences
    language_preference: str = "auto"  # zh-TW, en, auto
    response_style: str = "balanced"   # concise, detailed, balanced
    expertise_level: str = "intermediate"  # beginner, intermediate, expert
    
    # Known facts
    profession: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    interests: List[str] = field(default_factory=list)
    tools_used: List[str] = field(default_factory=list)
    
    # Preferences
    preferred_formats: List[str] = field(default_factory=list)  # code, bullet, table
    dislikes: List[str] = field(default_factory=list)
    
    # Metadata
    created_at: str = None
    updated_at: str = None
    observation_count: int = 0
    
    def __post_init__(self):
        now = datetime.now().isoformat()
        if self.created_at is None:
            self.created_at = now
        if self.updated_at is None:
            self.updated_at = now
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_system_prompt(self) -> str:
        """Generate system prompt injection based on user profile"""
        lines = ["[User Context]"]
        
        if self.display_name:
            lines.append(f"User: {self.display_name}")
        
        if self.language_preference != "auto":
            lang_map = {"zh-TW": "繁體中文", "en": "English", "zh-CN": "简体中文"}
            lines.append(f"Preferred language: {lang_map.get(self.language_preference, self.language_preference)}")
        
        if self.profession:
            lines.append(f"Profession: {self.profession}")
        
        if self.skills:
            lines.append(f"Skills: {', '.join(self.skills[:5])}")
        
        if self.response_style == "concise":
            lines.append("Style: Prefers concise, direct answers")
        elif self.response_style == "detailed":
            lines.append("Style: Prefers detailed explanations")
        
        if self.expertise_level == "expert":
            lines.append("Level: Expert - skip basic explanations")
        elif self.expertise_level == "beginner":
            lines.append("Level: Beginner - explain concepts clearly")
        
        if self.dislikes:
            lines.append(f"Avoid: {', '.join(self.dislikes[:3])}")
        
        return "\n".join(lines)


@dataclass
class SessionSummary:
    """Summary of a chat session"""
    id: str
    session_id: str
    user_id: str
    
    # Structured summary
    request: Optional[str] = None      # What user asked for
    investigated: Optional[str] = None  # What was explored
    learned: Optional[str] = None       # What was learned
    completed: Optional[str] = None     # What was accomplished
    next_steps: Optional[str] = None    # Suggested follow-ups
    
    # File/Code context
    files_read: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    
    # Metadata
    message_count: int = 0
    duration_seconds: int = 0
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CerebroMemory:
    """
    Cerebro: Personalized Memory System
    
    Thread-safe singleton with SQLite backend.
    Named after Professor X's Cerebro - enhances understanding of users.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, db_path: str = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, db_path: str = None):
        if self._initialized:
            return
        
        self._initialized = True
        self.db_path = db_path or "./rag-database/cerebro.db"
        
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Thread-local connections
        self._local = threading.local()
        
        # Initialize database
        self._init_db()
        
        logger.info(f"CerebroMemory initialized at {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            conn = sqlite3.connect(
                self.db_path,
                timeout=30.0,
                check_same_thread=False,
                isolation_level='DEFERRED'
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA busy_timeout=30000")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.connection = conn
        return self._local.connection
    
    @contextmanager
    def _cursor(self):
        """Context manager for database cursor"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
    
    def _init_db(self):
        """Initialize database schema"""
        with self._cursor() as cursor:
            # Schema version tracking
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_versions (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL
                )
            """)
            
            # User Profiles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profiles (
                    user_id TEXT PRIMARY KEY,
                    display_name TEXT,
                    language_preference TEXT DEFAULT 'auto',
                    response_style TEXT DEFAULT 'balanced',
                    expertise_level TEXT DEFAULT 'intermediate',
                    profession TEXT,
                    skills TEXT,
                    interests TEXT,
                    tools_used TEXT,
                    preferred_formats TEXT,
                    dislikes TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    observation_count INTEGER DEFAULT 0
                )
            """)
            
            # Observations table (core memories)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS observations (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    memory_type TEXT NOT NULL,
                    importance TEXT NOT NULL,
                    title TEXT NOT NULL,
                    subtitle TEXT,
                    facts TEXT,
                    narrative TEXT,
                    concepts TEXT,
                    source_message TEXT,
                    confidence REAL DEFAULT 0.8,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT NOT NULL,
                    access_count INTEGER DEFAULT 0,
                    decay_factor REAL DEFAULT 1.0,
                    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
                )
            """)
            
            # Session Summaries table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS session_summaries (
                    id TEXT PRIMARY KEY,
                    session_id TEXT UNIQUE NOT NULL,
                    user_id TEXT NOT NULL,
                    request TEXT,
                    investigated TEXT,
                    learned TEXT,
                    completed TEXT,
                    next_steps TEXT,
                    files_read TEXT,
                    files_modified TEXT,
                    message_count INTEGER DEFAULT 0,
                    duration_seconds INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES user_profiles(user_id)
                )
            """)
            
            # Indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_user ON observations(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_session ON observations(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_type ON observations(memory_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_importance ON observations(importance)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_obs_created ON observations(created_at DESC)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_summary_user ON session_summaries(user_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_summary_session ON session_summaries(session_id)")
            
            # Record schema version
            cursor.execute("""
                INSERT OR IGNORE INTO schema_versions (version, applied_at)
                VALUES (1, ?)
            """, (datetime.now().isoformat(),))
        
        logger.info("Cerebro database schema initialized")
    
    # ============== User Profile Operations ==============
    
    def get_or_create_user(self, user_id: str, display_name: str = None) -> UserProfile:
        """Get or create a user profile"""
        with self._cursor() as cursor:
            cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            
            if row:
                return UserProfile(
                    user_id=row['user_id'],
                    display_name=row['display_name'],
                    language_preference=row['language_preference'],
                    response_style=row['response_style'],
                    expertise_level=row['expertise_level'],
                    profession=row['profession'],
                    skills=json.loads(row['skills']) if row['skills'] else [],
                    interests=json.loads(row['interests']) if row['interests'] else [],
                    tools_used=json.loads(row['tools_used']) if row['tools_used'] else [],
                    preferred_formats=json.loads(row['preferred_formats']) if row['preferred_formats'] else [],
                    dislikes=json.loads(row['dislikes']) if row['dislikes'] else [],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    observation_count=row['observation_count']
                )
            
            # Create new user
            now = datetime.now().isoformat()
            profile = UserProfile(
                user_id=user_id,
                display_name=display_name,
                created_at=now,
                updated_at=now
            )
            
            cursor.execute("""
                INSERT INTO user_profiles (
                    user_id, display_name, language_preference, response_style,
                    expertise_level, profession, skills, interests, tools_used,
                    preferred_formats, dislikes, created_at, updated_at, observation_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile.user_id, profile.display_name, profile.language_preference,
                profile.response_style, profile.expertise_level, profile.profession,
                json.dumps(profile.skills), json.dumps(profile.interests),
                json.dumps(profile.tools_used), json.dumps(profile.preferred_formats),
                json.dumps(profile.dislikes), profile.created_at, profile.updated_at, 0
            ))
            
            logger.info(f"Created new user profile: {user_id}")
            return profile
    
    def update_user_profile(self, user_id: str, updates: Dict[str, Any]) -> UserProfile:
        """Update user profile with new information"""
        profile = self.get_or_create_user(user_id)
        
        # Apply updates
        for key, value in updates.items():
            if hasattr(profile, key):
                if key in ['skills', 'interests', 'tools_used', 'preferred_formats', 'dislikes']:
                    # Merge lists
                    current = getattr(profile, key, [])
                    if isinstance(value, list):
                        merged = list(set(current + value))
                    else:
                        merged = list(set(current + [value]))
                    setattr(profile, key, merged)
                else:
                    setattr(profile, key, value)
        
        profile.updated_at = datetime.now().isoformat()
        
        with self._cursor() as cursor:
            cursor.execute("""
                UPDATE user_profiles SET
                    display_name = ?, language_preference = ?, response_style = ?,
                    expertise_level = ?, profession = ?, skills = ?, interests = ?,
                    tools_used = ?, preferred_formats = ?, dislikes = ?, updated_at = ?
                WHERE user_id = ?
            """, (
                profile.display_name, profile.language_preference, profile.response_style,
                profile.expertise_level, profile.profession, json.dumps(profile.skills),
                json.dumps(profile.interests), json.dumps(profile.tools_used),
                json.dumps(profile.preferred_formats), json.dumps(profile.dislikes),
                profile.updated_at, user_id
            ))
        
        return profile
    
    # ============== Observation Operations ==============
    
    def _generate_observation_id(self, user_id: str, title: str) -> str:
        """Generate unique observation ID"""
        content = f"{user_id}:{title}:{datetime.now().timestamp()}"
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def store_observation(
        self,
        user_id: str,
        session_id: str,
        memory_type: MemoryType,
        title: str,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        subtitle: str = None,
        facts: List[str] = None,
        narrative: str = None,
        concepts: List[str] = None,
        source_message: str = None,
        confidence: float = 0.8
    ) -> Observation:
        """Store a new observation/memory"""
        
        obs_id = self._generate_observation_id(user_id, title)
        now = datetime.now().isoformat()
        
        observation = Observation(
            id=obs_id,
            user_id=user_id,
            session_id=session_id,
            memory_type=memory_type,
            importance=importance,
            title=title,
            subtitle=subtitle,
            facts=facts or [],
            narrative=narrative,
            concepts=concepts or [],
            source_message=source_message,
            confidence=confidence,
            created_at=now,
            last_accessed=now
        )
        
        with self._cursor() as cursor:
            cursor.execute("""
                INSERT INTO observations (
                    id, user_id, session_id, memory_type, importance,
                    title, subtitle, facts, narrative, concepts,
                    source_message, confidence, created_at, last_accessed,
                    access_count, decay_factor
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                observation.id, observation.user_id, observation.session_id,
                observation.memory_type.value, observation.importance.value,
                observation.title, observation.subtitle, json.dumps(observation.facts),
                observation.narrative, json.dumps(observation.concepts),
                observation.source_message, observation.confidence,
                observation.created_at, observation.last_accessed,
                observation.access_count, observation.decay_factor
            ))
            
            # Update user observation count
            cursor.execute("""
                UPDATE user_profiles SET observation_count = observation_count + 1
                WHERE user_id = ?
            """, (user_id,))
        
        logger.info(f"Stored observation: {title} for user {user_id}")
        return observation
    
    def get_observations(
        self,
        user_id: str,
        memory_types: List[MemoryType] = None,
        importance_levels: List[MemoryImportance] = None,
        limit: int = 20,
        include_low_confidence: bool = False
    ) -> List[Observation]:
        """Retrieve observations for a user"""
        
        query = "SELECT * FROM observations WHERE user_id = ?"
        params = [user_id]
        
        if memory_types:
            placeholders = ','.join(['?' for _ in memory_types])
            query += f" AND memory_type IN ({placeholders})"
            params.extend([mt.value for mt in memory_types])
        
        if importance_levels:
            placeholders = ','.join(['?' for _ in importance_levels])
            query += f" AND importance IN ({placeholders})"
            params.extend([il.value for il in importance_levels])
        
        if not include_low_confidence:
            query += " AND confidence >= 0.5"
        
        query += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)
        
        observations = []
        with self._cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            for row in rows:
                obs = Observation(
                    id=row['id'],
                    user_id=row['user_id'],
                    session_id=row['session_id'],
                    memory_type=MemoryType(row['memory_type']),
                    importance=MemoryImportance(row['importance']),
                    title=row['title'],
                    subtitle=row['subtitle'],
                    facts=json.loads(row['facts']) if row['facts'] else [],
                    narrative=row['narrative'],
                    concepts=json.loads(row['concepts']) if row['concepts'] else [],
                    source_message=row['source_message'],
                    confidence=row['confidence'],
                    created_at=row['created_at'],
                    last_accessed=row['last_accessed'],
                    access_count=row['access_count'],
                    decay_factor=row['decay_factor']
                )
                observations.append(obs)
                
                # Update access count
                cursor.execute("""
                    UPDATE observations SET
                        access_count = access_count + 1,
                        last_accessed = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), obs.id))
        
        return observations
    
    def search_observations(
        self,
        user_id: str,
        query: str,
        limit: int = 10
    ) -> List[Observation]:
        """Search observations by keyword matching"""
        
        # Simple keyword search (can be enhanced with vector search later)
        search_query = """
            SELECT * FROM observations
            WHERE user_id = ?
            AND (
                title LIKE ? OR
                subtitle LIKE ? OR
                narrative LIKE ? OR
                facts LIKE ? OR
                concepts LIKE ?
            )
            ORDER BY importance DESC, created_at DESC
            LIMIT ?
        """
        
        pattern = f"%{query}%"
        params = [user_id, pattern, pattern, pattern, pattern, pattern, limit]
        
        observations = []
        with self._cursor() as cursor:
            cursor.execute(search_query, params)
            rows = cursor.fetchall()
            
            for row in rows:
                obs = Observation(
                    id=row['id'],
                    user_id=row['user_id'],
                    session_id=row['session_id'],
                    memory_type=MemoryType(row['memory_type']),
                    importance=MemoryImportance(row['importance']),
                    title=row['title'],
                    subtitle=row['subtitle'],
                    facts=json.loads(row['facts']) if row['facts'] else [],
                    narrative=row['narrative'],
                    concepts=json.loads(row['concepts']) if row['concepts'] else [],
                    source_message=row['source_message'],
                    confidence=row['confidence'],
                    created_at=row['created_at'],
                    last_accessed=row['last_accessed'],
                    access_count=row['access_count'],
                    decay_factor=row['decay_factor']
                )
                observations.append(obs)
        
        return observations
    
    def delete_observation(self, observation_id: str) -> bool:
        """Delete an observation"""
        with self._cursor() as cursor:
            cursor.execute("DELETE FROM observations WHERE id = ?", (observation_id,))
            return cursor.rowcount > 0
    
    # ============== Session Summary Operations ==============
    
    def store_session_summary(
        self,
        session_id: str,
        user_id: str,
        request: str = None,
        investigated: str = None,
        learned: str = None,
        completed: str = None,
        next_steps: str = None,
        files_read: List[str] = None,
        files_modified: List[str] = None,
        message_count: int = 0,
        duration_seconds: int = 0
    ) -> SessionSummary:
        """Store or update a session summary"""
        
        summary_id = hashlib.md5(f"{session_id}:{user_id}".encode()).hexdigest()[:16]
        
        summary = SessionSummary(
            id=summary_id,
            session_id=session_id,
            user_id=user_id,
            request=request,
            investigated=investigated,
            learned=learned,
            completed=completed,
            next_steps=next_steps,
            files_read=files_read or [],
            files_modified=files_modified or [],
            message_count=message_count,
            duration_seconds=duration_seconds
        )
        
        with self._cursor() as cursor:
            cursor.execute("""
                INSERT OR REPLACE INTO session_summaries (
                    id, session_id, user_id, request, investigated, learned,
                    completed, next_steps, files_read, files_modified,
                    message_count, duration_seconds, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                summary.id, summary.session_id, summary.user_id,
                summary.request, summary.investigated, summary.learned,
                summary.completed, summary.next_steps,
                json.dumps(summary.files_read), json.dumps(summary.files_modified),
                summary.message_count, summary.duration_seconds, summary.created_at
            ))
        
        logger.info(f"Stored session summary for {session_id}")
        return summary
    
    def get_recent_summaries(
        self,
        user_id: str,
        limit: int = 10
    ) -> List[SessionSummary]:
        """Get recent session summaries for a user"""
        
        summaries = []
        with self._cursor() as cursor:
            cursor.execute("""
                SELECT * FROM session_summaries
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (user_id, limit))
            
            for row in cursor.fetchall():
                summary = SessionSummary(
                    id=row['id'],
                    session_id=row['session_id'],
                    user_id=row['user_id'],
                    request=row['request'],
                    investigated=row['investigated'],
                    learned=row['learned'],
                    completed=row['completed'],
                    next_steps=row['next_steps'],
                    files_read=json.loads(row['files_read']) if row['files_read'] else [],
                    files_modified=json.loads(row['files_modified']) if row['files_modified'] else [],
                    message_count=row['message_count'],
                    duration_seconds=row['duration_seconds'],
                    created_at=row['created_at']
                )
                summaries.append(summary)
        
        return summaries
    
    # ============== Context Injection ==============
    
    def get_context_for_prompt(
        self,
        user_id: str,
        query: str = None,
        max_observations: int = 10
    ) -> str:
        """
        Get formatted context for prompt injection.
        Returns a string suitable for adding to system prompt.
        """
        
        parts = []
        
        # 1. Get user profile
        profile = self.get_or_create_user(user_id)
        profile_text = profile.to_system_prompt()
        if profile_text and len(profile_text) > 20:
            parts.append(profile_text)
        
        # 2. Get critical observations (always inject)
        critical_obs = self.get_observations(
            user_id,
            importance_levels=[MemoryImportance.CRITICAL],
            limit=5
        )
        if critical_obs:
            parts.append("\n[Critical Context]")
            for obs in critical_obs:
                parts.append(obs.to_prompt_text())
        
        # 3. Get relevant observations if query provided
        if query:
            relevant_obs = self.search_observations(user_id, query, limit=max_observations)
            if relevant_obs:
                parts.append("\n[Relevant Memories]")
                for obs in relevant_obs[:5]:  # Limit to avoid prompt bloat
                    if obs.importance != MemoryImportance.CRITICAL:  # Avoid duplicates
                        parts.append(obs.to_prompt_text())
        
        # 4. Get recent high-importance observations
        high_obs = self.get_observations(
            user_id,
            importance_levels=[MemoryImportance.HIGH],
            limit=5
        )
        if high_obs:
            existing_ids = {o.id for o in critical_obs} | {o.id for o in (relevant_obs if query else [])}
            new_high = [o for o in high_obs if o.id not in existing_ids]
            if new_high:
                parts.append("\n[User Preferences]")
                for obs in new_high[:3]:
                    parts.append(obs.to_prompt_text())
        
        return "\n".join(parts) if parts else ""
    
    # ============== Memory Capture Helpers ==============
    
    def should_capture(self, message: str, response: str = None) -> Tuple[bool, Optional[MemoryType], Optional[str]]:
        """
        Heuristic to determine if a message should trigger memory capture.
        Returns: (should_capture, memory_type, reason)
        
        This is a simple rule-based approach. Can be enhanced with LLM later.
        """
        
        message_lower = message.lower()
        
        # Preference indicators
        preference_keywords = [
            "i prefer", "i like", "i want", "please always", "don't use",
            "我喜歡", "我偏好", "我希望", "請總是", "不要用",
            "偏好", "習慣", "喜歡", "討厭"
        ]
        for kw in preference_keywords:
            if kw in message_lower:
                return True, MemoryType.PREFERENCE, f"Contains preference keyword: {kw}"
        
        # Fact indicators (about user)
        fact_keywords = [
            "i am a", "i'm a", "my job", "i work", "i use",
            "我是", "我的工作", "我用", "我會"
        ]
        for kw in fact_keywords:
            if kw in message_lower:
                return True, MemoryType.FACT, f"Contains fact keyword: {kw}"
        
        # Style indicators
        style_keywords = [
            "be concise", "be brief", "more detail", "explain more",
            "簡潔", "詳細", "說明清楚"
        ]
        for kw in style_keywords:
            if kw in message_lower:
                return True, MemoryType.STYLE, f"Contains style keyword: {kw}"
        
        # Decision indicators
        decision_keywords = [
            "i decided", "let's go with", "i choose", "i'll use",
            "我決定", "就用", "選擇"
        ]
        for kw in decision_keywords:
            if kw in message_lower:
                return True, MemoryType.DECISION, f"Contains decision keyword: {kw}"
        
        return False, None, None
    
    def extract_memory_from_message(
        self,
        message: str,
        memory_type: MemoryType
    ) -> Dict[str, Any]:
        """
        Extract structured memory data from a message.
        Simple rule-based extraction. Can be enhanced with LLM.
        """
        
        # This is a placeholder - in production, use LLM for extraction
        return {
            "title": message[:100] if len(message) > 100 else message,
            "facts": [],
            "concepts": [],
            "importance": MemoryImportance.MEDIUM
        }


# ============== Singleton Instance ==============

_cerebro_instance: Optional[CerebroMemory] = None


def get_cerebro() -> CerebroMemory:
    """Get the singleton CerebroMemory instance"""
    global _cerebro_instance
    if _cerebro_instance is None:
        _cerebro_instance = CerebroMemory()
    return _cerebro_instance


# ============== Convenience Functions ==============

def remember(
    user_id: str,
    session_id: str,
    memory_type: MemoryType,
    title: str,
    **kwargs
) -> Observation:
    """Quick function to store a memory"""
    cerebro = get_cerebro()
    return cerebro.store_observation(
        user_id=user_id,
        session_id=session_id,
        memory_type=memory_type,
        title=title,
        **kwargs
    )


def recall(user_id: str, query: str = None, limit: int = 10) -> str:
    """Quick function to get context for a user"""
    cerebro = get_cerebro()
    return cerebro.get_context_for_prompt(user_id, query, limit)


def get_user(user_id: str) -> UserProfile:
    """Quick function to get user profile"""
    cerebro = get_cerebro()
    return cerebro.get_or_create_user(user_id)
