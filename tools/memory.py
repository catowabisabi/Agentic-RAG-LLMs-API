from typing import List, Dict, Any, Optional
from collections import deque
import json
import os
from datetime import datetime


class ConversationMemory:
    """Manages conversation history and context"""
    
    def __init__(self, window_size: int = 5, persist_path: Optional[str] = None):
        self.window_size = window_size
        self.persist_path = persist_path or "./conversation_memory.json"
        self.exchanges = deque(maxlen=window_size)
        self.long_term_memory = []
        self._load_memory()
    
    def add_exchange(self, human_input: str, assistant_response: str, metadata: Optional[Dict] = None):
        """Add a new conversation exchange"""
        exchange = {
            "timestamp": datetime.now().isoformat(),
            "human": human_input,
            "assistant": assistant_response,
            "metadata": metadata or {}
        }
        
        self.exchanges.append(exchange)
        self._save_memory()
    
    def get_recent_history(self, num_exchanges: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get recent conversation history"""
        if num_exchanges is None:
            num_exchanges = self.window_size
        
        return list(self.exchanges)[-num_exchanges:]
    
    def get_context_summary(self) -> str:
        """Generate a summary of recent context"""
        recent_exchanges = self.get_recent_history(3)
        
        if not recent_exchanges:
            return ""
        
        context_parts = []
        for exchange in recent_exchanges:
            context_parts.append(f"Human: {exchange['human']}")
            context_parts.append(f"Assistant: {exchange['assistant'][:200]}...")
        
        return "\n".join(context_parts)
    
    def search_memory(self, query: str, threshold: float = 0.5) -> List[Dict[str, Any]]:
        """Search through conversation history"""
        query_lower = query.lower()
        matches = []
        
        # Search recent exchanges
        for exchange in self.exchanges:
            relevance = 0.0
            
            # Simple keyword matching
            human_text = exchange["human"].lower()
            assistant_text = exchange["assistant"].lower()
            
            if query_lower in human_text:
                relevance += 0.8
            if query_lower in assistant_text:
                relevance += 0.6
            
            # Check for word overlap
            query_words = set(query_lower.split())
            human_words = set(human_text.split())
            assistant_words = set(assistant_text.split())
            
            human_overlap = len(query_words.intersection(human_words)) / len(query_words)
            assistant_overlap = len(query_words.intersection(assistant_words)) / len(query_words)
            
            relevance += (human_overlap + assistant_overlap) * 0.3
            
            if relevance >= threshold:
                matches.append({
                    "exchange": exchange,
                    "relevance": relevance
                })
        
        # Sort by relevance
        matches.sort(key=lambda x: x["relevance"], reverse=True)
        return matches
    
    def clear_memory(self):
        """Clear all conversation memory"""
        self.exchanges.clear()
        self.long_term_memory.clear()
        self._save_memory()
    
    def _save_memory(self):
        """Save memory to disk"""
        try:
            memory_data = {
                "exchanges": list(self.exchanges),
                "long_term_memory": self.long_term_memory,
                "window_size": self.window_size
            }
            
            with open(self.persist_path, 'w', encoding='utf-8') as f:
                json.dump(memory_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Error saving memory: {e}")
    
    def _load_memory(self):
        """Load memory from disk"""
        try:
            if os.path.exists(self.persist_path):
                with open(self.persist_path, 'r', encoding='utf-8') as f:
                    memory_data = json.load(f)
                
                # Restore exchanges with proper deque size
                exchanges_data = memory_data.get("exchanges", [])
                self.exchanges = deque(exchanges_data, maxlen=self.window_size)
                self.long_term_memory = memory_data.get("long_term_memory", [])
        except Exception as e:
            print(f"Error loading memory: {e}")


class SemanticMemory:
    """Advanced memory system with semantic understanding"""
    
    def __init__(self, embeddings_model=None):
        self.base_memory = ConversationMemory()
        self.embeddings_model = embeddings_model
        self.semantic_store = {}
    
    def add_semantic_exchange(self, human_input: str, assistant_response: str, 
                            concepts: List[str] = None, metadata: Dict = None):
        """Add exchange with semantic concepts"""
        # Add to base memory
        self.base_memory.add_exchange(human_input, assistant_response, metadata)
        
        # Extract and store semantic concepts
        if concepts:
            for concept in concepts:
                if concept not in self.semantic_store:
                    self.semantic_store[concept] = []
                
                self.semantic_store[concept].append({
                    "human": human_input,
                    "assistant": assistant_response,
                    "timestamp": datetime.now().isoformat()
                })
    
    def retrieve_by_concept(self, concept: str) -> List[Dict[str, Any]]:
        """Retrieve exchanges related to a specific concept"""
        return self.semantic_store.get(concept, [])
    
    def get_related_concepts(self, query: str) -> List[str]:
        """Find concepts related to a query"""
        query_lower = query.lower()
        related = []
        
        for concept in self.semantic_store.keys():
            if query_lower in concept.lower() or concept.lower() in query_lower:
                related.append(concept)
        
        return related


class MemoryManager:
    """High-level memory management interface"""
    
    def __init__(self, window_size: int = 5, use_semantic: bool = False):
        if use_semantic:
            self.memory = SemanticMemory()
        else:
            self.memory = ConversationMemory(window_size=window_size)
    
    def add_exchange(self, human_input: str, assistant_response: str, **kwargs):
        """Add a conversation exchange"""
        if hasattr(self.memory, 'add_semantic_exchange'):
            self.memory.add_semantic_exchange(human_input, assistant_response, **kwargs)
        else:
            self.memory.add_exchange(human_input, assistant_response, kwargs.get('metadata'))
    
    def get_context_for_query(self, query: str) -> Dict[str, Any]:
        """Get relevant context for a query"""
        context = {
            "recent_history": self.memory.base_memory.get_recent_history() if hasattr(self.memory, 'base_memory') else self.memory.get_recent_history(),
            "context_summary": self.memory.base_memory.get_context_summary() if hasattr(self.memory, 'base_memory') else self.memory.get_context_summary(),
        }
        
        # Add semantic context if available
        if hasattr(self.memory, 'get_related_concepts'):
            context["related_concepts"] = self.memory.get_related_concepts(query)
        
        return context
    
    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search memory for relevant exchanges"""
        if hasattr(self.memory, 'base_memory'):
            return self.memory.base_memory.search_memory(query)
        else:
            return self.memory.search_memory(query)