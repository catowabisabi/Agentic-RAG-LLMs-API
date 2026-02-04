"""
Broadcast Service - 統一的 WebSocket 廣播服務

統一管理所有 WebSocket 廣播：
1. Agent 狀態更新
2. 思考步驟廣播
3. 計劃更新廣播
4. 錯誤通知

使用範例:
    broadcast = get_broadcast_service()
    await broadcast.agent_status("rag_agent", "working", task_id, {...})
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from agents.shared_services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)


class BroadcastService:
    """
    統一的 WebSocket 廣播服務
    
    特性：
    - 統一的廣播格式
    - 自動添加時間戳
    - 錯誤處理
    """
    
    def __init__(self, ws_manager: Optional[WebSocketManager] = None):
        self.ws_manager = ws_manager or WebSocketManager()
        logger.info("[BroadcastService] Initialized")
    
    async def agent_status(
        self,
        agent_name: str,
        status: str,
        task_id: str,
        data: Dict[str, Any],
        step_number: Optional[int] = None
    ):
        """
        廣播 Agent 狀態更新
        
        Args:
            agent_name: Agent 名稱
            status: 狀態 (started, working, completed, failed, etc.)
            task_id: 任務 ID
            data: 附加數據
            step_number: 步驟編號（可選）
        """
        message = {
            "type": f"{agent_name}_{status}",
            "agent": agent_name,
            "task_id": task_id,
            "content": data,
            "timestamp": datetime.now().isoformat()
        }
        
        if step_number is not None:
            message["step"] = step_number
        
        await self._broadcast(message)
    
    async def thinking_step(
        self,
        agent_name: str,
        step_number: int,
        thought: str,
        action: Optional[str] = None,
        action_input: Optional[str] = None,
        observation: Optional[str] = None,
        task_id: Optional[str] = None
    ):
        """
        廣播思考步驟
        
        用於 ReAct Loop 或其他需要展示思考過程的場景
        """
        message = {
            "type": "thinking_step",
            "agent": agent_name,
            "step": step_number,
            "content": {
                "thought": thought,
                "action": action,
                "action_input": action_input,
                "observation": observation
            },
            "timestamp": datetime.now().isoformat()
        }
        
        if task_id:
            message["task_id"] = task_id
        
        await self._broadcast(message)
    
    async def plan_update(
        self,
        agent_name: str,
        plan_data: Dict[str, Any],
        task_id: Optional[str] = None
    ):
        """
        廣播計劃更新
        
        用於 Planning Agent 或 Manager Agent 的計劃變更
        """
        message = {
            "type": "plan_update",
            "agent": agent_name,
            "content": plan_data,
            "timestamp": datetime.now().isoformat()
        }
        
        if task_id:
            message["task_id"] = task_id
        
        await self._broadcast(message)
    
    async def agent_activity(
        self,
        agent_name: str,
        activity_type: str,
        content: Dict[str, Any]
    ):
        """
        廣播 Agent 活動
        
        通用的活動廣播接口
        """
        message = {
            "type": activity_type,
            "agent": agent_name,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        await self._broadcast(message)
    
    async def error(
        self,
        agent_name: str,
        error_message: str,
        task_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        廣播錯誤消息
        """
        message = {
            "type": "error",
            "agent": agent_name,
            "content": {
                "error": error_message,
                "details": details or {}
            },
            "timestamp": datetime.now().isoformat()
        }
        
        if task_id:
            message["task_id"] = task_id
        
        await self._broadcast(message)
    
    async def rag_sources(
        self,
        sources: list,
        task_id: Optional[str] = None
    ):
        """
        廣播 RAG 來源
        """
        message = {
            "type": "rag_sources",
            "content": {
                "sources": sources,
                "count": len(sources)
            },
            "timestamp": datetime.now().isoformat()
        }
        
        if task_id:
            message["task_id"] = task_id
        
        await self._broadcast(message)
    
    async def custom(
        self,
        message_type: str,
        content: Dict[str, Any],
        agent_name: Optional[str] = None
    ):
        """
        自定義廣播消息
        """
        message = {
            "type": message_type,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        if agent_name:
            message["agent"] = agent_name
        
        await self._broadcast(message)
    
    async def _broadcast(self, message: Dict[str, Any]):
        """內部廣播方法"""
        try:
            await self.ws_manager.broadcast_agent_activity(message)
        except Exception as e:
            logger.error(f"[BroadcastService] Broadcast failed: {e}")


# 單例模式
_broadcast_service: Optional[BroadcastService] = None


def get_broadcast_service(
    ws_manager: Optional[WebSocketManager] = None,
    reset: bool = False
) -> BroadcastService:
    """獲取 Broadcast Service 單例"""
    global _broadcast_service
    
    if reset or _broadcast_service is None:
        _broadcast_service = BroadcastService(ws_manager)
    
    return _broadcast_service
