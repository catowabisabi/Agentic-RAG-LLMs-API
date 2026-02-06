"""
統一事件管理器 (Unified Event Manager)

所有 Agent/Service 使用此管理器發送事件，確保：
1. 所有事件遵循統一結構
2. 自動填充必要欄位
3. 同時寫入 DB 和 WS
4. UI 可靠接收完整流程
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ============================================================
# 1. 枚舉定義
# ============================================================

class EventType(str, Enum):
    """事件類型"""
    INIT = "init"
    THINKING = "thinking"
    STATUS = "status"
    PROGRESS = "progress"
    STREAM = "stream"
    RESULT = "result"
    ERROR = "error"


class Stage(str, Enum):
    """處理階段"""
    INIT = "init"
    CLASSIFYING = "classifying"
    PLANNING = "planning"
    RETRIEVAL = "retrieval"
    EXECUTING = "executing"
    SYNTHESIS = "synthesis"
    COMPLETE = "complete"
    FAILED = "failed"


# ============================================================
# 2. 資料結構定義
# ============================================================

class AgentInfo(BaseModel):
    """Agent 資訊"""
    name: str = "unknown"
    role: str = "Agent"
    icon: str = "bot"


class TokenInfo(BaseModel):
    """Token 使用資訊"""
    prompt: int = 0
    completion: int = 0
    total: int = 0
    cost: float = 0.0


class ContentData(BaseModel):
    """事件內容"""
    message: str = ""
    data: Dict[str, Any] = Field(default_factory=dict)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    tokens: Optional[TokenInfo] = None
    answer: Optional[str] = None


class UIHints(BaseModel):
    """UI 渲染提示"""
    color: str = "#3b82f6"
    icon: str = "info"
    priority: int = 1
    dismissible: bool = True
    show_in_timeline: bool = True
    animate: bool = False


class EventMetadata(BaseModel):
    """事件元數據"""
    intent: Optional[str] = None
    handler: Optional[str] = None
    matched_by: Optional[str] = None
    duration_ms: Optional[int] = None
    step_index: Optional[int] = None
    total_steps: Optional[int] = None


class UnifiedEvent(BaseModel):
    """
    統一事件結構
    
    所有 WS/JSON 回應都使用此結構，確保 UI 可以用單一邏輯處理
    """
    # 必填 - 識別欄位
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    session_id: str
    task_id: str
    
    # 必填 - 事件類型
    type: EventType = EventType.STATUS
    
    # 可選 - 但永遠存在（可為 None 或空）
    conversation_id: Optional[str] = None
    stage: Stage = Stage.INIT
    
    agent: AgentInfo = Field(default_factory=AgentInfo)
    content: ContentData = Field(default_factory=ContentData)
    ui: UIHints = Field(default_factory=UIHints)
    metadata: EventMetadata = Field(default_factory=EventMetadata)
    
    # 時間戳
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    
    def to_ws_dict(self) -> Dict[str, Any]:
        """轉換為 WebSocket 傳輸格式"""
        return self.model_dump(mode="json")


# ============================================================
# 3. 預設 UI 配置
# ============================================================

STAGE_UI_CONFIG: Dict[Stage, UIHints] = {
    Stage.INIT: UIHints(color="#6b7280", icon="inbox", priority=0),
    Stage.CLASSIFYING: UIHints(color="#8b5cf6", icon="tag", priority=1),
    Stage.PLANNING: UIHints(color="#f59e0b", icon="clipboard-list", priority=2, animate=True),
    Stage.RETRIEVAL: UIHints(color="#10b981", icon="search", priority=2, animate=True),
    Stage.EXECUTING: UIHints(color="#3b82f6", icon="cog", priority=2, animate=True),
    Stage.SYNTHESIS: UIHints(color="#6366f1", icon="sparkles", priority=2, animate=True),
    Stage.COMPLETE: UIHints(color="#22c55e", icon="check-circle", priority=3),
    Stage.FAILED: UIHints(color="#ef4444", icon="x-circle", priority=3),
}

AGENT_UI_CONFIG: Dict[str, AgentInfo] = {
    "manager_agent": AgentInfo(name="manager_agent", role="協調者", icon="brain"),
    "planning_agent": AgentInfo(name="planning_agent", role="規劃師", icon="clipboard-list"),
    "thinking_agent": AgentInfo(name="thinking_agent", role="思考者", icon="lightbulb"),
    "rag_agent": AgentInfo(name="rag_agent", role="檢索專家", icon="search"),
    "casual_chat_agent": AgentInfo(name="casual_chat_agent", role="對話助手", icon="message-circle"),
    "sw_agent": AgentInfo(name="sw_agent", role="SolidWorks 專家", icon="cube"),
    "calculation_agent": AgentInfo(name="calculation_agent", role="計算專家", icon="calculator"),
    "translate_agent": AgentInfo(name="translate_agent", role="翻譯專家", icon="globe"),
    "summarize_agent": AgentInfo(name="summarize_agent", role="摘要專家", icon="file-text"),
    "data_agent": AgentInfo(name="data_agent", role="資料分析師", icon="bar-chart"),
    "entry_classifier": AgentInfo(name="entry_classifier", role="分類器", icon="tag"),
    "system": AgentInfo(name="system", role="系統", icon="server"),
}


# ============================================================
# 4. 統一事件管理器
# ============================================================

class UnifiedEventManager:
    """
    統一事件管理器
    
    功能：
    1. 創建符合統一結構的事件
    2. 同時推送到 WebSocket 和寫入 DB
    3. 自動填充預設值（顏色、圖標等）
    4. 提供便捷方法（emit_thinking, emit_result 等）
    """
    
    def __init__(self, ws_manager=None, session_db=None):
        """
        Args:
            ws_manager: WebSocket 管理器
            session_db: Session 資料庫（用於持久化）
        """
        self._ws_manager = ws_manager
        self._session_db = session_db
        self._event_history: Dict[str, List[UnifiedEvent]] = {}
        
        logger.info("[UnifiedEventManager] Initialized")
    
    def set_ws_manager(self, ws_manager):
        """設置 WebSocket 管理器"""
        self._ws_manager = ws_manager
    
    def set_session_db(self, session_db):
        """設置 Session DB"""
        self._session_db = session_db
    
    # --------------------------------------------------------
    # 核心方法
    # --------------------------------------------------------
    
    async def emit(
        self,
        session_id: str,
        task_id: str,
        event_type: EventType = EventType.STATUS,
        stage: Stage = Stage.INIT,
        agent_name: str = "system",
        message: str = "",
        data: Dict[str, Any] = None,
        sources: List[Dict[str, Any]] = None,
        tokens: TokenInfo = None,
        intent: str = None,
        handler: str = None,
        conversation_id: str = None,
        persist: bool = True
    ) -> UnifiedEvent:
        """
        發送統一事件
        
        Args:
            session_id: 會話 ID
            task_id: 任務 ID
            event_type: 事件類型
            stage: 處理階段
            agent_name: Agent 名稱
            message: 事件訊息
            data: 額外資料
            sources: 來源引用
            tokens: Token 使用資訊
            intent: 意圖
            handler: 處理器
            conversation_id: 對話 ID
            persist: 是否寫入 DB
        
        Returns:
            UnifiedEvent
        """
        # 獲取 Agent 配置
        agent_info = AGENT_UI_CONFIG.get(
            agent_name, 
            AgentInfo(name=agent_name, role="Agent", icon="bot")
        )
        
        # 獲取 Stage UI 配置
        ui_hints = STAGE_UI_CONFIG.get(stage, UIHints())
        
        # 創建事件
        event = UnifiedEvent(
            session_id=session_id,
            task_id=task_id,
            conversation_id=conversation_id or session_id,
            type=event_type,
            stage=stage,
            agent=agent_info,
            content=ContentData(
                message=message,
                data=data or {},
                sources=sources or [],
                tokens=tokens
            ),
            ui=ui_hints,
            metadata=EventMetadata(
                intent=intent,
                handler=handler
            )
        )
        
        # 保存到歷史
        if session_id not in self._event_history:
            self._event_history[session_id] = []
        self._event_history[session_id].append(event)
        
        # 發送到 WebSocket
        if self._ws_manager:
            try:
                await self._ws_manager.broadcast_to_clients(event.to_ws_dict())
                logger.info(f"[EventManager] WS broadcast sent: {event_type.value}/{stage.value}")
            except Exception as e:
                logger.warning(f"[EventManager] WS broadcast failed: {e}")
        else:
            logger.warning(f"[EventManager] No WS manager set, event not broadcasted")
        
        # 持久化到 DB
        if persist and self._session_db:
            try:
                self._persist_event(event)
            except Exception as e:
                logger.warning(f"[EventManager] DB persist failed: {e}")
        
        logger.info(f"[EventManager] Emitted: {event_type.value}/{stage.value} - {message[:50]}...")
        
        return event
    
    def _persist_event(self, event: UnifiedEvent):
        """持久化事件到 DB"""
        if not self._session_db:
            return
        
        try:
            from services.session_db import StepType
            
            step_type_map = {
                EventType.INIT: StepType.THINKING,
                EventType.THINKING: StepType.THINKING,
                EventType.STATUS: StepType.SEARCHING,
                EventType.PROGRESS: StepType.SEARCHING,
                EventType.RESULT: StepType.COMPLETED,
                EventType.ERROR: StepType.ERROR,
                EventType.STREAM: StepType.LLM_RESPONSE,
            }
            
            step_type = step_type_map.get(event.type, StepType.SEARCHING)
            
            self._session_db.add_step(
                task_uid=event.task_id,
                session_id=event.session_id,
                agent_name=event.agent.name,
                step_type=step_type,
                content={
                    "message": event.content.message,
                    "stage": event.stage.value,
                    **event.content.data
                }
            )
        except Exception as e:
            logger.warning(f"[EventManager] Persist failed: {e}")
    
    # --------------------------------------------------------
    # 便捷方法
    # --------------------------------------------------------
    
    async def emit_init(
        self,
        session_id: str,
        task_id: str,
        message: str = "收到您的訊息，正在處理...",
        **kwargs
    ) -> UnifiedEvent:
        """發送初始化事件"""
        return await self.emit(
            session_id=session_id,
            task_id=task_id,
            event_type=EventType.INIT,
            stage=Stage.INIT,
            message=message,
            **kwargs
        )
    
    async def emit_classifying(
        self,
        session_id: str,
        task_id: str,
        message: str = "正在分析問題類型...",
        **kwargs
    ) -> UnifiedEvent:
        """發送分類事件"""
        return await self.emit(
            session_id=session_id,
            task_id=task_id,
            event_type=EventType.STATUS,
            stage=Stage.CLASSIFYING,
            agent_name="entry_classifier",
            message=message,
            **kwargs
        )
    
    async def emit_thinking(
        self,
        session_id: str,
        task_id: str,
        agent_name: str,
        message: str,
        **kwargs
    ) -> UnifiedEvent:
        """發送思考事件"""
        return await self.emit(
            session_id=session_id,
            task_id=task_id,
            event_type=EventType.THINKING,
            stage=Stage.EXECUTING,
            agent_name=agent_name,
            message=message,
            **kwargs
        )
    
    async def emit_planning(
        self,
        session_id: str,
        task_id: str,
        message: str = "正在分析問題，制定計劃...",
        plan_steps: List[str] = None,
        **kwargs
    ) -> UnifiedEvent:
        """發送規劃事件"""
        return await self.emit(
            session_id=session_id,
            task_id=task_id,
            event_type=EventType.STATUS,
            stage=Stage.PLANNING,
            agent_name="planning_agent",
            message=message,
            data={"steps": plan_steps or []},
            **kwargs
        )
    
    async def emit_retrieval(
        self,
        session_id: str,
        task_id: str,
        message: str = "正在搜尋相關資料...",
        sources: List[Dict[str, Any]] = None,
        **kwargs
    ) -> UnifiedEvent:
        """發送檢索事件"""
        return await self.emit(
            session_id=session_id,
            task_id=task_id,
            event_type=EventType.STATUS,
            stage=Stage.RETRIEVAL,
            agent_name="rag_agent",
            message=message,
            sources=sources,
            **kwargs
        )
    
    async def emit_progress(
        self,
        session_id: str,
        task_id: str,
        message: str,
        current: int,
        total: int,
        agent_name: str = "system",
        **kwargs
    ) -> UnifiedEvent:
        """發送進度事件"""
        return await self.emit(
            session_id=session_id,
            task_id=task_id,
            event_type=EventType.PROGRESS,
            stage=Stage.EXECUTING,
            agent_name=agent_name,
            message=message,
            data={"current": current, "total": total, "percent": int(current / total * 100) if total > 0 else 0},
            **kwargs
        )
    
    async def emit_synthesis(
        self,
        session_id: str,
        task_id: str,
        message: str = "正在整合資訊，生成回答...",
        agent_name: str = "manager_agent",
        **kwargs
    ) -> UnifiedEvent:
        """發送整合事件"""
        return await self.emit(
            session_id=session_id,
            task_id=task_id,
            event_type=EventType.STATUS,
            stage=Stage.SYNTHESIS,
            agent_name=agent_name,
            message=message,
            **kwargs
        )
    
    async def emit_result(
        self,
        session_id: str,
        task_id: str,
        message: str,
        answer: str = None,
        sources: List[Dict[str, Any]] = None,
        tokens: TokenInfo = None,
        agents_involved: List[str] = None,
        **kwargs
    ) -> UnifiedEvent:
        """發送結果事件"""
        return await self.emit(
            session_id=session_id,
            task_id=task_id,
            event_type=EventType.RESULT,
            stage=Stage.COMPLETE,
            agent_name="system",
            message=message,
            data={
                "answer": answer or message,
                "agents_involved": agents_involved or []
            },
            sources=sources,
            tokens=tokens,
            **kwargs
        )
    
    async def emit_error(
        self,
        session_id: str,
        task_id: str,
        message: str,
        error_code: str = None,
        **kwargs
    ) -> UnifiedEvent:
        """發送錯誤事件"""
        return await self.emit(
            session_id=session_id,
            task_id=task_id,
            event_type=EventType.ERROR,
            stage=Stage.FAILED,
            agent_name="system",
            message=message,
            data={"error_code": error_code},
            **kwargs
        )
    
    async def emit_stream(
        self,
        session_id: str,
        task_id: str,
        chunk: str,
        agent_name: str = "assistant",
        **kwargs
    ) -> UnifiedEvent:
        """發送串流片段"""
        return await self.emit(
            session_id=session_id,
            task_id=task_id,
            event_type=EventType.STREAM,
            stage=Stage.SYNTHESIS,
            agent_name=agent_name,
            message=chunk,
            persist=False,  # 串流片段不持久化
            **kwargs
        )
    
    # --------------------------------------------------------
    # 查詢方法
    # --------------------------------------------------------
    
    def get_session_events(self, session_id: str) -> List[UnifiedEvent]:
        """獲取 Session 的所有事件"""
        return self._event_history.get(session_id, [])
    
    def get_session_timeline(self, session_id: str) -> List[Dict[str, Any]]:
        """獲取 Session 的時間線（UI 用）"""
        events = self.get_session_events(session_id)
        return [
            {
                "event_id": e.event_id,
                "type": e.type.value,
                "stage": e.stage.value,
                "agent": e.agent.name,
                "message": e.content.message[:100],
                "timestamp": e.timestamp,
                "ui": e.ui.model_dump()
            }
            for e in events
            if e.ui.show_in_timeline
        ]
    
    def clear_session(self, session_id: str):
        """清除 Session 事件歷史"""
        if session_id in self._event_history:
            del self._event_history[session_id]


# ============================================================
# 5. 單例
# ============================================================

_event_manager: Optional[UnifiedEventManager] = None


def get_event_manager() -> UnifiedEventManager:
    """獲取統一事件管理器單例"""
    global _event_manager
    if _event_manager is None:
        _event_manager = UnifiedEventManager()
    return _event_manager


def init_event_manager(ws_manager=None, session_db=None) -> UnifiedEventManager:
    """初始化事件管理器"""
    global _event_manager
    _event_manager = UnifiedEventManager(ws_manager, session_db)
    return _event_manager
