# -*- coding: utf-8 -*-
"""
=============================================================================
Entity Memory - 實體記憶系統
=============================================================================

參考 Microsoft AI Agents 課程設計，實現實體記憶：
- 從對話中提取實體（人、地點、概念）
- 追蹤實體間的關係
- 支持結構化查詢

核心概念（來自 MSFT 第13課）：
"Entity Memory involves extracting and remembering specific entities 
(like people, places, or things) and events from conversations."

=============================================================================
"""

import json
import logging
import hashlib
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import sqlite3
from contextlib import contextmanager
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


class EntityType(str, Enum):
    """Types of entities"""
    PERSON = "person"
    ORGANIZATION = "organization"
    LOCATION = "location"
    CONCEPT = "concept"
    TOOL = "tool"
    PROJECT = "project"
    DOCUMENT = "document"
    DATE = "date"
    CUSTOM = "custom"


class RelationType(str, Enum):
    """Types of relationships between entities"""
    WORKS_AT = "works_at"
    LOCATED_IN = "located_in"
    RELATED_TO = "related_to"
    PART_OF = "part_of"
    CREATED_BY = "created_by"
    USES = "uses"
    KNOWS = "knows"
    INTERESTED_IN = "interested_in"
    MENTIONED_WITH = "mentioned_with"


@dataclass
class Entity:
    """An entity extracted from conversation"""
    id: str
    name: str
    entity_type: EntityType
    
    # Attributes
    aliases: List[str] = field(default_factory=list)  # Alternative names
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    # Context
    user_id: Optional[str] = None
    first_mentioned: str = None
    last_mentioned: str = None
    mention_count: int = 1
    
    # Source
    source_sessions: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        if self.first_mentioned is None:
            self.first_mentioned = datetime.now().isoformat()
        if self.last_mentioned is None:
            self.last_mentioned = self.first_mentioned
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['entity_type'] = self.entity_type.value if isinstance(self.entity_type, EntityType) else self.entity_type
        return d
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Entity':
        data['entity_type'] = EntityType(data['entity_type'])
        return cls(**data)


@dataclass
class EntityRelation:
    """A relationship between two entities"""
    id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: RelationType
    
    # Metadata
    confidence: float = 0.8
    context: Optional[str] = None  # Context where relation was found
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d['relation_type'] = self.relation_type.value if isinstance(self.relation_type, RelationType) else self.relation_type
        return d


class EntityMemoryStore:
    """
    Entity Memory Storage and Retrieval.
    
    Features:
    - Entity extraction and storage
    - Relationship tracking
    - Graph-based queries
    - Entity merging (deduplication)
    """
    
    def __init__(self, db_path: str = "data/entity_memory.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._init_db()
        logger.info(f"EntityMemoryStore initialized at {db_path}")
    
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
            
            # Entities table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS entities (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    aliases TEXT,
                    attributes TEXT,
                    user_id TEXT,
                    first_mentioned TEXT,
                    last_mentioned TEXT,
                    mention_count INTEGER DEFAULT 1,
                    source_sessions TEXT
                )
            """)
            
            # Relations table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS relations (
                    id TEXT PRIMARY KEY,
                    source_entity_id TEXT NOT NULL,
                    target_entity_id TEXT NOT NULL,
                    relation_type TEXT NOT NULL,
                    confidence REAL DEFAULT 0.8,
                    context TEXT,
                    created_at TEXT,
                    FOREIGN KEY (source_entity_id) REFERENCES entities(id),
                    FOREIGN KEY (target_entity_id) REFERENCES entities(id)
                )
            """)
            
            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_entities_name 
                ON entities(name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_entities_type 
                ON entities(entity_type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_entities_user 
                ON entities(user_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_relations_source 
                ON relations(source_entity_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_relations_target 
                ON relations(target_entity_id)
            """)
            
            conn.commit()
    
    def _generate_entity_id(self, name: str, entity_type: EntityType, user_id: Optional[str] = None) -> str:
        """Generate deterministic entity ID"""
        key = f"{entity_type.value}:{name.lower()}:{user_id or 'global'}"
        return hashlib.md5(key.encode()).hexdigest()[:16]
    
    def store_entity(self, entity: Entity) -> str:
        """Store or update an entity"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if entity exists
            cursor.execute("SELECT * FROM entities WHERE id = ?", (entity.id,))
            existing = cursor.fetchone()
            
            if existing:
                # Update existing entity
                cursor.execute("""
                    UPDATE entities SET
                        last_mentioned = ?,
                        mention_count = mention_count + 1,
                        aliases = ?,
                        attributes = ?,
                        source_sessions = ?
                    WHERE id = ?
                """, (
                    datetime.now().isoformat(),
                    json.dumps(entity.aliases),
                    json.dumps(entity.attributes),
                    json.dumps(entity.source_sessions),
                    entity.id
                ))
            else:
                # Insert new entity
                cursor.execute("""
                    INSERT INTO entities (
                        id, name, entity_type, aliases, attributes,
                        user_id, first_mentioned, last_mentioned,
                        mention_count, source_sessions
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entity.id,
                    entity.name,
                    entity.entity_type.value,
                    json.dumps(entity.aliases),
                    json.dumps(entity.attributes),
                    entity.user_id,
                    entity.first_mentioned,
                    entity.last_mentioned,
                    entity.mention_count,
                    json.dumps(entity.source_sessions)
                ))
            
            conn.commit()
            return entity.id
    
    def store_relation(self, relation: EntityRelation) -> str:
        """Store a relationship between entities"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Check for existing relation
            cursor.execute("""
                SELECT id FROM relations
                WHERE source_entity_id = ? AND target_entity_id = ? AND relation_type = ?
            """, (relation.source_entity_id, relation.target_entity_id, relation.relation_type.value))
            
            existing = cursor.fetchone()
            if existing:
                # Update confidence
                cursor.execute("""
                    UPDATE relations SET confidence = ? WHERE id = ?
                """, (relation.confidence, existing['id']))
            else:
                cursor.execute("""
                    INSERT INTO relations (
                        id, source_entity_id, target_entity_id,
                        relation_type, confidence, context, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    relation.id,
                    relation.source_entity_id,
                    relation.target_entity_id,
                    relation.relation_type.value,
                    relation.confidence,
                    relation.context,
                    relation.created_at
                ))
            
            conn.commit()
            return relation.id
    
    def find_entity(self, name: str, entity_type: Optional[EntityType] = None) -> Optional[Entity]:
        """Find entity by name"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if entity_type:
                cursor.execute("""
                    SELECT * FROM entities
                    WHERE (name = ? OR aliases LIKE ?) AND entity_type = ?
                """, (name, f'%"{name}"%', entity_type.value))
            else:
                cursor.execute("""
                    SELECT * FROM entities
                    WHERE name = ? OR aliases LIKE ?
                """, (name, f'%"{name}"%'))
            
            row = cursor.fetchone()
            if row:
                return self._row_to_entity(row)
            return None
    
    def get_entity(self, entity_id: str) -> Optional[Entity]:
        """Get entity by ID"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM entities WHERE id = ?", (entity_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_entity(row)
            return None
    
    def get_related_entities(
        self,
        entity_id: str,
        relation_type: Optional[RelationType] = None
    ) -> List[Tuple[Entity, RelationType, float]]:
        """Get all entities related to given entity"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get outgoing relations
            if relation_type:
                cursor.execute("""
                    SELECT e.*, r.relation_type, r.confidence
                    FROM entities e
                    JOIN relations r ON e.id = r.target_entity_id
                    WHERE r.source_entity_id = ? AND r.relation_type = ?
                """, (entity_id, relation_type.value))
            else:
                cursor.execute("""
                    SELECT e.*, r.relation_type, r.confidence
                    FROM entities e
                    JOIN relations r ON e.id = r.target_entity_id
                    WHERE r.source_entity_id = ?
                """, (entity_id,))
            
            results = []
            for row in cursor.fetchall():
                entity = self._row_to_entity(row)
                rel_type = RelationType(row['relation_type'])
                confidence = row['confidence']
                results.append((entity, rel_type, confidence))
            
            return results
    
    def get_user_entities(
        self,
        user_id: str,
        entity_type: Optional[EntityType] = None,
        limit: int = 50
    ) -> List[Entity]:
        """Get all entities for a user"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            if entity_type:
                cursor.execute("""
                    SELECT * FROM entities
                    WHERE user_id = ? AND entity_type = ?
                    ORDER BY last_mentioned DESC
                    LIMIT ?
                """, (user_id, entity_type.value, limit))
            else:
                cursor.execute("""
                    SELECT * FROM entities
                    WHERE user_id = ?
                    ORDER BY last_mentioned DESC
                    LIMIT ?
                """, (user_id, limit))
            
            return [self._row_to_entity(row) for row in cursor.fetchall()]
    
    def search_entities(
        self,
        query: str,
        entity_type: Optional[EntityType] = None,
        limit: int = 10
    ) -> List[Entity]:
        """Search entities by name/attributes"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            search_pattern = f"%{query}%"
            
            if entity_type:
                cursor.execute("""
                    SELECT * FROM entities
                    WHERE (name LIKE ? OR aliases LIKE ? OR attributes LIKE ?)
                    AND entity_type = ?
                    ORDER BY mention_count DESC
                    LIMIT ?
                """, (search_pattern, search_pattern, search_pattern, entity_type.value, limit))
            else:
                cursor.execute("""
                    SELECT * FROM entities
                    WHERE name LIKE ? OR aliases LIKE ? OR attributes LIKE ?
                    ORDER BY mention_count DESC
                    LIMIT ?
                """, (search_pattern, search_pattern, search_pattern, limit))
            
            return [self._row_to_entity(row) for row in cursor.fetchall()]
    
    def _row_to_entity(self, row) -> Entity:
        """Convert database row to Entity"""
        return Entity(
            id=row['id'],
            name=row['name'],
            entity_type=EntityType(row['entity_type']),
            aliases=json.loads(row['aliases'] or '[]'),
            attributes=json.loads(row['attributes'] or '{}'),
            user_id=row['user_id'],
            first_mentioned=row['first_mentioned'],
            last_mentioned=row['last_mentioned'],
            mention_count=row['mention_count'],
            source_sessions=json.loads(row['source_sessions'] or '[]')
        )
    
    def to_context_string(self, user_id: str, limit: int = 10) -> str:
        """Generate context string from user's entities"""
        entities = self.get_user_entities(user_id, limit=limit)
        
        if not entities:
            return ""
        
        lines = ["## Known Entities:"]
        for entity in entities:
            line = f"- {entity.name} ({entity.entity_type.value})"
            if entity.attributes:
                attrs = ", ".join([f"{k}={v}" for k, v in list(entity.attributes.items())[:3]])
                line += f": {attrs}"
            lines.append(line)
        
        return "\n".join(lines)


# Singleton instance
_entity_store: Optional[EntityMemoryStore] = None


def get_entity_store() -> EntityMemoryStore:
    """Get the singleton entity memory store"""
    global _entity_store
    if _entity_store is None:
        _entity_store = EntityMemoryStore()
    return _entity_store
