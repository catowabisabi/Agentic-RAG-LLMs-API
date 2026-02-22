"""
Manager Agent

The central coordinator agent that:
- Receives and dispatches tasks to appropriate agents
- Has exclusive authority to issue interrupt commands
- Monitors overall system health
- Handles escalation from other agents

Integrated with EventBus for real-time status broadcasting.
Uses UnifiedEventManager for consistent event handling.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    MessageProtocol,
    AgentStatus,
    TaskAssignment,
    InterruptCommand
)
from agents.shared_services.websocket_manager import WebSocketManager
from agents.shared_services.agent_registry import AgentRegistry

# Import EventBus
try:
    from services.event_bus import event_bus, EventType, AgentState
    HAS_EVENT_BUS = True
except ImportError:
    HAS_EVENT_BUS = False
    event_bus = None

# Import UnifiedEventManager
try:
    from services.unified_event_manager import get_event_manager, EventType as UEventType, Stage
    HAS_UNIFIED_EVENTS = True
except ImportError:
    HAS_UNIFIED_EVENTS = False

# Import Debug Service
try:
    from services.agent_debug_service import get_debug_service
    _debug = get_debug_service()
except ImportError:
    _debug = None

# ManagerAgent sub-modules (God Class split)
from agents.core.query_classifier import QueryClassifier, QueryClassification
from agents.core.quality_controller import QualityController

logger = logging.getLogger(__name__)


class QueryClassification(BaseModel):
    """Classification of user query for routing"""
    query_type: str = Field(
        description="""Type of query:
        - 'casual_chat': greetings, chitchat, questions about AI capabilities
        - 'knowledge_rag': questions that need searching knowledge bases
        - 'general_knowledge': general questions LLM can answer without RAG (e.g., "what is VBA")
        - 'calculation': math, numbers, data analysis
        - 'translation': language translation requests
        - 'summarization': summarize content
        - 'complex_planning': multi-step reasoning, comparison, analysis
        """
    )
    reasoning: str = Field(description="Brief explanation for this classification")
    confidence: float = Field(default=0.8, description="Confidence in classification (0-1)")


class TaskRoutingDecision(BaseModel):
    """Decision for routing a task to an agent"""
    target_agent: str = Field(description="Name of the agent to handle the task")
    task_type: str = Field(description="Type of task to assign")
    reasoning: str = Field(description="Brief reasoning for the routing decision")
    requires_planning: bool = Field(default=False, description="Whether the task needs planning first")
    requires_rag: bool = Field(default=False, description="Whether the task needs RAG retrieval")


class ManagerAgent(BaseAgent):
    """
    Central Manager Agent for the multi-agent system.
    
    Responsibilities:
    - Task routing and delegation
    - Interrupt authority (only agent that can interrupt others)
    - System health monitoring
    - Error escalation handling
    """
    
    def __init__(self, agent_name: str = "manager_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Manager",
            agent_description="Central coordinator that routes tasks and manages other agents"
        )
        
        # Load prompt configuration (Service Layer)
        self.prompt_template = self.prompt_manager.get_prompt("manager_agent")
        
        self.registry = AgentRegistry()
        
        # Task queue for incoming requests
        self.pending_tasks: asyncio.Queue = asyncio.Queue()
        
        # Error tracking per agent
        self.agent_errors: Dict[str, List[Dict]] = {}
        
        # Available agents for routing
        self.available_agents = [
            "casual_chat_agent",
            "rag_agent",
            "memory_agent", 
            "notes_agent",
            "validation_agent",
            "planning_agent",
            "thinking_agent",
            "data_agent",
            "tool_agent",
            "summarize_agent",
            "translate_agent",
            "calculation_agent",
            "sw_agent"
        ]
        
        # Add custom message handlers
        self._message_handlers[MessageType.AGENT_ERROR] = self._handle_agent_error
        self._message_handlers[MessageType.AGENT_COMPLETED] = self._handle_agent_completed
        self._message_handlers[MessageType.QUERY] = self._handle_query
        
        # 統一事件管理器
        self._event_manager = get_event_manager() if HAS_UNIFIED_EVENTS else None

        # ── Sub-modules (God Class split) ────────────────────────────────────
        self.query_classifier = QueryClassifier(
            llm_service=self.llm_service,
            debug_service=_debug,
        )
        self.quality_controller = QualityController(
            llm_service=self.llm_service,
            debug_service=_debug,
            broadcast_thinking_fn=self._broadcast_thinking,
        )

        logger.info("ManagerAgent initialized")
    
    async def _broadcast_thinking(self, session_id: str, content: Dict[str, Any], task_id: str = None):
        """Helper to broadcast thinking steps using UnifiedEventManager"""
        message = content.get("status", content.get("message", "Thinking..."))
        
        # 優先使用統一事件管理器
        if self._event_manager and session_id:
            await self._event_manager.emit_thinking(
                session_id=session_id,
                task_id=task_id or "unknown",
                agent_name=self.agent_name,
                message=message,
                data=content
            )
        else:
            # Fallback to legacy broadcast
            await self.ws_manager.broadcast_agent_activity({
                "type": "thinking",
                "agent": self.agent_name,
                "session_id": session_id,
                "task_id": task_id,
                "content": content,
                "timestamp": datetime.now().isoformat()
            })
    
    # ============== Manager Double-Check: Validation & Retry ==============

    async def _manager_validate_response(
        self,
        query: str,
        response_text: str,
        sources: list = None,
        workflow: str = "unknown",
        session_id: str = None,
        task_id: str = None,
    ):
        """LLM quality validation — delegates to QualityController"""
        return await self.quality_controller.validate_response(
            query, response_text, sources, workflow, session_id, task_id
        )

    async def _manager_retry_with_feedback(
        self,
        query: str,
        original_response: str,
        validation_result,
        context: str = "",
        sources: list = None,
        session_id: str = None,
        task_id: str = None,
    ) -> str:
        """Targeted retry using validation feedback — delegates to QualityController"""
        return await self.quality_controller.retry_with_feedback(
            query, original_response, validation_result, context, sources, session_id, task_id
        )

    async def start(self):
        """Start the manager agent"""
        await super().start()

        # Start task processing loop
        asyncio.create_task(self._task_processing_loop())
        
        logger.info("ManagerAgent started and task processing loop running")
    
    async def _task_processing_loop(self):
        """Process pending tasks"""
        while self.is_running and not self.should_stop:
            try:
                # Get next task with timeout
                try:
                    task = await asyncio.wait_for(
                        self.pending_tasks.get(),
                        timeout=1.0
                    )
                    await self._route_task(task)
                except asyncio.TimeoutError:
                    continue
                    
            except Exception as e:
                logger.error(f"Error in task processing loop: {e}")
    
    async def process_task(self, task: TaskAssignment) -> Any:
        """
        Process a task - for manager, this means routing it appropriately.
        
        For user_query tasks, this orchestrates the full multi-agent workflow:
        1. Classify query type (casual_chat, simple_rag, complex_planning)
        2. Route to appropriate workflow
        3. Return response
        """
        if task.task_type == "user_query":
            return await self._handle_user_query(task)
        else:
            return await self._route_task(task)
    
    async def _classify_query(self, query: str, task_id: str) -> QueryClassification:
        """Classify user query — delegates to QueryClassifier"""
        return await self.query_classifier.classify(query, task_id)

    async def _handle_knowledge_inventory(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        Handle knowledge base inventory requests.
        Lists all available knowledge bases with their details.
        """
        from services.vectordb_manager import vectordb_manager
        
        task_id = task.task_id
        query = task.input_data.get("query", task.description)
        chat_history = task.input_data.get("chat_history", [])
        
        logger.info(f"[Manager] Knowledge inventory request: {query[:50]}...")
        
        # Emit start event
        if HAS_EVENT_BUS and event_bus:
            await event_bus.update_status(
                self.agent_name,
                AgentState.WORKING,
                task_id=task_id,
                message="Listing knowledge bases..."
            )
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "thinking",
            "agent": self.agent_name,
            "source": self.agent_name,
            "content": {"status": "Listing available knowledge bases"},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        try:
            databases = vectordb_manager.list_databases()
            
            if not databases:
                response_text = "目前沒有任何知識庫。您可以通過上傳文件來創建新的知識庫。"
            else:
                # Build a nice response
                lines = ["## 📚 可用知識庫清單\n"]
                for db in databases:
                    name = db.get("name", "Unknown")
                    description = db.get("description", "No description")
                    doc_count = db.get("document_count", 0)
                    created = db.get("created_at", "")[:10] if db.get("created_at") else ""
                    
                    lines.append(f"### 📁 **{name}**")
                    if description:
                        lines.append(f"- 描述: {description}")
                    lines.append(f"- 文件數量: {doc_count}")
                    if created:
                        lines.append(f"- 創建日期: {created}")
                    lines.append("")
                
                lines.append("\n---")
                lines.append("💡 **提示**: 您可以詢問任何知識庫中的內容，例如：")
                lines.append(f'- "搜尋 {databases[0]["name"]} 關於 XXX 的資料"')
                lines.append('- "我的文件中有什麼關於 YYY 的內容？"')
                
                response_text = "\n".join(lines)
            
            await self.ws_manager.broadcast_agent_activity({
                "type": "task_completed",
                "agent": self.agent_name,
                "source": self.agent_name,
                "content": {"workflow": "knowledge_inventory", "db_count": len(databases)},
                "timestamp": datetime.now().isoformat(),
                "priority": 1
            })
            
            return {
                "response": response_text,
                "agents_involved": ["manager_agent"],
                "sources": [],
                "workflow": "knowledge_inventory",
                "metadata": {
                    "databases": databases,
                    "count": len(databases)
                }
            }
            
        except Exception as e:
            logger.error(f"[Manager] Knowledge inventory error: {e}")
            return {
                "response": f"抱歉，無法獲取知識庫清單：{str(e)}",
                "agents_involved": ["manager_agent"],
                "sources": [],
                "workflow": "knowledge_inventory",
                "error": str(e)
            }
    
    async def _handle_casual_chat(self, task: TaskAssignment) -> Dict[str, Any]:
        """Handle a casual chat message via the casual_chat_agent"""
        from agents.core.casual_chat_agent import get_casual_chat_agent
        
        task_id = task.task_id
        query = task.input_data.get("query", task.description)
        
        logger.info(f"[Manager] Routing to casual_chat_agent: {query[:30]}...")
        
        # Emit routing event
        if HAS_EVENT_BUS and event_bus:
            await event_bus.emit(
                EventType.TASK_ASSIGNED,
                "casual_chat_agent",
                {"task": "casual_response", "query": query[:50]},
                task_id=task_id
            )
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "task_assigned",
            "agent": "casual_chat_agent",
            "source": self.agent_name,
            "target": "casual_chat_agent",
            "content": {"task": "casual_response"},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        # Get casual chat agent and process
        casual_agent = get_casual_chat_agent()
        result = await casual_agent.process_task(task)
        
        # Check for Escalation (if Casual Chat declined to answer)
        if result.get("status") == "escalate":
            reason = result.get("reason", "Unknown")
            logger.info(f"[Manager] Casual Chat escalated query: {reason}. Rerouting to Simple RAG.")
            
            # Notify UI of rerouting
            await self.ws_manager.broadcast_agent_activity({
                "type": "task_rerouted",
                "agent": "manager_agent",
                "source": "casual_chat_agent",
                "target": "rag_agent",
                "content": {"reason": reason},
                "timestamp": datetime.now().isoformat(),
                "priority": 1
            })
            
            # Re-route to general knowledge (not RAG, since user is asking about AI capabilities)
            return await self._handle_general_knowledge(task)

        await self.ws_manager.broadcast_agent_activity({
            "type": "task_completed",
            "agent": "casual_chat_agent",
            "source": "casual_chat_agent",
            "target": self.agent_name,
            "content": {"workflow": "casual_chat"},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        # Manager wraps the response
        result["agents_involved"] = ["manager_agent", "casual_chat_agent"]
        return result
    
    async def _handle_user_query(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        Handle a user query through smart routing.
        
        Workflow:
        1. Check if intent/handler provided from EntryClassifier (config-driven)
        2. If handler exists, use handler-based routing (no extra classification needed)
        3. Otherwise, fall back to internal classification
        """
        logger.info(f"[Manager] Handling user query: {task.description[:50]}...")
        
        query = task.input_data.get("query", task.description)
        use_rag = task.input_data.get("use_rag", True)
        task_id = task.task_id
        session_id = task.input_data.get("session_id") or task.input_data.get("conversation_id")
        
        # Check for intent/handler from EntryClassifier (config-driven routing)
        intent = task.input_data.get("intent")
        handler = task.input_data.get("handler")
        matched_by = task.input_data.get("matched_by", "internal")
        
        logger.info(f"[Manager] Received intent={intent}, handler={handler}, matched_by={matched_by}, session_id={session_id}")
        
        # If handler is provided, use handler-based routing (fast path)
        if handler:
            logger.info(f"[Manager] Handler-based routing: {handler} (intent: {intent}, matched_by: {matched_by})")
            
            # Debug trace: record routing decision
            if _debug:
                _debug.record_routing(
                    task_id=task_id,
                    classification={
                        "route": "handler_based",
                        "handler": handler,
                        "intent": intent,
                        "matched_by": matched_by
                    },
                    session_id=session_id or ""
                )
            
            # Emit start event
            if HAS_EVENT_BUS and event_bus:
                await event_bus.update_status(
                    self.agent_name,
                    AgentState.WORKING,
                    task_id=task_id,
                    message=f"Executing handler: {handler}"
                )
            
            await self._broadcast_thinking(session_id, {
                "status": f"Intent: {intent}, Handler: {handler}",
                "matched_by": matched_by
            }, task_id)
            
            # Handler dispatch - map handler names from intents.yaml to methods
            handler_map = {
                # Knowledge
                "list_knowledge_bases": self._handle_knowledge_inventory,
                "knowledge_inventory": self._handle_knowledge_inventory,
                "rag_search": self._handle_simple_rag_query,
                "search_knowledge": self._handle_simple_rag_query,
                # Processing
                "calculation": self._handle_calculation,
                "calculate": self._handle_calculation,
                "translation": self._handle_translation,
                "translate": self._handle_translation,
                "summarization": self._handle_summarization,
                "summarize": self._handle_summarization,
                # SolidWorks
                "solidworks_api": self._handle_solidworks_api,
                "sw_api": self._handle_solidworks_api,
                # Planning
                "planning": self._handle_complex_query,
                "plan_complex": self._handle_complex_query,
                # Accounting
                "accounting": self._handle_accounting,
                # General
                "general_answer": self._handle_general_knowledge,
                "casual_response": self._handle_casual_chat,
            }
            
            handler_func = handler_map.get(handler)
            if handler_func:
                return await handler_func(task)
            else:
                logger.warning(f"[Manager] Unknown handler '{handler}', falling back to classification")
        
        # Emit start event
        if HAS_EVENT_BUS and event_bus:
            await event_bus.update_status(
                self.agent_name,
                AgentState.WORKING,
                task_id=task_id,
                message=f"Classifying query..."
            )
        
        # Step 1: Classify the query
        classification = await self._classify_query(query, task_id)
        logger.info(f"[Manager] Query classified as: {classification.query_type} ({classification.reasoning})")
        
        # Debug trace: record classification result
        if _debug:
            _debug.record_routing(
                task_id=task_id,
                classification={
                    "query_type": classification.query_type,
                    "reasoning": classification.reasoning,
                    "confidence": classification.confidence
                },
                session_id=session_id or ""
            )
        
        await self._broadcast_thinking(session_id, {
            "status": f"Query type: {classification.query_type}",
            "reasoning": classification.reasoning
        }, task_id)
        
        # Step 2: Route based on classification
        if classification.query_type == "casual_chat":
            return await self._handle_casual_chat(task)
        elif classification.query_type == "knowledge_rag":
            # Only use RAG when specifically searching user's documents
            return await self._handle_simple_rag_query(task)
        elif classification.query_type == "general_knowledge":
            # Use thinking agent for general knowledge questions (no RAG)
            return await self._handle_general_knowledge(task)
        elif classification.query_type == "calculation":
            return await self._handle_calculation(task)
        elif classification.query_type == "translation":
            return await self._handle_translation(task)
        elif classification.query_type == "summarization":
            return await self._handle_summarization(task)
        elif classification.query_type == "solidworks_api":
            return await self._handle_solidworks_api(task)
        elif classification.query_type == "accounting":
            return await self._handle_accounting(task)
        elif classification.query_type == "complex_planning":
            return await self._handle_complex_query(task)
        else:
            # [NO FALLBACK] This should never happen if LLM is working correctly
            raise ValueError(f"Invalid query type from classification: {classification.query_type}")
    
    async def _handle_general_knowledge(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        Handle general knowledge questions using ThinkingAgent (no RAG needed).
        LLM can answer from its training data.
        """
        query = task.input_data.get("query", task.description)
        task_id = task.task_id
        chat_history = task.input_data.get("chat_history", [])
        user_context = task.input_data.get("user_context", "")
        session_id = task.input_data.get("session_id") or task.input_data.get("conversation_id")
        
        logger.info(f"[Manager] General knowledge query - direct LLM answer")
        
        agents_involved = ["manager_agent"]
        
        await self._broadcast_thinking(session_id, {
            "status": "Processing general knowledge query...",
            "task": "general_knowledge",
            "query": query[:100]
        }, task_id)
        
        # Build chat history context
        history_context = ""
        if chat_history:
            history_parts = []
            for exchange in chat_history[-5:]:
                if "human" in exchange:
                    history_parts.append(f"User: {exchange['human']}")
                if "assistant" in exchange:
                    history_parts.append(f"Assistant: {exchange['assistant']}")
            if history_parts:
                history_context = "Previous conversation:\n" + "\n".join(history_parts) + "\n\n"
        
        # Memory injection - get user context from Cerebro
        memory_context = ""
        user_id = task.input_data.get("user_id", "default")
        try:
            from services.cerebro_memory import get_cerebro
            cerebro = get_cerebro()
            memory_context = cerebro.get_context_for_prompt(user_id, query)
            if memory_context and _debug:
                _debug.record_memory_injection(
                    agent_name="manager_agent",
                    task_id=task_id,
                    memory_context=memory_context,
                    session_id=session_id or ""
                )
        except Exception as e:
            logger.debug(f"Memory injection skipped: {e}")
        
        # Direct LLM call for general knowledge
        # Modified: 2026-02-06 - 移除 user_context（可能包含跨 session 的 RAG 內容）
        # Modified: 2026-02-17 - 加入 memory_context 注入
        prompt = f"""You are a helpful AI assistant. Answer this question clearly and informatively.

{memory_context}

{history_context}
Question: {query}

Guidelines:
- Provide a clear, accurate answer
- Match the language of the question (if asked in Chinese, respond in Chinese)
- Be concise but informative
- If it's a greeting (like "Hello"), just respond naturally with a greeting
- Respect any user preferences mentioned in the context above"""
        
        # Debug trace: record LLM call
        if _debug:
            _debug.record_agent_input(
                agent_name="manager_agent",
                task_id=task_id,
                input_data={"query": query, "workflow": "general_knowledge"},
                session_id=session_id or ""
            )
        
        llm_result = await self.llm_service.generate(prompt=prompt)
        response_text = llm_result.content if hasattr(llm_result, 'content') else str(llm_result)
        
        # Debug trace: record output
        if _debug:
            _debug.record_agent_output(
                agent_name="manager_agent",
                task_id=task_id,
                output_data={"response": response_text[:500], "workflow": "general_knowledge"},
                session_id=session_id or ""
            )
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "task_completed",
            "agent": "manager_agent",
            "session_id": session_id,
            "task_id": task_id,
            "content": {"workflow": "general_knowledge", "status": "Completed"},
            "timestamp": datetime.now().isoformat()
        })
        
        # Manager validation for non-trivial responses (skip greetings/short answers)
        quality_score = 0.8
        if len(response_text) > 100:
            try:
                validation = await self._manager_validate_response(
                    query=query,
                    response_text=response_text,
                    sources=[],
                    workflow="general_knowledge",
                    session_id=session_id,
                    task_id=task_id
                )
                
                quality_score = validation.get("quality_score", 0.8)
                
                if validation.get("should_retry") and not validation.get("passed"):
                    logger.info(f"[Manager] General knowledge validation failed ({quality_score:.2f}), retrying...")
                    
                    improved_response = await self._manager_retry_with_feedback(
                        query=query,
                        original_response=response_text,
                        validation_result=validation,
                        context=memory_context,
                        sources=[],
                        session_id=session_id,
                        task_id=task_id
                    )
                    
                    retry_validation = await self._manager_validate_response(
                        query=query,
                        response_text=improved_response,
                        sources=[],
                        workflow="general_knowledge_retry",
                        session_id=session_id,
                        task_id=task_id
                    )
                    
                    retry_score = retry_validation.get("quality_score", 0.5)
                    if retry_score > quality_score:
                        logger.info(f"[Manager] General retry improved: {quality_score:.2f} → {retry_score:.2f}")
                        response_text = improved_response
                        quality_score = retry_score
                        agents_involved.append("manager_retry")
                    
            except Exception as e:
                logger.warning(f"Manager validation skipped for general knowledge: {e}")
        
        return {
            "response": response_text,
            "agents_involved": agents_involved,
            "sources": [],
            "workflow": "general_knowledge",
            "quality_score": quality_score,
            "manager_validated": len(response_text) > 100
        }
    
    # ====================================================== #
    # Accounting handler
    # ====================================================== #

    _ACCOUNTING_TOOL_PROMPT = """You are an accounting assistant. Decide which tool to call based on the user message.

Available tools (return the tool name + JSON parameters):
1. accounting_create_account - Create ledger account
   params: {"name": "str", "account_type": "general|bank|cash|receivable|payable", "currency": "HKD", "description": ""}
2. accounting_list_accounts - List all accounts  (no params)
3. accounting_add_transaction - Add income/expense
   params: {"account_id": int, "type": "income|expense|transfer|adjustment", "amount": float, "description": "", "reference": "", "counterparty": "", "category": "", "transaction_date": "YYYY-MM-DD"}
4. accounting_update_transaction - Edit a pending transaction
   params: {"transaction_id": int, "description": "", "amount": float, "category": "", "counterparty": "", "reference": "", "transaction_date": ""}
5. accounting_list_transactions - List/filter transactions
   params: {"account_id": int|null, "status": "pending|reconciled|voided"|null, "start_date": ""|null, "end_date": ""|null, "limit": 100}
6. accounting_reconcile - Reconcile transactions (對數)
   params: {"transaction_ids": [int, ...]}
7. accounting_void - Void a transaction
   params: {"transaction_id": int}
8. accounting_audit_log - View audit trail
   params: {"entity_type": "account|transaction"|null, "entity_id": int|null, "limit": 100}
9. accounting_summary - Account summary / dashboard of one account
   params: {"account_id": int}
10. accounting_dashboard - High-level overview  (no params)
11. accounting_create_category - Create category
    params: {"name": "str", "description": ""}
12. accounting_list_categories - List categories  (no params)
13. accounting_set_budget - Set budget (預算)
    params: {"account_id": int, "period": "YYYY-MM", "amount": float, "category": ""}
14. accounting_check_budget - Check budget status
    params: {"account_id": int, "period": "YYYY-MM"}
15. accounting_close_period - Month-end close (月結)
    params: {"period": "YYYY-MM", "notes": ""}
16. accounting_list_periods - List periods  (no params)
17. accounting_import_csv - Bulk import CSV
    params: {"account_id": int, "csv_text": "type,amount,description,...\\n..."}
18. accounting_create_invoice - Create invoice
    params: {"account_id": int, "invoice_number": "str", "amount": float, "counterparty": "", "due_date": "YYYY-MM-DD", "description": "", "tax_amount": 0.0, "currency": "HKD"}
19. accounting_list_invoices - List invoices
    params: {"account_id": int|null, "status": "unpaid|paid|overdue|cancelled"|null}
20. accounting_mark_invoice_paid - Mark invoice paid
    params: {"invoice_id": int}
21. accounting_archive_account - Archive/delete account
    params: {"account_id": int}

RULES:
- Return EXACTLY ONE line: tool_name|{"param": value, ...}
- Only include parameters you can extract; omit unknowns.
- If the user just wants information (list, dashboard, summary), use the appropriate list/dashboard tool.
- If you cannot determine which tool, return: accounting_dashboard|{}
- Amount is in dollars (e.g. 500.00), NOT cents.
- Do NOT include any explanation, only the tool_name|{json} line."""

    async def _handle_accounting(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        Handle accounting requests by selecting + executing the right accounting tool.

        Flow: LLM picks tool & params → ToolAgent executes → format response.
        """
        query = task.input_data.get("query", task.description)
        task_id = task.task_id
        session_id = task.input_data.get("session_id") or task.input_data.get("conversation_id")

        logger.info(f"[Manager] Accounting query: {query[:80]}")

        agents_involved = ["manager_agent"]

        # Broadcast thinking
        await self._broadcast_thinking(session_id, {
            "status": "Processing accounting request…",
            "query": query[:100]
        }, task_id)

        # Step 1 – Ask LLM which tool to call + extract parameters
        selection_prompt = f"{self._ACCOUNTING_TOOL_PROMPT}\n\nUser message: \"{query}\""

        llm_result = await self.llm_service.generate(
            prompt=selection_prompt,
            system_message="You are an accounting tool router. Reply with ONLY: tool_name|{{json params}}",
            temperature=0.1,
            session_id=self.agent_name
        )
        raw = (llm_result.content if hasattr(llm_result, "content") else str(llm_result)).strip()

        logger.info(f"[Manager] Accounting LLM selection: {raw}")

        # Parse tool_name|{json}
        import json as _json
        parts = raw.split("|", 1)
        tool_name = parts[0].strip()
        try:
            parameters = _json.loads(parts[1]) if len(parts) > 1 else {}
        except (_json.JSONDecodeError, IndexError):
            parameters = {}

        # Validate tool_name
        tool_agent = self.registry.get_agent("tool_agent")
        if not tool_agent:
            return {
                "response": "會計工具暫時無法使用，請稍後再試。(Tool agent unavailable)",
                "agents_involved": agents_involved,
                "sources": [],
                "workflow": "accounting"
            }

        if tool_name not in getattr(tool_agent, "tools", {}):
            logger.warning(f"[Manager] LLM selected unknown tool '{tool_name}', falling back to dashboard")
            tool_name = "accounting_dashboard"
            parameters = {}

        agents_involved.append("tool_agent")

        await self.ws_manager.broadcast_agent_activity({
            "type": "task_assigned",
            "agent": "tool_agent",
            "source": self.agent_name,
            "target": "tool_agent",
            "content": {"task": "accounting", "tool": tool_name, "query": query[:100]},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })

        # Step 2 – Execute via ToolAgent
        acct_task = TaskAssignment(
            task_id=task_id,
            task_type="execute",
            description=query,
            input_data={
                "tool_name": tool_name,
                "parameters": parameters,
                "session_id": session_id,
            }
        )
        tool_result = await tool_agent.process_task(acct_task)

        # Step 3 – Format a human-friendly response via LLM
        result_json = _json.dumps(tool_result, ensure_ascii=False, default=str)

        format_prompt = f"""The user asked: "{query}"
We executed accounting tool `{tool_name}` and got this result:
{result_json[:3000]}

Write a clear, concise answer in the SAME language as the user's message.
If the result contains a list, format it nicely.
If there was an error, explain it helpfully."""

        formatted = await self.llm_service.generate(
            prompt=format_prompt,
            system_message=(
                "You are a helpful accounting assistant. "
                "Respond in the same language the user used. "
                "Be concise. Use bullet points or tables when appropriate."
            ),
            temperature=0.3,
            session_id=session_id or self.agent_name
        )
        response_text = formatted.content if hasattr(formatted, "content") else str(formatted)

        return {
            "response": response_text,
            "agents_involved": agents_involved,
            "sources": [{"tool": tool_name, "parameters": parameters}],
            "workflow": "accounting",
            "tool_result": tool_result
        }

    async def _handle_calculation(self, task: TaskAssignment) -> Dict[str, Any]:
        """Handle calculation/math requests using CalculationAgent"""
        query = task.input_data.get("query", task.description)
        task_id = task.task_id
        
        logger.info(f"[Manager] Calculation query - using CalculationAgent")
        
        agents_involved = ["manager_agent"]
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "task_assigned",
            "agent": "calculation_agent",
            "source": self.agent_name,
            "target": "calculation_agent",
            "content": {"task": "calculate", "query": query[:100]},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        agents_involved.append("calculation_agent")
        
        calc_agent = self.registry.get_agent("calculation_agent")
        if calc_agent:
            calc_task = TaskAssignment(
                task_id=task_id,
                task_type="calculate",
                description=query,
                input_data={"expression": query}
            )
            result = await calc_agent.process_task(calc_task)
            response_text = result.get("response", result.get("result", str(result)))
        else:
            response_text = "Calculation agent not available."
        
        return {
            "response": response_text,
            "agents_involved": agents_involved,
            "sources": [],
            "workflow": "calculation"
        }
    
    async def _handle_translation(self, task: TaskAssignment) -> Dict[str, Any]:
        """Handle translation requests using TranslateAgent"""
        query = task.input_data.get("query", task.description)
        task_id = task.task_id
        
        logger.info(f"[Manager] Translation query - using TranslateAgent")
        
        agents_involved = ["manager_agent"]
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "task_assigned",
            "agent": "translate_agent",
            "source": self.agent_name,
            "target": "translate_agent",
            "content": {"task": "translate", "query": query[:100]},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        agents_involved.append("translate_agent")
        
        translate_agent = self.registry.get_agent("translate_agent")
        if translate_agent:
            translate_task = TaskAssignment(
                task_id=task_id,
                task_type="translate",
                description=query,
                input_data={"text": query}
            )
            result = await translate_agent.process_task(translate_task)
            response_text = result.get("response", result.get("translation", str(result)))
        else:
            response_text = "Translation agent not available."
        
        return {
            "response": response_text,
            "agents_involved": agents_involved,
            "sources": [],
            "workflow": "translation"
        }
    
    async def _handle_summarization(self, task: TaskAssignment) -> Dict[str, Any]:
        """Handle summarization requests using SummarizeAgent"""
        query = task.input_data.get("query", task.description)
        task_id = task.task_id
        
        logger.info(f"[Manager] Summarization query - using SummarizeAgent")
        
        agents_involved = ["manager_agent"]
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "task_assigned",
            "agent": "summarize_agent",
            "source": self.agent_name,
            "target": "summarize_agent",
            "content": {"task": "summarize", "query": query[:100]},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        agents_involved.append("summarize_agent")
        
        summarize_agent = self.registry.get_agent("summarize_agent")
        if summarize_agent:
            summarize_task = TaskAssignment(
                task_id=task_id,
                task_type="summarize",
                description=query,
                input_data={"text": query}
            )
            result = await summarize_agent.process_task(summarize_task)
            response_text = result.get("response", result.get("summary", str(result)))
        else:
            response_text = "Summarization agent not available."
        
        return {
            "response": response_text,
            "agents_involved": agents_involved,
            "sources": [],
            "workflow": "summarization"
        }

    async def _handle_solidworks_api(self, task: TaskAssignment) -> Dict[str, Any]:
        """Handle SolidWorks API queries using SWAgent"""
        query = task.input_data.get("query", task.description)
        task_id = task.task_id
        session_id = task.input_data.get("session_id") or task.input_data.get("conversation_id")
        
        logger.info(f"[Manager] SolidWorks API query - using SWAgent: {query[:50]}...")
        
        agents_involved = ["manager_agent"]
        
        await self._broadcast_thinking(session_id, {
            "status": "Processing SolidWorks API query...",
            "task": "solidworks_api"
        }, task_id)
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "task_assigned",
            "agent": "sw_agent",
            "source": self.agent_name,
            "target": "sw_agent",
            "content": {"task": "search", "query": query[:100]},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        agents_involved.append("sw_agent")
        
        sw_agent = self.registry.get_agent("sw_agent")
        if sw_agent:
            sw_task = TaskAssignment(
                task_id=task_id,
                task_type="search",
                description=query,
                input_data={"query": query, "type": "search"}
            )
            result = await sw_agent.process_task(sw_task)
            response_text = result.get("response", str(result))
            sources = result.get("search_results", {})
            
            # Format sources for frontend display
            formatted_sources = []
            if isinstance(sources, dict):
                if sources.get("documents"):
                    for doc in sources["documents"][:3]:
                        formatted_sources.append({
                            "title": doc.get("title", "SolidWorks API Doc"),
                            "content": doc.get("content", "")[:300],
                            "source": "SolidWorks API Database",
                            "score": 0.9
                        })
                if sources.get("code_examples"):
                    for code in sources["code_examples"][:2]:
                        formatted_sources.append({
                            "title": f"Code Example: {code.get('title', 'Untitled')}",
                            "content": f"Language: {code.get('language', 'Unknown')}\n{code.get('code', '')[:200]}...",
                            "source": "SolidWorks Code Examples",
                            "score": 0.85
                        })
        else:
            response_text = "SolidWorks API agent not available."
            formatted_sources = []
        
        return {
            "response": response_text,
            "agents_involved": agents_involved,
            "sources": formatted_sources,
            "workflow": "solidworks_api"
        }

    async def _handle_simple_rag_query(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        Handle RAG query with ReAct Loop and Metacognition.
        
        Implements:
        1. Think -> Act -> Observe -> Reflect loop
        2. Self-evaluation and retry if quality is low
        3. Memory integration for context
        
        This is the AGENTIC approach (not a simple pipeline).
        """
        query = task.input_data.get("query", task.description)
        task_id = task.task_id
        use_react = task.input_data.get("use_react", True)
        session_id = task.input_data.get("session_id", task_id)
        user_id = task.input_data.get("user_id", "default")
        
        agents_involved = ["manager_agent"]
        sources = []
        
        start_time = datetime.now()
        
        # Emit start event
        if HAS_EVENT_BUS and event_bus:
            await event_bus.update_status(
                self.agent_name,
                AgentState.WORKING,
                task_id=task_id,
                message=f"Agentic RAG query with ReAct..."
            )
        
        # ============== Memory Integration ==============
        try:
            from agents.shared_services.memory_integration import get_memory_manager, TaskCategory, EpisodeOutcome
            memory_manager = get_memory_manager()
            
            # Get conversation context
            # 用戶偏好跨 session 保留，但具體問題不跨 session
            # Modified: 2026-02-06 - 記憶分離
            memory_context = memory_manager.build_context_prompt(
                session_id=session_id,
                user_id=user_id,
                current_query=query,
                task_category=TaskCategory.RAG_SEARCH,
                include_user_preferences=True,          # 用戶偏好跨 session
                include_cross_session_episodes=False    # 具體問題不跨 session
            )
        except Exception as e:
            logger.warning(f"Memory integration failed: {e}")
            memory_context = ""
            memory_manager = None
        
        # Also inject Cerebro personal memory
        try:
            from services.cerebro_memory import get_cerebro
            cerebro = get_cerebro()
            cerebro_context = cerebro.get_context_for_prompt(user_id, query)
            if cerebro_context:
                memory_context = cerebro_context + "\n\n" + memory_context
                if _debug:
                    _debug.record_memory_injection(
                        agent_name="manager_agent",
                        task_id=task_id,
                        memory_context=cerebro_context,
                        session_id=session_id
                    )
        except Exception as e:
            logger.debug(f"Cerebro memory injection skipped: {e}")
        
        # Debug trace: record RAG agent input
        if _debug:
            _debug.record_agent_input(
                agent_name="rag_agent",
                task_id=task_id,
                input_data={"query": query, "workflow": "agentic_rag", "has_memory": bool(memory_context)},
                session_id=session_id,
                source="manager_agent"
            )
        
        logger.info("[Manager] → Starting Agentic RAG with ReAct Loop...")
        
        await self._broadcast_thinking(session_id, {
            "status": "Initiating ReAct reasoning loop...",
            "workflow": "agentic_rag"
        }, task_id)
        
        if use_react:
            # ============== ReAct Loop Mode ==============
            # [NO FALLBACK] Errors propagate for testing visibility
            from agents.core.react_loop import get_react_loop, ActionType
            
            react_loop = get_react_loop(max_iterations=3)
            
            # Register RAG search tool
            async def rag_search_tool(search_query: str) -> Dict[str, Any]:
                """RAG search tool for ReAct"""
                rag_agent = self.registry.get_agent("rag_agent")
                if not rag_agent:
                    return {"content": "RAG agent not available", "sources": []}
                
                rag_task = TaskAssignment(
                    task_id=f"{task_id}-search",
                    task_type="query_knowledge",
                    description=search_query,
                    input_data={"query": search_query}
                )
                
                # Broadcast search event
                await self.ws_manager.broadcast_agent_activity({
                    "type": "task_assigned",
                    "agent": "rag_agent",
                    "source": self.agent_name,
                    "target": "rag_agent",
                    "content": {"task": "search", "query": search_query[:100]},
                    "timestamp": datetime.now().isoformat(),
                    "priority": 1
                })
                
                result = await rag_agent.process_task(rag_task)
                
                if isinstance(result, dict):
                    return {
                        "content": result.get("context", ""),
                        "sources": result.get("sources", [])
                    }
                return {"content": str(result), "sources": []}
            
            react_loop.register_tool(ActionType.SEARCH, rag_search_tool)
            
            # Define step callback for real-time updates
            async def on_react_step(step):
                await self.ws_manager.broadcast_agent_activity({
                    "type": "thinking",
                    "agent": self.agent_name,
                    "source": self.agent_name,
                    "content": {
                        "step": step.step_number,
                        "thought": step.thought[:200],
                        "action": step.action.value
                    },
                    "timestamp": datetime.now().isoformat(),
                    "priority": 1
                })
            
            react_loop.on_step_callback = on_react_step
            agents_involved.append("react_loop")
            
            # Execute ReAct loop
            result = await react_loop.run(
                query=query,
                initial_context=memory_context
            )
            
            response_text = result.final_answer
            sources = result.sources
            reasoning_trace = result.reasoning_trace
            
            logger.info(f"[Manager] ReAct completed in {result.total_iterations} iterations")
        
        # [NO FALLBACK] ReAct loop is the ONLY path - no simple RAG fallback
        # If ReAct fails, the error should propagate for visibility
        # 
        # [REMOVED] The entire "if not use_react:" fallback block has been removed
        # All RAG queries now go through ReAct loop for consistent behavior
        
        # ============== Manager Double-Check: Validate & Retry ==============
        quality_score = 0.7
        should_retry = False
        retry_performed = False
        full_eval = None
        
        try:
            # Step 1: Use existing Metacognition for quick check
            from agents.core.metacognition_engine import get_self_evaluator, get_strategy_adapter
            
            evaluator = get_self_evaluator()
            quick_score, needs_full_eval = await evaluator.quick_evaluate(query, response_text)
            quality_score = quick_score
            
            if needs_full_eval and quick_score < 0.6:
                # Step 2: Full metacognition evaluation
                full_eval = await evaluator.evaluate_response(
                    query=query,
                    response=response_text,
                    context=memory_context,
                    sources=sources
                )
                quality_score = full_eval.score
                should_retry = full_eval.should_retry
            
            # Step 3: Manager's own validation (the real double-check)
            validation = await self._manager_validate_response(
                query=query,
                response_text=response_text,
                sources=sources,
                workflow="agentic_rag",
                session_id=session_id,
                task_id=task_id
            )
            
            # Use the lower of metacognition and manager validation scores
            manager_score = validation.get("quality_score", 0.7)
            quality_score = min(quality_score, manager_score)
            
            # Step 4: Retry if either check says quality is too low
            if validation.get("should_retry") or (should_retry and quality_score < 0.6):
                logger.info(f"[Manager] Quality too low ({quality_score:.2f}), retrying with feedback...")
                
                improved_response = await self._manager_retry_with_feedback(
                    query=query,
                    original_response=response_text,
                    validation_result=validation,
                    context=memory_context,
                    sources=sources,
                    session_id=session_id,
                    task_id=task_id
                )
                
                # Validate the retry
                retry_validation = await self._manager_validate_response(
                    query=query,
                    response_text=improved_response,
                    sources=sources,
                    workflow="agentic_rag_retry",
                    session_id=session_id,
                    task_id=task_id
                )
                
                retry_score = retry_validation.get("quality_score", 0.5)
                
                # Use improved version if it's actually better
                if retry_score > quality_score:
                    logger.info(f"[Manager] Retry improved quality: {quality_score:.2f} → {retry_score:.2f}")
                    response_text = improved_response
                    quality_score = retry_score
                    retry_performed = True
                    agents_involved.append("manager_retry")
                else:
                    logger.info(f"[Manager] Retry did not improve ({retry_score:.2f} vs {quality_score:.2f}), keeping original")
            
            # Record experience
            try:
                adapter = get_strategy_adapter()
                adapter.record_outcome(
                    query=query,
                    strategy="react_loop",
                    evaluation=full_eval if needs_full_eval else None
                ) if needs_full_eval else None
            except Exception:
                pass
            
        except Exception as e:
            logger.warning(f"Manager validation failed: {e}")
        
        # ============== Store Memory ==============
        try:
            if memory_manager:
                # Update working memory
                memory_manager.update_context(
                    session_id,
                    query=query,
                    response=response_text[:500]
                )
                
                # Store episode
                outcome = (
                    EpisodeOutcome.SUCCESS if quality_score > 0.7
                    else EpisodeOutcome.PARTIAL if quality_score > 0.4
                    else EpisodeOutcome.FAILURE
                )
                
                duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)
                
                memory_manager.store_episode(
                    session_id=session_id,
                    user_id=user_id,
                    query=query,
                    response=response_text,
                    task_category=TaskCategory.RAG_SEARCH,
                    outcome=outcome,
                    quality_score=quality_score,
                    agents_involved=agents_involved,
                    sources_used=[s.get("title", "") for s in sources[:3]] if sources else [],
                    duration_ms=duration_ms
                )
        except Exception as e:
            logger.warning(f"Memory storage failed: {e}")
        
        # ============== Complete ==============
        if HAS_EVENT_BUS and event_bus:
            await event_bus.update_status(self.agent_name, AgentState.IDLE, message="Ready")
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "task_completed",
            "agent": self.agent_name,
            "source": self.agent_name,
            "content": {
                "workflow": "agentic_rag" if use_react else "simple_rag",
                "sources_count": len(sources),
                "quality_score": quality_score
            },
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        return {
            "response": response_text,
            "agents_involved": agents_involved,
            "sources": sources,
            "workflow": "agentic_rag" if use_react else "simple_rag",
            "metadata": {
                "quality_score": quality_score,
                "used_react": use_react,
                "manager_validated": True,
                "retry_performed": retry_performed
            }
        }
    
    async def _handle_complex_query(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        Handle a complex query that requires planning and multi-step reasoning.
        This is the original full workflow.
        """
        logger.info(f"[Manager] Complex query - full planning workflow")
        
        query = task.input_data.get("query", task.description)
        use_rag = task.input_data.get("use_rag", True)
        task_id = task.task_id
        session_id = task.input_data.get("session_id") or task.input_data.get("conversation_id")
        
        agents_involved = ["manager_agent"]
        sources = []
        rag_context = ""
        memory_context = ""
        
        # Emit start event
        if HAS_EVENT_BUS and event_bus:
            await event_bus.update_status(
                self.agent_name,
                AgentState.WORKING,
                task_id=task_id,
                message=f"Handling query: {query[:50]}..."
            )
        
        # STEP 1: Planning - Analyze query and create plan
        logger.info("[Manager] → Planning Agent: Analyzing query...")
        
        if HAS_EVENT_BUS and event_bus:
            await event_bus.emit(
                EventType.TASK_ASSIGNED,
                "planning_agent",
                {"task": "analyze_query", "query": query[:100]},
                task_id=task_id
            )
            await event_bus.update_status(
                "planning_agent",
                AgentState.THINKING,
                task_id=task_id,
                message="Analyzing query complexity..."
            )
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "task_assigned",
            "agent": "planning_agent",
            "source": self.agent_name,
            "target": "planning_agent",
            "content": {"task": "analyze_query", "query": query[:100]},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        agents_involved.append("planning_agent")
        
        # Emit thinking event
        if HAS_EVENT_BUS and event_bus:
            await event_bus.emit_thinking(
                "planning_agent",
                "Analyzing query complexity and determining execution strategy...",
                step=1,
                task_id=task_id
            )
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "thinking",
            "agent": "planning_agent",
            "source": "planning_agent",
            "target": self.agent_name,
            "content": {"status": "Analyzing query complexity and determining execution strategy..."},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        # Check for interrupt
        if HAS_EVENT_BUS and event_bus and event_bus.is_interrupted(task_id):
            await event_bus.acknowledge_interrupt(self.agent_name, task_id)
            return {"response": "Task was interrupted", "status": "interrupted", "agents_involved": agents_involved}
        
        # === ACTUAL PLANNING LOGIC ===
        # Get the planning agent and create a real plan
        import time
        planning_start = time.time()
        
        planning_agent = self.registry.get_agent("planning_agent")
        if planning_agent:
            try:
                plan_task = TaskAssignment(
                    task_id=f"{task_id}_plan",
                    task_type="create_plan",
                    description=f"Create execution plan for: {query}",
                    input_data={"query": query, "use_rag": use_rag},
                    priority=1
                )
                plan_result = await planning_agent.process_task(plan_task)
                planning_time_ms = int((time.time() - planning_start) * 1000)
                
                # Broadcast planning result (collapsible in UI)
                await self.ws_manager.broadcast_agent_activity({
                    "type": "planning_result",
                    "agent": "planning_agent",
                    "source": "planning_agent",
                    "target": self.agent_name,
                    "content": {
                        "plan": plan_result.get("plan", {}),
                        "planning_time_ms": planning_time_ms,
                        "collapsible": True
                    },
                    "timestamp": datetime.now().isoformat(),
                    "priority": 1
                })
                logger.info(f"[Manager] Planning completed in {planning_time_ms}ms")
            except Exception as e:
                logger.warning(f"[Manager] Planning failed, continuing without plan: {e}")
                planning_time_ms = int((time.time() - planning_start) * 1000)
        else:
            planning_time_ms = 0
        
        # Update planning agent to idle
        if HAS_EVENT_BUS and event_bus:
            await event_bus.update_status("planning_agent", AgentState.IDLE, message="Ready")
        
        # STEP 2: RAG retrieval if needed
        if use_rag:
            logger.info("[Manager] → RAG Agent: Querying knowledge bases...")
            
            if HAS_EVENT_BUS and event_bus:
                await event_bus.emit(
                    EventType.RAG_QUERY,
                    "rag_agent",
                    {"query": query[:100]},
                    task_id=task_id
                )
                await event_bus.update_status(
                    "rag_agent",
                    AgentState.QUERYING_RAG,
                    task_id=task_id,
                    message="Searching knowledge bases..."
                )
            
            await self.ws_manager.broadcast_agent_activity({
                "type": "task_assigned",
                "agent": "rag_agent",
                "source": self.agent_name,
                "target": "rag_agent",
                "content": {"task": "retrieve_context", "query": query[:100]},
                "timestamp": datetime.now().isoformat(),
                "priority": 1
            })
            agents_involved.append("rag_agent")
            
            # Get RAG agent and query
            rag_agent = self.registry.get_agent("rag_agent")
            if rag_agent:
                if HAS_EVENT_BUS and event_bus:
                    await event_bus.emit_thinking(
                        "rag_agent",
                        "Searching across all knowledge bases...",
                        step=2,
                        task_id=task_id
                    )
                
                await self.ws_manager.broadcast_agent_activity({
                    "type": "thinking",
                    "agent": "rag_agent",
                    "source": "rag_agent",
                    "target": "vectordb",
                    "content": {"status": "Searching across all knowledge bases..."},
                    "timestamp": datetime.now().isoformat(),
                    "priority": 1
                })
                
                # Check for interrupt
                if HAS_EVENT_BUS and event_bus and event_bus.is_interrupted(task_id):
                    await event_bus.acknowledge_interrupt(self.agent_name, task_id)
                    return {"response": "Task was interrupted", "status": "interrupted", "agents_involved": agents_involved}
                
                # Execute RAG query (this takes real time)
                rag_task = TaskAssignment(
                    task_id=task_id,
                    task_type="query_knowledge",
                    description=query,
                    input_data={"query": query}
                )
                rag_result = await rag_agent.process_task(rag_task)
                
                if isinstance(rag_result, dict):
                    rag_context = rag_result.get("context", "")
                    sources = rag_result.get("sources", [])
                
                # Emit RAG result
                if HAS_EVENT_BUS and event_bus:
                    await event_bus.emit(
                        EventType.RAG_RESULT,
                        "rag_agent",
                        {"sources_found": len(sources), "context_length": len(rag_context)},
                        task_id=task_id
                    )
                    await event_bus.update_status("rag_agent", AgentState.IDLE, message="Ready")
                
                await self.ws_manager.broadcast_agent_activity({
                    "type": "agent_completed",
                    "agent": "rag_agent",
                    "source": "rag_agent",
                    "target": self.agent_name,
                    "content": {"sources_found": len(sources), "context_length": len(rag_context)},
                    "timestamp": datetime.now().isoformat(),
                    "priority": 1
                })
        
        # STEP 3: Thinking agent processes with context
        logger.info("[Manager] → Thinking Agent: Deep reasoning...")
        
        if HAS_EVENT_BUS and event_bus:
            await event_bus.emit(
                EventType.TASK_ASSIGNED,
                "thinking_agent",
                {"task": "reason_and_respond", "has_context": bool(rag_context)},
                task_id=task_id
            )
            await event_bus.update_status(
                "thinking_agent",
                AgentState.CALLING_LLM,
                task_id=task_id,
                message="Performing deep reasoning..."
            )
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "task_assigned",
            "agent": "thinking_agent",
            "source": self.agent_name,
            "target": "thinking_agent",
            "content": {"task": "reason_and_respond", "has_context": bool(rag_context)},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        agents_involved.append("thinking_agent")
        
        if HAS_EVENT_BUS and event_bus:
            await event_bus.emit_thinking(
                "thinking_agent",
                "Performing deep reasoning and synthesizing response...",
                step=3,
                task_id=task_id
            )
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "thinking",
            "agent": "thinking_agent",
            "source": "thinking_agent",
            "target": "llm",
            "content": {"status": "Performing deep reasoning and synthesizing response..."},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        # Check for interrupt
        if HAS_EVENT_BUS and event_bus and event_bus.is_interrupted(task_id):
            await event_bus.acknowledge_interrupt(self.agent_name, task_id)
            return {"response": "Task was interrupted", "status": "interrupted", "agents_involved": agents_involved}
        
        # Get thinking agent and process
        thinking_agent = self.registry.get_agent("thinking_agent")
        if thinking_agent:
            # Get chat history from task input
            chat_history = task.input_data.get("chat_history", [])
            
            # Memory injection for complex queries
            memory_context = ""
            user_id = task.input_data.get("user_id", "default")
            try:
                from services.cerebro_memory import get_cerebro
                cerebro = get_cerebro()
                memory_context = cerebro.get_context_for_prompt(user_id, query)
                if memory_context:
                    logger.info(f"[Manager] Injecting memory context into complex query ({len(memory_context)} chars)")
                    try:
                        debug_svc = get_debug_service()
                        debug_svc.record_memory_injection(
                            agent_name=self.agent_name,
                            task_id=task_id,
                            memory_context=memory_context,
                            query=query
                        )
                    except Exception:
                        pass
            except Exception as e:
                logger.debug(f"[Manager] Memory injection skipped for complex query: {e}")
            
            # Combine RAG context with memory context
            combined_context = rag_context
            if memory_context:
                combined_context = f"{rag_context}\n\n{memory_context}" if rag_context else memory_context
            
            thinking_task = TaskAssignment(
                task_id=task_id,
                task_type="deep_thinking",
                description=query,
                input_data={
                    "query": query,
                    "rag_context": combined_context,
                    "sources": sources,
                    "chat_history": chat_history  # Pass conversation history
                }
            )
            thinking_result = await thinking_agent.process_task(thinking_task)
            
            # Extract response from thinking result
            if isinstance(thinking_result, dict):
                # ThinkingAgent returns structured result
                if "conclusion" in thinking_result:
                    response_text = thinking_result["conclusion"]
                elif "response" in thinking_result:
                    response_text = thinking_result["response"]
                else:
                    response_text = str(thinking_result)
            else:
                response_text = str(thinking_result)
        else:
            # [NO FALLBACK] ThinkingAgent is required for general knowledge
            # If thinking_agent is not available, error should propagate
            raise RuntimeError("ThinkingAgent is required for general knowledge queries but was not available")
        
        # Update thinking agent status
        if HAS_EVENT_BUS and event_bus:
            await event_bus.update_status("thinking_agent", AgentState.IDLE, message="Ready")
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "agent_completed",
            "agent": "thinking_agent",
            "source": "thinking_agent",
            "target": self.agent_name,
            "content": {"response_length": len(response_text)},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        # Check for interrupt before validation
        if HAS_EVENT_BUS and event_bus and event_bus.is_interrupted(task_id):
            await event_bus.acknowledge_interrupt(self.agent_name, task_id)
            return {
                "response": response_text,  # Return partial result
                "status": "interrupted_before_validation",
                "agents_involved": agents_involved
            }
        
        # STEP 4: Validation agent checks response
        logger.info("[Manager] → Validation Agent: Checking quality...")
        
        if HAS_EVENT_BUS and event_bus:
            await event_bus.emit(
                EventType.TASK_ASSIGNED,
                "validation_agent",
                {"task": "validate_response", "response_length": len(response_text)},
                task_id=task_id
            )
            await event_bus.update_status(
                "validation_agent",
                AgentState.WORKING,
                task_id=task_id,
                message="Validating response quality..."
            )
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "task_assigned",
            "agent": "validation_agent",
            "source": self.agent_name,
            "target": "validation_agent",
            "content": {"task": "validate_response"},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        agents_involved.append("validation_agent")
        
        if HAS_EVENT_BUS and event_bus:
            await event_bus.emit_thinking(
                "validation_agent",
                "Validating response coherence, accuracy, and completeness...",
                step=4,
                task_id=task_id
            )
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "thinking",
            "agent": "validation_agent",
            "source": "validation_agent",
            "target": self.agent_name,
            "content": {"status": "Validating response coherence and accuracy..."},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        # Real validation using Manager's LLM-based quality check
        validation_passed = True
        quality_score = 0.7
        retry_performed = False
        
        try:
            validation = await self._manager_validate_response(
                query=query,
                response_text=response_text,
                sources=sources,
                workflow="complex_query",
                session_id=session_id,
                task_id=task_id
            )
            
            quality_score = validation.get("quality_score", 0.7)
            validation_passed = validation.get("passed", True)
            
            # If validation fails, retry with feedback
            if validation.get("should_retry") and not validation_passed:
                logger.info(f"[Manager] Complex query validation failed ({quality_score:.2f}), retrying...")
                
                improved_response = await self._manager_retry_with_feedback(
                    query=query,
                    original_response=response_text,
                    validation_result=validation,
                    context=memory_context,
                    sources=sources,
                    session_id=session_id,
                    task_id=task_id
                )
                
                # Re-validate the improved response
                retry_validation = await self._manager_validate_response(
                    query=query,
                    response_text=improved_response,
                    sources=sources,
                    workflow="complex_query_retry",
                    session_id=session_id,
                    task_id=task_id
                )
                
                retry_score = retry_validation.get("quality_score", 0.5)
                if retry_score > quality_score:
                    logger.info(f"[Manager] Complex retry improved: {quality_score:.2f} → {retry_score:.2f}")
                    response_text = improved_response
                    quality_score = retry_score
                    validation_passed = retry_validation.get("passed", True)
                    retry_performed = True
                    agents_involved.append("manager_retry")
                else:
                    logger.info(f"[Manager] Complex retry not better, keeping original")
                    
        except Exception as e:
            logger.warning(f"Manager validation in complex query failed: {e}")
            quality_score = 0.7
            validation_passed = True
        
        if HAS_EVENT_BUS and event_bus:
            await event_bus.emit(
                EventType.TASK_COMPLETED,
                "validation_agent",
                {
                    "validation": "passed" if validation_passed else "failed",
                    "quality_score": quality_score
                },
                task_id=task_id
            )
            await event_bus.update_status("validation_agent", AgentState.IDLE, message="Ready")
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "agent_completed",
            "agent": "validation_agent",
            "source": "validation_agent",
            "target": self.agent_name,
            "content": {"validation": "passed" if validation_passed else "failed", "quality_score": quality_score},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        # Update manager to idle
        if HAS_EVENT_BUS and event_bus:
            await event_bus.emit(
                EventType.TASK_COMPLETED,
                self.agent_name,
                {
                    "response_length": len(response_text),
                    "sources_count": len(sources),
                    "agents_involved": agents_involved,
                    "quality_score": quality_score
                },
                task_id=task_id
            )
            await event_bus.update_status(self.agent_name, AgentState.IDLE, message="Ready")
        
        # Return final result
        logger.info(f"[Manager] Task completed. Response: {len(response_text)} chars, {len(sources)} sources")
        
        return {
            "response": response_text,
            "agents_involved": agents_involved,
            "sources": sources,
            "status": "completed",
            "quality_score": quality_score,
            "manager_validated": True,
            "retry_performed": retry_performed
        }
    
    async def _route_task(self, task: TaskAssignment) -> Dict[str, Any]:
        """Route a task to the appropriate agent"""
        logger.info(f"Routing task: {task.task_type}")
        
        # Use LLM to decide routing
        routing_decision = await self._decide_routing(task)
        
        # Notify frontend about routing decision
        await self.ws_manager.broadcast_to_clients({
            "type": "task_routed",
            "task_id": task.task_id,
            "target_agent": routing_decision.target_agent,
            "reasoning": routing_decision.reasoning,
            "timestamp": datetime.now().isoformat()
        })
        
        # Handle special cases
        if routing_decision.requires_planning:
            # Send to planning agent first
            await self._send_to_planning(task)
            return {"status": "sent_to_planning", "task_id": task.task_id}
        
        if routing_decision.requires_rag:
            # Request RAG check first
            task.metadata = task.metadata or {}
            task.metadata["requires_rag"] = True
        
        # Send task to target agent
        message = MessageProtocol.create_task_assignment(
            self.agent_name,
            routing_decision.target_agent,
            task
        )
        await self.ws_manager.send_to_agent(message)
        
        return {
            "status": "routed",
            "task_id": task.task_id,
            "target_agent": routing_decision.target_agent
        }
    
    async def _decide_routing(self, task: TaskAssignment) -> TaskRoutingDecision:
        """Use LLM to decide which agent should handle the task"""
        
        try:
            decision = await self.llm_service.generate_with_structured_output(
                prompt_key="manager_agent",
                output_schema=TaskRoutingDecision,
                variables={
                    "task_type": task.task_type,
                    "description": task.description,
                    "input_data": str(task.input_data)
                },
                user_input=f"""Analyze this task and decide which agent should handle it.

Task Details:
- Type: {task.task_type}
- Description: {task.description}
- Input Data: {str(task.input_data)[:500]}

Available Agents: rag_agent, memory_agent, notes_agent, validation_agent, planning_agent, thinking_agent, data_agent, tool_agent, summarize_agent, translate_agent, calculation_agent

Determine:
1. Which agent is best suited
2. Whether planning is needed first
3. Whether RAG retrieval is needed"""
            )
            return decision
        except Exception as e:
            logger.error(f"Error in routing decision: {e}")
            # Default to thinking agent for general queries
            return TaskRoutingDecision(
                target_agent="thinking_agent",
                task_type=task.task_type,
                reasoning="Default routing due to decision error",
                requires_planning=False,
                requires_rag=True
            )
    
    async def _send_to_planning(self, task: TaskAssignment):
        """Send task to planning agent for decomposition"""
        planning_task = TaskAssignment(
            task_type="create_plan",
            description=f"Create a plan for: {task.description}",
            input_data={
                "original_task": task.model_dump(),
                "available_agents": self.available_agents
            }
        )
        
        message = MessageProtocol.create_task_assignment(
            self.agent_name,
            "planning_agent",
            planning_task
        )
        await self.ws_manager.send_to_agent(message)
    
    # ============== Interrupt Authority ==============
    
    async def interrupt_agent(
        self, 
        agent_name: str, 
        reason: str, 
        action: str = "stop"
    ):
        """
        Issue an interrupt command to an agent.
        Only the Manager has this authority.
        """
        logger.warning(f"Interrupting agent {agent_name}: {reason}")
        
        message = MessageProtocol.create_interrupt(
            self.agent_name,
            agent_name,
            reason,
            action
        )
        
        await self.ws_manager.send_to_agent(message)
        
        # Notify frontend
        await self.ws_manager.broadcast_to_clients({
            "type": "agent_interrupted",
            "agent_name": agent_name,
            "reason": reason,
            "action": action,
            "timestamp": datetime.now().isoformat()
        })
    
    async def interrupt_all_agents(self, reason: str):
        """Interrupt all agents (emergency stop)"""
        logger.warning(f"Emergency stop: {reason}")
        
        for agent_name in self.available_agents:
            await self.interrupt_agent(agent_name, reason, "stop")
    
    # ============== Error Handling ==============
    
    async def _handle_agent_error(self, message: AgentMessage):
        """Handle error reports from agents"""
        source_agent = message.source_agent
        error = message.content.get("error", "Unknown error")
        details = message.content.get("details", {})
        
        logger.error(f"Error from {source_agent}: {error}")
        
        # Track errors
        if source_agent not in self.agent_errors:
            self.agent_errors[source_agent] = []
        
        self.agent_errors[source_agent].append({
            "error": error,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
        
        # Check if agent has too many errors
        recent_errors = [
            e for e in self.agent_errors[source_agent]
            if (datetime.now() - datetime.fromisoformat(e["timestamp"])).seconds < 300
        ]
        
        if len(recent_errors) >= 3:
            # Too many errors - notify roles agent for correction
            await self._request_role_correction(source_agent, recent_errors)
        
        if len(recent_errors) >= 5:
            # Critical - interrupt the agent
            await self.interrupt_agent(
                source_agent,
                f"Too many errors: {len(recent_errors)} in last 5 minutes",
                "stop"
            )
        
        # Notify frontend
        await self.ws_manager.broadcast_to_clients({
            "type": "agent_error",
            "agent_name": source_agent,
            "error": error,
            "error_count": len(recent_errors),
            "timestamp": datetime.now().isoformat()
        })
    
    async def _request_role_correction(
        self, 
        agent_name: str, 
        errors: List[Dict]
    ):
        """Request roles agent to correct an agent's role/behavior"""
        message = AgentMessage(
            type=MessageType.QUERY,
            source_agent=self.agent_name,
            target_agent="roles_agent",
            content={
                "action": "correct_agent",
                "target_agent": agent_name,
                "errors": errors
            }
        )
        await self.ws_manager.send_to_agent(message)
    
    async def _handle_agent_completed(self, message: AgentMessage):
        """Handle task completion from agents"""
        source_agent = message.source_agent
        result = message.content.get("result")
        
        logger.info(f"Task completed by {source_agent}")
        
        # Clear error count on success
        if source_agent in self.agent_errors:
            self.agent_errors[source_agent] = []
        
        # Forward result to appropriate handler
        # This could trigger validation, notes creation, etc.
    
    async def _handle_query(self, message: AgentMessage):
        """Handle incoming queries (from API)"""
        query = message.content.get("query", "")
        
        task = TaskAssignment(
            task_type="user_query",
            description=query,
            input_data={"query": query}
        )
        
        await self.pending_tasks.put(task)
    
    # ============== System Health ==============
    
    async def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        agent_statuses = {}
        
        for agent_name in self.available_agents:
            status = self.ws_manager.get_agent_status(agent_name)
            agent_statuses[agent_name] = {
                "status": status.value if status else "unknown",
                "recent_errors": len(self.agent_errors.get(agent_name, []))
            }
        
        return {
            "manager_status": self.status.value,
            "agents": agent_statuses,
            "pending_tasks": self.pending_tasks.qsize(),
            "timestamp": datetime.now().isoformat()
        }


# ========================================
# Singleton accessor
# ========================================

_manager_agent: Optional[ManagerAgent] = None


def get_manager_agent() -> ManagerAgent:
    """Get or create the manager agent singleton"""
    global _manager_agent
    if _manager_agent is None:
        _manager_agent = ManagerAgent()
    return _manager_agent
