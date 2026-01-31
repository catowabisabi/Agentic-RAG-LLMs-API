"""
ReAct Loop Engine (Enhanced with PEV and Self-Correction)
==========================================================

實現 Reason + Act 迭代推理循環，讓 Agent 能夠：
1. 思考（Think）: 分析當前狀態，決定下一步行動
2. 行動（Act）: 執行搜尋、調用工具等
3. 觀察（Observe）: 獲取行動結果
4. 驗證（Verify - PEV）: 評估結果品質
5. 反思（Reflect）: 評估結果是否足夠回答問題，Self-Correction

參考: 
- app_docs/Agentic-Rag-Examples/03_ReAct.ipynb
- app_docs/Agentic-Rag-Examples/06_PEV.ipynb
- example/01/05-agentic-rag/README.md
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
    SEARCH = "search"           # 搜尋知識庫 (RAG)
    WEB_SEARCH = "web_search"   # 網絡搜尋
    CALCULATE = "calculate"     # 計算
    FINAL_ANSWER = "final_answer"  # 給出最終答案
    CLARIFY = "clarify"         # 需要用戶澄清
    REFINE_QUERY = "refine_query"  # 改寫查詢 (Self-Correction)
    VERIFY = "verify"           # 驗證資訊


class VerificationResult(BaseModel):
    """PEV 驗證結果"""
    is_valid: bool = Field(description="資訊是否有效")
    quality_score: float = Field(default=0.5, description="品質分數 0-1")
    issues: List[str] = Field(default_factory=list, description="發現的問題")
    should_retry: bool = Field(default=False, description="是否需要重試")
    retry_strategy: Optional[str] = Field(default=None, description="重試策略")


class ThoughtAction(BaseModel):
    """思考結果和決定的行動"""
    thought: str = Field(description="當前的思考內容")
    action: ActionType = Field(description="決定採取的行動")
    action_input: str = Field(description="行動的輸入參數")
    confidence: float = Field(default=0.5, description="對當前方向的信心 (0-1)")
    self_assessment: str = Field(default="", description="自我評估：我能處理這個問題嗎?")


class Observation(BaseModel):
    """觀察結果"""
    content: str = Field(description="觀察到的內容")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="來源")
    success: bool = Field(default=True, description="行動是否成功")
    quality_score: float = Field(default=0.5, description="品質評分 0-1")


class ReActStep(BaseModel):
    """一個 ReAct 步驟 (增加驗證結果)"""
    step_number: int
    thought: str
    action: ActionType
    action_input: str
    observation: Optional[str] = None
    verification: Optional[VerificationResult] = None
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ReActResult(BaseModel):
    """ReAct 循環的最終結果"""
    final_answer: str
    steps: List[ReActStep]
    total_iterations: int
    sources: List[Dict[str, Any]]
    success: bool
    reasoning_trace: str  # 完整推理軌跡
    verification_passed: bool = Field(default=True, description="是否通過 PEV 驗證")
    strategy_used: str = Field(default="react", description="使用的策略")


class ReActLoop:
    """
    ReAct 循環引擎 (Enhanced with PEV and Self-Correction)
    
    實現 Think -> Act -> Observe -> Verify -> Reflect 的迭代推理
    
    關鍵改進：
    1. RAG 作為 Tool - 動態決定是否使用
    2. PEV 驗證 - 每個步驟都驗證結果
    3. Self-Correction - 失敗時自動調整策略
    4. Metacognitive Assessment - 自我評估能力邊界
    """
    
    def __init__(
        self,
        max_iterations: int = 5,
        verification_threshold: float = 0.6,
        max_retries_per_step: int = 2,
        on_step_callback: Optional[Callable[[ReActStep], Awaitable[None]]] = None
    ):
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.3,
            api_key=self.config.OPENAI_API_KEY
        )
        self.max_iterations = max_iterations
        self.verification_threshold = verification_threshold
        self.max_retries_per_step = max_retries_per_step
        self.on_step_callback = on_step_callback
        
        # 工具註冊表
        self.tools: Dict[ActionType, Callable] = {}
        
        # 失敗記錄 (用於 Self-Correction)
        self.failed_attempts: List[Dict[str, Any]] = []
        
    def register_tool(self, action_type: ActionType, tool_func: Callable):
        """註冊一個工具"""
        self.tools[action_type] = tool_func
        logger.info(f"Registered tool: {action_type.value}")
    
    async def verify_observation(
        self,
        query: str,
        observation: Observation,
        step_context: str
    ) -> VerificationResult:
        """
        PEV 驗證器：檢查觀察結果的品質和有效性
        
        參考: 06_PEV.ipynb
        """
        prompt = ChatPromptTemplate.from_template(
            """You are a verification agent (PEV - Plan, Execute, Verify).
Your job is to verify if the tool output is valid and useful for answering the question.

Original Question: {query}

Tool Output to Verify:
{observation}

Step Context:
{step_context}

Check for:
1. Is this a valid result or an error message?
2. Does the result contain relevant information for the question?
3. Is the information complete enough to proceed?
4. Are there any inconsistencies or red flags?

If the result is an error or insufficient:
- Suggest a retry strategy: "refine_query" (try different search terms), 
  "different_source" (try another tool), "decompose" (break into simpler questions)

Respond in JSON format:
{{
    "is_valid": true/false,
    "quality_score": 0.0-1.0,
    "issues": ["issue1", "issue2"],
    "should_retry": true/false,
    "retry_strategy": "refine_query|different_source|decompose|null"
}}
"""
        )
        
        try:
            chain = prompt | self.llm
            result = await chain.ainvoke({
                "query": query,
                "observation": observation.content[:2000],
                "step_context": step_context[:1000]
            })
            
            response = result.content if hasattr(result, 'content') else str(result)
            
            import json
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            data = json.loads(response.strip())
            
            return VerificationResult(
                is_valid=data.get("is_valid", True),
                quality_score=float(data.get("quality_score", 0.5)),
                issues=data.get("issues", []),
                should_retry=data.get("should_retry", False),
                retry_strategy=data.get("retry_strategy")
            )
            
        except Exception as e:
            logger.error(f"Verification error: {e}")
            # 默認通過，避免阻塞流程
            return VerificationResult(
                is_valid=True,
                quality_score=0.5,
                issues=[f"Verification error: {e}"]
            )
    
    async def self_correct(
        self,
        query: str,
        failed_action: ActionType,
        failed_input: str,
        failure_reason: str,
        retry_strategy: Optional[str]
    ) -> ThoughtAction:
        """
        Self-Correction: 當步驟失敗時，生成新的策略
        
        參考: 06_PEV.ipynb 的 re-planning 機制
        """
        prompt = ChatPromptTemplate.from_template(
            """You are a self-correcting agent. A previous action failed and you need to adapt.

Original Question: {query}

Failed Action: {failed_action}({failed_input})
Failure Reason: {failure_reason}

Suggested Retry Strategy: {retry_strategy}

Previous Failed Attempts:
{failed_attempts}

Generate a NEW action that avoids the previous mistakes:
1. If "refine_query": Try different search terms or phrasing
2. If "different_source": Use a different tool or approach
3. If "decompose": Break the question into simpler parts

Do NOT repeat the same failed query.

Respond in JSON:
{{
    "thought": "reasoning about the correction",
    "action": "search|calculate|final_answer|clarify",
    "action_input": "new input that avoids previous mistakes",
    "confidence": 0.0-1.0,
    "self_assessment": "assessment of ability to handle this"
}}
"""
        )
        
        failed_attempts_str = "\n".join([
            f"- {a['action']}: {a['input'][:50]}... -> {a['reason']}"
            for a in self.failed_attempts[-3:]  # 最近3次失敗
        ])
        
        try:
            chain = prompt | self.llm
            result = await chain.ainvoke({
                "query": query,
                "failed_action": failed_action.value,
                "failed_input": failed_input[:200],
                "failure_reason": failure_reason,
                "retry_strategy": retry_strategy or "refine_query",
                "failed_attempts": failed_attempts_str or "None"
            })
            
            response = result.content if hasattr(result, 'content') else str(result)
            
            import json
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
                "calculate": ActionType.CALCULATE,
                "refine_query": ActionType.REFINE_QUERY
            }
            
            return ThoughtAction(
                thought=data.get("thought", "Attempting correction"),
                action=action_map.get(action_str, ActionType.SEARCH),
                action_input=data.get("action_input", query),
                confidence=float(data.get("confidence", 0.4)),
                self_assessment=data.get("self_assessment", "")
            )
            
        except Exception as e:
            logger.error(f"Self-correction error: {e}")
            # 最後手段：直接回答
            return ThoughtAction(
                thought=f"Self-correction failed: {e}. Will attempt direct answer.",
                action=ActionType.FINAL_ANSWER,
                action_input="I apologize, but I encountered difficulties processing your question. Could you please rephrase it?",
                confidence=0.2,
                self_assessment="Low confidence due to repeated failures"
            )
    
    async def think(
        self,
        query: str,
        context: str,
        previous_steps: List[ReActStep]
    ) -> ThoughtAction:
        """
        思考步驟：分析當前狀態，決定下一步行動
        
        增強：加入 Metacognitive 自我評估
        """
        # 構建歷史軌跡
        history = ""
        for step in previous_steps:
            history += f"\nStep {step.step_number}:\n"
            history += f"  Thought: {step.thought}\n"
            history += f"  Action: {step.action.value}({step.action_input})\n"
            if step.observation:
                history += f"  Observation: {step.observation[:500]}...\n"
            if step.verification:
                history += f"  Verification: valid={step.verification.is_valid}, score={step.verification.quality_score}\n"
        
        # 構建失敗記錄
        failed_info = ""
        if self.failed_attempts:
            failed_info = "Failed attempts to avoid:\n" + "\n".join([
                f"- {a['input'][:50]}..."
                for a in self.failed_attempts[-3:]
            ])
        
        prompt = ChatPromptTemplate.from_template(
            """You are a reasoning agent with self-awareness. Analyze the question and decide your next action.

Question: {query}

Current Knowledge Context:
{context}

Previous Steps:
{history}

{failed_info}

Available Actions:
1. search: Search the knowledge base for more information. Input: search query string
2. final_answer: Provide the final answer if you have enough information. Input: your complete answer
3. clarify: Ask for clarification if the question is unclear. Input: clarification question
4. calculate: Perform a calculation. Input: the calculation expression
5. refine_query: Refine a previous search query that didn't work well. Input: improved query

**Metacognitive Self-Assessment:**
Before deciding, ask yourself:
- Do I have enough information to answer confidently?
- Is this within my knowledge capabilities?
- Should I search for more information or can I answer directly?
- If previous searches failed, how should I adjust my approach?

Think step by step:
1. What do I know so far?
2. What do I still need to find out?
3. Is the current context sufficient to answer the question?
4. Can I answer this confidently, or do I need more information?

If you have gathered enough information to fully answer the question, use final_answer.
If you need more information, use search with a specific query.
If previous searches didn't help, try refine_query with different terms.

Respond in this exact JSON format:
{{
    "thought": "your reasoning here",
    "action": "search|final_answer|clarify|calculate|refine_query",
    "action_input": "the input for your chosen action",
    "confidence": 0.0-1.0,
    "self_assessment": "brief assessment: can I handle this? what are my limitations here?"
}}
"""
        )
        
        try:
            chain = prompt | self.llm
            result = await chain.ainvoke({
                "query": query,
                "context": context[:3000] if context else "No context yet.",
                "history": history if history else "No previous steps.",
                "failed_info": failed_info
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
                "calculate": ActionType.CALCULATE,
                "refine_query": ActionType.REFINE_QUERY,
                "verify": ActionType.VERIFY
            }
            
            return ThoughtAction(
                thought=data.get("thought", ""),
                action=action_map.get(action_str, ActionType.SEARCH),
                action_input=data.get("action_input", query),
                confidence=float(data.get("confidence", 0.5)),
                self_assessment=data.get("self_assessment", "")
            )
            
        except Exception as e:
            logger.error(f"Think step error: {e}")
            # 發生錯誤時，嘗試直接回答
            return ThoughtAction(
                thought=f"Error during reasoning: {e}",
                action=ActionType.FINAL_ANSWER,
                action_input="I encountered an issue while processing your question. Please try rephrasing it.",
                confidence=0.3,
                self_assessment="Error occurred - low confidence"
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
                success=True,
                quality_score=0.8
            )
        
        if action == ActionType.CLARIFY:
            return Observation(
                content=f"Clarification needed: {action_input}",
                sources=[],
                success=True,
                quality_score=0.7
            )
        
        if action == ActionType.REFINE_QUERY:
            # 將 refine_query 轉換為 search
            action = ActionType.SEARCH
        
        # 查找已註冊的工具
        tool_func = self.tools.get(action)
        if tool_func:
            try:
                result = await tool_func(action_input)
                
                # 判斷結果品質
                content = result.get("content", str(result))
                sources = result.get("sources", [])
                
                # 簡單的品質評估
                quality_score = 0.5
                if content and len(content) > 100:
                    quality_score += 0.2
                if sources:
                    quality_score += 0.1 * min(len(sources), 3)
                if "error" in content.lower() or "not found" in content.lower():
                    quality_score -= 0.3
                
                return Observation(
                    content=content,
                    sources=sources,
                    success=True,
                    quality_score=min(1.0, max(0.0, quality_score))
                )
            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                return Observation(
                    content=f"Error executing {action.value}: {str(e)}",
                    sources=[],
                    success=False,
                    quality_score=0.0
                )
        
        return Observation(
            content=f"No tool registered for action: {action.value}",
            sources=[],
            success=False,
            quality_score=0.0
        )
    
    async def run(
        self,
        query: str,
        initial_context: str = "",
        enable_verification: bool = True
    ) -> ReActResult:
        """
        執行完整的 ReAct 循環 (Enhanced with PEV)
        
        Args:
            query: 用戶查詢
            initial_context: 初始上下文（可能來自之前的 RAG）
            enable_verification: 是否啟用 PEV 驗證
        """
        steps: List[ReActStep] = []
        all_sources: List[Dict[str, Any]] = []
        accumulated_context = initial_context
        self.failed_attempts = []  # 重置失敗記錄
        
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
            
            # Step 3: Verify (PEV)
            if enable_verification and thought_action.action not in [ActionType.FINAL_ANSWER, ActionType.CLARIFY]:
                verification = await self.verify_observation(
                    query=query,
                    observation=observation,
                    step_context=accumulated_context[:500]
                )
                step.verification = verification
                
                # Step 4: Self-Correction if verification failed
                if not verification.is_valid or verification.quality_score < self.verification_threshold:
                    logger.warning(f"[ReAct] Verification failed (score={verification.quality_score}), attempting self-correction")
                    
                    # 記錄失敗
                    self.failed_attempts.append({
                        "action": thought_action.action.value,
                        "input": thought_action.action_input,
                        "reason": "; ".join(verification.issues) if verification.issues else "Low quality"
                    })
                    
                    # 嘗試 Self-Correction
                    if verification.should_retry and len(self.failed_attempts) < self.max_retries_per_step * self.max_iterations:
                        corrected_action = await self.self_correct(
                            query=query,
                            failed_action=thought_action.action,
                            failed_input=thought_action.action_input,
                            failure_reason="; ".join(verification.issues),
                            retry_strategy=verification.retry_strategy
                        )
                        
                        # 使用修正後的行動重新執行
                        observation = await self.act(
                            corrected_action.action,
                            corrected_action.action_input
                        )
                        step.observation = f"[Corrected] {observation.content[:900]}"
                        step.thought = f"{step.thought} → Corrected: {corrected_action.thought}"
            
            steps.append(step)
            all_sources.extend(observation.sources)
            
            # Step 5: Check if we should stop
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
                    reasoning_trace=trace,
                    verification_passed=True,
                    strategy_used="react_pev" if enable_verification else "react"
                )
            
            if thought_action.action == ActionType.CLARIFY:
                return ReActResult(
                    final_answer=observation.content,
                    steps=steps,
                    total_iterations=step_number,
                    sources=[],
                    success=True,
                    reasoning_trace=self._build_reasoning_trace(steps),
                    verification_passed=True,
                    strategy_used="clarification"
                )
            
            # Step 6: Update context with observation
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
                        reasoning_trace=self._build_reasoning_trace(steps),
                        verification_passed=True,
                        strategy_used="react_high_confidence"
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
            reasoning_trace=self._build_reasoning_trace(steps),
            verification_passed=len(self.failed_attempts) < 3,
            strategy_used="react_max_iterations"
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
            if step.verification:
                v = step.verification
                status = "✅" if v.is_valid else "❌"
                trace_parts.append(f"🔍 Verification: {status} (score={v.quality_score:.2f})")
                if v.issues:
                    trace_parts.append(f"   Issues: {', '.join(v.issues[:2])}")
            trace_parts.append("")
        
        return "\n".join(trace_parts)


# 單例獲取
_react_loop_instance = None


def get_react_loop(
    max_iterations: int = 5,
    verification_threshold: float = 0.6
) -> ReActLoop:
    """獲取 ReAct 循環引擎單例"""
    global _react_loop_instance
    if _react_loop_instance is None:
        _react_loop_instance = ReActLoop(
            max_iterations=max_iterations,
            verification_threshold=verification_threshold
        )
    return _react_loop_instance


def create_react_loop(
    max_iterations: int = 5,
    verification_threshold: float = 0.6,
    max_retries_per_step: int = 2,
    on_step_callback: Optional[Callable[[ReActStep], Awaitable[None]]] = None
) -> ReActLoop:
    """創建新的 ReAct 循環引擎實例"""
    return ReActLoop(
        max_iterations=max_iterations,
        verification_threshold=verification_threshold,
        max_retries_per_step=max_retries_per_step,
        on_step_callback=on_step_callback
    )
