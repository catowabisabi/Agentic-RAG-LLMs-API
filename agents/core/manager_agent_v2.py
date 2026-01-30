# -*- coding: utf-8 -*-
"""
=============================================================================
Manager Agent V2 - Planning-Driven Task Orchestrator
=============================================================================

核心協調者，使用 Planning-driven 執行模式：

1. 收到任務 → 發送給 Planning Agent 分析
2. Planning Agent 返回計劃（Todo List）
3. Manager 根據計劃分派給不同 Agent
4. Agent 可能返回新的 planning 需求
5. Manager 整合、更新 planning/todo
6. 追蹤誰在工作、做什麼（metadata）
7. 持續分派直到完成所有 todo
8. 整個過程反映在 UI

=============================================================================
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
    TaskAssignment
)
from agents.shared_services.websocket_manager import WebSocketManager
from agents.shared_services.agent_registry import AgentRegistry
from agents.shared_services.task_planning import (
    ExecutionPlan, TodoItem, TaskStatus, TaskPriority,
    PlanningRequest, PlanningResponse
)
from config.config import Config

try:
    from services.event_bus import event_bus, EventType, AgentState
    HAS_EVENT_BUS = True
except ImportError:
    HAS_EVENT_BUS = False
    event_bus = None

logger = logging.getLogger(__name__)


class ManagerAgentV2(BaseAgent):
    """
    Planning-Driven Manager Agent
    
    職責：
    - 接收 Entry Classifier 分派的非閒聊任務
    - 發送給 Planning Agent 獲取執行計劃
    - 根據計劃分派任務給各 Agent
    - 追蹤執行進度和狀態
    - 處理 Agent 返回的新 planning 需求
    - 將所有過程廣播到 UI
    """
    
    def __init__(self, agent_name: str = "manager_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Manager",
            agent_description="Planning-driven task orchestrator"
        )
        
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.2,
            api_key=self.config.OPENAI_API_KEY
        )
        
        self.registry = AgentRegistry()
        self.ws_manager = WebSocketManager()
        
        # Active execution plans (task_id -> ExecutionPlan)
        self.active_plans: Dict[str, ExecutionPlan] = {}
        
        # Agent capabilities mapping
        self.agent_capabilities = {
            "rag_agent": {
                "tasks": ["search_knowledge", "retrieve_documents"],
                "description": "Search uploaded documents and knowledge bases"
            },
            "thinking_agent": {
                "tasks": ["analyze", "reason", "evaluate"],
                "description": "Deep reasoning and analysis"
            },
            "calculation_agent": {
                "tasks": ["calculate", "compute", "math"],
                "description": "Mathematical calculations"
            },
            "translate_agent": {
                "tasks": ["translate", "language_convert"],
                "description": "Language translation"
            },
            "summarize_agent": {
                "tasks": ["summarize", "condense", "extract_key_points"],
                "description": "Summarize and condense content"
            },
            "data_agent": {
                "tasks": ["parse_data", "format_data", "data_analysis"],
                "description": "Data parsing and formatting"
            },
            "tool_agent": {
                "tasks": ["use_tool", "external_api", "file_operation"],
                "description": "External tool usage"
            },
            "validation_agent": {
                "tasks": ["validate", "verify", "check"],
                "description": "Validate and verify results"
            },
            "memory_agent": {
                "tasks": ["store_memory", "retrieve_memory"],
                "description": "Long-term memory operations"
            }
        }
        
        logger.info("ManagerAgentV2 (Planning-Driven) initialized")
    
    async def process_task(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        Main entry point for processing tasks.
        
        流程：
        1. 創建執行計劃
        2. 獲取 Planning Agent 的計劃
        3. 執行 Todo List
        4. 返回最終結果
        """
        task_id = task.task_id
        query = task.input_data.get("query", task.description)
        
        logger.info(f"[Manager] Processing task: {query[:50]}...")
        
        # Broadcast: Manager started
        await self._broadcast_status("started", task_id, {
            "query": query[:100],
            "status": "Planning task..."
        })
        
        try:
            # Step 1: Get execution plan from Planning Agent
            plan = await self._create_execution_plan(task)
            self.active_plans[task_id] = plan
            
            # Broadcast: Plan created
            await self._broadcast_plan_update(plan)
            
            # Step 2: Execute the plan
            result = await self._execute_plan(plan, task)
            
            # Step 3: Clean up
            del self.active_plans[task_id]
            
            # Broadcast: Completed
            await self._broadcast_status("completed", task_id, {
                "response_preview": result.get("response", "")[:200]
            })
            
            return result
            
        except Exception as e:
            logger.error(f"[Manager] Task failed: {e}")
            await self._broadcast_status("failed", task_id, {"error": str(e)})
            return {
                "response": f"抱歉，處理您的請求時發生錯誤：{str(e)}",
                "error": str(e),
                "agents_involved": ["manager_agent"]
            }
    
    async def _create_execution_plan(self, task: TaskAssignment) -> ExecutionPlan:
        """
        使用 Planning Agent 創建執行計劃
        """
        query = task.input_data.get("query", task.description)
        context = task.input_data.get("context", "")
        user_context = task.input_data.get("user_context", "")
        chat_history = task.input_data.get("chat_history", [])
        
        # Broadcast: Calling Planning Agent
        await self._broadcast_status("thinking", task.task_id, {
            "step": "Planning",
            "message": "Analyzing query and creating execution plan..."
        })
        
        # Get plan from Planning Agent
        planning_agent = self.registry.get_agent("planning_agent")
        
        if planning_agent:
            planning_task = TaskAssignment(
                task_id=task.task_id,
                task_type="create_plan",
                description=query,
                input_data={
                    "query": query,
                    "context": context,
                    "user_context": user_context,
                    "chat_history": chat_history,
                    "available_agents": list(self.agent_capabilities.keys())
                }
            )
            
            plan_result = await planning_agent.process_task(planning_task)
            
            # Parse plan result into ExecutionPlan
            plan = self._parse_plan_result(query, plan_result)
        else:
            # Fallback: Create simple plan
            plan = await self._create_simple_plan(query, task)
        
        logger.info(f"[Manager] Plan created: {len(plan.todos)} todos")
        return plan
    
    def _parse_plan_result(self, query: str, plan_result: Dict[str, Any]) -> ExecutionPlan:
        """Parse planning agent result into ExecutionPlan"""
        
        goal = plan_result.get("goal", query)
        strategy = plan_result.get("strategy", "Direct execution")
        todos_data = plan_result.get("todos", [])
        
        todos = []
        for i, todo_data in enumerate(todos_data):
            todo = TodoItem(
                title=todo_data.get("title", f"Step {i+1}"),
                description=todo_data.get("description", ""),
                agent=todo_data.get("agent", "thinking_agent"),
                task_type=todo_data.get("task_type", "process"),
                priority=TaskPriority(todo_data.get("priority", "medium")),
                depends_on=todo_data.get("depends_on", []),
                input_data=todo_data.get("input_data", {"query": query})
            )
            todos.append(todo)
        
        return ExecutionPlan(
            query=query,
            goal=goal,
            strategy=strategy,
            todos=todos
        )
    
    async def _create_simple_plan(self, query: str, task: TaskAssignment) -> ExecutionPlan:
        """
        Fallback: Create a simple single-step plan using LLM
        """
        # Determine best agent for the query
        prompt = ChatPromptTemplate.from_template(
            """Analyze this query and determine the best approach:

Query: "{query}"

Available agents and their capabilities:
{agent_list}

Respond with:
1. goal: What is the main goal?
2. agent: Which agent is best suited? (agent name)
3. task_type: What type of task? (e.g., search_knowledge, calculate, translate)
4. needs_rag: Does this need to search knowledge bases? (true/false)

Format: goal|agent|task_type|needs_rag"""
        )
        
        agent_list = "\n".join([
            f"- {name}: {info['description']}"
            for name, info in self.agent_capabilities.items()
        ])
        
        try:
            result = await self.llm.ainvoke(
                prompt.format(query=query, agent_list=agent_list)
            )
            content = result.content if hasattr(result, 'content') else str(result)
            
            parts = content.strip().split("|")
            goal = parts[0] if len(parts) > 0 else query
            agent = parts[1].strip() if len(parts) > 1 else "thinking_agent"
            task_type = parts[2].strip() if len(parts) > 2 else "analyze"
            needs_rag = parts[3].strip().lower() == "true" if len(parts) > 3 else False
            
            # Validate agent
            if agent not in self.agent_capabilities:
                agent = "thinking_agent"
                task_type = "analyze"
                
        except Exception as e:
            logger.warning(f"Simple plan creation failed: {e}")
            goal = query
            agent = "thinking_agent"
            task_type = "analyze"
            needs_rag = False
        
        # Create todos
        todos = []
        
        # Add RAG step if needed
        if needs_rag:
            todos.append(TodoItem(
                title="Search knowledge bases",
                description="Retrieve relevant information",
                agent="rag_agent",
                task_type="search_knowledge",
                priority=TaskPriority.HIGH,
                input_data={"query": query}
            ))
        
        # Add main processing step
        todos.append(TodoItem(
            title="Process query",
            description=goal,
            agent=agent,
            task_type=task_type,
            priority=TaskPriority.MEDIUM,
            depends_on=[todos[0].id] if needs_rag else [],
            input_data={
                "query": query,
                "user_context": task.input_data.get("user_context", ""),
                "chat_history": task.input_data.get("chat_history", [])
            }
        ))
        
        return ExecutionPlan(
            query=query,
            goal=goal,
            strategy="Simple execution",
            todos=todos
        )
    
    async def _execute_plan(self, plan: ExecutionPlan, task: TaskAssignment) -> Dict[str, Any]:
        """
        Execute the plan by processing todos in order
        """
        plan.status = TaskStatus.IN_PROGRESS
        agents_involved = ["manager_agent"]
        collected_results = {}
        
        # Process todos until all are done
        while True:
            # Get next todo
            next_todo = plan.get_next_todo()
            
            if next_todo is None:
                # Check if we're done or stuck
                running = plan.get_running_todos()
                if not running:
                    # All done
                    break
                else:
                    # Wait for running todos
                    await asyncio.sleep(0.1)
                    continue
            
            # Execute the todo
            logger.info(f"[Manager] Executing: {next_todo.title} via {next_todo.agent}")
            
            plan.mark_todo_started(next_todo.id)
            await self._broadcast_plan_update(plan)
            
            try:
                # Prepare input data with collected results
                input_data = {**next_todo.input_data}
                input_data["collected_data"] = collected_results
                
                # Execute via appropriate agent
                result = await self._execute_todo(next_todo, input_data, task.task_id)
                
                # Store result
                collected_results[next_todo.id] = result
                plan.mark_todo_completed(next_todo.id, result)
                
                if next_todo.agent not in agents_involved:
                    agents_involved.append(next_todo.agent)
                
                # Check if agent returned new todos
                if result.get("new_todos"):
                    await self._handle_new_todos(plan, result["new_todos"])
                
                await self._broadcast_plan_update(plan)
                
            except Exception as e:
                logger.error(f"[Manager] Todo failed: {e}")
                plan.mark_todo_failed(next_todo.id, str(e))
                await self._broadcast_plan_update(plan)
        
        # Compile final response
        final_response = await self._compile_response(plan, collected_results, task)
        
        return {
            "response": final_response,
            "agents_involved": agents_involved,
            "sources": collected_results.get("sources", []),
            "workflow": "planning_driven",
            "plan_summary": plan.to_ui_dict()
        }
    
    async def _execute_todo(
        self, 
        todo: TodoItem, 
        input_data: Dict[str, Any],
        task_id: str
    ) -> Dict[str, Any]:
        """Execute a single todo via its assigned agent"""
        
        agent = self.registry.get_agent(todo.agent)
        
        if not agent:
            # Fallback to direct LLM
            return await self._execute_via_llm(todo, input_data)
        
        # Create task assignment
        agent_task = TaskAssignment(
            task_id=task_id,
            task_type=todo.task_type,
            description=todo.description or todo.title,
            input_data=input_data
        )
        
        # Broadcast: Agent working
        await self._broadcast_status("agent_working", task_id, {
            "agent": todo.agent,
            "task": todo.title
        })
        
        # Execute
        result = await agent.process_task(agent_task)
        
        return result if isinstance(result, dict) else {"result": result}
    
    async def _execute_via_llm(self, todo: TodoItem, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback: Execute via direct LLM call"""
        
        query = input_data.get("query", todo.description)
        context = input_data.get("collected_data", {})
        
        prompt = f"""Execute this task:

Task: {todo.title}
Description: {todo.description}
Query: {query}

Context from previous steps:
{context}

Provide a helpful response."""
        
        result = await self.llm.ainvoke(prompt)
        content = result.content if hasattr(result, 'content') else str(result)
        
        return {"response": content}
    
    async def _handle_new_todos(self, plan: ExecutionPlan, new_todos: List[Dict[str, Any]]):
        """Handle new todos returned by an agent"""
        
        for todo_data in new_todos:
            new_todo = TodoItem(
                title=todo_data.get("title", "Additional task"),
                description=todo_data.get("description", ""),
                agent=todo_data.get("agent", "thinking_agent"),
                task_type=todo_data.get("task_type", "process"),
                priority=TaskPriority(todo_data.get("priority", "medium")),
                depends_on=todo_data.get("depends_on", []),
                input_data=todo_data.get("input_data", {})
            )
            plan.add_todo(new_todo)
            logger.info(f"[Manager] Added new todo: {new_todo.title}")
    
    async def _compile_response(
        self, 
        plan: ExecutionPlan, 
        results: Dict[str, Any],
        task: TaskAssignment
    ) -> str:
        """Compile final response from all results"""
        
        # Find the last processing result
        for todo in reversed(plan.todos):
            if todo.status == TaskStatus.COMPLETED and todo.result:
                response = todo.result.get("response", todo.result.get("answer", ""))
                if response:
                    return response
        
        # Fallback: Compile from all results
        all_responses = []
        for todo_id, result in results.items():
            if isinstance(result, dict) and result.get("response"):
                all_responses.append(result["response"])
        
        if all_responses:
            return "\n\n".join(all_responses)
        
        return "處理完成，但沒有生成回覆。"
    
    async def _broadcast_status(self, status: str, task_id: str, data: Dict[str, Any]):
        """Broadcast status update to UI"""
        await self.ws_manager.broadcast_agent_activity({
            "type": f"manager_{status}",
            "agent": self.agent_name,
            "task_id": task_id,
            "content": data,
            "timestamp": datetime.now().isoformat()
        })
    
    async def _broadcast_plan_update(self, plan: ExecutionPlan):
        """Broadcast plan update to UI"""
        await self.ws_manager.broadcast_agent_activity({
            "type": "plan_update",
            "agent": self.agent_name,
            "content": plan.to_ui_dict(),
            "timestamp": datetime.now().isoformat()
        })


# Singleton
_manager_agent_v2 = None

def get_manager_agent_v2() -> ManagerAgentV2:
    global _manager_agent_v2
    if _manager_agent_v2 is None:
        _manager_agent_v2 = ManagerAgentV2()
    return _manager_agent_v2
