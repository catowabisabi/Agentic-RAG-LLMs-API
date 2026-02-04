"""
WebSocket Chat Router
======================

實時串流聊天端點，支持：
1. ReAct Loop 實時推送思考過程
2. 多步驟任務進度更新
3. 取消/中斷請求
4. 心跳保持連接

使用方式:
    ws = new WebSocket("ws://localhost:1130/ws/chat")
    ws.send(JSON.stringify({type: "chat", content: {message: "..."}}))
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from agents.shared_services.websocket_manager import WebSocketManager
from agents.shared_services.agent_registry import AgentRegistry
from agents.shared_services.message_protocol import TaskAssignment
from agents.core.react_loop import get_react_loop, ReActStep, ActionType
from agents.core.metacognition_engine import get_self_evaluator, get_strategy_adapter
from agents.shared_services.memory_integration import (
    get_memory_manager,
    TaskCategory,
    EpisodeOutcome
)
from services.vectordb_manager import vectordb_manager as vectordb_mgr

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket-chat"])


class WSMessageType(str, Enum):
    """WebSocket 消息類型"""
    # 客戶端 -> 服務器
    CHAT = "chat"
    CANCEL = "cancel"
    PING = "ping"
    SUBSCRIBE = "subscribe"
    
    # 服務器 -> 客戶端
    CONNECTED = "connected"
    THINKING = "thinking"
    SEARCHING = "searching"
    STEP = "step"
    SOURCES = "sources"
    EVALUATING = "evaluating"
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
    use_react: bool = True  # 使用 ReAct 循環
    use_memory: bool = True
    max_iterations: int = 3


class StreamStep(BaseModel):
    """串流步驟"""
    type: WSMessageType
    content: Dict[str, Any]
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    step_number: Optional[int] = None


async def send_step(websocket: WebSocket, step_type: WSMessageType, content: Dict[str, Any], step_number: int = None):
    """發送步驟更新"""
    step = StreamStep(
        type=step_type,
        content=content,
        step_number=step_number
    )
    await websocket.send_json(step.model_dump())


async def rag_search_tool(query: str) -> Dict[str, Any]:
    """RAG 搜尋工具（用於 ReAct）"""
    try:
        # 獲取所有有效的數據庫
        db_list = vectordb_mgr.list_databases()
        active_dbs = [db["name"] for db in db_list if db.get("document_count", 0) > 0]
        
        if not active_dbs:
            return {
                "content": "No knowledge bases available.",
                "sources": []
            }
        
        all_content = []
        all_sources = []
        
        for db_name in active_dbs[:3]:  # 最多搜尋 3 個數據庫
            try:
                result = await vectordb_mgr.query(query, db_name, n_results=3)
                
                for item in result.get("results", []):
                    content = item.get("content", item.get("page_content", ""))
                    if content:
                        all_content.append(f"[{db_name}]: {content[:500]}")
                        
                        metadata = item.get("metadata", {})
                        all_sources.append({
                            "database": db_name,
                            "title": metadata.get("title", metadata.get("source", "Unknown")),
                            "relevance": max(0, 1 - item.get("distance", 1) / 2)
                        })
            except Exception as e:
                logger.warning(f"Error querying {db_name}: {e}")
                continue
        
        return {
            "content": "\n\n".join(all_content) if all_content else "No relevant information found.",
            "sources": all_sources
        }
        
    except Exception as e:
        logger.error(f"RAG search error: {e}")
        return {
            "content": f"Search error: {str(e)}",
            "sources": []
        }


async def process_chat_stream(
    websocket: WebSocket,
    message: ChatMessage,
    task_id: str
):
    """處理串流聊天請求"""
    
    start_time = datetime.now()
    all_sources = []
    step_count = 0
    final_answer = ""
    
    memory_manager = get_memory_manager()
    
    try:
        # 獲取或創建對話上下文
        session_id = message.session_id or f"ws-{task_id}"
        ctx = memory_manager.get_or_create_context(session_id, message.user_id)
        
        # 獲取歷史上下文
        history_context = ""
        if message.use_memory:
            history_context = memory_manager.get_recent_context(session_id, n_turns=3)
        
        # Step 1: 思考開始
        await send_step(websocket, WSMessageType.THINKING, {
            "message": "Analyzing your question...",
            "task_id": task_id
        }, step_number=1)
        step_count = 1
        
        if message.use_react and message.use_rag:
            # ============== ReAct Loop 模式 ==============
            react_loop = get_react_loop(max_iterations=message.max_iterations)
            
            # 註冊 RAG 搜尋工具
            react_loop.register_tool(ActionType.SEARCH, rag_search_tool)
            
            # 定義步驟回調
            async def on_react_step(step: ReActStep):
                nonlocal step_count, all_sources
                step_count += 1
                
                # 發送思考步驟
                await send_step(websocket, WSMessageType.STEP, {
                    "step": step_count,
                    "thought": step.thought,
                    "action": step.action.value,
                    "action_input": step.action_input[:200]
                }, step_number=step_count)
                
                # 如果是搜尋行動，發送搜尋中狀態
                if step.action == ActionType.SEARCH:
                    await send_step(websocket, WSMessageType.SEARCHING, {
                        "query": step.action_input,
                        "message": f"Searching knowledge base for: {step.action_input[:50]}..."
                    }, step_number=step_count)
            
            react_loop.on_step_callback = on_react_step
            
            # 執行 ReAct 循環
            result = await react_loop.run(
                query=message.message,
                initial_context=history_context
            )
            
            final_answer = result.final_answer
            all_sources = result.sources
            
            # 發送來源信息
            if all_sources:
                await send_step(websocket, WSMessageType.SOURCES, {
                    "sources": all_sources[:5],
                    "total": len(all_sources)
                })
        
        else:
            # ============== 簡單模式（無 ReAct） ==============
            
            if message.use_rag:
                # Step 2: 搜尋知識庫
                await send_step(websocket, WSMessageType.SEARCHING, {
                    "message": "Searching knowledge bases..."
                }, step_number=2)
                step_count = 2
                
                rag_result = await rag_search_tool(message.message)
                rag_context = rag_result.get("content", "")
                all_sources = rag_result.get("sources", [])
                
                # 發送來源
                if all_sources:
                    await send_step(websocket, WSMessageType.SOURCES, {
                        "sources": all_sources[:5],
                        "total": len(all_sources)
                    })
            else:
                rag_context = ""
            
            # Step 3: 生成回答
            await send_step(websocket, WSMessageType.THINKING, {
                "message": "Generating response..."
            }, step_number=step_count + 1)
            
            # 使用 LLM 生成回答
            from langchain_openai import ChatOpenAI
            from langchain_core.prompts import ChatPromptTemplate
            from config.config import Config
            
            config = Config()
            llm = ChatOpenAI(
                model=config.DEFAULT_MODEL,
                temperature=0.3,
                api_key=config.OPENAI_API_KEY
            )
            
            prompt = ChatPromptTemplate.from_template(
                """You are a helpful AI assistant. Answer the user's question based on the available context.

{history_context}

{rag_section}

User Question: {query}

Provide a clear, helpful answer. Match the language of the question."""
            )
            
            rag_section = f"Knowledge Base Context:\n{rag_context[:3000]}" if rag_context else ""
            history_section = f"Previous Conversation:\n{history_context}" if history_context else ""
            
            chain = prompt | llm
            result = await chain.ainvoke({
                "history_context": history_section,
                "rag_section": rag_section,
                "query": message.message
            })
            
            final_answer = result.content if hasattr(result, 'content') else str(result)
        
        # ============== Metacognition 評估 ==============
        await send_step(websocket, WSMessageType.EVALUATING, {
            "message": "Evaluating response quality..."
        })
        
        evaluator = get_self_evaluator()
        score, needs_full_eval = await evaluator.quick_evaluate(message.message, final_answer)
        
        quality_info = {
            "score": score,
            "confidence": "high" if score > 0.7 else "medium" if score > 0.5 else "low"
        }
        
        # ============== 發送最終答案 ==============
        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)
        
        await send_step(websocket, WSMessageType.FINAL_ANSWER, {
            "response": final_answer,
            "sources": all_sources[:5],
            "quality": quality_info,
            "stats": {
                "steps": step_count,
                "duration_ms": duration_ms,
                "sources_found": len(all_sources)
            }
        })
        
        # ============== 存儲記憶 ==============
        if message.use_memory:
            # 更新工作記憶
            memory_manager.update_context(
                session_id,
                query=message.message,
                response=final_answer[:500]
            )
            
            # 存儲情節記憶
            outcome = EpisodeOutcome.SUCCESS if score > 0.6 else EpisodeOutcome.PARTIAL if score > 0.4 else EpisodeOutcome.FAILURE
            
            memory_manager.store_episode(
                session_id=session_id,
                user_id=message.user_id,
                query=message.message,
                response=final_answer,
                task_category=TaskCategory.RAG_SEARCH if message.use_rag else TaskCategory.GENERAL_CHAT,
                outcome=outcome,
                quality_score=score,
                agents_involved=["react_loop" if message.use_react else "simple_rag"],
                sources_used=[s.get("title", "") for s in all_sources[:3]],
                duration_ms=duration_ms
            )
        
    except asyncio.CancelledError:
        await send_step(websocket, WSMessageType.CANCELLED, {
            "message": "Request was cancelled"
        })
        raise
        
    except Exception as e:
        logger.error(f"Chat processing error: {e}")
        await send_step(websocket, WSMessageType.ERROR, {
            "error": str(e),
            "message": "An error occurred while processing your request"
        })


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket 串流聊天端點
    
    消息格式:
    - 發送: {"type": "chat", "content": {"message": "...", "use_rag": true}}
    - 接收: {"type": "thinking|searching|step|final_answer", "content": {...}}
    """
    await websocket.accept()
    
    client_id = f"ws-client-{uuid.uuid4().hex[:8]}"
    active_tasks: Dict[str, asyncio.Task] = {}
    
    logger.info(f"WebSocket chat client connected: {client_id}")
    
    # 發送連接確認
    await websocket.send_json({
        "type": WSMessageType.CONNECTED.value,
        "content": {
            "client_id": client_id,
            "message": "Connected to Agentic RAG chat",
            "capabilities": ["react_loop", "rag_search", "memory", "metacognition"]
        },
        "timestamp": datetime.now().isoformat()
    })
    
    try:
        while True:
            # 接收消息
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                msg_type = message.get("type", "")
                content = message.get("content", {})
                
                if msg_type == WSMessageType.PING.value:
                    await websocket.send_json({
                        "type": WSMessageType.PONG.value,
                        "timestamp": datetime.now().isoformat()
                    })
                
                elif msg_type == WSMessageType.CHAT.value:
                    # 創建聊天任務
                    task_id = f"task-{uuid.uuid4().hex[:8]}"
                    
                    chat_msg = ChatMessage(
                        message=content.get("message", ""),
                        session_id=content.get("session_id"),
                        user_id=content.get("user_id", "default"),
                        use_rag=content.get("use_rag", True),
                        use_react=content.get("use_react", True),
                        use_memory=content.get("use_memory", True),
                        max_iterations=content.get("max_iterations", 3)
                    )
                    
                    # 啟動處理任務
                    task = asyncio.create_task(
                        process_chat_stream(websocket, chat_msg, task_id)
                    )
                    active_tasks[task_id] = task
                    
                    # 清理完成的任務
                    def cleanup_task(t):
                        if task_id in active_tasks:
                            del active_tasks[task_id]
                    
                    task.add_done_callback(lambda t: cleanup_task(t))
                
                elif msg_type == WSMessageType.CANCEL.value:
                    task_id = content.get("task_id")
                    if task_id and task_id in active_tasks:
                        active_tasks[task_id].cancel()
                        await websocket.send_json({
                            "type": WSMessageType.CANCELLED.value,
                            "content": {"task_id": task_id}
                        })
                
                elif msg_type == WSMessageType.SUBSCRIBE.value:
                    # 訂閱特定會話更新
                    session_id = content.get("session_id")
                    ws_manager = WebSocketManager()
                    ws_manager.subscribe_session(client_id, session_id)
                    await websocket.send_json({
                        "type": "subscribed",
                        "content": {"session_id": session_id}
                    })
                
                else:
                    await websocket.send_json({
                        "type": WSMessageType.ERROR.value,
                        "content": {"message": f"Unknown message type: {msg_type}"}
                    })
                    
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": WSMessageType.ERROR.value,
                    "content": {"message": "Invalid JSON format"}
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket chat client disconnected: {client_id}")
        
        # 取消所有活動任務
        for task_id, task in active_tasks.items():
            task.cancel()
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason=str(e))
