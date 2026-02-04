"""
WebSocket Chat Router (Refactored)
===================================

薄 WebSocket Router 層，負責 WebSocket 協議適配。
所有業務邏輯已移至 services/chat_service.py。

職責：
- 管理 WebSocket 連接
- 解析 WebSocket 消息
- 調用 ChatService 處理
- 推送實時更新到客戶端
- 心跳保持連接

設計：
- 單一職責：WebSocket 協議適配
- 使用 ChatService 統一業務邏輯
- 簡潔清晰（原 460 行 → ~150 行）

使用方式:
    ws = new WebSocket("ws://localhost:1130/ws/chat")
    ws.send(JSON.stringify({type: "chat", content: {message: "..."}}))
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from services.chat_service import get_chat_service, ChatMode
from agents.shared_services.websocket_manager import WebSocketManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket-chat"])


# ========================================
# Message Types & Models
# ========================================

class WSMessageType(str, Enum):
    """WebSocket 消息類型"""
    # 客戶端 -> 服務器
    CHAT = "chat"
    CANCEL = "cancel"
    PING = "ping"
    
    # 服務器 -> 客戶端
    CONNECTED = "connected"
    THINKING = "thinking"
    SEARCHING = "searching"
    STEP = "step"
    SOURCES = "sources"
    FINAL_ANSWER = "final_answer"
    ERROR = "error"
    PONG = "pong"
    CANCELLED = "cancelled"


class ChatMessage(BaseModel):
    """聊天消息"""
    message: str
    session_id: Optional[str] = None
    user_id: Optional[str] = "default"
    use_rag: bool = True
    use_memory: bool = True


# ========================================
# WebSocket Endpoint
# ========================================

@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket 聊天端點
    
    支持：
    - 實時串流響應
    - 思考過程推送
    - 任務取消
    - 心跳保持
    """
    ws_manager = WebSocketManager()
    chat_service = get_chat_service()
    
    session_id = str(uuid.uuid4())
    current_task_id = None
    
    await websocket.accept()
    
    # 發送連接確認
    await websocket.send_json({
        "type": WSMessageType.CONNECTED,
        "content": {
            "session_id": session_id,
            "message": "Connected to chat server"
        },
        "timestamp": datetime.now().isoformat()
    })
    
    logger.info(f"[WS] Client connected: {session_id}")
    
    try:
        while True:
            # 接收消息
            data = await websocket.receive_json()
            msg_type = data.get("type")
            content = data.get("content", {})
            
            # === PING（心跳）===
            if msg_type == WSMessageType.PING:
                await websocket.send_json({
                    "type": WSMessageType.PONG,
                    "timestamp": datetime.now().isoformat()
                })
                continue
            
            # === CANCEL（取消任務）===
            if msg_type == WSMessageType.CANCEL:
                if current_task_id:
                    chat_service.cancel_task(current_task_id)
                    await websocket.send_json({
                        "type": WSMessageType.CANCELLED,
                        "content": {"task_id": current_task_id},
                        "timestamp": datetime.now().isoformat()
                    })
                    current_task_id = None
                continue
            
            # === CHAT（處理消息）===
            if msg_type == WSMessageType.CHAT:
                # 解析消息
                chat_msg = ChatMessage(**content)
                current_task_id = str(uuid.uuid4())
                
                logger.info(f"[WS] Processing message: {chat_msg.message[:50]}...")
                
                # 定義串流回調
                async def stream_callback(step_type: str, step_content: Dict[str, Any], step_number: int = None):
                    """推送處理步驟到客戶端"""
                    await websocket.send_json({
                        "type": step_type,
                        "content": step_content,
                        "step_number": step_number,
                        "timestamp": datetime.now().isoformat()
                    })
                
                try:
                    # 發送思考中狀態
                    await stream_callback(
                        WSMessageType.THINKING,
                        {"message": "Analyzing your question...", "task_id": current_task_id},
                        step_number=1
                    )
                    
                    # 處理消息（使用 ChatService）
                    result = await chat_service.process_message(
                        message=chat_msg.message,
                        conversation_id=chat_msg.session_id or session_id,
                        user_id=chat_msg.user_id,
                        use_rag=chat_msg.use_rag,
                        enable_memory=chat_msg.use_memory,
                        mode=ChatMode.STREAM,
                        stream_callback=stream_callback
                    )
                    
                    # 發送來源（如果有）
                    if result.sources:
                        await stream_callback(
                            WSMessageType.SOURCES,
                            {
                                "sources": result.sources[:5],
                                "total": len(result.sources)
                            }
                        )
                    
                    # 發送最終答案
                    await websocket.send_json({
                        "type": WSMessageType.FINAL_ANSWER,
                        "content": {
                            "response": result.response,
                            "agents_involved": result.agents_involved,
                            "conversation_id": result.conversation_id,
                            "task_id": current_task_id
                        },
                        "timestamp": result.timestamp
                    })
                    
                    logger.info(f"[WS] Message processed successfully: {current_task_id}")
                    
                except Exception as e:
                    logger.error(f"[WS] Error processing message: {e}", exc_info=True)
                    
                    # 發送錯誤
                    await websocket.send_json({
                        "type": WSMessageType.ERROR,
                        "content": {
                            "error": str(e),
                            "task_id": current_task_id
                        },
                        "timestamp": datetime.now().isoformat()
                    })
                
                finally:
                    current_task_id = None
    
    except WebSocketDisconnect:
        logger.info(f"[WS] Client disconnected: {session_id}")
    except Exception as e:
        logger.error(f"[WS] Unexpected error: {e}", exc_info=True)
        try:
            await websocket.close()
        except:
            pass
