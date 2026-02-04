"""
Chat Router (Refactored)
=========================

薄 HTTP Router 層，負責協議適配。
所有業務邏輯已移至 services/chat_service.py。

職責：
- 驗證 HTTP 請求
- 調用 ChatService 處理
- 格式化 HTTP 響應
- 錯誤處理

設計：
- 單一職責：協議適配
- 無業務邏輯
- 簡潔清晰（原 968 行 → ~200 行）
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from services.chat_service import get_chat_service, ChatMode

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ========================================
# Request/Response Models
# ========================================

class ChatRequest(BaseModel):
    """Chat request"""
    message: str = Field(description="User message")
    conversation_id: Optional[str] = Field(default=None, description="Conversation ID")
    user_id: Optional[str] = Field(default="default", description="User ID for personalization")
    context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")
    use_rag: bool = Field(default=True, description="Whether to use RAG for context")
    async_mode: bool = Field(default=False, description="If True, returns task_id immediately and processes in background")
    enable_memory: bool = Field(default=True, description="Enable personalized memory capture")


class ChatResponse(BaseModel):
    """Chat response"""
    message_id: str
    response: str
    conversation_id: str
    agents_involved: List[str]
    sources: List[Dict[str, Any]] = []
    timestamp: str


class AsyncChatResponse(BaseModel):
    """Response for async mode - returns immediately with task_id"""
    task_id: str
    conversation_id: str
    status: str = "pending"
    message: str = "Task submitted. Poll /chat/task/{task_id} for status or wait for WebSocket updates."


class TaskStatusResponse(BaseModel):
    """Task status response"""
    task_id: str
    status: str
    progress: float
    current_step: str
    agents_involved: List[str]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


# ========================================
# HTTP Endpoints
# ========================================

@router.post("/send", response_model=ChatResponse | AsyncChatResponse)
async def send_message(request: ChatRequest):
    """
    發送消息並獲取響應
    
    模式：
    - async_mode=False（默認）：等待完整響應（20-60秒）
    - async_mode=True：立即返回 task_id，後台處理
    
    異步模式：輪詢 /chat/task/{task_id} 獲取狀態，或通過 WebSocket 監聽更新
    """
    chat_service = get_chat_service()
    
    try:
        # ============================================
        # ASYNC MODE: 返回 task_id，後台處理
        # ============================================
        if request.async_mode:
            # 創建後台任務
            task_id = chat_service.create_background_task(
                message=request.message,
                conversation_id=request.conversation_id or chat_service.get_or_create_conversation(),
                user_id=request.user_id,
                use_rag=request.use_rag,
                enable_memory=request.enable_memory,
                context=request.context
            )
            
            # 啟動後台處理
            asyncio.create_task(_process_async_task(task_id, request))
            
            logger.info(f"[Router] Async task {task_id} created")
            
            return AsyncChatResponse(
                task_id=task_id,
                conversation_id=request.conversation_id,
                status="pending"
            )
        
        # ============================================
        # SYNC MODE: 等待完整響應
        # ============================================
        result = await chat_service.process_message(
            message=request.message,
            conversation_id=request.conversation_id,
            user_id=request.user_id,
            use_rag=request.use_rag,
            enable_memory=request.enable_memory,
            context=request.context,
            mode=ChatMode.SYNC
        )
        
        return ChatResponse(
            message_id=result.task_uid,
            response=result.response,
            conversation_id=result.conversation_id,
            agents_involved=result.agents_involved,
            sources=result.sources,
            timestamp=result.timestamp
        )
        
    except Exception as e:
        logger.error(f"[Router] Error processing message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _process_async_task(task_id: str, request: ChatRequest):
    """後台任務處理器"""
    from services.task_manager import task_manager
    
    chat_service = get_chat_service()
    
    async def _task_handler():
        return await chat_service.process_message(
            message=request.message,
            conversation_id=request.conversation_id,
            user_id=request.user_id,
            use_rag=request.use_rag,
            enable_memory=request.enable_memory,
            context=request.context,
            mode=ChatMode.ASYNC
        )
    
    await task_manager.run_task(task_id, _task_handler)


# ========================================
# Conversation Management Endpoints
# ========================================

@router.get("/conversations")
async def list_conversations():
    """列出所有會話"""
    chat_service = get_chat_service()
    try:
        conversations = chat_service.list_conversations()
        return {
            "status": "success",
            "conversations": conversations,
            "count": len(conversations)
        }
    except Exception as e:
        logger.error(f"[Router] Error listing conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    """獲取會話詳情"""
    chat_service = get_chat_service()
    try:
        conversation = chat_service.get_conversation(conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conversation
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Router] Error getting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """刪除會話"""
    chat_service = get_chat_service()
    try:
        success = chat_service.delete_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"status": "success", "message": "Conversation deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Router] Error deleting conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/conversations/{conversation_id}/clear")
async def clear_conversation(conversation_id: str):
    """清空會話消息"""
    chat_service = get_chat_service()
    try:
        success = chat_service.clear_conversation(conversation_id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"status": "success", "message": "Conversation cleared"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Router] Error clearing conversation: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ========================================
# Task Management Endpoints
# ========================================

@router.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """獲取任務狀態（用於異步模式輪詢）"""
    chat_service = get_chat_service()
    try:
        task = chat_service.get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        return TaskStatusResponse(
            task_id=task["task_id"],
            status=task["status"],
            progress=task.get("progress", 0.0),
            current_step=task.get("current_step", ""),
            agents_involved=task.get("agents_involved", []),
            result=task.get("result"),
            error=task.get("error"),
            created_at=task.get("created_at", ""),
            completed_at=task.get("completed_at")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Router] Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task/{task_id}/result")
async def get_task_result(task_id: str):
    """獲取任務結果（僅當任務完成時）"""
    chat_service = get_chat_service()
    try:
        task = chat_service.get_task_status(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        if task["status"] != "completed":
            raise HTTPException(
                status_code=400,
                detail=f"Task is not completed yet. Current status: {task['status']}"
            )
        
        return {
            "status": "success",
            "task_id": task_id,
            "result": task.get("result"),
            "completed_at": task.get("completed_at")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Router] Error getting task result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/task/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消正在執行的任務"""
    chat_service = get_chat_service()
    try:
        success = chat_service.cancel_task(task_id)
        if not success:
            raise HTTPException(status_code=404, detail="Task not found or already completed")
        
        return {"status": "success", "message": "Task cancelled"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[Router] Error cancelling task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tasks")
async def list_tasks(status: Optional[str] = None, limit: int = 50):
    """列出任務（支持按狀態過濾）"""
    from services.task_manager import task_manager
    
    try:
        tasks = task_manager.list_tasks(status_filter=status, limit=limit)
        return {
            "status": "success",
            "tasks": tasks,
            "count": len(tasks),
            "filter": status
        }
    except Exception as e:
        logger.error(f"[Router] Error listing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))
