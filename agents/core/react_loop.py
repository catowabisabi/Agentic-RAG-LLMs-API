"""
ReAct Loop Engine
==================

實現 Reason + Act 迭代推理循環，讓 Agent 能夠：
1. 思考（Think）: 分析當前狀態，決定下一步行動
2. 行動（Act）: 執行搜尋、調用工具等
3. 觀察（Observe）: 獲取行動結果
4. 反思（Reflect）: 評估結果是否足夠回答問題

參考: app_docs/Agentic-Rag-Examples/03_ReAct.ipynb
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from config.config import Config

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """可執行的行動類型"""
    SEARCH = "search"           # 搜尋知識庫
    WEB_SEARCH = "web_search"   # 網絡搜尋
    CALCULATE = "calculate"     # 計算
    FINAL_ANSWER = "final_answer"  # 給出最終答案
    CLARIFY = "clarify"         # 需要用戶澄清


class ThoughtAction(BaseModel):
    """思考結果和決定的行動"""
    thought: str = Field(description="當前的思考內容")
    action: ActionType = Field(description="決定採取的行動")
    action_input: str = Field(description="行動的輸入參數")
    confidence: float = Field(default=0.5, description="對當前方向的信心 (0-1)")


class Observation(BaseModel):
    """觀察結果"""
    content: str = Field(description="觀察到的內容")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="來源")
    success: bool = Field(default=True, description="行動是否成功")


class ReActStep(BaseModel):
    """一個 ReAct 步驟"""
    step_number: int
    thought: str
    action: ActionType
    action_input: str
    observation: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ReActResult(BaseModel):
    """ReAct 循環的最終結果"""
    final_answer: str
    steps: List[ReActStep]
    total_iterations: int
    sources: List[Dict[str, Any]]
    success: bool
    reasoning_trace: str  # 完整推理軌跡


class ReActLoop:
    """
    ReAct 循環引擎
    
    實現 Think -> Act -> Observe -> Reflect 的迭代推理
    """
    
    def __init__(
        self,
        max_iterations: int = 3,
        on_step_callback: Optional[Callable[[ReActStep], Awaitable[None]]] = None
    ):
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.3,
            api_key=self.config.OPENAI_API_KEY
        )
        self.max_iterations = max_iterations
        self.on_step_callback = on_step_callback
        
        # 工具註冊表
        self.tools: Dict[ActionType, Callable] = {}
        
    def register_tool(self, action_type: ActionType, tool_func: Callable):
        """註冊一個工具"""
        self.tools[action_type] = tool_func
        logger.info(f"Registered tool: {action_type.value}")
    
    async def think(
        self,
        query: str,
        context: str,
        previous_steps: List[ReActStep]
    ) -> ThoughtAction:
        """
        思考步驟：分析當前狀態，決定下一步行動
        """
        # 構建歷史軌跡
        history = ""
        for step in previous_steps:
            history += f"\nStep {step.step_number}:\n"
            history += f"  Thought: {step.thought}\n"
            history += f"  Action: {step.action.value}({step.action_input})\n"
            if step.observation:
                history += f"  Observation: {step.observation[:500]}...\n"
        
        prompt = ChatPromptTemplate.from_template(
            """You are a reasoning agent. Analyze the question and decide your next action.

Question: {query}

Current Knowledge Context:
{context}

Previous Steps:
{history}

Available Actions:
1. search: Search the knowledge base for more information. Input: search query string
2. final_answer: Provide the final answer if you have enough information. Input: your complete answer
3. clarify: Ask for clarification if the question is unclear. Input: clarification question

Think step by step:
1. What do I know so far?
2. What do I still need to find out?
3. Is the current context sufficient to answer the question?

If you have gathered enough information to fully answer the question, use final_answer.
If you need more information, use search with a specific query.

Respond in this exact JSON format:
{{
    "thought": "your reasoning here",
    "action": "search|final_answer|clarify",
    "action_input": "the input for your chosen action",
    "confidence": 0.0-1.0
}}
"""
        )
        
        try:
            chain = prompt | self.llm
            result = await chain.ainvoke({
                "query": query,
                "context": context[:3000] if context else "No context yet.",
                "history": history if history else "No previous steps."
            })
            
            response = result.content if hasattr(result, 'content') else str(result)
            
            # 解析 JSON 回應
            import json
            # 清理可能的 markdown 標記
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            data = json.loads(response.strip())
            
            action_str = data.get("action", "search").lower()
            action_map = {
                "search": ActionType.SEARCH,
                "final_answer": ActionType.FINAL_ANSWER,
                "clarify": ActionType.CLARIFY,
                "web_search": ActionType.WEB_SEARCH,
                "calculate": ActionType.CALCULATE
            }
            
            return ThoughtAction(
                thought=data.get("thought", ""),
                action=action_map.get(action_str, ActionType.SEARCH),
                action_input=data.get("action_input", query),
                confidence=float(data.get("confidence", 0.5))
            )
            
        except Exception as e:
            logger.error(f"Think step error: {e}")
            # 發生錯誤時，嘗試直接回答
            return ThoughtAction(
                thought=f"Error during reasoning: {e}",
                action=ActionType.FINAL_ANSWER,
                action_input="I encountered an issue while processing your question. Please try rephrasing it.",
                confidence=0.3
            )
    
    async def act(
        self,
        action: ActionType,
        action_input: str
    ) -> Observation:
        """
        執行行動步驟
        """
        if action == ActionType.FINAL_ANSWER:
            return Observation(
                content=action_input,
                sources=[],
                success=True
            )
        
        if action == ActionType.CLARIFY:
            return Observation(
                content=f"Clarification needed: {action_input}",
                sources=[],
                success=True
            )
        
        # 查找已註冊的工具
        tool_func = self.tools.get(action)
        if tool_func:
            try:
                result = await tool_func(action_input)
                return Observation(
                    content=result.get("content", str(result)),
                    sources=result.get("sources", []),
                    success=True
                )
            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                return Observation(
                    content=f"Error executing {action.value}: {str(e)}",
                    sources=[],
                    success=False
                )
        
        return Observation(
            content=f"No tool registered for action: {action.value}",
            sources=[],
            success=False
        )
    
    async def run(
        self,
        query: str,
        initial_context: str = ""
    ) -> ReActResult:
        """
        執行完整的 ReAct 循環
        """
        steps: List[ReActStep] = []
        all_sources: List[Dict[str, Any]] = []
        accumulated_context = initial_context
        
        logger.info(f"[ReAct] Starting loop for query: {query[:50]}...")
        
        for iteration in range(self.max_iterations):
            step_number = iteration + 1
            logger.info(f"[ReAct] Iteration {step_number}/{self.max_iterations}")
            
            # Step 1: Think
            thought_action = await self.think(query, accumulated_context, steps)
            
            step = ReActStep(
                step_number=step_number,
                thought=thought_action.thought,
                action=thought_action.action,
                action_input=thought_action.action_input
            )
            
            # 回調通知
            if self.on_step_callback:
                await self.on_step_callback(step)
            
            # Step 2: Act
            observation = await self.act(
                thought_action.action,
                thought_action.action_input
            )
            
            step.observation = observation.content[:1000]  # 限制觀察長度
            steps.append(step)
            all_sources.extend(observation.sources)
            
            # Step 3: Check if we should stop
            if thought_action.action == ActionType.FINAL_ANSWER:
                logger.info(f"[ReAct] Final answer reached at iteration {step_number}")
                
                # 構建推理軌跡
                trace = self._build_reasoning_trace(steps)
                
                return ReActResult(
                    final_answer=observation.content,
                    steps=steps,
                    total_iterations=step_number,
                    sources=all_sources,
                    success=True,
                    reasoning_trace=trace
                )
            
            if thought_action.action == ActionType.CLARIFY:
                return ReActResult(
                    final_answer=observation.content,
                    steps=steps,
                    total_iterations=step_number,
                    sources=[],
                    success=True,
                    reasoning_trace=self._build_reasoning_trace(steps)
                )
            
            # Step 4: Update context with observation
            accumulated_context += f"\n\n[Search Result {step_number}]:\n{observation.content}"
            
            # 如果信心足夠高，提前結束
            if thought_action.confidence >= 0.85:
                logger.info(f"[ReAct] High confidence ({thought_action.confidence}), generating final answer")
                # 強制生成最終答案
                final_thought = await self.think(
                    query,
                    accumulated_context,
                    steps
                )
                if final_thought.action == ActionType.FINAL_ANSWER:
                    return ReActResult(
                        final_answer=final_thought.action_input,
                        steps=steps,
                        total_iterations=step_number,
                        sources=all_sources,
                        success=True,
                        reasoning_trace=self._build_reasoning_trace(steps)
                    )
        
        # 達到最大迭代次數，強制生成答案
        logger.warning(f"[ReAct] Max iterations reached, forcing final answer")
        
        final_prompt = ChatPromptTemplate.from_template(
            """Based on all the information gathered, provide the best possible answer to the question.

Question: {query}

Gathered Information:
{context}

Provide a comprehensive answer based on available information. If information is incomplete, acknowledge this but still provide the best answer you can."""
        )
        
        chain = final_prompt | self.llm
        result = await chain.ainvoke({
            "query": query,
            "context": accumulated_context[:4000]
        })
        
        final_answer = result.content if hasattr(result, 'content') else str(result)
        
        return ReActResult(
            final_answer=final_answer,
            steps=steps,
            total_iterations=self.max_iterations,
            sources=all_sources,
            success=True,
            reasoning_trace=self._build_reasoning_trace(steps)
        )
    
    def _build_reasoning_trace(self, steps: List[ReActStep]) -> str:
        """構建可讀的推理軌跡"""
        trace_parts = []
        for step in steps:
            trace_parts.append(f"**Step {step.step_number}**")
            trace_parts.append(f"💭 Thought: {step.thought}")
            trace_parts.append(f"🔧 Action: {step.action.value}({step.action_input[:100]}...)")
            if step.observation:
                trace_parts.append(f"👁️ Observation: {step.observation[:200]}...")
            trace_parts.append("")
        
        return "\n".join(trace_parts)


# 單例獲取
_react_loop_instance = None


def get_react_loop(max_iterations: int = 3) -> ReActLoop:
    """獲取 ReAct 循環引擎單例"""
    global _react_loop_instance
    if _react_loop_instance is None:
        _react_loop_instance = ReActLoop(max_iterations=max_iterations)
    return _react_loop_instance
