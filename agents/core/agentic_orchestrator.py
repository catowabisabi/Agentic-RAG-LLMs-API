# -*- coding: utf-8 -*-
"""
=============================================================================
Agentic Orchestrator - 核心協調器
=============================================================================

整合所有 Agentic 元素的協調器：
1. Metacognition - 自我評估和策略選擇
2. RAG Decision - 智能 RAG 決策（非強制）
3. ReAct Loop - 迭代推理
4. PEV Verification - 結果驗證
5. Self-Correction - 錯誤自動修正

參考:
- example/01/05-agentic-rag/README.md (Agentic RAG)
- app_docs/Agentic-Rag-Examples/03_ReAct.ipynb (ReAct)
- app_docs/Agentic-Rag-Examples/06_PEV.ipynb (PEV)
- app_docs/Agentic-Rag-Examples/17_reflexive_metacognitive.ipynb (Metacognition)

核心原則 (來自 05-agentic-rag):
"The distinguishing quality that makes a system 'agentic' is its ability to 
OWN ITS REASONING PROCESS. Traditional RAG implementations often depend on 
humans pre-defining a path for the model."
=============================================================================
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


class AgentStrategy(str, Enum):
    """Agent 可選擇的策略"""
    DIRECT_ANSWER = "direct_answer"      # 直接回答，不需要 RAG
    SINGLE_RAG = "single_rag"            # 單次 RAG 檢索
    REACT_ITERATIVE = "react_iterative"  # ReAct 迭代推理
    ESCALATE = "escalate"                # 超出能力範圍，需要升級
    CLARIFY = "clarify"                  # 需要用戶澄清


class AgentSelfModel(BaseModel):
    """
    Agent 自我模型 (Metacognition)
    
    參考: 17_reflexive_metacognitive.ipynb
    """
    name: str = Field(default="AgenticRAG-Agent")
    role: str = Field(default="Intelligent Assistant with RAG capabilities")
    
    # 知識邊界
    knowledge_domains: List[str] = Field(
        default_factory=lambda: [
            "general_knowledge",
            "uploaded_documents",
            "conversation_history"
        ],
        description="Agent 擅長的領域"
    )
    
    # 可用工具
    available_tools: List[str] = Field(
        default_factory=lambda: [
            "rag_search",      # 知識庫搜索
            "calculation",     # 計算
            "web_search",      # 網絡搜索 (如果可用)
        ],
        description="可用的工具"
    )
    
    # 信心閾值
    confidence_threshold: float = Field(
        default=0.6,
        description="低於此閾值需要額外步驟或升級"
    )
    
    # 高風險主題 (需要驗證)
    high_risk_topics: List[str] = Field(
        default_factory=lambda: [
            "medical", "legal", "financial", "safety"
        ],
        description="需要額外驗證的高風險主題"
    )


class MetacognitiveAnalysis(BaseModel):
    """
    Metacognitive 分析結果
    
    Agent 在回答之前的自我評估
    """
    confidence: float = Field(description="信心分數 0-1")
    strategy: AgentStrategy = Field(description="選擇的策略")
    reasoning: str = Field(description="選擇策略的原因")
    requires_verification: bool = Field(default=False, description="是否需要 PEV 驗證")
    estimated_complexity: str = Field(default="simple", description="預估複雜度")
    self_assessment: str = Field(default="", description="自我能力評估")


class OrchestratorResult(BaseModel):
    """Orchestrator 執行結果"""
    response: str = Field(description="最終回應")
    strategy_used: AgentStrategy = Field(description="使用的策略")
    confidence: float = Field(description="最終信心分數")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="來源")
    reasoning_trace: str = Field(default="", description="推理軌跡")
    verification_passed: bool = Field(default=True, description="是否通過驗證")
    iterations: int = Field(default=1, description="迭代次數")
    metacognitive_analysis: Optional[MetacognitiveAnalysis] = Field(
        default=None, description="Metacognition 分析"
    )


class AgenticOrchestrator:
    """
    Agentic 協調器
    
    核心流程：
    1. Metacognitive Analysis - 分析問題，評估自身能力
    2. Strategy Selection - 選擇最佳策略
    3. Execute Strategy - 執行選定的策略
    4. PEV Verification - 驗證結果
    5. Self-Correction - 如需要則修正
    
    這個設計確保 Agent "owns its reasoning process"
    """
    
    def __init__(
        self,
        self_model: Optional[AgentSelfModel] = None,
        on_step_callback: Optional[Callable[[Dict], Awaitable[None]]] = None
    ):
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.2,
            api_key=self.config.OPENAI_API_KEY
        )
        
        self.self_model = self_model or AgentSelfModel()
        self.on_step_callback = on_step_callback
        
        # 延遲導入避免循環依賴
        self._react_loop = None
        self._rag_agent = None
        
        logger.info(f"[AgenticOrchestrator] Initialized with self-model: {self.self_model.name}")
    
    def _get_react_loop(self):
        """延遲獲取 ReAct Loop"""
        if self._react_loop is None:
            from agents.core.react_loop import create_react_loop, ActionType
            self._react_loop = create_react_loop(
                max_iterations=5,
                verification_threshold=0.6,
                on_step_callback=self._react_step_callback
            )
            
            # 註冊 RAG 作為 Tool
            self._react_loop.register_tool(
                ActionType.SEARCH,
                self._rag_search_tool
            )
        return self._react_loop
    
    async def _react_step_callback(self, step):
        """ReAct 步驟回調"""
        if self.on_step_callback:
            await self.on_step_callback({
                "type": "react_step",
                "step_number": step.step_number,
                "thought": step.thought,
                "action": step.action.value,
                "action_input": step.action_input[:100]
            })
    
    async def _rag_search_tool(self, query: str) -> Dict[str, Any]:
        """RAG 搜索工具 - 供 ReAct 調用"""
        try:
            from services.vectordb_manager import vectordb_manager
            
            # 獲取所有活動的資料庫
            db_list = vectordb_manager.list_databases()
            active_dbs = [db["name"] for db in db_list if db.get("document_count", 0) > 0]
            
            if not active_dbs:
                return {
                    "content": "No documents found in knowledge base.",
                    "sources": []
                }
            
            # 搜索所有活動資料庫
            all_results = []
            for db_name in active_dbs:
                try:
                    result = await vectordb_manager.query(query, db_name, n_results=3)
                    docs = result.get("results", [])
                    all_results.extend(docs)
                except Exception as e:
                    logger.warning(f"Error querying {db_name}: {e}")
            
            if not all_results:
                return {
                    "content": f"No relevant information found for: {query}",
                    "sources": []
                }
            
            # 構建內容和來源
            content_parts = []
            sources = []
            for doc in all_results[:5]:  # 最多5個結果
                doc_content = doc.get("content", "")
                if doc_content:
                    content_parts.append(doc_content)
                    sources.append({
                        "content": doc_content[:200],
                        "title": doc.get("metadata", {}).get("title", "Unknown"),
                        "source": doc.get("metadata", {}).get("source", "RAG Database")
                    })
            
            return {
                "content": "\n\n---\n\n".join(content_parts),
                "sources": sources
            }
            
        except Exception as e:
            logger.error(f"RAG search error: {e}")
            return {
                "content": f"Error searching knowledge base: {e}",
                "sources": []
            }
    
    async def metacognitive_analysis(
        self,
        query: str,
        chat_history: List[Dict] = None,
        user_context: str = ""
    ) -> MetacognitiveAnalysis:
        """
        Metacognitive 分析：Agent 評估自己的能力
        
        這是 Agentic 的核心 - Agent 決定如何處理問題，而非人類預定義
        
        參考: 17_reflexive_metacognitive.ipynb
        """
        # 構建歷史摘要
        history_summary = ""
        if chat_history:
            recent = chat_history[-5:]
            history_summary = "\n".join([
                f"{m.get('role', 'user')}: {m.get('content', '')[:100]}"
                for m in recent
            ])
        
        prompt = ChatPromptTemplate.from_template(
            """You are a metacognitive reasoning engine. Analyze the query IN THE CONTEXT OF YOUR OWN CAPABILITIES.

**Your Self-Model:**
- Name: {agent_name}
- Role: {agent_role}
- Knowledge Domains: {knowledge_domains}
- Available Tools: {available_tools}
- High-Risk Topics (require verification): {high_risk_topics}

**Recent Conversation:**
{history_summary}

**User Context:** {user_context}

**User Query:** {query}

**STRATEGY SELECTION RULES:**

1. **DIRECT_ANSWER** (confidence > 0.8):
   - Simple greetings, casual chat
   - Questions you can answer confidently from general knowledge
   - Follow-up questions where context is already available
   - No need for document retrieval

2. **SINGLE_RAG** (0.6 < confidence < 0.8):
   - Specific factual questions about uploaded documents
   - Questions mentioning specific documents/data
   - Single-step retrieval should suffice

3. **REACT_ITERATIVE** (confidence < 0.6 OR complex query):
   - Multi-hop questions requiring connecting multiple facts
   - Questions where initial retrieval may be insufficient
   - Complex analysis requiring multiple sources
   - Questions with ambiguous terms needing refinement

4. **ESCALATE** (out of scope OR high risk):
   - Questions about topics in high_risk_topics requiring professional expertise
   - Questions completely outside your knowledge domains
   - When you have serious doubts about providing accurate information

5. **CLARIFY** (ambiguous query):
   - Very vague questions that could mean multiple things
   - When more context would significantly improve the answer

**SELF-ASSESSMENT QUESTIONS:**
- Can I answer this confidently without retrieval?
- Is this within my knowledge domain?
- Does this require information from uploaded documents?
- Is this a high-risk topic requiring extra verification?
- How complex is this query?

Respond with your analysis as JSON:
{{
    "confidence": 0.0-1.0,
    "strategy": "direct_answer|single_rag|react_iterative|escalate|clarify",
    "reasoning": "Brief explanation of your choice",
    "requires_verification": true/false,
    "estimated_complexity": "simple|moderate|complex|multi_hop",
    "self_assessment": "What are my capabilities and limitations for this query?"
}}
"""
        )
        
        try:
            chain = prompt | self.llm
            result = await chain.ainvoke({
                "agent_name": self.self_model.name,
                "agent_role": self.self_model.role,
                "knowledge_domains": ", ".join(self.self_model.knowledge_domains),
                "available_tools": ", ".join(self.self_model.available_tools),
                "high_risk_topics": ", ".join(self.self_model.high_risk_topics),
                "history_summary": history_summary or "No previous conversation",
                "user_context": user_context or "No specific context",
                "query": query
            })
            
            response = result.content if hasattr(result, 'content') else str(result)
            
            # 解析 JSON
            import json
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            
            data = json.loads(response.strip())
            
            strategy_map = {
                "direct_answer": AgentStrategy.DIRECT_ANSWER,
                "single_rag": AgentStrategy.SINGLE_RAG,
                "react_iterative": AgentStrategy.REACT_ITERATIVE,
                "escalate": AgentStrategy.ESCALATE,
                "clarify": AgentStrategy.CLARIFY
            }
            
            analysis = MetacognitiveAnalysis(
                confidence=float(data.get("confidence", 0.5)),
                strategy=strategy_map.get(
                    data.get("strategy", "single_rag").lower(),
                    AgentStrategy.SINGLE_RAG
                ),
                reasoning=data.get("reasoning", ""),
                requires_verification=data.get("requires_verification", False),
                estimated_complexity=data.get("estimated_complexity", "simple"),
                self_assessment=data.get("self_assessment", "")
            )
            
            logger.info(
                f"[Metacognition] strategy={analysis.strategy.value}, "
                f"confidence={analysis.confidence:.2f}, "
                f"complexity={analysis.estimated_complexity}"
            )
            
            return analysis
            
        except Exception as e:
            logger.error(f"Metacognitive analysis error: {e}")
            # 發生錯誤時使用安全的默認值
            return MetacognitiveAnalysis(
                confidence=0.5,
                strategy=AgentStrategy.SINGLE_RAG,
                reasoning=f"Error in metacognition: {e}. Using safe default.",
                requires_verification=True,
                estimated_complexity="unknown",
                self_assessment="Error occurred, proceeding with caution"
            )
    
    async def execute_direct_answer(
        self,
        query: str,
        chat_history: List[Dict] = None
    ) -> str:
        """
        直接回答策略 - 不需要 RAG
        """
        history_context = ""
        if chat_history:
            recent = chat_history[-3:]
            history_context = "\n".join([
                f"{m.get('role', 'user')}: {m.get('content', '')}"
                for m in recent
            ])
        
        prompt = ChatPromptTemplate.from_template(
            """You are a helpful assistant. Answer the user's question directly.

Recent Conversation:
{history_context}

User: {query}

Provide a helpful, conversational response."""
        )
        
        chain = prompt | self.llm
        result = await chain.ainvoke({
            "history_context": history_context or "No previous conversation",
            "query": query
        })
        
        return result.content if hasattr(result, 'content') else str(result)
    
    async def execute_single_rag(
        self,
        query: str,
        chat_history: List[Dict] = None
    ) -> Dict[str, Any]:
        """
        單次 RAG 策略 - 一次檢索後生成答案
        """
        # 執行 RAG 搜索
        rag_result = await self._rag_search_tool(query)
        context = rag_result.get("content", "")
        sources = rag_result.get("sources", [])
        
        # 構建歷史
        history_context = ""
        if chat_history:
            recent = chat_history[-3:]
            history_context = "\n".join([
                f"{m.get('role', 'user')}: {m.get('content', '')[:200]}"
                for m in recent
            ])
        
        prompt = ChatPromptTemplate.from_template(
            """You are a helpful assistant with access to a knowledge base.

Recent Conversation:
{history_context}

Retrieved Information:
{context}

User Question: {query}

Provide a comprehensive answer based on the retrieved information. 
If the information is insufficient, acknowledge this and provide what you can.
Always cite sources when using specific information from the retrieved content."""
        )
        
        chain = prompt | self.llm
        result = await chain.ainvoke({
            "history_context": history_context or "No previous conversation",
            "context": context or "No relevant documents found.",
            "query": query
        })
        
        response = result.content if hasattr(result, 'content') else str(result)
        
        return {
            "response": response,
            "sources": sources,
            "context_used": context[:500] if context else ""
        }
    
    async def execute_react_iterative(
        self,
        query: str,
        chat_history: List[Dict] = None,
        enable_verification: bool = True
    ) -> Dict[str, Any]:
        """
        ReAct 迭代策略 - 多步驟推理
        """
        react_loop = self._get_react_loop()
        
        # 構建初始上下文
        initial_context = ""
        if chat_history:
            recent = chat_history[-3:]
            initial_context = "Recent conversation:\n" + "\n".join([
                f"{m.get('role', 'user')}: {m.get('content', '')[:200]}"
                for m in recent
            ])
        
        # 執行 ReAct 循環
        result = await react_loop.run(
            query=query,
            initial_context=initial_context,
            enable_verification=enable_verification
        )
        
        return {
            "response": result.final_answer,
            "sources": result.sources,
            "reasoning_trace": result.reasoning_trace,
            "iterations": result.total_iterations,
            "verification_passed": result.verification_passed,
            "strategy_used": result.strategy_used
        }
    
    async def run(
        self,
        query: str,
        chat_history: List[Dict] = None,
        user_context: str = ""
    ) -> OrchestratorResult:
        """
        執行完整的 Agentic 流程
        
        這是主入口點，實現：
        1. Metacognitive Analysis
        2. Strategy Selection
        3. Strategy Execution
        4. Result Verification (if needed)
        """
        chat_history = chat_history or []
        
        logger.info(f"[Orchestrator] Processing: {query[:50]}...")
        
        # Step 1: Notify callback
        if self.on_step_callback:
            await self.on_step_callback({
                "type": "orchestrator_start",
                "query": query[:100]
            })
        
        # Step 2: Metacognitive Analysis
        analysis = await self.metacognitive_analysis(
            query=query,
            chat_history=chat_history,
            user_context=user_context
        )
        
        if self.on_step_callback:
            await self.on_step_callback({
                "type": "metacognition_complete",
                "strategy": analysis.strategy.value,
                "confidence": analysis.confidence,
                "reasoning": analysis.reasoning[:100]
            })
        
        # Step 3: Execute Strategy
        try:
            if analysis.strategy == AgentStrategy.DIRECT_ANSWER:
                response = await self.execute_direct_answer(query, chat_history)
                return OrchestratorResult(
                    response=response,
                    strategy_used=AgentStrategy.DIRECT_ANSWER,
                    confidence=analysis.confidence,
                    sources=[],
                    reasoning_trace="Direct answer - no retrieval needed",
                    verification_passed=True,
                    iterations=1,
                    metacognitive_analysis=analysis
                )
            
            elif analysis.strategy == AgentStrategy.SINGLE_RAG:
                result = await self.execute_single_rag(query, chat_history)
                return OrchestratorResult(
                    response=result["response"],
                    strategy_used=AgentStrategy.SINGLE_RAG,
                    confidence=analysis.confidence,
                    sources=result.get("sources", []),
                    reasoning_trace="Single RAG retrieval",
                    verification_passed=True,
                    iterations=1,
                    metacognitive_analysis=analysis
                )
            
            elif analysis.strategy == AgentStrategy.REACT_ITERATIVE:
                result = await self.execute_react_iterative(
                    query=query,
                    chat_history=chat_history,
                    enable_verification=analysis.requires_verification
                )
                return OrchestratorResult(
                    response=result["response"],
                    strategy_used=AgentStrategy.REACT_ITERATIVE,
                    confidence=analysis.confidence,
                    sources=result.get("sources", []),
                    reasoning_trace=result.get("reasoning_trace", ""),
                    verification_passed=result.get("verification_passed", True),
                    iterations=result.get("iterations", 1),
                    metacognitive_analysis=analysis
                )
            
            elif analysis.strategy == AgentStrategy.ESCALATE:
                return OrchestratorResult(
                    response=(
                        "This question appears to require expertise beyond my capabilities. "
                        f"Reason: {analysis.reasoning}\n\n"
                        "I recommend consulting a qualified professional for accurate information."
                    ),
                    strategy_used=AgentStrategy.ESCALATE,
                    confidence=analysis.confidence,
                    sources=[],
                    reasoning_trace="Escalated - outside capability boundary",
                    verification_passed=True,
                    iterations=1,
                    metacognitive_analysis=analysis
                )
            
            elif analysis.strategy == AgentStrategy.CLARIFY:
                return OrchestratorResult(
                    response=f"I'd like to help, but I need some clarification: {analysis.reasoning}",
                    strategy_used=AgentStrategy.CLARIFY,
                    confidence=analysis.confidence,
                    sources=[],
                    reasoning_trace="Clarification requested",
                    verification_passed=True,
                    iterations=1,
                    metacognitive_analysis=analysis
                )
            
            else:
                # 默認使用 single_rag
                result = await self.execute_single_rag(query, chat_history)
                return OrchestratorResult(
                    response=result["response"],
                    strategy_used=AgentStrategy.SINGLE_RAG,
                    confidence=0.5,
                    sources=result.get("sources", []),
                    reasoning_trace="Default fallback to single RAG",
                    verification_passed=True,
                    iterations=1,
                    metacognitive_analysis=analysis
                )
                
        except Exception as e:
            logger.error(f"[Orchestrator] Execution error: {e}")
            return OrchestratorResult(
                response=f"I apologize, but I encountered an error while processing your request: {str(e)}",
                strategy_used=AgentStrategy.SINGLE_RAG,
                confidence=0.2,
                sources=[],
                reasoning_trace=f"Error: {e}",
                verification_passed=False,
                iterations=1,
                metacognitive_analysis=analysis
            )


# 單例
_orchestrator_instance = None


def get_agentic_orchestrator(
    self_model: Optional[AgentSelfModel] = None,
    on_step_callback: Optional[Callable[[Dict], Awaitable[None]]] = None
) -> AgenticOrchestrator:
    """獲取 Agentic Orchestrator 單例"""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = AgenticOrchestrator(
            self_model=self_model,
            on_step_callback=on_step_callback
        )
    return _orchestrator_instance


def create_agentic_orchestrator(
    self_model: Optional[AgentSelfModel] = None,
    on_step_callback: Optional[Callable[[Dict], Awaitable[None]]] = None
) -> AgenticOrchestrator:
    """創建新的 Agentic Orchestrator 實例"""
    return AgenticOrchestrator(
        self_model=self_model,
        on_step_callback=on_step_callback
    )
