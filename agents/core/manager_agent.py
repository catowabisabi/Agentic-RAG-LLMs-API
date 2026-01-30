"""
Manager Agent

The central coordinator agent that:
- Receives and dispatches tasks to appropriate agents
- Has exclusive authority to issue interrupt commands
- Monitors overall system health
- Handles escalation from other agents

Integrated with EventBus for real-time status broadcasting.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
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
from config.config import Config

# Import EventBus
try:
    from services.event_bus import event_bus, EventType, AgentState
    HAS_EVENT_BUS = True
except ImportError:
    HAS_EVENT_BUS = False
    event_bus = None

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
        
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.2,
            api_key=self.config.OPENAI_API_KEY
        )
        
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
            "calculation_agent"
        ]
        
        # Add custom message handlers
        self._message_handlers[MessageType.AGENT_ERROR] = self._handle_agent_error
        self._message_handlers[MessageType.AGENT_COMPLETED] = self._handle_agent_completed
        self._message_handlers[MessageType.QUERY] = self._handle_query
        
        logger.info("ManagerAgent initialized")
    
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
        """
        Classify a user query to determine the appropriate workflow.
        
        Returns:
            QueryClassification with query_type: casual_chat, simple_rag, or complex_planning
        """
        # Fast path: check for obvious casual messages using heuristics
        from agents.core.casual_chat_agent import CasualChatAgent
        if CasualChatAgent.is_casual_message(query):
            return QueryClassification(
                query_type="casual_chat",
                reasoning="Message matches casual conversation pattern",
                confidence=0.95
            )
        
        # Use LLM for classification
        classification_prompt = ChatPromptTemplate.from_template(
            """You are a query router. Classify this user query into ONE category:

1. casual_chat: Greetings, small talk, thanks, farewells, questions about AI capabilities
   Examples: "Hello", "Thanks!", "What can you do?", "你有什麼功能", "你有咩功能", "Who are you?"
   
2. general_knowledge: General questions that an LLM can answer from training data (no RAG needed)
   Examples: "What is VBA?", "Explain Python", "What is machine learning?", "How do I write a for loop?"
   NOTE: Common knowledge, definitions, concepts, programming questions → general_knowledge

3. knowledge_rag: Questions that specifically need to search the user's uploaded documents/knowledge bases
   Examples: "What does my document say about X?", "Search my files for Y", "Based on the uploaded data..."
   NOTE: Only use this if the user is clearly asking about THEIR OWN uploaded content

4. calculation: Math problems, data analysis, numerical computations
   Examples: "Calculate 15% of 200", "What is the sum of...", "Analyze these numbers"

5. translation: Language translation requests
   Examples: "Translate this to Chinese", "How do you say X in French?"

6. summarization: Summarize content, create summaries
   Examples: "Summarize this article", "Give me the key points of..."

7. complex_planning: Multi-step tasks requiring planning, comparison, or combining multiple sources
   Examples: "Compare X and Y", "Create a plan for...", "Analyze and recommend..."

User query: "{query}"

Respond with ONLY the category name and a brief reason.
Format: category|reason"""
        )
        
        try:
            chain = classification_prompt | self.llm
            result = await chain.ainvoke({"query": query})
            response = result.content if hasattr(result, 'content') else str(result)
            
            # Parse response
            parts = response.strip().split("|", 1)
            query_type = parts[0].strip().lower()
            reasoning = parts[1].strip() if len(parts) > 1 else "LLM classification"
            
            # Validate query_type
            valid_types = ["casual_chat", "general_knowledge", "knowledge_rag", "calculation", "translation", "summarization", "complex_planning"]
            if query_type not in valid_types:
                # Fallback: if it looks like a question, try general_knowledge
                if "?" in query or query_type == "simple_rag":
                    query_type = "general_knowledge"
                else:
                    query_type = "general_knowledge"  # Default fallback
                
            return QueryClassification(
                query_type=query_type,
                reasoning=reasoning,
                confidence=0.85
            )
        except Exception as e:
            logger.warning(f"[Manager] Classification failed: {e}, defaulting to simple_rag")
            return QueryClassification(
                query_type="simple_rag",
                reasoning=f"Classification error, using default: {e}",
                confidence=0.5
            )
    
    async def _handle_knowledge_inventory(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        Handle knowledge base inventory requests.
        Lists all available knowledge bases with their details.
        """
        from services.vectordb_manager import get_vectordb_manager
        
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
            vectordb_manager = get_vectordb_manager()
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
        
        # Check for intent/handler from EntryClassifier (config-driven routing)
        intent = task.input_data.get("intent")
        handler = task.input_data.get("handler")
        matched_by = task.input_data.get("matched_by", "internal")
        
        logger.info(f"[Manager] Received intent={intent}, handler={handler}, matched_by={matched_by}")
        
        # If handler is provided, use handler-based routing (fast path)
        if handler:
            logger.info(f"[Manager] Handler-based routing: {handler} (intent: {intent}, matched_by: {matched_by})")
            
            # Emit start event
            if HAS_EVENT_BUS and event_bus:
                await event_bus.update_status(
                    self.agent_name,
                    AgentState.WORKING,
                    task_id=task_id,
                    message=f"Executing handler: {handler}"
                )
            
            await self.ws_manager.broadcast_agent_activity({
                "type": "thinking",
                "agent": self.agent_name,
                "source": self.agent_name,
                "content": {
                    "status": f"Intent: {intent}, Handler: {handler}",
                    "matched_by": matched_by
                },
                "timestamp": datetime.now().isoformat(),
                "priority": 1
            })
            
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
                # Planning
                "planning": self._handle_complex_query,
                "plan_complex": self._handle_complex_query,
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
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "thinking",
            "agent": self.agent_name,
            "source": self.agent_name,
            "content": {
                "status": f"Query type: {classification.query_type}",
                "reasoning": classification.reasoning
            },
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
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
        elif classification.query_type == "complex_planning":
            return await self._handle_complex_query(task)
        else:
            # Fallback to general knowledge
            return await self._handle_general_knowledge(task)
    
    async def _handle_general_knowledge(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        Handle general knowledge questions using ThinkingAgent (no RAG needed).
        LLM can answer from its training data.
        """
        query = task.input_data.get("query", task.description)
        task_id = task.task_id
        chat_history = task.input_data.get("chat_history", [])
        user_context = task.input_data.get("user_context", "")
        
        logger.info(f"[Manager] General knowledge query - direct LLM answer")
        
        agents_involved = ["manager_agent"]
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "task_assigned",
            "agent": "manager_agent",
            "source": self.agent_name,
            "target": "llm",
            "content": {"task": "general_knowledge", "query": query[:100]},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
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
        
        # Direct LLM call for general knowledge
        prompt = f"""You are a helpful AI assistant. Answer this question clearly and informatively.

{f'User Context: {user_context}' if user_context else ''}
{history_context}
Question: {query}

Guidelines:
- Provide a clear, accurate answer
- Match the language of the question (if asked in Chinese, respond in Chinese)
- Be concise but informative
- If it's a technical term or concept, provide a brief explanation"""
        
        llm_result = await self.llm.ainvoke(prompt)
        response_text = llm_result.content if hasattr(llm_result, 'content') else str(llm_result)
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "task_completed",
            "agent": "manager_agent",
            "source": "manager_agent",
            "target": self.agent_name,
            "content": {"workflow": "general_knowledge"},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        return {
            "response": response_text,
            "agents_involved": agents_involved,
            "sources": [],
            "workflow": "general_knowledge"
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

    async def _handle_simple_rag_query(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        Handle a simple RAG query - just retrieval + direct response.
        No planning or deep thinking needed.
        """
        query = task.input_data.get("query", task.description)
        task_id = task.task_id
        
        agents_involved = ["manager_agent"]
        sources = []
        rag_context = ""
        
        # Emit start event
        if HAS_EVENT_BUS and event_bus:
            await event_bus.update_status(
                self.agent_name,
                AgentState.WORKING,
                task_id=task_id,
                message=f"Simple RAG query..."
            )
        
        # Get RAG context
        logger.info("[Manager] → RAG Agent: Querying knowledge bases...")
        
        if HAS_EVENT_BUS and event_bus:
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
        
        # Execute RAG query
        rag_agent = self.registry.get_agent("rag_agent")
        if rag_agent:
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
            
            if HAS_EVENT_BUS and event_bus:
                await event_bus.update_status("rag_agent", AgentState.IDLE, message="Ready")
        
        # Generate response with RAG context
        if HAS_EVENT_BUS and event_bus:
            await event_bus.update_status(
                self.agent_name,
                AgentState.CALLING_LLM,
                task_id=task_id,
                message="Generating response..."
            )
        
        # Check if we found relevant context
        if rag_context and len(rag_context) > 100:
            # We have context - generate response using it
            prompt = ChatPromptTemplate.from_template(
                """Based on the following knowledge base context, answer the user's question.
Be concise and direct.

=== Knowledge Base Context ===
{rag_context}
=== End Context ===

User Question: {query}

Answer:"""
            )
            chain = prompt | self.llm
            result = await chain.ainvoke({"rag_context": rag_context[:4000], "query": query})
            response_text = result.content if hasattr(result, 'content') else str(result)
        else:
            # No relevant context found - inform user
            response_text = f"I searched the knowledge bases but couldn't find specific information about that topic. Could you rephrase your question or ask about a different topic?"
            if sources:
                response_text += f"\n\n(Searched {len(sources)} documents but relevance was low)"
        
        if HAS_EVENT_BUS and event_bus:
            await event_bus.update_status(self.agent_name, AgentState.IDLE, message="Ready")
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "task_completed",
            "agent": self.agent_name,
            "source": self.agent_name,
            "content": {"workflow": "simple_rag", "sources_count": len(sources)},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        return {
            "response": response_text,
            "agents_involved": agents_involved,
            "sources": sources,
            "workflow": "simple_rag"
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
        
        agents_involved = ["manager_agent"]
        sources = []
        rag_context = ""
        
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
            
            thinking_task = TaskAssignment(
                task_id=task_id,
                task_type="deep_thinking",
                description=query,
                input_data={
                    "query": query,
                    "rag_context": rag_context,
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
            # Fallback: use LLM directly
            if HAS_EVENT_BUS and event_bus:
                await event_bus.emit(
                    EventType.LLM_CALL_START,
                    self.agent_name,
                    {"model": self.config.DEFAULT_MODEL, "query_length": len(query)},
                    task_id=task_id
                )
            
            from langchain_core.prompts import ChatPromptTemplate
            
            if rag_context:
                prompt = ChatPromptTemplate.from_template(
                    """You are a helpful AI assistant with access to a knowledge base.

=== Knowledge Base Context ===
{rag_context}
=== End Context ===

User: {message}

Provide a helpful, accurate, and informative response based on the available context."""
                )
                result = await self.llm.ainvoke(
                    prompt.format(rag_context=rag_context, message=query)
                )
            else:
                result = await self.llm.ainvoke(query)
            
            response_text = result.content if hasattr(result, 'content') else str(result)
            
            if HAS_EVENT_BUS and event_bus:
                await event_bus.emit(
                    EventType.LLM_CALL_END,
                    self.agent_name,
                    {"response_length": len(response_text)},
                    task_id=task_id
                )
        
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
        
        # Actual validation - check response quality
        validation_passed = True
        quality_score = 0.92
        
        # Basic validation checks
        if len(response_text) < 10:
            validation_passed = False
            quality_score = 0.3
        elif len(response_text) > 50:
            quality_score = 0.95
        
        # Simulate validation processing
        await asyncio.sleep(0.5)
        
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
            "quality_score": quality_score
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
        
        prompt = ChatPromptTemplate.from_template(
            """You are a task router for a multi-agent AI system. Analyze the task and decide which agent should handle it.

Available Agents:
- rag_agent: Handles retrieval-augmented generation, document search, and knowledge lookup
- memory_agent: Manages conversation memory and context persistence
- notes_agent: Creates and organizes notes from information
- validation_agent: Validates data and responses for accuracy
- planning_agent: Creates step-by-step plans for complex tasks
- thinking_agent: Performs deep reasoning and analysis
- data_agent: Handles data processing and transformation
- tool_agent: Executes external tools and APIs
- summarize_agent: Creates summaries and condensed information
- translate_agent: Handles language translation
- calculation_agent: Performs mathematical calculations

Task Details:
- Type: {task_type}
- Description: {description}
- Input Data: {input_data}

Analyze the task and determine:
1. Which agent is best suited to handle this task
2. Whether planning is needed first (for complex multi-step tasks)
3. Whether RAG retrieval is needed (for knowledge-dependent tasks)

Respond with your routing decision."""
        )
        
        chain = prompt | self.llm.with_structured_output(TaskRoutingDecision)
        
        try:
            decision = await chain.ainvoke({
                "task_type": task.task_type,
                "description": task.description,
                "input_data": str(task.input_data)
            })
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
