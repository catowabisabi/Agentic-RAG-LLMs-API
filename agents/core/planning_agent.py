"""
Planning Agent（LangGraph 整合版）
===================================

使用 LangGraph StateGraph 實作深度思考與自我修正迴圈的規劃代理。

核心特性：
- 使用 LangGraph 建立 Generate → Validate → Refine 迴圈
- 支援最多 5 次自我修正（recursion_limit=5）
- 完整整合 EventBus 保持 UI 即時更新
- 自動分解複雜任務並分配給適當的 Agents

LangGraph 工作流程：
1. generate_node: 產生執行計劃
2. validate_node: 驗證計劃結構
3. conditional_edge: 根據驗證結果決定下一步
   - 有效 → 結束
   - 無效且 iteration < max → refine_node
   - 達到上限 → 結束
4. refine_node: 修正計劃並回到 validate

Architecture Diagram:
    ┌──────────────┐
    │   START      │
    └──────┬───────┘
           ▼
    ┌──────────────┐
    │   Generate   │
    └──────┬───────┘
           ▼
    ┌──────────────┐     is_valid=True
    │   Validate   │────────────────────► END
    └──────┬───────┘
           │ is_valid=False
           ▼
    ┌──────────────┐
    │   Refine     │
    └──────┬───────┘
           │
           └──────────────────────────────┐
                                          │
           ┌──────────────────────────────┘
           ▼
    ┌──────────────┐
    │   Validate   │  (loop back, max 5 iterations)
    └──────────────┘
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from datetime import datetime

from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    MessageProtocol,
    TaskAssignment,
    ValidationResult
)

logger = logging.getLogger(__name__)


class PlanStep(BaseModel):
    """A single step in a plan"""
    step_number: int = Field(description="Step number in sequence")
    agent: str = Field(description="Agent to execute this step")
    action: str = Field(description="Action to perform")
    description: str = Field(description="Detailed description of the step")
    input_from: List[int] = Field(
        default_factory=list, 
        description="Step numbers this step depends on"
    )
    expected_output: str = Field(description="What this step should produce")


class ExecutionPlan(BaseModel):
    """Complete execution plan"""
    goal: str = Field(description="The main goal of this plan")
    reasoning: str = Field(description="Reasoning behind the plan structure")
    steps: List[PlanStep] = Field(description="Ordered list of steps")
    estimated_time: str = Field(description="Estimated time to complete")


# ============== LangGraph State Definition ==============
class PlanningState(TypedDict):
    """
    LangGraph 狀態定義
    
    用於追蹤規劃迴圈中的狀態：
    - query: 原始查詢
    - plan: 當前執行計劃
    - validation_result: 驗證結果
    - errors: 錯誤列表
    - iteration: 當前迭代次數
    - messages: 用於 UI 串流的訊息列表
    """
    query: str
    agent_descriptions: str
    plan: Optional[Dict[str, Any]]
    validation_result: Optional[Dict[str, Any]]
    errors: List[str]
    iteration: int
    messages: List[str]
    is_complete: bool


# ============== Constants ==============
MAX_REFINEMENT_ITERATIONS = 5  # recursion_limit


class PlanningAgent(BaseAgent):
    """
    Planning Agent for the multi-agent system.
    
    Responsibilities:
    - Decompose complex tasks into steps
    - Create execution plans
    - Stream planning process to frontend
    """
    
    def __init__(self, agent_name: str = "planning_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Planning Specialist",
            agent_description="Creates step-by-step plans for complex tasks"
        )
        
        # Load prompt configuration
        self.prompt_template = self.prompt_manager.get_prompt("planning_agent")
        
        # Available agents for planning
        self.available_agents = [
            ("rag_agent", "Document retrieval and knowledge lookup"),
            ("memory_agent", "Memory storage and retrieval"),
            ("notes_agent", "Note creation and organization"),
            ("validation_agent", "Data and response validation"),
            ("thinking_agent", "Deep reasoning and analysis"),
            ("data_agent", "Data processing and transformation"),
            ("tool_agent", "External tool and API execution"),
            ("summarize_agent", "Summarization and condensation"),
            ("translate_agent", "Language translation"),
            ("calculation_agent", "Mathematical calculations")
        ]
        
        # 建立 LangGraph
        self.planning_graph = self._build_planning_graph()
        
        logger.info("PlanningAgent initialized with LangGraph (recursion_limit=%d)", 
                    MAX_REFINEMENT_ITERATIONS)
    
    # ============== LangGraph 建構 ==============
    def _build_planning_graph(self) -> StateGraph:
        """
        建立 LangGraph StateGraph
        
        節點：
        - generate: 產生執行計劃
        - validate: 驗證計劃
        - refine: 修正計劃
        
        邊：
        - START → generate
        - generate → validate
        - validate → END (if valid)
        - validate → refine (if invalid and iteration < max)
        - validate → END (if iteration >= max)
        - refine → validate (loop back)
        """
        # 建立 StateGraph
        workflow = StateGraph(PlanningState)
        
        # 添加節點
        workflow.add_node("generate", self._graph_generate)
        workflow.add_node("validate", self._graph_validate)
        workflow.add_node("refine", self._graph_refine)
        
        # 設定入口點
        workflow.set_entry_point("generate")
        
        # 添加邊
        workflow.add_edge("generate", "validate")
        workflow.add_conditional_edges(
            "validate",
            self._should_continue,
            {
                "end": END,
                "refine": "refine"
            }
        )
        workflow.add_edge("refine", "validate")
        
        return workflow.compile()
    
    async def _graph_generate(self, state: PlanningState) -> Dict[str, Any]:
        """
        LangGraph 節點：產生執行計劃
        """
        query = state["query"]
        agent_descriptions = state["agent_descriptions"]
        
        try:
            plan = await self.llm_service.generate_with_structured_output(
                prompt_key="planning_agent",
                output_schema=ExecutionPlan,
                variables={
                    "query": query,
                    "agents": agent_descriptions
                }
            )
            
            plan_dict = {
                "goal": plan.goal,
                "reasoning": plan.reasoning,
                "steps": [step.model_dump() for step in plan.steps],
                "estimated_time": plan.estimated_time
            }
            
            return {
                "plan": plan_dict,
                "messages": state["messages"] + [f"📌 Generated plan: {plan.goal}"],
                "iteration": state["iteration"]
            }
            
        except Exception as e:
            logger.error(f"Error generating plan: {e}")
            return {
                "plan": None,
                "errors": [str(e)],
                "messages": state["messages"] + [f"❌ Generation error: {e}"],
                "is_complete": True
            }
    
    async def _graph_validate(self, state: PlanningState) -> Dict[str, Any]:
        """
        LangGraph 節點：驗證計劃
        """
        plan = state["plan"]
        
        if not plan:
            return {
                "validation_result": {"is_valid": False, "errors": ["No plan generated"]},
                "errors": ["No plan generated"],
                "is_complete": True
            }
        
        errors = []
        warnings = []
        valid_agents = [name for name, _ in self.available_agents]
        
        steps = plan.get("steps", [])
        
        for step in steps:
            agent = step.get("agent", "")
            step_num = step.get("step_number", 0)
            
            if agent not in valid_agents:
                errors.append(f"Step {step_num}: Unknown agent '{agent}'")
            
            for dep in step.get("input_from", []):
                if dep >= step_num:
                    errors.append(f"Step {step_num}: Invalid dependency on future step {dep}")
                if dep < 1:
                    errors.append(f"Step {step_num}: Invalid step reference {dep}")
        
        if len(steps) == 0:
            errors.append("Plan has no steps")
        
        if len(steps) > 10:
            warnings.append("Plan has many steps, consider simplifying")
        
        validation_result = {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
        
        iteration = state["iteration"] + 1
        new_messages = state["messages"] + [
            f"🔍 Validation iteration {iteration}: {'✅ Valid' if validation_result['is_valid'] else f'❌ {len(errors)} errors'}"
        ]
        
        return {
            "validation_result": validation_result,
            "errors": errors,
            "iteration": iteration,
            "messages": new_messages
        }
    
    async def _graph_refine(self, state: PlanningState) -> Dict[str, Any]:
        """
        LangGraph 節點：修正計劃
        """
        plan = state["plan"]
        errors = state["errors"]
        agent_descriptions = state["agent_descriptions"]
        
        refine_prompt = f"""Fix these errors in the execution plan:

Current Plan:
Goal: {plan.get("goal", "")}
Steps: {str(plan.get("steps", []))}

Errors to fix:
{chr(10).join(errors)}

Available Agents:
{agent_descriptions}

Create a corrected plan."""
        
        try:
            refined = await self.llm_service.generate_with_structured_output(
                prompt_key="planning_agent",
                output_schema=ExecutionPlan,
                user_input=refine_prompt
            )
            
            refined_dict = {
                "goal": refined.goal,
                "reasoning": refined.reasoning,
                "steps": [step.model_dump() for step in refined.steps],
                "estimated_time": refined.estimated_time
            }
            
            return {
                "plan": refined_dict,
                "messages": state["messages"] + [f"🔧 Refined plan (iteration {state['iteration']})"]
            }
            
        except Exception as e:
            logger.error(f"Error refining plan: {e}")
            return {
                "messages": state["messages"] + [f"⚠️ Refinement failed: {e}"]
            }
    
    def _should_continue(self, state: PlanningState) -> str:
        """
        條件邊：決定是否繼續迴圈
        
        返回：
        - "end": 計劃有效或達到迭代上限
        - "refine": 計劃無效且未達上限
        """
        validation = state.get("validation_result", {})
        iteration = state.get("iteration", 0)
        
        # 已完成（錯誤或成功）
        if state.get("is_complete", False):
            return "end"
        
        # 計劃有效
        if validation.get("is_valid", False):
            return "end"
        
        # 達到迭代上限
        if iteration >= MAX_REFINEMENT_ITERATIONS:
            logger.warning(f"Reached max refinement iterations ({MAX_REFINEMENT_ITERATIONS})")
            return "end"
        
        # 繼續修正
        return "refine"
    
    async def process_task(self, task: TaskAssignment) -> Any:
        """Process a planning task"""
        task_type = task.task_type
        
        if task_type == "create_plan":
            return await self._create_plan_for_manager(task)
        elif task_type == "create_plan_langgraph":
            return await self._create_plan_with_langgraph(task)
        elif task_type == "refine_plan":
            return await self._refine_plan(task)
        else:
            return await self._create_plan_for_manager(task)
    
    async def _create_plan_for_manager(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        Create execution plan for Manager Agent V2.
        
        Returns plan in Todo format that Manager can execute directly.
        """
        query = task.input_data.get("query", task.description)
        context = task.input_data.get("context", "")
        user_context = task.input_data.get("user_context", "")
        available_agents = task.input_data.get("available_agents", [])
        
        # Agent descriptions
        agent_desc = "\n".join([
            f"- {name}: {desc}" for name, desc in self.available_agents
            if name in available_agents or not available_agents
        ])
        
        context_section = f"\nContext: {context}" if context else ""
        user_context_section = f"\nUser preferences: {user_context}" if user_context else ""
        
        plan_prompt = f"""You are a task planner. Analyze this query and create an execution plan.

Query: {query}
{context_section}
{user_context_section}

Available Agents:
{agent_desc}

Create a plan with these guidelines:
1. Break into minimal steps (1-5 steps usually)
2. Each step should have: agent, task_type, title, description
3. Specify dependencies if steps need to run in order
4. For simple queries, just 1 step is fine

Respond in JSON format:
{{
    "goal": "main goal",
    "strategy": "brief strategy",
    "complexity": "simple|medium|complex",
    "todos": [
        {{
            "title": "step title",
            "description": "what to do",
            "agent": "agent_name",
            "task_type": "task type (e.g., analyze, calculate, translate)",
            "priority": "high|medium|low",
            "depends_on": [],
            "input_data": {{}}
        }}
    ]
}}"""
        
        # [NO FALLBACK] Errors propagate for testing visibility
        result = await self.llm_service.generate(
            prompt_key="planning_agent",
            user_input=plan_prompt
        )
        
        content = result.get("content", "")
        
        # Parse JSON
        import json
        import re
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            plan_data = json.loads(json_match.group())
            
            # Add query to each todo's input_data
            for todo in plan_data.get("todos", []):
                if "input_data" not in todo:
                    todo["input_data"] = {}
                todo["input_data"]["query"] = query
                todo["input_data"]["user_context"] = user_context
            
            return {
                "success": True,
                "goal": plan_data.get("goal", query),
                "strategy": plan_data.get("strategy", "Direct execution"),
                "complexity": plan_data.get("complexity", "simple"),
                "todos": plan_data.get("todos", [])
            }
        else:
            # [NO FALLBACK] Plan creation must succeed - errors propagate for testing
            raise ValueError(f"LLM did not return valid plan data for query: {query[:50]}...")
    
    # [REMOVED] _create_fallback_plan() method - no longer used as fallback is disabled
    
    async def _create_plan_with_langgraph(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        使用 LangGraph 建立執行計劃
        
        透過 StateGraph 實現 Generate → Validate → Refine 迴圈，
        支援最多 MAX_REFINEMENT_ITERATIONS 次自我修正。
        """
        original_task = task.input_data.get("original_task", {})
        query = original_task.get("description", task.description)
        
        # Stream initial thinking to frontend
        await self.stream_to_frontend(
            f"📋 Analyzing task with LangGraph: {query[:100]}...\n", 
            0
        )
        
        agent_descriptions = "\n".join([
            f"- {name}: {desc}" for name, desc in self.available_agents
        ])
        
        # 初始化 LangGraph 狀態
        initial_state: PlanningState = {
            "query": query,
            "agent_descriptions": agent_descriptions,
            "plan": None,
            "validation_result": None,
            "errors": [],
            "iteration": 0,
            "messages": [],
            "is_complete": False
        }
        
        await self.stream_to_frontend(
            "🔍 Starting LangGraph planning workflow...\n", 
            1
        )
        
        try:
            # 執行 LangGraph（使用 astream 保持 UI 更新）
            final_state = None
            step_count = 0
            
            async for state in self.planning_graph.astream(initial_state):
                step_count += 1
                
                # 取得當前節點的狀態
                for node_name, node_state in state.items():
                    if "messages" in node_state:
                        for msg in node_state.get("messages", [])[-1:]:
                            await self.stream_to_frontend(f"  [{node_name}] {msg}\n", step_count)
                    
                    final_state = node_state
            
            # 檢查最終結果
            if final_state and final_state.get("plan"):
                plan_dict = final_state["plan"]
                validation = final_state.get("validation_result", {})
                
                # 串流計劃到前端
                await self._stream_plan_dict(plan_dict)
                
                result = {
                    "success": True,
                    "plan": plan_dict,
                    "validation": validation,
                    "iterations": final_state.get("iteration", 1),
                    "langgraph": True
                }
                
                # 發送計劃到 Manager
                plan_obj = ExecutionPlan(
                    goal=plan_dict["goal"],
                    reasoning=plan_dict["reasoning"],
                    steps=[PlanStep(**s) for s in plan_dict["steps"]],
                    estimated_time=plan_dict["estimated_time"]
                )
                await self._send_plan_to_manager(plan_obj, original_task)
                
                return result
            else:
                errors = final_state.get("errors", ["Unknown error"]) if final_state else ["No state returned"]
                return {
                    "success": False,
                    "error": "; ".join(errors),
                    "langgraph": True
                }
                
        except Exception as e:
            logger.error(f"LangGraph error: {e}")
            await self.stream_to_frontend(f"❌ LangGraph error: {e}\n", -1)
            return {
                "success": False,
                "error": str(e),
                "langgraph": True
            }
    
    async def _stream_plan_dict(self, plan: Dict[str, Any]):
        """Stream plan dictionary to frontend"""
        await self.stream_to_frontend(
            f"\n📌 Goal: {plan.get('goal', 'N/A')}\n",
            100
        )
        
        await self.stream_to_frontend(
            f"💭 Reasoning: {plan.get('reasoning', 'N/A')}\n\n",
            101
        )
        
        await self.stream_to_frontend(
            "📝 Execution Steps:\n",
            102
        )
        
        for i, step in enumerate(plan.get("steps", [])):
            step_text = (
                f"\n  Step {step.get('step_number', i+1)}: [{step.get('agent', 'unknown')}]\n"
                f"  Action: {step.get('action', 'N/A')}\n"
                f"  Details: {step.get('description', 'N/A')}\n"
                f"  Expected: {step.get('expected_output', 'N/A')}\n"
            )
            if step.get("input_from"):
                step_text += f"  Depends on: Steps {step['input_from']}\n"
            
            await self.stream_to_frontend(step_text, 103 + i)
            await asyncio.sleep(0.1)
        
        await self.stream_to_frontend(
            f"\n⏱️ Estimated time: {plan.get('estimated_time', 'N/A')}\n",
            200
        )

    async def _create_plan(self, task: TaskAssignment) -> Dict[str, Any]:
        """Create an execution plan for a complex task"""
        original_task = task.input_data.get("original_task", {})
        query = original_task.get("description", task.description)
        
        # Stream initial thinking to frontend
        await self.stream_to_frontend(
            f"📋 Analyzing task: {query[:100]}...\n", 
            0
        )
        
        agent_descriptions = "\n".join([
            f"- {name}: {desc}" for name, desc in self.available_agents
        ])
        
        # Stream planning process
        await self.stream_to_frontend(
            "🔍 Identifying required agents and steps...\n", 
            1
        )
        
        try:
            plan = await self.llm_service.generate_with_structured_output(
                prompt_key="planning_agent",
                output_schema=ExecutionPlan,
                variables={
                    "query": query,
                    "agents": agent_descriptions
                }
            )
            
            # Stream the plan to frontend
            await self._stream_plan(plan)
            
            # Validate the plan
            validation = await self._validate_plan(plan)
            
            if not validation["is_valid"]:
                # Refine the plan
                plan = await self._refine_plan_internal(plan, validation["errors"])
            
            result = {
                "success": True,
                "plan": {
                    "goal": plan.goal,
                    "reasoning": plan.reasoning,
                    "steps": [step.model_dump() for step in plan.steps],
                    "estimated_time": plan.estimated_time
                },
                "validation": validation
            }
            
            # Send plan to manager for execution
            await self._send_plan_to_manager(plan, original_task)
            
            return result
            
        except Exception as e:
            logger.error(f"Error creating plan: {e}")
            await self.stream_to_frontend(f"❌ Error creating plan: {e}\n", -1)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _stream_plan(self, plan: ExecutionPlan):
        """Stream the plan to frontend"""
        await self.stream_to_frontend(
            f"\n📌 Goal: {plan.goal}\n",
            2
        )
        
        await self.stream_to_frontend(
            f"💭 Reasoning: {plan.reasoning}\n\n",
            3
        )
        
        await self.stream_to_frontend(
            "📝 Execution Steps:\n",
            4
        )
        
        for i, step in enumerate(plan.steps):
            step_text = (
                f"\n  Step {step.step_number}: [{step.agent}]\n"
                f"  Action: {step.action}\n"
                f"  Details: {step.description}\n"
                f"  Expected: {step.expected_output}\n"
            )
            if step.input_from:
                step_text += f"  Depends on: Steps {step.input_from}\n"
            
            await self.stream_to_frontend(step_text, 5 + i)
            await asyncio.sleep(0.2)  # Small delay for visual effect
        
        await self.stream_to_frontend(
            f"\n⏱️ Estimated time: {plan.estimated_time}\n",
            100
        )
    
    async def _validate_plan(self, plan: ExecutionPlan) -> Dict[str, Any]:
        """Validate the plan structure"""
        errors = []
        warnings = []
        
        valid_agents = [name for name, _ in self.available_agents]
        
        for step in plan.steps:
            if step.agent not in valid_agents:
                errors.append(f"Step {step.step_number}: Unknown agent '{step.agent}'")
            
            for dep in step.input_from:
                if dep >= step.step_number:
                    errors.append(
                        f"Step {step.step_number}: Invalid dependency on future step {dep}"
                    )
                if dep < 1:
                    errors.append(
                        f"Step {step.step_number}: Invalid step reference {dep}"
                    )
        
        if len(plan.steps) == 0:
            errors.append("Plan has no steps")
        
        if len(plan.steps) > 10:
            warnings.append("Plan has many steps, consider simplifying")
        
        return {
            "is_valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }
    
    async def _refine_plan(self, task: TaskAssignment) -> Dict[str, Any]:
        """Refine an existing plan based on feedback"""
        original_plan = task.input_data.get("plan", {})
        feedback = task.input_data.get("feedback", "")
        
        agent_descriptions = "\n".join([
            f"- {name}: {desc}" for name, desc in self.available_agents
        ])
        
        refine_prompt = f"""Refine this execution plan based on the feedback.

Original Plan:
{str(original_plan)}

Feedback:
{feedback}

Available Agents:
{agent_descriptions}

Create an improved plan that addresses the feedback."""
        
        try:
            plan = await self.llm_service.generate_with_structured_output(
                prompt_key="planning_agent",
                output_schema=ExecutionPlan,
                user_input=refine_prompt
            )
            
            return {
                "success": True,
                "plan": {
                    "goal": plan.goal,
                    "reasoning": plan.reasoning,
                    "steps": [step.model_dump() for step in plan.steps],
                    "estimated_time": plan.estimated_time
                }
            }
            
        except Exception as e:
            logger.error(f"Error refining plan: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _refine_plan_internal(
        self, 
        plan: ExecutionPlan, 
        errors: List[str]
    ) -> ExecutionPlan:
        """Internal plan refinement based on validation errors"""
        agent_descriptions = "\n".join([
            f"- {name}: {desc}" for name, desc in self.available_agents
        ])
        
        refine_prompt = f"""Fix these errors in the execution plan:

Current Plan:
Goal: {plan.goal}
Steps: {str([s.model_dump() for s in plan.steps])}

Errors to fix:
{chr(10).join(errors)}

Available Agents:
{agent_descriptions}

Create a corrected plan."""
        
        # [NO FALLBACK] Refinement - errors propagate for testing
        refined = await self.llm_service.generate_with_structured_output(
            prompt_key="planning_agent",
            output_schema=ExecutionPlan,
            user_input=refine_prompt
        )
        return refined
    
    async def _send_plan_to_manager(
        self, 
        plan: ExecutionPlan, 
        original_task: Dict
    ):
        """Send the completed plan to manager for execution"""
        message = AgentMessage(
            type=MessageType.TASK_RESULT,
            source_agent=self.agent_name,
            target_agent="manager_agent",
            content={
                "result_type": "execution_plan",
                "plan": {
                    "goal": plan.goal,
                    "steps": [step.model_dump() for step in plan.steps]
                },
                "original_task": original_task
            }
        )
        
        await self.ws_manager.send_to_agent(message)
