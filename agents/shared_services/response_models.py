"""
Structured Response Models for Agent Outputs

All agent responses use structured JSON formats for frontend consumption.
Each response type has a defined schema for consistent parsing.
"""

from enum import Enum
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field
from datetime import datetime
import uuid


class ResponseType(str, Enum):
    """Types of agent responses"""
    YES_NO = "yes_no"
    SUGGESTION = "suggestion"
    CALCULATION = "calculation"
    VALIDATION = "validation"
    THINKING = "thinking"
    PLANNING = "planning"
    SUMMARY = "summary"
    TRANSLATION = "translation"
    DATA = "data"
    MEMORY = "memory"
    NOTE = "note"
    RAG = "rag"
    ERROR = "error"
    STREAM = "stream"


class BaseResponse(BaseModel):
    """Base response model for all agent outputs"""
    response_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    response_type: ResponseType
    agent_name: str
    timestamp: datetime = Field(default_factory=datetime.now)
    success: bool = True
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True


# ============== Decision Responses ==============

class YesNoResponse(BaseResponse):
    """Response for yes/no decisions"""
    response_type: ResponseType = ResponseType.YES_NO
    decision: bool  # True = Yes, False = No
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    reason: str = ""
    alternatives: List[str] = Field(default_factory=list)


class SuggestionResponse(BaseResponse):
    """Response for suggestions"""
    response_type: ResponseType = ResponseType.SUGGESTION
    suggestions: List[Dict[str, Any]] = Field(default_factory=list)
    primary_suggestion: Optional[str] = None
    priority: str = "medium"  # low, medium, high, critical
    reasoning: str = ""
    implementation_steps: List[str] = Field(default_factory=list)


# ============== Computation Responses ==============

class CalculationResponse(BaseResponse):
    """Response for mathematical calculations"""
    response_type: ResponseType = ResponseType.CALCULATION
    result: Union[int, float, str, List, Dict]
    formula: Optional[str] = None
    input_values: Dict[str, Any] = Field(default_factory=dict)
    unit: Optional[str] = None
    precision: int = 2
    steps: List[str] = Field(default_factory=list)


class ValidationResponse(BaseResponse):
    """Response for validation results"""
    response_type: ResponseType = ResponseType.VALIDATION
    is_valid: bool
    errors: List[Dict[str, str]] = Field(default_factory=list)
    warnings: List[Dict[str, str]] = Field(default_factory=list)
    should_retry: bool = False
    retry_suggestions: List[str] = Field(default_factory=list)
    validated_data: Optional[Dict[str, Any]] = None


# ============== Thinking Responses ==============

class ThoughtStep(BaseModel):
    """A single step in the thinking process"""
    step_number: int
    thought: str
    reasoning: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    alternatives_considered: List[str] = Field(default_factory=list)


class ThinkingResponse(BaseResponse):
    """Response for deep thinking/reasoning"""
    response_type: ResponseType = ResponseType.THINKING
    thought_process: List[ThoughtStep] = Field(default_factory=list)
    conclusion: str = ""
    key_insights: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    uncertainties: List[str] = Field(default_factory=list)
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.5)


class PlanStep(BaseModel):
    """A single step in a plan"""
    step_number: int
    action: str
    description: str
    dependencies: List[int] = Field(default_factory=list)  # Step numbers this depends on
    estimated_duration: Optional[str] = None
    assigned_agent: Optional[str] = None
    status: str = "pending"  # pending, in_progress, completed, failed


class PlanningResponse(BaseResponse):
    """Response for planning/task breakdown"""
    response_type: ResponseType = ResponseType.PLANNING
    plan_name: str = ""
    objective: str = ""
    steps: List[PlanStep] = Field(default_factory=list)
    total_estimated_duration: Optional[str] = None
    risks: List[str] = Field(default_factory=list)
    contingencies: List[str] = Field(default_factory=list)


# ============== Content Responses ==============

class SummaryResponse(BaseResponse):
    """Response for summarization"""
    response_type: ResponseType = ResponseType.SUMMARY
    summary: str
    key_points: List[str] = Field(default_factory=list)
    word_count: int = 0
    original_length: int = 0
    compression_ratio: float = 0.0
    topics: List[str] = Field(default_factory=list)


class TranslationResponse(BaseResponse):
    """Response for translation"""
    response_type: ResponseType = ResponseType.TRANSLATION
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    alternative_translations: List[str] = Field(default_factory=list)


# ============== Data Responses ==============

class DataResponse(BaseResponse):
    """Response for data processing"""
    response_type: ResponseType = ResponseType.DATA
    data: Any
    data_type: str = "object"  # object, array, string, number
    record_count: Optional[int] = None
    schema: Optional[Dict[str, str]] = None
    transformations_applied: List[str] = Field(default_factory=list)


class RAGResponse(BaseResponse):
    """Response for RAG queries"""
    response_type: ResponseType = ResponseType.RAG
    answer: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    relevance_scores: List[float] = Field(default_factory=list)
    collection_used: str = ""
    total_chunks_searched: int = 0
    needs_more_context: bool = False


# ============== Memory Responses ==============

class MemoryResponse(BaseResponse):
    """Response for memory operations"""
    response_type: ResponseType = ResponseType.MEMORY
    operation: str  # store, retrieve, update, delete
    memory_type: str  # short_term, long_term
    memory_id: Optional[str] = None
    content: Optional[Dict[str, Any]] = None
    related_memories: List[str] = Field(default_factory=list)


class NoteResponse(BaseResponse):
    """Response for note operations"""
    response_type: ResponseType = ResponseType.NOTE
    note_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    content: str
    tags: List[str] = Field(default_factory=list)
    category: str = "general"
    links: List[str] = Field(default_factory=list)


# ============== Error Response ==============

class ErrorResponse(BaseResponse):
    """Response for errors"""
    response_type: ResponseType = ResponseType.ERROR
    success: bool = False
    error_code: str = "UNKNOWN_ERROR"
    error_message: str
    error_details: Dict[str, Any] = Field(default_factory=dict)
    recoverable: bool = True
    suggested_action: Optional[str] = None


# ============== Stream Response ==============

class StreamChunk(BaseModel):
    """A single chunk in a streaming response"""
    chunk_index: int
    content: str
    is_final: bool = False


class StreamResponse(BaseResponse):
    """Response for streaming content"""
    response_type: ResponseType = ResponseType.STREAM
    chunks: List[StreamChunk] = Field(default_factory=list)
    total_chunks: int = 0
    stream_complete: bool = False
    content_type: str = "text"  # text, thinking, planning


# ============== Response Factory ==============

class ResponseFactory:
    """Factory for creating structured responses"""
    
    @staticmethod
    def yes(agent_name: str, reason: str = "", confidence: float = 1.0) -> YesNoResponse:
        return YesNoResponse(
            agent_name=agent_name,
            decision=True,
            reason=reason,
            confidence=confidence
        )
    
    @staticmethod
    def no(agent_name: str, reason: str = "", confidence: float = 1.0, 
           alternatives: List[str] = None) -> YesNoResponse:
        return YesNoResponse(
            agent_name=agent_name,
            decision=False,
            reason=reason,
            confidence=confidence,
            alternatives=alternatives or []
        )
    
    @staticmethod
    def suggestion(agent_name: str, suggestions: List[Dict], 
                   primary: str = None, reasoning: str = "") -> SuggestionResponse:
        return SuggestionResponse(
            agent_name=agent_name,
            suggestions=suggestions,
            primary_suggestion=primary,
            reasoning=reasoning
        )
    
    @staticmethod
    def calculation(agent_name: str, result: Any, formula: str = None,
                    input_values: Dict = None, steps: List[str] = None) -> CalculationResponse:
        return CalculationResponse(
            agent_name=agent_name,
            result=result,
            formula=formula,
            input_values=input_values or {},
            steps=steps or []
        )
    
    @staticmethod
    def validation(agent_name: str, is_valid: bool, errors: List[Dict] = None,
                   should_retry: bool = False) -> ValidationResponse:
        return ValidationResponse(
            agent_name=agent_name,
            is_valid=is_valid,
            errors=errors or [],
            should_retry=should_retry
        )
    
    @staticmethod
    def thinking(agent_name: str, steps: List[ThoughtStep], 
                 conclusion: str, insights: List[str] = None) -> ThinkingResponse:
        return ThinkingResponse(
            agent_name=agent_name,
            thought_process=steps,
            conclusion=conclusion,
            key_insights=insights or []
        )
    
    @staticmethod
    def planning(agent_name: str, objective: str, 
                 steps: List[PlanStep], name: str = "") -> PlanningResponse:
        return PlanningResponse(
            agent_name=agent_name,
            plan_name=name,
            objective=objective,
            steps=steps
        )
    
    @staticmethod
    def error(agent_name: str, error_code: str, message: str,
              recoverable: bool = True) -> ErrorResponse:
        return ErrorResponse(
            agent_name=agent_name,
            error_code=error_code,
            error_message=message,
            recoverable=recoverable
        )
    
    @staticmethod
    def rag(agent_name: str, answer: str, sources: List[Dict],
            collection: str = "") -> RAGResponse:
        return RAGResponse(
            agent_name=agent_name,
            answer=answer,
            sources=sources,
            collection_used=collection
        )
    
    @staticmethod
    def summary(agent_name: str, summary: str, key_points: List[str],
                original_length: int = 0) -> SummaryResponse:
        return SummaryResponse(
            agent_name=agent_name,
            summary=summary,
            key_points=key_points,
            word_count=len(summary.split()),
            original_length=original_length,
            compression_ratio=len(summary.split()) / original_length if original_length > 0 else 0
        )
