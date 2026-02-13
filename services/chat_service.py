"""
Chat Service
============

統一聊天業務邏輯層，服務於 HTTP 和 WebSocket Routers。

核心職責：
1. 會話管理 - 創建、獲取、更新會話上下文
2. 消息處理 - Entry classification、Agent routing、歷史管理
3. RAG 整合 - 查詢知識庫、合併上下文
4. Agent 協調 - Manager vs Casual routing、任務分配
5. Memory 整合 - Cerebro 個性化、歷史上下文
6. Task 管理 - 任務創建、狀態追蹤、結果存儲

設計原則：
- 薄 Router，厚 Service
- Router 只負責協議適配（HTTP/WebSocket）
- Service 包含所有業務邏輯
- 使用 Service Layer (llm_service, rag_service, etc.)
- 使用 UnifiedEventManager 統一事件管理
"""

import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime
from enum import Enum

from agents.shared_services.agent_registry import AgentRegistry
from services.redis_service import get_redis_service
from services.celery_service import get_celery_service
from agents.shared_services.websocket_manager import WebSocketManager
from agents.shared_services.message_protocol import TaskAssignment
from agents.core.entry_classifier import get_entry_classifier
from config.config import Config
from services.vectordb_manager import vectordb_manager
from services.task_manager import task_manager, TaskStatus
from services.session_db import session_db, TaskStatus as DBTaskStatus, StepType
from services.cerebro_memory import get_cerebro, MemoryType, MemoryImportance
from agents.auxiliary.memory_capture_agent import process_message_for_memory, get_user_context_for_prompt
from services.unified_event_manager import (
    get_event_manager, init_event_manager,
    EventType, Stage, TokenInfo
)

# Architecture V2: Agentic Loop Engine
from agents.core.agentic_loop_engine import AgenticLoopEngine, create_agentic_loop
from agents.core.agentic_task_queue import TodoTask, TodoStatus

logger = logging.getLogger(__name__)


class ChatMode(str, Enum):
    """聊天模式"""
    SYNC = "sync"          # 同步模式（等待完整響應）
    ASYNC = "async"        # 異步模式（後台任務）
    STREAM = "stream"      # 串流模式（WebSocket 實時推送）


class ProcessingResult:
    """處理結果"""
    def __init__(
        self,
        response: str,
        conversation_id: str,
        agents_involved: List[str],
        sources: List[Dict[str, Any]] = None,
        task_uid: Optional[str] = None,
        task_id: Optional[str] = None,
        metadata: Dict[str, Any] = None
    ):
        self.response = response
        self.conversation_id = conversation_id
        self.agents_involved = agents_involved
        self.sources = sources or []
        self.task_uid = task_uid
        self.task_id = task_id
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()


class ChatService:
    """
    統一聊天服務
    
    管理所有聊天相關業務邏輯，無論來源是 HTTP 還是 WebSocket。
    """
    
    def __init__(self):
        self.config = Config()
        self.ws_manager = WebSocketManager()
        self.registry = AgentRegistry()
        # Redis 服務（優雅降級到內存）
        self.redis = get_redis_service()
        # Celery 服務（優雅降級到 asyncio）
        self.celery = get_celery_service()
        # 內存會話存儲（Redis 不可用時的 fallback）
        self.conversations: Dict[str, List[Dict]] = {}
        # 統一事件管理器
        self.event_manager = init_event_manager(self.ws_manager, session_db)
        
        # Architecture V2: Agentic Loop Engine (初始化時不創建，按需創建)
        self._agentic_loop: Optional[AgenticLoopEngine] = None
        
        # 嘗試連接 Redis
        self._redis_initialized = False
    
    async def _ensure_redis(self):
        """確保 Redis 已初始化（懶連接）"""
        if not self._redis_initialized:
            self._redis_initialized = True
            if self.redis.enabled:
                await self.redis.connect()
    
    def _get_agentic_loop(self, session_id: str) -> AgenticLoopEngine:
        """
        獲取 Agentic Loop Engine（按需創建）
        
        Architecture V2: 連接 AgenticLoopEngine 回調到 UnifiedEventManager
        """
        async def on_thinking(step_type: str, content: str, metadata: Dict):
            """思考步驟回調 -> 發送到 WebSocket"""
            await self.event_manager.emit_thinking(
                session_id=session_id,
                task_id=metadata.get("task_id", session_id),
                agent_name=metadata.get("agent", "agentic_loop"),
                message=f"[{step_type}] {content}",
                data=metadata
            )
        
        async def on_task_update(task: TodoTask):
            """任務更新回調 -> 發送到 WebSocket"""
            stage = Stage.EXECUTING
            if task.status == TodoStatus.COMPLETED:
                stage = Stage.COMPLETE
            elif task.status == TodoStatus.FAILED:
                stage = Stage.FAILED
            
            await self.event_manager.emit(
                session_id=session_id,
                task_id=task.id,
                event_type=EventType.PROGRESS,
                stage=stage,
                agent_name=task.assigned_agent or "agentic_loop",
                message=f"任務 '{task.title}': {task.status}",
                data={
                    "task_id": task.id,
                    "title": task.title,
                    "status": task.status,
                    "retry_count": task.retry_count
                }
            )
        
        async def on_intermediate(task_id: str, result: Dict, message: str):
            """中間結果回調 -> 發送到 WebSocket"""
            await self.event_manager.emit(
                session_id=session_id,
                task_id=task_id,
                event_type=EventType.STATUS,
                stage=Stage.SYNTHESIS,
                agent_name="agentic_loop",
                message=f"中間結果: {message}",
                data={"intermediate_result": result}
            )
        
        async def on_final(summary: str):
            """最終回應回調 -> 發送到 WebSocket"""
            await self.event_manager.emit_result(
                session_id=session_id,
                task_id=session_id,
                message="處理完成",
                answer=summary
            )
        
        return create_agentic_loop(
            on_thinking=on_thinking,
            on_task=on_task_update,
            on_intermediate=on_intermediate,
            on_final=on_final
        )
    
    # ========================================
    # 會話管理
    # ========================================
    
    def get_or_create_conversation(self, conversation_id: Optional[str] = None) -> str:
        """獲取或創建會話 ID"""
        if conversation_id is None:
            conversation_id = str(uuid.uuid4())
        
        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        
        # 確保 SessionDB 中也有記錄
        session_db.get_or_create_session(conversation_id, "Chat Session")
        
        # 確保 Redis 中也有記錄
        if self.redis.is_connected:
            asyncio.create_task(self.redis.set_conversation(conversation_id, []))
        
        return conversation_id
    
    def add_user_message(
        self,
        conversation_id: str,
        message: str,
        task_uid: Optional[str] = None
    ) -> str:
        """添加用戶消息到歷史"""
        message_id = str(uuid.uuid4())
        
        # 添加到內存
        msg_entry = {
            "id": message_id,
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        }
        self.conversations[conversation_id].append(msg_entry)
        
        # 同步到 Redis（fire-and-forget）
        if self.redis.is_connected:
            asyncio.create_task(self.redis.append_message(conversation_id, msg_entry))
        
        # 添加到數據庫
        session_db.add_message(
            session_id=conversation_id,
            role="user",
            content=message,
            task_uid=task_uid
        )
        
        return message_id
    
    def add_assistant_message(
        self,
        conversation_id: str,
        message: str,
        task_uid: Optional[str] = None,
        agents_involved: List[str] = None,
        sources: List[Dict] = None
    ) -> str:
        """添加助手消息到歷史"""
        message_id = str(uuid.uuid4())
        
        # 從 SessionDB 獲取此任務的處理步驟
        thinking_steps = None
        if task_uid:
            try:
                steps = session_db.get_task_steps(task_uid)
                if steps:
                    thinking_steps = [
                        {
                            "step_type": s.get("step_type"),
                            "agent_name": s.get("agent_name"),
                            "content": s.get("content"),
                            "timestamp": s.get("timestamp")
                        }
                        for s in steps
                    ]
            except Exception as e:
                logger.warning(f"Failed to get task steps: {e}")
        
        # 添加到內存
        msg_entry = {
            "id": message_id,
            "role": "assistant",
            "content": message,
            "timestamp": datetime.now().isoformat()
        }
        self.conversations[conversation_id].append(msg_entry)
        
        # 同步到 Redis（fire-and-forget）
        if self.redis.is_connected:
            asyncio.create_task(self.redis.append_message(conversation_id, msg_entry))
        
        # 添加到數據庫（包含 thinking_steps）
        session_db.add_message(
            session_id=conversation_id,
            role="assistant",
            content=message,
            task_uid=task_uid,
            agents_involved=agents_involved,
            sources=sources,
            thinking_steps=thinking_steps
        )
        
        return message_id
    
    def get_conversation_history(
        self,
        conversation_id: str,
        limit: Optional[int] = None
    ) -> List[Dict]:
        """獲取會話歷史"""
        if limit is None:
            limit = self.config.MEMORY_WINDOW * 2
        
        # 從 SessionDB 獲取持久化的消息
        previous_messages = session_db.get_session_messages(conversation_id, limit=limit)
        
        chat_history = []
        for msg in previous_messages:
            if msg.get("role") == "user":
                chat_history.append({"human": msg.get("content", "")})
            elif msg.get("role") == "assistant":
                if chat_history and "assistant" not in chat_history[-1]:
                    chat_history[-1]["assistant"] = msg.get("content", "")
                else:
                    chat_history.append({"assistant": msg.get("content", "")})
        
        # 保持在窗口大小內
        if len(chat_history) > self.config.MEMORY_WINDOW:
            chat_history = chat_history[-self.config.MEMORY_WINDOW:]
        
        return chat_history
    
    # ========================================
    # RAG 整合
    # ========================================
    
    async def get_rag_context(self, query: str) -> Tuple[str, List[Dict]]:
        """查詢所有 RAG 數據庫並返回相關上下文"""
        try:
            # 獲取數據庫列表並過濾非空數據庫
            db_list = vectordb_manager.list_databases()
            active_dbs = [db["name"] for db in db_list if db.get("document_count", 0) > 0]
            
            if not active_dbs:
                logger.warning("No non-empty databases found for RAG query")
                return "", []
            
            all_sources = []
            all_contexts = []
            
            # 查詢每個數據庫
            for db_name in active_dbs:
                try:
                    results = await vectordb_manager.query(
                        query=query,
                        db_name=db_name,
                        n_results=3
                    )
                    
                    if results and "documents" in results and results["documents"]:
                        docs = results["documents"][0]
                        metadatas = results.get("metadatas", [[]])[0]
                        distances = results.get("distances", [[]])[0]
                        
                        for i, (doc, meta, dist) in enumerate(zip(docs, metadatas, distances)):
                            all_contexts.append(doc)
                            all_sources.append({
                                "database": db_name,
                                "content": doc[:300],
                                "metadata": meta,
                                "relevance_score": float(1 - dist) if dist else 0.0,
                                "rank": len(all_sources) + 1
                            })
                except Exception as db_error:
                    logger.error(f"Error querying database {db_name}: {db_error}")
                    continue
            
            # 合併上下文
            if all_contexts:
                combined_context = "\n\n---\n\n".join(all_contexts[:10])
                logger.info(f"Retrieved {len(all_contexts)} contexts from {len(active_dbs)} databases")
                return combined_context, all_sources
            else:
                return "", []
                
        except Exception as e:
            logger.error(f"RAG context retrieval failed: {e}", exc_info=True)
            return "", []
    
    # ========================================
    # Memory 整合（Cerebro）
    # ========================================
    
    def get_user_context(
        self,
        user_id: str,
        message: str,
        enable_memory: bool = True
    ) -> str:
        """獲取用戶個性化上下文（Cerebro）"""
        if not enable_memory:
            return ""
        
        try:
            user_context = get_user_context_for_prompt(user_id, message)
            if user_context:
                logger.info(f"[Cerebro] Loaded user context for {user_id}: {len(user_context)} chars")
                return user_context
        except Exception as e:
            logger.warning(f"[Cerebro] Failed to load user context: {e}")
        
        return ""
    
    async def capture_memory(
        self,
        user_id: str,
        message: str,
        response: str,
        conversation_id: str
    ):
        """捕獲對話記憶（Cerebro）- Fire-and-forget，不阻塞主流程"""
        try:
            await process_message_for_memory(
                user_id=user_id,
                message=message,
                response=response,
                session_id=conversation_id
            )
            logger.info(f"[Cerebro] Captured memory for user {user_id}")
        except Exception as e:
            logger.warning(f"[Cerebro] Memory capture failed: {e}")

    def _fire_and_forget_memory(
        self,
        user_id: str,
        message: str,
        response: str,
        conversation_id: str
    ):
        """以 asyncio.create_task 啟動記憶捕獲，完全非阻塞"""
        import asyncio
        asyncio.create_task(
            self.capture_memory(user_id, message, response, conversation_id)
        )
    
    # ========================================
    # 核心處理邏輯
    # ========================================
    
    async def process_message(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        user_id: str = "default",
        use_rag: bool = True,
        enable_memory: bool = True,
        context: Dict[str, Any] = None,
        mode: ChatMode = ChatMode.SYNC,
        stream_callback: Optional[Callable] = None
    ) -> ProcessingResult:
        """
        處理聊天消息的核心方法
        
        Args:
            message: 用戶消息
            conversation_id: 會話 ID（可選）
            user_id: 用戶 ID
            use_rag: 是否使用 RAG
            enable_memory: 是否啟用記憶
            context: 額外上下文
            mode: 處理模式（sync/async/stream）
            stream_callback: 串流回調函數（僅 stream 模式）
        
        Returns:
            ProcessingResult: 處理結果
        """
        context = context or {}
        
        # 確保 Redis 已初始化
        await self._ensure_redis()
        
        # 獲取或創建會話
        conversation_id = self.get_or_create_conversation(conversation_id)
        
        # 獲取用戶個性化上下文
        user_context = self.get_user_context(user_id, message, enable_memory)
        
        # 獲取會話歷史
        chat_history = self.get_conversation_history(conversation_id)
        
        # 創建任務 UID
        task_uid = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{conversation_id}_{mode.value}"
        
        # 添加用戶消息
        self.add_user_message(conversation_id, message, task_uid)
        
        # 創建數據庫任務
        db_task = session_db.create_task(
            session_id=conversation_id,
            agent_name="manager_agent",
            task_type="user_query",
            description=message[:200],
            input_data={
                "query": message,
                "use_rag": use_rag,
                "context": context,
                "chat_history": chat_history,
                "user_context": user_context,
                "user_id": user_id
            }
        )
        task_uid = db_task.task_uid
        
        # 更新任務狀態
        session_db.update_task_status(task_uid, DBTaskStatus.RUNNING)
        
        # 添加初始化步驟 - 使用統一事件管理器
        await self.event_manager.emit_init(
            session_id=conversation_id,
            task_id=task_uid,
            message="收到您的訊息，正在處理..."
        )
        
        try:
            # ===== STEP 1: Entry Classification =====
            await self.event_manager.emit_classifying(
                session_id=conversation_id,
                task_id=task_uid,
                message="正在分析問題類型..."
            )
            
            entry_classifier = get_entry_classifier()
            classification = await entry_classifier.classify(message, user_context)
            
            # 只有當 entry_classifier 判定為非 casual，且 use_rag=True 時，才強制走 RAG
            # 不要覆蓋 casual chat 的判定！
            if use_rag and not classification.is_casual:
                logger.info(f"[Entry] use_rag=True and not casual. Will use RAG for manager_agent.")
                classification.route_to = "manager_agent"
                classification.intent = classification.intent or "search_knowledge"
                # 不改變 reason，保留原始分類理由
            
            logger.info(f"[Entry] Classified as: {'casual' if classification.is_casual else 'task'} ({classification.reason})")
            
            # 廣播分類結果 - 使用統一事件管理器
            await self.event_manager.emit(
                session_id=conversation_id,
                task_id=task_uid,
                event_type=EventType.STATUS,
                stage=Stage.CLASSIFYING,
                agent_name="entry_classifier",
                message=f"分類完成：{'休閒聊天' if classification.is_casual else '任務查詢'}",
                data={
                    "is_casual": classification.is_casual,
                    "reason": classification.reason,
                    "route_to": "casual_chat_agent" if classification.is_casual else "manager_agent"
                },
                intent=classification.intent if hasattr(classification, 'intent') else None,
                handler=classification.handler if hasattr(classification, 'handler') else None
            )
            
            # ===== STEP 2: Route to Appropriate Agent =====
            agents_involved = []
            response_text = ""
            sources = []
            
            if classification.is_casual:
                # Route to Casual Chat Agent
                response_text, agents_involved = await self._process_casual_chat(
                    message=message,
                    chat_history=chat_history,
                    user_context=user_context,
                    task_uid=task_uid,
                    conversation_id=conversation_id
                )
            else:
                # Route to Manager Agent
                response_text, agents_involved, sources = await self._process_manager_agent(
                    message=message,
                    chat_history=chat_history,
                    user_context=user_context,
                    use_rag=use_rag,
                    context=context,
                    task_uid=task_uid,
                    conversation_id=conversation_id,
                    classification=classification,
                    stream_callback=stream_callback
                )
            
            # 添加助手消息（包含處理步驟）
            self.add_assistant_message(
                conversation_id=conversation_id,
                message=response_text,
                task_uid=task_uid,
                agents_involved=agents_involved,
                sources=sources
            )
            
            # 更新任務狀態為完成
            session_db.update_task_status(task_uid, DBTaskStatus.COMPLETED)
            
            # 發送結果事件
            await self.event_manager.emit_result(
                session_id=conversation_id,
                task_id=task_uid,
                message="處理完成",
                answer=response_text,
                sources=sources,
                agents_involved=agents_involved
            )
            
            # 捕獲記憶（fire-and-forget，完全非阻塞）
            if enable_memory:
                self._fire_and_forget_memory(user_id, message, response_text, conversation_id)
            
            return ProcessingResult(
                response=response_text,
                conversation_id=conversation_id,
                agents_involved=agents_involved,
                sources=sources,
                task_uid=task_uid
            )
            
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            
            # 更新任務狀態為失敗
            session_db.update_task_status(task_uid, DBTaskStatus.FAILED)
            
            # 發送錯誤事件
            await self.event_manager.emit_error(
                session_id=conversation_id,
                task_id=task_uid,
                message=f"處理失敗：{str(e)}",
                error_code="PROCESSING_ERROR"
            )
            
            raise
    
    # ========================================
    # Architecture V2: Agentic Loop 處理
    # ========================================
    
    async def process_message_agentic(
        self,
        message: str,
        conversation_id: Optional[str] = None,
        user_id: str = "default",
        use_rag: bool = True,
        enable_memory: bool = True,
        context: Dict[str, Any] = None
    ) -> ProcessingResult:
        """
        使用 Agentic Loop Engine 處理消息
        
        Architecture V2: 無限反饋循環，任務驅動，LLM 決策
        
        NOTE: 測試模式 - 不使用 fallback，錯誤直接傳播
        TODO: 生產環境需要添加適當的錯誤處理
        
        Args:
            message: 用戶消息
            conversation_id: 會話 ID
            user_id: 用戶 ID
            use_rag: 是否使用 RAG
            enable_memory: 是否啟用記憶
            context: 額外上下文
            
        Returns:
            ProcessingResult
        """
        context = context or {}
        
        # 確保 Redis 已初始化
        await self._ensure_redis()
        
        # 獲取或創建會話
        conversation_id = self.get_or_create_conversation(conversation_id)
        
        # 創建任務 UID
        task_uid = f"agentic_{datetime.now().strftime('%Y%m%d%H%M%S')}_{conversation_id}"
        
        # 添加用戶消息
        self.add_user_message(conversation_id, message, task_uid)
        
        # 創建數據庫任務
        db_task = session_db.create_task(
            session_id=conversation_id,
            agent_name="agentic_loop",
            task_type="agentic_query",
            description=message[:200],
            input_data={
                "query": message,
                "use_rag": use_rag,
                "context": context,
                "user_id": user_id
            }
        )
        task_uid = db_task.task_uid
        
        # 更新任務狀態
        session_db.update_task_status(task_uid, DBTaskStatus.RUNNING)
        
        # 發送初始化事件
        await self.event_manager.emit_init(
            session_id=conversation_id,
            task_id=task_uid,
            message="收到您的訊息，正在啟動 Agentic Loop..."
        )
        
        # 獲取用戶上下文
        user_context = self.get_user_context(user_id, message, enable_memory)
        
        # NOTE: No try-catch - errors propagate for testing visibility
        # TODO: Add proper error handling for production
        
        # 獲取 Agentic Loop Engine
        agentic_loop = self._get_agentic_loop(conversation_id)
        
        # 構建上下文字符串
        context_str = ""
        if user_context:
            context_str += f"User Context: {user_context}\n"
        if use_rag:
            rag_context, _ = await self.get_rag_context(message)
            if rag_context:
                context_str += f"RAG Context: {rag_context[:2000]}\n"
        
        # 運行 Agentic Loop
        result = await agentic_loop.run(
            user_query=message,
            session_id=conversation_id,
            context_str=context_str
        )
        
        # 如果是閒聊，使用簡單處理
        if result.get("is_casual"):
            # 使用原有的 casual chat 處理
            chat_history = self.get_conversation_history(conversation_id)
            response_text, agents_involved = await self._process_casual_chat(
                message=message,
                chat_history=chat_history,
                user_context=user_context,
                task_uid=task_uid,
                conversation_id=conversation_id
            )
        else:
            response_text = result.get("summary", str(result))
            agents_involved = ["agentic_loop"]
            if result.get("execution_summary"):
                agents_involved.extend(
                    task["agent"] 
                    for task in result["execution_summary"].get("tasks", {}).values()
                    if task.get("agent")
                )
        
        # 添加助手消息
        self.add_assistant_message(
            conversation_id=conversation_id,
            message=response_text,
            task_uid=task_uid,
            agents_involved=agents_involved,
            sources=[]  # TODO: 從 result 中提取 sources
        )
        
        # 更新任務狀態
        session_db.update_task_status(task_uid, DBTaskStatus.COMPLETED)
        
        # 捕獲記憶（fire-and-forget，完全非阻塞）
        if enable_memory:
            self._fire_and_forget_memory(user_id, message, response_text, conversation_id)
        
        return ProcessingResult(
            response=response_text,
            conversation_id=conversation_id,
            agents_involved=agents_involved,
            sources=[],
            task_uid=task_uid,
            metadata={
                "agentic": True,
                "thinking_steps": result.get("thinking_steps", []),
                "execution_summary": result.get("execution_summary")
            }
        )
    
    async def _process_casual_chat(
        self,
        message: str,
        chat_history: List[Dict],
        user_context: str,
        task_uid: str,
        conversation_id: str
    ) -> Tuple[str, List[str]]:
        """處理休閒聊天"""
        from agents.core.casual_chat_agent import get_casual_chat_agent
        
        casual_agent = get_casual_chat_agent()
        
        # 發送思考事件
        await self.event_manager.emit_thinking(
            session_id=conversation_id,
            task_id=task_uid,
            agent_name="casual_chat_agent",
            message="正在處理休閒對話..."
        )
        
        task = TaskAssignment(
            task_id=task_uid,
            task_type="casual_response",
            description=message,
            input_data={
                "query": message,
                "chat_history": chat_history,
                "user_context": user_context,
                "session_id": conversation_id
            }
        )
        
        result = await casual_agent.process_task(task)
        
        response_text = result.get("response", str(result))
        
        return response_text, result.get("agents_involved", ["casual_chat_agent"])
    
    async def _process_manager_agent(
        self,
        message: str,
        chat_history: List[Dict],
        user_context: str,
        use_rag: bool,
        context: Dict[str, Any],
        task_uid: str,
        conversation_id: str,
        classification = None,
        stream_callback: Optional[Callable] = None
    ) -> Tuple[str, List[str], List[Dict]]:
        """處理 Manager Agent 任務（使用 UnifiedManagerAgent）"""
        from agents.core.unified_manager_agent import get_unified_manager
        
        manager = get_unified_manager()
        
        # 獲取 RAG 上下文（如果啟用）
        rag_context = ""
        sources = []
        if use_rag:
            # 發送檢索事件
            await self.event_manager.emit_retrieval(
                session_id=conversation_id,
                task_id=task_uid,
                message="正在搜尋相關知識庫..."
            )
            
            rag_context, sources = await self.get_rag_context(message)
            
            if sources:
                # 發送檢索結果事件
                await self.event_manager.emit(
                    session_id=conversation_id,
                    task_id=task_uid,
                    event_type=EventType.STATUS,
                    stage=Stage.RETRIEVAL,
                    agent_name="rag_agent",
                    message=f"找到 {len(sources)} 條相關資料",
                    sources=sources[:5],  # 限制傳輸數量
                    data={"context_length": len(rag_context)}
                )
        
        # 創建任務分配 (使用 user_query 以觸發正確的路由邏輯)
        task = TaskAssignment(
            task_id=task_uid,
            task_type="user_query",
            description=message,
            input_data={
                "query": message,
                "chat_history": chat_history,
                "user_context": user_context,
                "rag_context": rag_context,
                "use_rag": use_rag,
                "additional_context": context,
                # 從 EntryClassifier 傳遞 intent 路由信息
                "intent": classification.intent if classification and hasattr(classification, 'intent') else None,
                "handler": classification.handler if classification and hasattr(classification, 'handler') else None,
                "matched_by": classification.matched_by if classification and hasattr(classification, 'matched_by') else "internal",
                # 傳遞 session_id 給 manager_agent 用於廣播
                "session_id": conversation_id,
                "conversation_id": conversation_id
            }
        )
        
        # 發送規劃事件
        await self.event_manager.emit_planning(
            session_id=conversation_id,
            task_id=task_uid,
            message="正在分析問題，制定回答策略...",
            plan_steps=["分析問題", "查找資料", "整合回答"]
        )
        
        # 發送執行事件
        await self.event_manager.emit_thinking(
            session_id=conversation_id,
            task_id=task_uid,
            agent_name="manager_agent",
            message="正在處理您的查詢..."
        )
        
        # 處理任務
        result = await manager.process_task(task)
        
        # 提取響應文本（result 是 Dict）
        response_text = result.get("response", result.get("content", str(result)))
        agents_used = result.get("agents_involved", [])
        result_sources = result.get("sources", [])
        
        # 發送整合事件
        await self.event_manager.emit_synthesis(
            session_id=conversation_id,
            task_id=task_uid,
            message="正在整合資訊，生成最終回答..."
        )
        
        agents_involved = ["manager_agent"] + agents_used
        
        # 合併 RAG sources 和 result sources
        all_sources = sources + result_sources
        
        return response_text, agents_involved, all_sources
    
    # ========================================
    # 任務管理
    # ========================================
    
    def create_background_task(
        self,
        message: str,
        conversation_id: str,
        user_id: str,
        use_rag: bool,
        enable_memory: bool,
        context: Dict[str, Any]
    ) -> str:
        """
        創建後台任務（異步模式）
        
        優先使用 Celery（分布式），fallback 到 asyncio（本地）。
        """
        # 嘗試 Celery
        if self.celery.is_available:
            celery_task_id = self.celery.submit_chat_task(
                message=message,
                conversation_id=conversation_id,
                user_id=user_id,
                use_rag=use_rag,
                enable_memory=enable_memory,
                context=context
            )
            if celery_task_id:
                logger.info(f"[ChatService] Task submitted to Celery: {celery_task_id}")
                return celery_task_id
        
        # Fallback 到本地 asyncio task manager
        task_id = task_manager.create_task(
            task_type="chat",
            input_data={
                "message": message,
                "conversation_id": conversation_id,
                "use_rag": use_rag,
                "context": context,
                "user_id": user_id,
                "enable_memory": enable_memory
            }
        )
        
        logger.info(f"[ChatService] Background task {task_id} (asyncio) for conversation {conversation_id}")
        
        return task_id
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """獲取任務狀態"""
        return task_manager.get_task(task_id)
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任務"""
        return task_manager.cancel_task(task_id)
    
    # ========================================
    # 會話管理端點
    # ========================================
    
    def list_conversations(self) -> List[Dict[str, Any]]:
        """列出所有會話"""
        return [
            {
                "conversation_id": conv_id,
                "message_count": len(messages),
                "last_message": messages[-1] if messages else None
            }
            for conv_id, messages in self.conversations.items()
        ]
    
    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """獲取會話詳情"""
        if conversation_id not in self.conversations:
            return None
        
        return {
            "conversation_id": conversation_id,
            "messages": self.conversations[conversation_id]
        }
    
    def delete_conversation(self, conversation_id: str) -> bool:
        """刪除會話"""
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            # 同步刪除 Redis
            if self.redis.is_connected:
                asyncio.create_task(self.redis.delete_conversation(conversation_id))
            return True
        return False
    
    def clear_conversation(self, conversation_id: str) -> bool:
        """清空會話消息"""
        if conversation_id in self.conversations:
            self.conversations[conversation_id] = []
            # 同步清空 Redis
            if self.redis.is_connected:
                asyncio.create_task(self.redis.set_conversation(conversation_id, []))
            return True
        return False


# ========================================
# 全局實例（單例模式）
# ========================================

_chat_service_instance = None


def get_chat_service() -> ChatService:
    """獲取 ChatService 單例"""
    global _chat_service_instance
    if _chat_service_instance is None:
        _chat_service_instance = ChatService()
    return _chat_service_instance
