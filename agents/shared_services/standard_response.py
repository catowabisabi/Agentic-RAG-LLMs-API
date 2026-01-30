# -*- coding: utf-8 -*-
"""
=============================================================================
Standard Agent Response - 標準化回應格式
=============================================================================

所有 Agent 都使用這個標準格式回應，確保前端可以統一處理。

=============================================================================
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class ResponseStatus(str, Enum):
    """Response status codes"""
    OK = "ok"
    ERROR = "error"
    ESCALATE = "escalate"
    PENDING = "pending"


class ThinkingStep(BaseModel):
    """A single thinking/planning step for UI display"""
    step_number: int
    title: str
    content: str
    agent: Optional[str] = None
    duration_ms: Optional[int] = None
    status: str = "completed"  # pending, in_progress, completed, failed


class AgentResponse(BaseModel):
    """
    標準化的 Agent 回應格式
    
    所有 Agent 的 process_task() 都應該返回這個格式
    """
    # === 必填欄位 ===
    response: str = Field(description="主要回答內容")
    status: ResponseStatus = Field(default=ResponseStatus.OK, description="狀態: ok/error/escalate")
    agents_involved: List[str] = Field(default_factory=list, description="參與處理的 agent 列表")
    workflow: str = Field(default="general", description="處理流程標籤")
    
    # === 選填欄位 ===
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="RAG/工具來源")
    reason: Optional[str] = Field(default=None, description="錯誤或升級的原因")
    steps: List[ThinkingStep] = Field(default_factory=list, description="思考/計劃步驟，供 UI 折疊顯示")
    duration_ms: Optional[int] = Field(default=None, description="處理時間(毫秒)")
    
    # === 元數據 ===
    intent: Optional[str] = Field(default=None, description="識別的意圖")
    confidence: Optional[float] = Field(default=None, description="意圖識別信心度")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="其他元數據")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        result = {
            "response": self.response,
            "status": self.status.value,
            "agents_involved": self.agents_involved,
            "workflow": self.workflow,
            "sources": self.sources,
            "timestamp": self.timestamp
        }
        
        # Only include optional fields if they have values
        if self.reason:
            result["reason"] = self.reason
        if self.steps:
            result["steps"] = [s.model_dump() for s in self.steps]
        if self.duration_ms is not None:
            result["duration_ms"] = self.duration_ms
        if self.intent:
            result["intent"] = self.intent
        if self.confidence is not None:
            result["confidence"] = self.confidence
        if self.metadata:
            result["metadata"] = self.metadata
            
        return result
    
    @classmethod
    def ok(cls, response: str, agents: List[str], workflow: str = "general", **kwargs) -> "AgentResponse":
        """Factory method for successful response"""
        return cls(
            response=response,
            status=ResponseStatus.OK,
            agents_involved=agents,
            workflow=workflow,
            **kwargs
        )
    
    @classmethod
    def error(cls, message: str, agents: List[str], reason: str = None, **kwargs) -> "AgentResponse":
        """Factory method for error response"""
        return cls(
            response=message,
            status=ResponseStatus.ERROR,
            agents_involved=agents,
            reason=reason,
            workflow="error",
            **kwargs
        )
    
    @classmethod
    def escalate(cls, original_query: str, agents: List[str], reason: str, **kwargs) -> "AgentResponse":
        """Factory method for escalation response"""
        return cls(
            response=original_query,
            status=ResponseStatus.ESCALATE,
            agents_involved=agents,
            reason=reason,
            workflow="escalation",
            **kwargs
        )


def normalize_response(result: Dict[str, Any], agent_name: str) -> Dict[str, Any]:
    """
    將舊格式的 agent 回應正規化為標準格式
    
    用於向後兼容：如果 agent 返回舊格式，自動轉換
    """
    # 如果已經是標準格式，直接返回
    if "status" in result and "agents_involved" in result:
        return result
    
    # 轉換舊格式
    normalized = {
        "response": result.get("response", result.get("content", str(result))),
        "status": "ok",
        "agents_involved": result.get("agents_involved", [agent_name]),
        "workflow": result.get("workflow", "general"),
        "sources": result.get("sources", []),
        "timestamp": datetime.now().isoformat()
    }
    
    # 處理錯誤狀態
    if "error" in result:
        normalized["status"] = "error"
        normalized["reason"] = result["error"]
    
    # 處理升級狀態
    if result.get("status") == "escalate":
        normalized["status"] = "escalate"
        normalized["reason"] = result.get("reason", "Escalated to specialist")
    
    # 複製其他有用欄位
    for key in ["duration_ms", "steps", "intent", "confidence", "metadata"]:
        if key in result:
            normalized[key] = result[key]
    
    return normalized
