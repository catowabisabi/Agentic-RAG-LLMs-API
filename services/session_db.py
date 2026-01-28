# -*- coding: utf-8 -*-
"""
=============================================================================
會話資料庫服務 (Session Database Service)
=============================================================================

功能說明：
-----------
提供持久化存儲，用於保存聊天會話、任務和交互歷史。

核心功能：
-----------
1. 聊天會話管理（創建、讀取、更新、刪除）
2. 代理任務綁定到會話
3. 任務步驟和回應記錄
4. 完整交互歷史恢復

資料模型：
-----------
    ┌─────────────────────────────────────────────────────────────────────┐
    │                         Session Database                              │
    │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐│
    │  │ ChatSession  │ │  AgentTask   │ │  TaskStep    │ │  Message     ││
    │  │  - id        │ │  - task_uid  │ │  - step_id   │ │  - msg_id    ││
    │  │  - created   │ │  - session_id│ │  - task_uid  │ │  - session_id││
    │  │  - title     │ │  - agent     │ │  - agent     │ │  - role      ││
    │  │  - status    │ │  - status    │ │  - type      │ │  - content   ││
    │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘│
    └─────────────────────────────────────────────────────────────────────┘

存儲引擎：
-----------
- SQLite（rag-database/sessions.db）
- 線程安全連接池
- 自動表結構遷移

使用方式：
-----------
from services import session_db

# 創建/獲取會話
session = session_db.get_or_create_session(session_id, title)

# 添加訊息
session_db.add_message(session_id, "user", content)

# 創建任務
task = session_db.create_task(session_id, agent_name, task_type, description)

# 獲取會話狀態
state = session_db.get_session_state(session_id)

作者：Agentic RAG Team
版本：2.0
=============================================================================
"""

import sqlite3
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    WAITING = "waiting"  # Waiting for sub-tasks
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"


class StepType(str, Enum):
    """Types of task steps"""
    THINKING = "thinking"
    PLANNING = "planning"
    RAG_QUERY = "rag_query"
    RAG_RESULT = "rag_result"
    LLM_CALL = "llm_call"
    LLM_RESPONSE = "llm_response"
    AGENT_MESSAGE = "agent_message"
    AGENT_RESPONSE = "agent_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    INTERRUPT = "interrupt"


@dataclass
class ChatSession:
    """A chat session (conversation)"""
    session_id: str
    title: str
    created_at: str
    updated_at: str
    status: str = "active"  # active, archived, deleted
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if isinstance(d['metadata'], str):
            d['metadata'] = json.loads(d['metadata']) if d['metadata'] else {}
        return d


@dataclass
class AgentTask:
    """A task assigned to an agent within a session"""
    task_uid: str          # Unique: timestamp_sessionid_sequence
    session_id: str        # Links to ChatSession
    parent_task_uid: Optional[str]  # For sub-tasks
    sequence: int          # Order within session
    agent_name: str
    task_type: str
    description: str
    input_data: Dict[str, Any]
    status: TaskStatus
    priority: int = 1
    created_at: str = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['status'] = self.status.value if isinstance(self.status, TaskStatus) else self.status
        if isinstance(d['input_data'], str):
            d['input_data'] = json.loads(d['input_data']) if d['input_data'] else {}
        if isinstance(d['result'], str):
            d['result'] = json.loads(d['result']) if d['result'] else None
        return d


@dataclass
class TaskStep:
    """A single step in task execution"""
    step_id: str
    task_uid: str
    session_id: str
    agent_name: str
    step_type: StepType
    sequence: int
    content: Dict[str, Any]
    timestamp: str
    duration_ms: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['step_type'] = self.step_type.value if isinstance(self.step_type, StepType) else self.step_type
        if isinstance(d['content'], str):
            d['content'] = json.loads(d['content']) if d['content'] else {}
        return d


@dataclass
class ChatMessage:
    """A message in a chat session"""
    message_id: str
    session_id: str
    role: str  # user, assistant, system
    content: str
    timestamp: str
    task_uid: Optional[str] = None  # Links to the task that generated this response
    agents_involved: List[str] = None
    sources: List[Dict[str, Any]] = None
    thinking_steps: List[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        for key in ['agents_involved', 'sources', 'thinking_steps', 'metadata']:
            if isinstance(d[key], str):
                d[key] = json.loads(d[key]) if d[key] else None
        return d


class SessionDatabase:
    """
    SQLite-based session database.
    
    Thread-safe singleton pattern.
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
        self.db_path = db_path or "./rag-database/sessions.db"
        
        # Ensure directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Thread-local connections
        self._local = threading.local()
        
        # Initialize database
        self._init_db()
        
        # Task sequence counter per session
        self._sequence_counters: Dict[str, int] = {}
        
        logger.info(f"SessionDatabase initialized at {self.db_path}")
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.connection.row_factory = sqlite3.Row
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
            raise e
    
    def _init_db(self):
        """Initialize database schema"""
        with self._cursor() as cursor:
            # Chat Sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    metadata TEXT
                )
            """)
            
            # Agent Tasks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS agent_tasks (
                    task_uid TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    parent_task_uid TEXT,
                    sequence INTEGER NOT NULL,
                    agent_name TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    description TEXT,
                    input_data TEXT,
                    status TEXT NOT NULL,
                    priority INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    result TEXT,
                    error TEXT,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id),
                    FOREIGN KEY (parent_task_uid) REFERENCES agent_tasks(task_uid)
                )
            """)
            
            # Task Steps table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS task_steps (
                    step_id TEXT PRIMARY KEY,
                    task_uid TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    step_type TEXT NOT NULL,
                    sequence INTEGER NOT NULL,
                    content TEXT,
                    timestamp TEXT NOT NULL,
                    duration_ms INTEGER,
                    FOREIGN KEY (task_uid) REFERENCES agent_tasks(task_uid),
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id)
                )
            """)
            
            # Chat Messages table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS chat_messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    task_uid TEXT,
                    agents_involved TEXT,
                    sources TEXT,
                    thinking_steps TEXT,
                    metadata TEXT,
                    FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id),
                    FOREIGN KEY (task_uid) REFERENCES agent_tasks(task_uid)
                )
            """)
            
            # Indexes for fast lookups
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_session ON agent_tasks(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON agent_tasks(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_steps_task ON task_steps(task_uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_steps_session ON task_steps(session_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_session ON chat_messages(session_id)")
        
        logger.info("Database schema initialized")
    
    # ============== Session Operations ==============
    
    def create_session(self, session_id: str, title: str = "New Chat") -> ChatSession:
        """Create a new chat session"""
        now = datetime.now().isoformat()
        session = ChatSession(
            session_id=session_id,
            title=title,
            created_at=now,
            updated_at=now,
            status="active",
            metadata={}
        )
        
        with self._cursor() as cursor:
            cursor.execute("""
                INSERT INTO chat_sessions (session_id, title, created_at, updated_at, status, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (session.session_id, session.title, session.created_at, session.updated_at, 
                  session.status, json.dumps(session.metadata)))
        
        # Initialize sequence counter
        self._sequence_counters[session_id] = 0
        
        logger.info(f"Created session: {session_id}")
        return session
    
    def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a session by ID"""
        with self._cursor() as cursor:
            cursor.execute("SELECT * FROM chat_sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            
            if row:
                return ChatSession(
                    session_id=row['session_id'],
                    title=row['title'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    status=row['status'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                )
        return None
    
    def get_or_create_session(self, session_id: str, title: str = "New Chat") -> ChatSession:
        """Get existing session or create new one"""
        session = self.get_session(session_id)
        if session:
            return session
        return self.create_session(session_id, title)
    
    def list_sessions(self, status: str = None, limit: int = 50) -> List[ChatSession]:
        """List all sessions"""
        with self._cursor() as cursor:
            if status:
                cursor.execute(
                    "SELECT * FROM chat_sessions WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                    (status, limit)
                )
            else:
                cursor.execute(
                    "SELECT * FROM chat_sessions ORDER BY updated_at DESC LIMIT ?",
                    (limit,)
                )
            
            return [
                ChatSession(
                    session_id=row['session_id'],
                    title=row['title'],
                    created_at=row['created_at'],
                    updated_at=row['updated_at'],
                    status=row['status'],
                    metadata=json.loads(row['metadata']) if row['metadata'] else {}
                )
                for row in cursor.fetchall()
            ]
    
    def update_session(self, session_id: str, **kwargs):
        """Update session fields"""
        allowed_fields = {'title', 'status', 'metadata'}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        
        if not updates:
            return
        
        updates['updated_at'] = datetime.now().isoformat()
        
        if 'metadata' in updates:
            updates['metadata'] = json.dumps(updates['metadata'])
        
        set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
        values = list(updates.values()) + [session_id]
        
        with self._cursor() as cursor:
            cursor.execute(f"UPDATE chat_sessions SET {set_clause} WHERE session_id = ?", values)
    
    # ============== Task Operations ==============
    
    def generate_task_uid(self, session_id: str) -> str:
        """Generate unique task UID: timestamp_sessionid_sequence"""
        if session_id not in self._sequence_counters:
            # Load max sequence from DB
            with self._cursor() as cursor:
                cursor.execute(
                    "SELECT MAX(sequence) FROM agent_tasks WHERE session_id = ?",
                    (session_id,)
                )
                row = cursor.fetchone()
                self._sequence_counters[session_id] = (row[0] or 0)
        
        self._sequence_counters[session_id] += 1
        seq = self._sequence_counters[session_id]
        timestamp = int(datetime.now().timestamp() * 1000)
        
        # Format: timestamp_shortSessionId_sequence
        short_session = session_id[-8:] if len(session_id) > 8 else session_id
        return f"{timestamp}_{short_session}_{seq:04d}"
    
    def create_task(
        self,
        session_id: str,
        agent_name: str,
        task_type: str,
        description: str,
        input_data: Dict[str, Any],
        parent_task_uid: str = None,
        priority: int = 1
    ) -> AgentTask:
        """Create a new agent task"""
        task_uid = self.generate_task_uid(session_id)
        now = datetime.now().isoformat()
        
        task = AgentTask(
            task_uid=task_uid,
            session_id=session_id,
            parent_task_uid=parent_task_uid,
            sequence=self._sequence_counters[session_id],
            agent_name=agent_name,
            task_type=task_type,
            description=description,
            input_data=input_data,
            status=TaskStatus.PENDING,
            priority=priority,
            created_at=now
        )
        
        with self._cursor() as cursor:
            cursor.execute("""
                INSERT INTO agent_tasks 
                (task_uid, session_id, parent_task_uid, sequence, agent_name, task_type,
                 description, input_data, status, priority, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_uid, task.session_id, task.parent_task_uid, task.sequence,
                task.agent_name, task.task_type, task.description,
                json.dumps(task.input_data), task.status.value, task.priority, task.created_at
            ))
        
        logger.info(f"Created task: {task_uid} for session {session_id}")
        return task
    
    def get_task(self, task_uid: str) -> Optional[AgentTask]:
        """Get a task by UID"""
        with self._cursor() as cursor:
            cursor.execute("SELECT * FROM agent_tasks WHERE task_uid = ?", (task_uid,))
            row = cursor.fetchone()
            
            if row:
                return AgentTask(
                    task_uid=row['task_uid'],
                    session_id=row['session_id'],
                    parent_task_uid=row['parent_task_uid'],
                    sequence=row['sequence'],
                    agent_name=row['agent_name'],
                    task_type=row['task_type'],
                    description=row['description'],
                    input_data=json.loads(row['input_data']) if row['input_data'] else {},
                    status=TaskStatus(row['status']),
                    priority=row['priority'],
                    created_at=row['created_at'],
                    started_at=row['started_at'],
                    completed_at=row['completed_at'],
                    result=json.loads(row['result']) if row['result'] else None,
                    error=row['error']
                )
        return None
    
    def update_task_status(
        self,
        task_uid: str,
        status: TaskStatus,
        result: Dict[str, Any] = None,
        error: str = None
    ):
        """Update task status"""
        now = datetime.now().isoformat()
        
        with self._cursor() as cursor:
            if status == TaskStatus.RUNNING:
                cursor.execute(
                    "UPDATE agent_tasks SET status = ?, started_at = ? WHERE task_uid = ?",
                    (status.value, now, task_uid)
                )
            elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED, TaskStatus.INTERRUPTED]:
                cursor.execute(
                    "UPDATE agent_tasks SET status = ?, completed_at = ?, result = ?, error = ? WHERE task_uid = ?",
                    (status.value, now, json.dumps(result) if result else None, error, task_uid)
                )
            else:
                cursor.execute(
                    "UPDATE agent_tasks SET status = ? WHERE task_uid = ?",
                    (status.value, task_uid)
                )
        
        logger.debug(f"Updated task {task_uid} status to {status.value}")
    
    def get_session_tasks(
        self,
        session_id: str,
        status: TaskStatus = None,
        include_steps: bool = False
    ) -> List[Dict[str, Any]]:
        """Get all tasks for a session"""
        with self._cursor() as cursor:
            if status:
                cursor.execute(
                    "SELECT * FROM agent_tasks WHERE session_id = ? AND status = ? ORDER BY sequence",
                    (session_id, status.value)
                )
            else:
                cursor.execute(
                    "SELECT * FROM agent_tasks WHERE session_id = ? ORDER BY sequence",
                    (session_id,)
                )
            
            tasks = []
            for row in cursor.fetchall():
                task = AgentTask(
                    task_uid=row['task_uid'],
                    session_id=row['session_id'],
                    parent_task_uid=row['parent_task_uid'],
                    sequence=row['sequence'],
                    agent_name=row['agent_name'],
                    task_type=row['task_type'],
                    description=row['description'],
                    input_data=json.loads(row['input_data']) if row['input_data'] else {},
                    status=TaskStatus(row['status']),
                    priority=row['priority'],
                    created_at=row['created_at'],
                    started_at=row['started_at'],
                    completed_at=row['completed_at'],
                    result=json.loads(row['result']) if row['result'] else None,
                    error=row['error']
                )
                task_dict = task.to_dict()
                
                if include_steps:
                    task_dict['steps'] = self.get_task_steps(row['task_uid'])
                
                tasks.append(task_dict)
            
            return tasks
    
    def get_running_tasks(self, session_id: str = None) -> List[Dict[str, Any]]:
        """Get all running tasks, optionally filtered by session"""
        with self._cursor() as cursor:
            if session_id:
                cursor.execute(
                    "SELECT * FROM agent_tasks WHERE session_id = ? AND status IN (?, ?, ?) ORDER BY sequence",
                    (session_id, TaskStatus.PENDING.value, TaskStatus.RUNNING.value, TaskStatus.ASSIGNED.value)
                )
            else:
                cursor.execute(
                    "SELECT * FROM agent_tasks WHERE status IN (?, ?, ?) ORDER BY created_at DESC",
                    (TaskStatus.PENDING.value, TaskStatus.RUNNING.value, TaskStatus.ASSIGNED.value)
                )
            
            return [self._row_to_task(row).to_dict() for row in cursor.fetchall()]
    
    def _row_to_task(self, row) -> AgentTask:
        """Convert DB row to AgentTask"""
        return AgentTask(
            task_uid=row['task_uid'],
            session_id=row['session_id'],
            parent_task_uid=row['parent_task_uid'],
            sequence=row['sequence'],
            agent_name=row['agent_name'],
            task_type=row['task_type'],
            description=row['description'],
            input_data=json.loads(row['input_data']) if row['input_data'] else {},
            status=TaskStatus(row['status']),
            priority=row['priority'],
            created_at=row['created_at'],
            started_at=row['started_at'],
            completed_at=row['completed_at'],
            result=json.loads(row['result']) if row['result'] else None,
            error=row['error']
        )
    
    # ============== Step Operations ==============
    
    def add_step(
        self,
        task_uid: str,
        session_id: str,
        agent_name: str,
        step_type: StepType,
        content: Dict[str, Any],
        duration_ms: int = None
    ) -> TaskStep:
        """Add a step to a task"""
        # Get next sequence for this task
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT MAX(sequence) FROM task_steps WHERE task_uid = ?",
                (task_uid,)
            )
            row = cursor.fetchone()
            sequence = (row[0] or 0) + 1
        
        step_id = f"{task_uid}_step{sequence:03d}"
        now = datetime.now().isoformat()
        
        step = TaskStep(
            step_id=step_id,
            task_uid=task_uid,
            session_id=session_id,
            agent_name=agent_name,
            step_type=step_type,
            sequence=sequence,
            content=content,
            timestamp=now,
            duration_ms=duration_ms
        )
        
        with self._cursor() as cursor:
            cursor.execute("""
                INSERT INTO task_steps
                (step_id, task_uid, session_id, agent_name, step_type, sequence, content, timestamp, duration_ms)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                step.step_id, step.task_uid, step.session_id, step.agent_name,
                step.step_type.value, step.sequence, json.dumps(step.content),
                step.timestamp, step.duration_ms
            ))
        
        return step
    
    def get_task_steps(self, task_uid: str) -> List[Dict[str, Any]]:
        """Get all steps for a task"""
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT * FROM task_steps WHERE task_uid = ? ORDER BY sequence",
                (task_uid,)
            )
            
            return [
                TaskStep(
                    step_id=row['step_id'],
                    task_uid=row['task_uid'],
                    session_id=row['session_id'],
                    agent_name=row['agent_name'],
                    step_type=StepType(row['step_type']),
                    sequence=row['sequence'],
                    content=json.loads(row['content']) if row['content'] else {},
                    timestamp=row['timestamp'],
                    duration_ms=row['duration_ms']
                ).to_dict()
                for row in cursor.fetchall()
            ]
    
    def get_session_steps(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all steps for a session"""
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT * FROM task_steps WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit)
            )
            
            return [
                TaskStep(
                    step_id=row['step_id'],
                    task_uid=row['task_uid'],
                    session_id=row['session_id'],
                    agent_name=row['agent_name'],
                    step_type=StepType(row['step_type']),
                    sequence=row['sequence'],
                    content=json.loads(row['content']) if row['content'] else {},
                    timestamp=row['timestamp'],
                    duration_ms=row['duration_ms']
                ).to_dict()
                for row in cursor.fetchall()
            ]
    
    # ============== Message Operations ==============
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        task_uid: str = None,
        agents_involved: List[str] = None,
        sources: List[Dict[str, Any]] = None,
        thinking_steps: List[Dict[str, Any]] = None,
        metadata: Dict[str, Any] = None
    ) -> ChatMessage:
        """Add a message to a session"""
        message_id = f"{session_id}_msg_{int(datetime.now().timestamp() * 1000)}"
        now = datetime.now().isoformat()
        
        message = ChatMessage(
            message_id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            timestamp=now,
            task_uid=task_uid,
            agents_involved=agents_involved,
            sources=sources,
            thinking_steps=thinking_steps,
            metadata=metadata
        )
        
        with self._cursor() as cursor:
            cursor.execute("""
                INSERT INTO chat_messages
                (message_id, session_id, role, content, timestamp, task_uid, 
                 agents_involved, sources, thinking_steps, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message.message_id, message.session_id, message.role, message.content,
                message.timestamp, message.task_uid,
                json.dumps(message.agents_involved) if message.agents_involved else None,
                json.dumps(message.sources) if message.sources else None,
                json.dumps(message.thinking_steps) if message.thinking_steps else None,
                json.dumps(message.metadata) if message.metadata else None
            ))
        
        # Update session timestamp
        self.update_session(session_id)
        
        return message
    
    def get_session_messages(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get all messages for a session"""
        with self._cursor() as cursor:
            cursor.execute(
                "SELECT * FROM chat_messages WHERE session_id = ? ORDER BY timestamp LIMIT ?",
                (session_id, limit)
            )
            
            return [
                ChatMessage(
                    message_id=row['message_id'],
                    session_id=row['session_id'],
                    role=row['role'],
                    content=row['content'],
                    timestamp=row['timestamp'],
                    task_uid=row['task_uid'],
                    agents_involved=json.loads(row['agents_involved']) if row['agents_involved'] else None,
                    sources=json.loads(row['sources']) if row['sources'] else None,
                    thinking_steps=json.loads(row['thinking_steps']) if row['thinking_steps'] else None,
                    metadata=json.loads(row['metadata']) if row['metadata'] else None
                ).to_dict()
                for row in cursor.fetchall()
            ]
    
    # ============== Session State Recovery ==============
    
    def get_session_state(self, session_id: str) -> Dict[str, Any]:
        """
        Get complete session state for recovery.
        
        Returns everything needed to restore a session:
        - Session metadata
        - All messages
        - All tasks with their status
        - All steps (for thinking visualization)
        - Summary statistics
        """
        session = self.get_session(session_id)
        if not session:
            return None
        
        messages = self.get_session_messages(session_id)
        tasks = self.get_session_tasks(session_id, include_steps=True)
        
        # Calculate statistics
        task_stats = {
            "total": len(tasks),
            "pending": sum(1 for t in tasks if t['status'] == 'pending'),
            "running": sum(1 for t in tasks if t['status'] in ['running', 'assigned']),
            "completed": sum(1 for t in tasks if t['status'] == 'completed'),
            "failed": sum(1 for t in tasks if t['status'] == 'failed'),
        }
        
        # Get agents involved
        agents_involved = list(set(t['agent_name'] for t in tasks))
        
        # Get running tasks for status display
        running_tasks = [t for t in tasks if t['status'] in ['pending', 'running', 'assigned']]
        
        return {
            "session": session.to_dict(),
            "messages": messages,
            "tasks": tasks,
            "running_tasks": running_tasks,
            "task_stats": task_stats,
            "agents_involved": agents_involved,
            "is_processing": task_stats['running'] > 0 or task_stats['pending'] > 0
        }
    
    # ============== Cleanup ==============
    
    def delete_session(self, session_id: str, hard_delete: bool = False):
        """Delete or archive a session"""
        if hard_delete:
            with self._cursor() as cursor:
                cursor.execute("DELETE FROM task_steps WHERE session_id = ?", (session_id,))
                cursor.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
                cursor.execute("DELETE FROM agent_tasks WHERE session_id = ?", (session_id,))
                cursor.execute("DELETE FROM chat_sessions WHERE session_id = ?", (session_id,))
        else:
            self.update_session(session_id, status="deleted")
        
        # Clear sequence counter
        if session_id in self._sequence_counters:
            del self._sequence_counters[session_id]


# Global singleton instance
session_db = SessionDatabase()
