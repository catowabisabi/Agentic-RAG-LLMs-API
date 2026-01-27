"""
Planning Agent

Creates step-by-step plans for complex tasks:
- Decomposes complex queries into sub-tasks
- Assigns tasks to appropriate agents
- Streams planning process to frontend
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
    TaskAssignment,
    ValidationResult
)
from config.config import Config

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
        
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.3,
            api_key=self.config.OPENAI_API_KEY
        )
        
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
        
        logger.info("PlanningAgent initialized")
    
    async def process_task(self, task: TaskAssignment) -> Any:
        """Process a planning task"""
        task_type = task.task_type
        
        if task_type == "create_plan":
            return await self._create_plan(task)
        elif task_type == "refine_plan":
            return await self._refine_plan(task)
        else:
            return await self._create_plan(task)
    
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
        
        prompt = ChatPromptTemplate.from_template(
            """You are an expert task planner. Create a detailed execution plan for this task.

Task: {query}

Available Agents:
{agents}

Create a step-by-step plan that:
1. Breaks down the task into atomic, manageable steps
2. Assigns each step to the most appropriate agent
3. Specifies dependencies between steps
4. Estimates completion time

Consider:
- Some steps may require RAG retrieval first
- Validation should be included for important outputs
- Complex reasoning should use the thinking_agent

Respond with your execution plan."""
        )
        
        # Stream planning process
        await self.stream_to_frontend(
            "🔍 Identifying required agents and steps...\n", 
            1
        )
        
        chain = prompt | self.llm.with_structured_output(ExecutionPlan)
        
        try:
            plan = await chain.ainvoke({
                "query": query,
                "agents": agent_descriptions
            })
            
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
        
        prompt = ChatPromptTemplate.from_template(
            """Refine this execution plan based on the feedback.

Original Plan:
{plan}

Feedback:
{feedback}

Available Agents:
{agents}

Create an improved plan that addresses the feedback."""
        )
        
        agent_descriptions = "\n".join([
            f"- {name}: {desc}" for name, desc in self.available_agents
        ])
        
        chain = prompt | self.llm.with_structured_output(ExecutionPlan)
        
        try:
            plan = await chain.ainvoke({
                "plan": str(original_plan),
                "feedback": feedback,
                "agents": agent_descriptions
            })
            
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
        prompt = ChatPromptTemplate.from_template(
            """Fix these errors in the execution plan:

Current Plan:
Goal: {goal}
Steps: {steps}

Errors to fix:
{errors}

Available Agents:
{agents}

Create a corrected plan."""
        )
        
        agent_descriptions = "\n".join([
            f"- {name}: {desc}" for name, desc in self.available_agents
        ])
        
        chain = prompt | self.llm.with_structured_output(ExecutionPlan)
        
        try:
            refined = await chain.ainvoke({
                "goal": plan.goal,
                "steps": str([s.model_dump() for s in plan.steps]),
                "errors": "\n".join(errors),
                "agents": agent_descriptions
            })
            return refined
        except:
            return plan  # Return original if refinement fails
    
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
