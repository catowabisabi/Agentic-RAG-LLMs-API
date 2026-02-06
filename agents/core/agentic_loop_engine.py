# -*- coding: utf-8 -*-
"""
=============================================================================
Agentic Loop Engine - 無限反饋循環引擎
=============================================================================

Architecture V2 核心組件：Manager Agent 的主循環引擎

功能：
1. 目標發現 - 從用戶查詢中提取目標
2. 任務規劃 - 調用 Planning Agent 生成任務
3. 任務執行 - 分發任務給對應 Agent
4. 結果聚合 - 收集並整合結果
5. 最終總結 - 生成用戶可讀的總結

設計原則：
- 無限循環直到完成或失敗
- 即時推送中間結果
- 完整的思考過程保留
- 錯誤不靜默處理（測試模式）

=============================================================================
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime

from pydantic import BaseModel, Field

from agents.core.agentic_task_queue import (
    TaskQueue, TodoTask, TodoStatus,
    AgenticLoopContext, AgenticLoopState,
    create_task_queue, create_todo_task
)
from services.llm_service import LLMService

logger = logging.getLogger(__name__)


class GoalAnalysis(BaseModel):
    """目標分析結果"""
    goal: str = Field(description="識別出的目標")
    is_casual: bool = Field(default=False, description="是否為閒聊")
    complexity: str = Field(default="medium", description="複雜度: simple | medium | complex")
    requires_rag: bool = Field(default=False, description="是否需要 RAG")
    requires_planning: bool = Field(default=True, description="是否需要規劃")
    reasoning: str = Field(description="分析原因")


class AgentTaskResult(BaseModel):
    """Agent 任務執行結果"""
    success: bool = Field(description="是否成功")
    data: Dict[str, Any] = Field(default_factory=dict, description="結果數據")
    message: str = Field(default="", description="可讀消息")
    error: Optional[str] = Field(default=None, description="錯誤信息")


class AgenticLoopEngine:
    """
    Agentic Loop 引擎
    
    這是 Agentic AI 的心臟，實現無限反饋循環。
    
    核心流程：
    1. Goal Detection - 分析用戶意圖，發現目標
    2. Planning - 調用 PlanningAgent 生成任務列表
    3. Execution Loop - 循環執行任務直到完成
    4. Aggregation - 收集所有結果
    5. Summarization - 生成最終總結
    
    關鍵特性：
    - 即時推送：完成任務後立即推送給用戶
    - 持續執行：推送後繼續執行剩餘任務
    - 重試機制：失敗任務自動重試（最多 5 次）
    - 完整記錄：所有思考和決策都保留
    """
    
    def __init__(
        self,
        on_thinking_step: Optional[Callable[[str, str, Dict], Awaitable[None]]] = None,
        on_task_update: Optional[Callable[[TodoTask], Awaitable[None]]] = None,
        on_intermediate_result: Optional[Callable[[str, Dict, str], Awaitable[None]]] = None,
        on_final_response: Optional[Callable[[str], Awaitable[None]]] = None,
        max_parallel_tasks: int = 3
    ):
        """
        初始化 Agentic Loop 引擎
        
        Args:
            on_thinking_step: 思考步驟回調 (step_type, content, metadata)
            on_task_update: 任務更新回調 (task)
            on_intermediate_result: 中間結果回調 (task_id, result, message)
            on_final_response: 最終回應回調 (summary)
            max_parallel_tasks: 最大並行任務數
        """
        self.llm_service = LLMService()
        
        # 事件回調
        self.on_thinking_step = on_thinking_step
        self.on_task_update = on_task_update
        self.on_intermediate_result = on_intermediate_result
        self.on_final_response = on_final_response
        
        # 配置
        self.max_parallel_tasks = max_parallel_tasks
        
        # Agent 註冊表（延遲導入避免循環依賴）
        self._agents: Dict[str, Any] = {}
        
        logger.info("[AgenticLoop] Engine initialized")
    
    def _get_agent(self, agent_name: str):
        """獲取 Agent 實例（懶加載）"""
        if agent_name not in self._agents:
            # 延遲導入
            if agent_name == "planning_agent":
                from agents.core.planning_agent import PlanningAgent
                self._agents[agent_name] = PlanningAgent()
            elif agent_name == "rag_agent":
                from agents.core.rag_agent import RAGAgent
                self._agents[agent_name] = RAGAgent()
            elif agent_name == "thinking_agent":
                from agents.core.thinking_agent import ThinkingAgent
                self._agents[agent_name] = ThinkingAgent()
            elif agent_name == "validation_agent":
                from agents.core.validation_agent import ValidationAgent
                self._agents[agent_name] = ValidationAgent()
            elif agent_name == "summarize_agent":
                from agents.auxiliary.summarize_agent import SummarizeAgent
                self._agents[agent_name] = SummarizeAgent()
            elif agent_name == "translate_agent":
                from agents.auxiliary.translate_agent import TranslateAgent
                self._agents[agent_name] = TranslateAgent()
            elif agent_name == "calculation_agent":
                from agents.auxiliary.calculation_agent import CalculationAgent
                self._agents[agent_name] = CalculationAgent()
            elif agent_name == "tool_agent":
                from agents.auxiliary.tool_agent import ToolAgent
                self._agents[agent_name] = ToolAgent()
            elif agent_name == "data_agent":
                from agents.auxiliary.data_agent import DataAgent
                self._agents[agent_name] = DataAgent()
            else:
                raise ValueError(f"Unknown agent: {agent_name}")
        
        return self._agents[agent_name]
    
    async def _emit_thinking(self, step_type: str, content: str, metadata: Dict = None):
        """發射思考步驟事件"""
        if self.on_thinking_step:
            await self.on_thinking_step(step_type, content, metadata or {})
        logger.info(f"[AgenticLoop] Thinking: {step_type} - {content[:50]}...")
    
    async def _emit_task_update(self, task: TodoTask):
        """發射任務更新事件"""
        if self.on_task_update:
            await self.on_task_update(task)
    
    async def _emit_intermediate(self, task_id: str, result: Dict, message: str):
        """發射中間結果事件"""
        if self.on_intermediate_result:
            await self.on_intermediate_result(task_id, result, message)
        logger.info(f"[AgenticLoop] Intermediate result for {task_id}: {message[:50]}...")
    
    async def _emit_final(self, summary: str):
        """發射最終回應事件"""
        if self.on_final_response:
            await self.on_final_response(summary)
    
    # =========================================================================
    # Phase 1: Goal Detection
    # =========================================================================
    
    async def detect_goal(self, user_query: str, context: str = "") -> GoalAnalysis:
        """
        Phase 1: 目標發現
        
        分析用戶查詢，識別出明確的目標。
        
        NOTE: 不使用 fallback，錯誤會傳播
        """
        await self._emit_thinking("goal_detection", "Analyzing user query to identify goal...")
        
        prompt = f"""Analyze this user query and identify the goal.

User Query: "{user_query}"

Context: {context if context else "No additional context"}

Respond in this JSON format:
{{
    "goal": "The specific goal the user wants to achieve",
    "is_casual": true/false,
    "complexity": "simple" | "medium" | "complex",
    "requires_rag": true/false,
    "requires_planning": true/false,
    "reasoning": "Brief explanation of your analysis"
}}

Examples:
- "Hello" -> is_casual=true, requires_planning=false
- "What is VBA?" -> is_casual=false, complexity=simple, requires_rag=false
- "Search my documents for project X" -> requires_rag=true
- "Compare A and B, then recommend..." -> complexity=complex, requires_planning=true
"""
        
        # NOTE: No try-catch - errors propagate for testing
        result = await self.llm_service.generate_json(
            prompt=prompt,
            output_schema=GoalAnalysis.model_json_schema(),
            temperature=0.1
        )
        
        goal = GoalAnalysis(**result)
        await self._emit_thinking("goal_detected", f"Goal: {goal.goal}", goal.model_dump())
        
        return goal
    
    # =========================================================================
    # Phase 2: Planning
    # =========================================================================
    
    async def generate_plan(self, goal: str, context: AgenticLoopContext) -> TaskQueue:
        """
        Phase 2: 任務規劃
        
        調用 Planning Agent 生成任務列表。
        
        NOTE: 不使用 fallback，錯誤會傳播
        """
        await self._emit_thinking("planning", f"Generating plan for goal: {goal}")
        
        # 獲取 Planning Agent
        planning_agent = self._get_agent("planning_agent")
        
        # 創建任務
        from agents.shared_services.message_protocol import TaskAssignment
        task = TaskAssignment(
            task_id=f"plan_{context.session_id}",
            description=goal,
            task_type="planning",
            input_data={
                "query": goal,
                "session_id": context.session_id
            }
        )
        
        # NOTE: No try-catch - errors propagate for testing
        plan_result = await planning_agent.process_task(task)
        
        # 創建 TaskQueue
        task_queue = create_task_queue(
            goal=goal,
            session_id=context.session_id,
            on_update=self._emit_task_update
        )
        
        # 將計劃轉換為 TodoTasks
        if "steps" in plan_result:
            for i, step in enumerate(plan_result["steps"]):
                todo = create_todo_task(
                    title=step.get("action", f"Step {i+1}"),
                    description=step.get("description", ""),
                    agent=step.get("agent", "thinking_agent"),
                    depends_on=self._resolve_dependencies(step.get("input_from", []), plan_result["steps"]),
                    priority=len(plan_result["steps"]) - i  # 先規劃的任務優先級高
                )
                task_queue.add_task(todo)
        
        await self._emit_thinking(
            "plan_created", 
            f"Created {len(task_queue.tasks)} tasks",
            {"tasks": [t.title for t in task_queue.tasks.values()]}
        )
        
        return task_queue
    
    def _resolve_dependencies(self, input_from: List[int], steps: List[Dict]) -> List[str]:
        """解析任務依賴（步驟編號 -> 任務 ID）"""
        # TODO: 實現依賴解析邏輯
        return []
    
    # =========================================================================
    # Phase 3: Execution Loop
    # =========================================================================
    
    async def execute_loop(self, context: AgenticLoopContext) -> bool:
        """
        Phase 3: 執行循環
        
        核心無限循環，直到所有任務完成或達到終止條件。
        
        Returns:
            True if all tasks completed successfully
        """
        task_queue = context.task_queue
        if not task_queue:
            raise ValueError("TaskQueue not initialized")
        
        context.state = AgenticLoopState.EXECUTING
        await self._emit_thinking("execution_start", f"Starting execution loop with {len(task_queue.tasks)} tasks")
        
        # 無限循環直到終止
        iteration = 0
        max_iterations = 100  # 安全限制
        
        while not task_queue.is_terminal_state():
            iteration += 1
            if iteration > max_iterations:
                raise RuntimeError(f"Execution loop exceeded max iterations ({max_iterations})")
            
            # 獲取可執行的任務
            ready_tasks = task_queue.get_ready_tasks()
            
            if not ready_tasks:
                # 有任務在執行中，等待
                in_progress = task_queue.get_in_progress()
                if in_progress:
                    context.state = AgenticLoopState.WAITING
                    await self._emit_thinking("waiting", f"Waiting for {len(in_progress)} tasks to complete...")
                    await asyncio.sleep(0.5)  # 短暫等待
                    continue
                
                # 檢查是否有可重試的失敗任務
                retryable = task_queue.get_retryable()
                if retryable:
                    for task in retryable:
                        task.mark_retry()
                        await task_queue.update_task(task.id, status=TodoStatus.RETRYING)
                    continue
                
                # 沒有任務可執行，退出循環
                break
            
            # 限制並行任務數
            tasks_to_run = ready_tasks[:self.max_parallel_tasks]
            
            # 並行執行任務
            context.state = AgenticLoopState.EXECUTING
            futures = []
            
            for task in tasks_to_run:
                task.mark_started()
                await task_queue.update_task(task.id, status=TodoStatus.IN_PROGRESS)
                
                future = asyncio.create_task(self._execute_single_task(task, context))
                futures.append((task.id, future))
            
            # 使用 as_completed 處理結果（有結果就處理）
            for task_id, future in futures:
                # NOTE: No try-catch - errors propagate for testing
                result: AgentTaskResult = await future
                task = task_queue.get_task(task_id)
                
                if result.success:
                    task.mark_completed(result.data, result.message)
                    
                    # 即時推送中間結果
                    if task.can_show_to_user and task.intermediate_message:
                        context.add_intermediate_result(task.id, result.data, task.intermediate_message)
                        await self._emit_intermediate(task.id, result.data, task.intermediate_message)
                else:
                    if task.can_retry():
                        task.mark_retry()
                        await self._emit_thinking(
                            "task_retry",
                            f"Task '{task.title}' failed, retrying ({task.retry_count}/{task.max_retries}): {result.error}"
                        )
                    else:
                        task.mark_failed(result.error or "Unknown error")
                        await self._emit_thinking("task_failed", f"Task '{task.title}' failed permanently: {result.error}")
                
                await task_queue.update_task(task.id, status=task.status)
            
            # 更新進度
            progress = task_queue.get_progress()
            await self._emit_thinking("progress", f"Progress: {progress['progress']}%", progress)
        
        return task_queue.has_all_completed()
    
    async def _execute_single_task(self, task: TodoTask, context: AgenticLoopContext) -> AgentTaskResult:
        """
        執行單個任務
        
        NOTE: 不使用 fallback，錯誤會傳播
        """
        agent_name = task.assigned_agent or "thinking_agent"
        
        await self._emit_thinking(
            "task_executing",
            f"Executing task '{task.title}' with {agent_name}",
            {"task_id": task.id, "agent": agent_name}
        )
        
        # 獲取 Agent
        agent = self._get_agent(agent_name)
        
        # 創建任務分配
        from agents.shared_services.message_protocol import TaskAssignment
        assignment = TaskAssignment(
            task_id=task.id,
            description=task.description,
            task_type=agent_name,
            input_data={
                "query": task.description,
                "session_id": context.session_id,
                "goal": context.goal
            }
        )
        
        # NOTE: No try-catch - errors propagate for testing
        result = await agent.process_task(assignment)
        
        # 構建結果
        return AgentTaskResult(
            success=result.get("status") != "error",
            data=result,
            message=result.get("response", result.get("summary", "")),
            error=result.get("error")
        )
    
    # =========================================================================
    # Phase 4 & 5: Aggregation & Summarization
    # =========================================================================
    
    async def generate_summary(self, context: AgenticLoopContext) -> str:
        """
        Phase 4 & 5: 聚合結果並生成最終總結
        
        NOTE: 不使用 fallback，錯誤會傳播
        """
        context.state = AgenticLoopState.AGGREGATING
        await self._emit_thinking("aggregating", "Collecting all results...")
        
        task_queue = context.task_queue
        all_results = task_queue.get_all_results()
        execution_summary = task_queue.get_execution_summary()
        
        context.state = AgenticLoopState.SUMMARIZING
        await self._emit_thinking("summarizing", "Generating final summary...")
        
        # 構建總結 prompt
        results_text = "\n".join([
            f"- Task '{task_id}': {result.get('response', result.get('summary', str(result)))[:200]}"
            for task_id, result in all_results.items()
        ])
        
        prompt = f"""Generate a comprehensive summary of the completed tasks.

Original Goal: {context.goal}

Execution Summary:
- Total Tasks: {execution_summary['total_tasks']}
- Completed: {execution_summary['completed_tasks']}
- Failed: {execution_summary['failed_tasks']}
- All Completed: {execution_summary['all_completed']}

Task Results:
{results_text}

Intermediate Results Shown to User:
{len(context.intermediate_results)} results were already shown.

Please provide:
1. A clear summary of what was accomplished
2. Key findings or results
3. Any issues encountered (if any)
4. Next steps or recommendations (if applicable)

Respond in the same language as the original query.
"""
        
        # NOTE: No try-catch - errors propagate for testing
        result = await self.llm_service.generate(prompt=prompt, temperature=0.3)
        summary = result.content
        
        context.final_summary = summary
        context.state = AgenticLoopState.DONE
        context.completed_at = datetime.now()
        
        await self._emit_final(summary)
        
        return summary
    
    # =========================================================================
    # Main Entry Point
    # =========================================================================
    
    async def run(self, user_query: str, session_id: str, context_str: str = "") -> Dict[str, Any]:
        """
        運行 Agentic Loop
        
        這是主入口點，執行完整的 Agentic 工作流。
        
        Args:
            user_query: 用戶查詢
            session_id: 會話 ID
            context_str: 額外上下文
            
        Returns:
            完整的執行結果
        """
        logger.info(f"[AgenticLoop] Starting for query: {user_query[:50]}...")
        
        # 創建上下文
        context = AgenticLoopContext(
            session_id=session_id,
            user_query=user_query
        )
        context.started_at = datetime.now()
        
        # Phase 1: Goal Detection
        goal_analysis = await self.detect_goal(user_query, context_str)
        context.goal = goal_analysis.goal
        
        # 如果是閒聊，直接返回（不需要複雜流程）
        if goal_analysis.is_casual:
            await self._emit_thinking("casual_detected", "This is casual chat, no planning needed")
            return {
                "is_casual": True,
                "goal": goal_analysis.goal,
                "reasoning": goal_analysis.reasoning
            }
        
        # Phase 2: Planning
        if goal_analysis.requires_planning:
            context.task_queue = await self.generate_plan(goal_analysis.goal, context)
        else:
            # 簡單查詢，創建單一任務
            context.task_queue = create_task_queue(
                goal=goal_analysis.goal,
                session_id=session_id,
                on_update=self._emit_task_update
            )
            
            if goal_analysis.requires_rag:
                task = create_todo_task(
                    title="Search Knowledge Base",
                    description=goal_analysis.goal,
                    agent="rag_agent"
                )
            else:
                task = create_todo_task(
                    title="Analyze Query",
                    description=goal_analysis.goal,
                    agent="thinking_agent"
                )
            context.task_queue.add_task(task)
        
        # Phase 3: Execution Loop
        success = await self.execute_loop(context)
        
        # Phase 4 & 5: Summarization
        summary = await self.generate_summary(context)
        
        # 返回完整結果
        return {
            "success": success,
            "goal": context.goal,
            "summary": summary,
            "thinking_steps": context.thinking_steps,
            "intermediate_results": context.intermediate_results,
            "execution_summary": context.task_queue.get_execution_summary() if context.task_queue else None,
            "started_at": context.started_at.isoformat() if context.started_at else None,
            "completed_at": context.completed_at.isoformat() if context.completed_at else None
        }


# =============================================================================
# Factory Function
# =============================================================================

def create_agentic_loop(
    on_thinking: Callable = None,
    on_task: Callable = None,
    on_intermediate: Callable = None,
    on_final: Callable = None
) -> AgenticLoopEngine:
    """創建 Agentic Loop 引擎"""
    return AgenticLoopEngine(
        on_thinking_step=on_thinking,
        on_task_update=on_task,
        on_intermediate_result=on_intermediate,
        on_final_response=on_final
    )
