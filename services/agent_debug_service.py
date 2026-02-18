# -*- coding: utf-8 -*-
"""
=============================================================================
Agent Debug Service - Agent 互動追蹤和除錯服務
=============================================================================

功能說明：
-----------
記錄 Agent 之間的所有訊息傳遞、LLM 請求/回應、路由決策，
方便除錯和理解系統行為。

核心功能：
-----------
1. 記錄每次 Agent 的輸入/輸出
2. 記錄 LLM 請求和回應
3. 記錄路由決策
4. 提供查詢 API
5. 按 session/task 分組查看

=============================================================================
"""

import logging
import threading
from typing import Dict, Any, List, Optional
from datetime import datetime
from collections import deque
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)


@dataclass
class DebugTrace:
    """A single debug trace entry"""
    id: str
    timestamp: str
    session_id: str
    task_id: str
    trace_type: str  # agent_input, agent_output, llm_request, llm_response, routing, thinking, error
    agent_name: str
    source: str  # Who initiated this
    target: str  # Who receives this
    content: Dict[str, Any] = field(default_factory=dict)
    duration_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class AgentDebugService:
    """
    Singleton service for capturing and querying agent debug traces.
    Uses in-memory ring buffer (max 2000 entries) for performance.
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._traces: deque = deque(maxlen=2000)
        self._counter = 0
        self._trace_lock = threading.Lock()
        logger.info("AgentDebugService initialized (max 2000 traces)")
    
    def _next_id(self) -> str:
        with self._trace_lock:
            self._counter += 1
            return f"trace_{self._counter}"
    
    def record(
        self,
        trace_type: str,
        agent_name: str,
        session_id: str = "",
        task_id: str = "",
        source: str = "",
        target: str = "",
        content: Dict[str, Any] = None,
        duration_ms: float = None,
        metadata: Dict[str, Any] = None
    ) -> DebugTrace:
        """Record a debug trace"""
        trace = DebugTrace(
            id=self._next_id(),
            timestamp=datetime.now().isoformat(),
            session_id=session_id,
            task_id=task_id,
            trace_type=trace_type,
            agent_name=agent_name,
            source=source or agent_name,
            target=target,
            content=content or {},
            duration_ms=duration_ms,
            metadata=metadata or {}
        )
        self._traces.append(trace)
        return trace
    
    # Convenience methods
    def record_agent_input(self, agent_name: str, task_id: str, input_data: Dict, session_id: str = "", source: str = ""):
        """Record what was sent TO an agent"""
        return self.record(
            trace_type="agent_input",
            agent_name=agent_name,
            session_id=session_id,
            task_id=task_id,
            source=source or "manager_agent",
            target=agent_name,
            content={"input": _truncate_content(input_data)}
        )
    
    def record_agent_output(self, agent_name: str, task_id: str, output_data: Any, session_id: str = "", duration_ms: float = None):
        """Record what an agent returned"""
        return self.record(
            trace_type="agent_output",
            agent_name=agent_name,
            session_id=session_id,
            task_id=task_id,
            source=agent_name,
            target="manager_agent",
            content={"output": _truncate_content(output_data)},
            duration_ms=duration_ms
        )
    
    def record_llm_request(self, agent_name: str, task_id: str, prompt: str, session_id: str = "", model: str = ""):
        """Record an LLM request"""
        return self.record(
            trace_type="llm_request",
            agent_name=agent_name,
            session_id=session_id,
            task_id=task_id,
            source=agent_name,
            target="llm",
            content={"prompt": prompt[:2000] if prompt else ""},
            metadata={"model": model}
        )
    
    def record_llm_response(self, agent_name: str, task_id: str, response: str, session_id: str = "", duration_ms: float = None, model: str = ""):
        """Record an LLM response"""
        return self.record(
            trace_type="llm_response",
            agent_name=agent_name,
            session_id=session_id,
            task_id=task_id,
            source="llm",
            target=agent_name,
            content={"response": response[:2000] if response else ""},
            duration_ms=duration_ms,
            metadata={"model": model}
        )
    
    def record_routing(self, task_id: str, classification: Dict, session_id: str = ""):
        """Record a routing decision"""
        return self.record(
            trace_type="routing",
            agent_name="manager_agent",
            session_id=session_id,
            task_id=task_id,
            source="manager_agent",
            target=classification.get("target_agent", classification.get("query_type", "")),
            content={"classification": _truncate_content(classification)}
        )
    
    def record_thinking(self, agent_name: str, task_id: str, thought: str, session_id: str = ""):
        """Record a thinking step"""
        return self.record(
            trace_type="thinking",
            agent_name=agent_name,
            session_id=session_id,
            task_id=task_id,
            source=agent_name,
            target="",
            content={"thought": thought[:1000] if thought else ""}
        )
    
    def record_error(self, agent_name: str, task_id: str, error: str, session_id: str = ""):
        """Record an error"""
        return self.record(
            trace_type="error",
            agent_name=agent_name,
            session_id=session_id,
            task_id=task_id,
            source=agent_name,
            target="",
            content={"error": str(error)[:1000]}
        )
    
    def record_memory_injection(self, agent_name: str, task_id: str, memory_context: str, session_id: str = ""):
        """Record memory context injection"""
        return self.record(
            trace_type="memory_injection",
            agent_name=agent_name,
            session_id=session_id,
            task_id=task_id,
            source="cerebro_memory",
            target=agent_name,
            content={"memory_context": memory_context[:2000] if memory_context else ""}
        )
    
    # Query methods
    def get_traces(
        self,
        session_id: str = None,
        task_id: str = None,
        agent_name: str = None,
        trace_type: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Query traces with filters"""
        results = []
        for trace in reversed(self._traces):
            if session_id and trace.session_id != session_id:
                continue
            if task_id and trace.task_id != task_id:
                continue
            if agent_name and trace.agent_name != agent_name:
                continue
            if trace_type and trace.trace_type != trace_type:
                continue
            results.append(trace.to_dict())
            if len(results) >= limit:
                break
        return results
    
    def get_task_flow(self, task_id: str) -> Dict[str, Any]:
        """Get the complete flow for a specific task (ordered by time)"""
        traces = [t.to_dict() for t in self._traces if t.task_id == task_id]
        traces.sort(key=lambda x: x["timestamp"])
        
        # Build a summary
        agents_involved = list(set(t["agent_name"] for t in traces))
        total_duration = 0
        for t in traces:
            if t.get("duration_ms"):
                total_duration += t["duration_ms"]
        
        return {
            "task_id": task_id,
            "agents_involved": agents_involved,
            "total_traces": len(traces),
            "total_duration_ms": total_duration,
            "flow": traces
        }
    
    def get_session_flow(self, session_id: str) -> Dict[str, Any]:
        """Get all traces for a session grouped by task"""
        traces = [t.to_dict() for t in self._traces if t.session_id == session_id]
        traces.sort(key=lambda x: x["timestamp"])
        
        # Group by task
        tasks = {}
        for t in traces:
            tid = t["task_id"]
            if tid not in tasks:
                tasks[tid] = []
            tasks[tid].append(t)
        
        return {
            "session_id": session_id,
            "total_traces": len(traces),
            "task_count": len(tasks),
            "tasks": tasks
        }
    
    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get the most recent traces"""
        traces = list(self._traces)
        return [t.to_dict() for t in traces[-limit:]]
    
    def clear(self):
        """Clear all traces"""
        self._traces.clear()
        self._counter = 0


def _truncate_content(data: Any, max_len: int = 500) -> Any:
    """Truncate content for storage"""
    if isinstance(data, str):
        return data[:max_len] + "..." if len(data) > max_len else data
    elif isinstance(data, dict):
        return {k: _truncate_content(v, max_len) for k, v in data.items()}
    elif isinstance(data, list):
        return [_truncate_content(item, max_len) for item in data[:10]]
    return data


# Singleton
_debug_service: Optional[AgentDebugService] = None

def get_debug_service() -> AgentDebugService:
    """Get the singleton AgentDebugService instance"""
    global _debug_service
    if _debug_service is None:
        _debug_service = AgentDebugService()
    return _debug_service
