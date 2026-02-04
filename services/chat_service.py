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
"""

import logging
import uuid
from typing import Dict, Any, List, Optional, Tuple, Callable
from datetime import datetime
from enum import Enum

from agents.shared_services.agent_registry import AgentRegistry
from agents.shared_services.websocket_manager import WebSocketManager
from agents.shared_services.message_protocol import TaskAssignment
from agents.core.entry_classifier import get_entry_classifier
from config.config import Config
from services.vectordb_manager import vectordb_manager
from services.task_manager import task_manager, TaskStatus
from services.session_db import session_db, TaskStatus as DBTaskStatus, StepType
from services.cerebro_memory import get_cerebro, MemoryType, MemoryImportance
from agents.auxiliary.memory_capture_agent import process_message_for_memory, get_user_context_for_prompt

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
        # 內存會話存儲（生產環境使用 Redis）
        self.conversations: Dict[str, List[Dict]] = {}
    
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
        self.conversations[conversation_id].append({
            "id": message_id,
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        
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
        task_uid: Optional[str] = None
    ) -> str:
        """添加助手消息到歷史"""
        message_id = str(uuid.uuid4())
        
        # 添加到內存
        self.conversations[conversation_id].append({
            "id": message_id,
            "role": "assistant",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })
        
        # 添加到數據庫
        session_db.add_message(
            session_id=conversation_id,
            role="assistant",
            content=message,
            task_uid=task_uid
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
                    results = vectordb_manager.query(
                        db_name=db_name,
                        query_text=query,
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
        """捕獲對話記憶（Cerebro）"""
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
        
        # 添加初始化步驟
        session_db.add_step(
            task_uid=task_uid,
            session_id=conversation_id,
            agent_name="system",
            step_type=StepType.THINKING,
            content={"status": "Initializing task", "task_uid": task_uid}
        )
        
        try:
            # ===== STEP 1: Entry Classification =====
            entry_classifier = get_entry_classifier()
            classification = await entry_classifier.classify(message, user_context)
            
            # 強制 RAG 覆蓋
            if use_rag:
                logger.info(f"[Entry] Override: use_rag=True. Forcing manager_agent.")
                classification.is_casual = False
                classification.route_to = "manager_agent"
                classification.intent = "search_knowledge"
                classification.reason = "Forced RAG execution"
                classification.confidence = 1.0
            
            logger.info(f"[Entry] Classified as: {'casual' if classification.is_casual else 'task'} ({classification.reason})")
            
            # 廣播分類結果
            await self.ws_manager.broadcast_agent_activity({
                "type": "entry_classification",
                "agent": "entry_classifier",
                "session_id": conversation_id,
                "content": {
                    "is_casual": classification.is_casual,
                    "reason": classification.reason,
                    "route_to": "casual_chat_agent" if classification.is_casual else "manager_agent"
                },
                "timestamp": datetime.now().isoformat()
            })
            
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
                    stream_callback=stream_callback
                )
            
            # 添加助手消息
            self.add_assistant_message(conversation_id, response_text, task_uid)
            
            # 更新任務狀態為完成
            session_db.update_task_status(task_uid, DBTaskStatus.COMPLETED)
            
            # 捕獲記憶
            if enable_memory:
                await self.capture_memory(user_id, message, response_text, conversation_id)
            
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
            session_db.add_step(
                task_uid=task_uid,
                session_id=conversation_id,
                agent_name="system",
                step_type=StepType.ERROR,
                content={"error": str(e)}
            )
            
            raise
    
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
        
        session_db.add_step(
            task_uid=task_uid,
            session_id=conversation_id,
            agent_name="casual_chat_agent",
            step_type=StepType.THINKING,
            content={"status": "Processing casual chat", "query": message[:100]}
        )
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "agent_started",
            "agent": "casual_chat_agent",
            "task_id": task_uid,
            "session_id": conversation_id,
            "content": {"query": message[:100]},
            "timestamp": datetime.now().isoformat()
        })
        
        task = TaskAssignment(
            task_id=task_uid,
            task_type="casual_response",
            description=message,
            input_data={
                "query": message,
                "chat_history": chat_history,
                "user_context": user_context
            }
        )
        
        result = await casual_agent.process(task)
        
        session_db.add_step(
            task_uid=task_uid,
            session_id=conversation_id,
            agent_name="casual_chat_agent",
            step_type=StepType.COMPLETED,
            content={"response": result.response[:200]}
        )
        
        return result.response, ["casual_chat_agent"]
    
    async def _process_manager_agent(
        self,
        message: str,
        chat_history: List[Dict],
        user_context: str,
        use_rag: bool,
        context: Dict[str, Any],
        task_uid: str,
        conversation_id: str,
        stream_callback: Optional[Callable] = None
    ) -> Tuple[str, List[str], List[Dict]]:
        """處理 Manager Agent 任務"""
        from agents.core.manager_agent import get_manager_agent
        
        manager = get_manager_agent()
        
        # 獲取 RAG 上下文（如果啟用）
        rag_context = ""
        sources = []
        if use_rag:
            session_db.add_step(
                task_uid=task_uid,
                session_id=conversation_id,
                agent_name="rag_system",
                step_type=StepType.SEARCHING,
                content={"status": "Querying knowledge bases"}
            )
            
            rag_context, sources = await self.get_rag_context(message)
            
            if sources:
                session_db.add_step(
                    task_uid=task_uid,
                    session_id=conversation_id,
                    agent_name="rag_system",
                    step_type=StepType.COMPLETED,
                    content={
                        "sources_count": len(sources),
                        "context_length": len(rag_context)
                    }
                )
        
        # 創建任務分配
        task = TaskAssignment(
            task_id=task_uid,
            task_type="coordinated_query",
            description=message,
            input_data={
                "query": message,
                "chat_history": chat_history,
                "user_context": user_context,
                "rag_context": rag_context,
                "use_rag": use_rag,
                "additional_context": context
            }
        )
        
        # 廣播開始
        await self.ws_manager.broadcast_agent_activity({
            "type": "agent_started",
            "agent": "manager_agent",
            "task_id": task_uid,
            "session_id": conversation_id,
            "content": {"query": message[:100]},
            "timestamp": datetime.now().isoformat()
        })
        
        # 處理任務
        result = await manager.process(task)
        
        # 記錄完成
        session_db.add_step(
            task_uid=task_uid,
            session_id=conversation_id,
            agent_name="manager_agent",
            step_type=StepType.COMPLETED,
            content={
                "response": result.response[:200],
                "agents_used": result.metadata.get("agents_used", [])
            }
        )
        
        agents_involved = ["manager_agent"] + result.metadata.get("agents_used", [])
        
        return result.response, agents_involved, sources
    
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
        """創建後台任務（異步模式）"""
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
        
        logger.info(f"[ChatService] Created background task {task_id} for conversation {conversation_id}")
        
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
            return True
        return False
    
    def clear_conversation(self, conversation_id: str) -> bool:
        """清空會話消息"""
        if conversation_id in self.conversations:
            self.conversations[conversation_id] = []
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
