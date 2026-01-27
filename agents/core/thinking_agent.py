"""
Thinking Agent

Performs deep reasoning and analysis:
- Multi-step reasoning
- Critical thinking
- Streams thinking process to frontend
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


class ThoughtStep(BaseModel):
    """A single step in the thinking process"""
    step_type: str = Field(description="Type of thinking: analyze, reason, evaluate, conclude")
    content: str = Field(description="The thought content")
    confidence: float = Field(default=0.5, ge=0, le=1)


class ThinkingResult(BaseModel):
    """Complete thinking result"""
    question: str = Field(description="The question being analyzed")
    thought_process: List[ThoughtStep] = Field(description="Steps in the thinking process")
    conclusion: str = Field(description="Final conclusion")
    confidence: float = Field(default=0.5, ge=0, le=1)
    caveats: List[str] = Field(default_factory=list, description="Important caveats or limitations")


class ThinkingAgent(BaseAgent):
    """
    Thinking Agent for the multi-agent system.
    
    Responsibilities:
    - Perform deep reasoning and analysis
    - Break down complex problems
    - Stream thinking process to frontend
    """
    
    def __init__(self, agent_name: str = "thinking_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Thinking Specialist",
            agent_description="Performs deep reasoning and analysis"
        )
        
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.4,
            api_key=self.config.OPENAI_API_KEY
        )
        
        logger.info("ThinkingAgent initialized")
    
    async def should_check_rag(self, task: TaskAssignment) -> bool:
        """Thinking agent should usually check RAG"""
        return True
    
    async def process_task(self, task: TaskAssignment) -> Any:
        """Process a thinking task"""
        task_type = task.task_type
        
        if task_type == "analyze":
            return await self._analyze(task)
        elif task_type == "reason":
            return await self._deep_reasoning(task)
        elif task_type == "evaluate":
            return await self._evaluate(task)
        else:
            return await self._deep_reasoning(task)
    
    async def _deep_reasoning(self, task: TaskAssignment) -> Dict[str, Any]:
        """Perform deep reasoning on a query"""
        query = task.input_data.get("query", task.description)
        context = task.input_data.get("context", "")
        
        # Get RAG context if available
        rag_context = ""
        if hasattr(self, '_rag_result') and self._rag_result.get("should_use"):
            docs = self._rag_result.get("documents", [])
            rag_context = "\n\n".join([
                f"Document {i+1}:\n{doc.get('content', '')}"
                for i, doc in enumerate(docs[:3])
            ])
        
        # Stream initial thinking
        await self.stream_to_frontend(
            f"🧠 Starting deep reasoning on: {query[:80]}...\n\n",
            0
        )
        
        # Step 1: Analyze the question
        await self.stream_to_frontend(
            "📊 Step 1: Analyzing the question...\n",
            1
        )
        
        analysis = await self._step_analyze(query)
        await self.stream_to_frontend(
            f"   {analysis}\n\n",
            2
        )
        
        # Step 2: Break down into components
        await self.stream_to_frontend(
            "🔍 Step 2: Breaking down into components...\n",
            3
        )
        
        components = await self._step_decompose(query, analysis)
        for i, comp in enumerate(components):
            await self.stream_to_frontend(
                f"   {i+1}. {comp}\n",
                4 + i
            )
        await self.stream_to_frontend("\n", 10)
        
        # Step 3: Reason about each component
        await self.stream_to_frontend(
            "💭 Step 3: Reasoning through components...\n",
            11
        )
        
        reasonings = []
        for i, comp in enumerate(components):
            reasoning = await self._step_reason(comp, context + rag_context)
            reasonings.append(reasoning)
            await self.stream_to_frontend(
                f"   Component {i+1}: {reasoning[:200]}...\n",
                12 + i
            )
        
        # Step 4: Synthesize conclusion
        await self.stream_to_frontend(
            "\n✨ Step 4: Synthesizing conclusion...\n",
            20
        )
        
        conclusion = await self._step_conclude(query, reasonings)
        await self.stream_to_frontend(
            f"\n📌 Conclusion:\n{conclusion}\n",
            21
        )
        
        result = {
            "query": query,
            "analysis": analysis,
            "components": components,
            "reasonings": reasonings,
            "conclusion": conclusion,
            "thinking_steps": [
                {"type": "analyze", "content": analysis},
                {"type": "decompose", "content": components},
                {"type": "reason", "content": reasonings},
                {"type": "conclude", "content": conclusion}
            ]
        }
        
        return result
    
    async def _step_analyze(self, query: str) -> str:
        """Analyze the question"""
        prompt = ChatPromptTemplate.from_template(
            """Analyze this question briefly. What type of question is it? 
What knowledge domains does it touch? What approach would be best?

Question: {query}

Brief analysis (2-3 sentences):"""
        )
        
        chain = prompt | self.llm
        result = await chain.ainvoke({"query": query})
        return result.content.strip()
    
    async def _step_decompose(self, query: str, analysis: str) -> List[str]:
        """Decompose into components"""
        prompt = ChatPromptTemplate.from_template(
            """Break down this question into smaller components or sub-questions.

Question: {query}
Analysis: {analysis}

List 2-4 key components (one per line):"""
        )
        
        chain = prompt | self.llm
        result = await chain.ainvoke({"query": query, "analysis": analysis})
        
        lines = result.content.strip().split("\n")
        return [line.strip().lstrip("0123456789.-) ") for line in lines if line.strip()]
    
    async def _step_reason(self, component: str, context: str) -> str:
        """Reason about a component"""
        prompt = ChatPromptTemplate.from_template(
            """Reason about this component/sub-question.

Component: {component}

Available Context:
{context}

Your reasoning (2-4 sentences):"""
        )
        
        chain = prompt | self.llm
        result = await chain.ainvoke({
            "component": component,
            "context": context[:2000] if context else "No additional context"
        })
        return result.content.strip()
    
    async def _step_conclude(self, query: str, reasonings: List[str]) -> str:
        """Synthesize final conclusion"""
        prompt = ChatPromptTemplate.from_template(
            """Based on the reasoning about each component, synthesize a final answer.

Original Question: {query}

Component Reasonings:
{reasonings}

Provide a comprehensive, well-reasoned answer:"""
        )
        
        reasonings_text = "\n".join([
            f"{i+1}. {r}" for i, r in enumerate(reasonings)
        ])
        
        chain = prompt | self.llm
        result = await chain.ainvoke({
            "query": query,
            "reasonings": reasonings_text
        })
        return result.content.strip()
    
    async def _analyze(self, task: TaskAssignment) -> Dict[str, Any]:
        """Perform analysis on content"""
        content = task.input_data.get("content", task.description)
        analysis_type = task.input_data.get("analysis_type", "general")
        
        prompt = ChatPromptTemplate.from_template(
            """Perform a {analysis_type} analysis of this content.

Content:
{content}

Provide:
1. Key insights
2. Important patterns or themes
3. Conclusions and recommendations"""
        )
        
        chain = prompt | self.llm
        
        await self.stream_to_frontend(
            f"🔬 Performing {analysis_type} analysis...\n",
            0
        )
        
        result = await chain.ainvoke({
            "content": content,
            "analysis_type": analysis_type
        })
        
        await self.stream_to_frontend(
            f"\n{result.content}\n",
            1
        )
        
        return {
            "analysis_type": analysis_type,
            "result": result.content
        }
    
    async def _evaluate(self, task: TaskAssignment) -> Dict[str, Any]:
        """Evaluate options or decisions"""
        options = task.input_data.get("options", [])
        criteria = task.input_data.get("criteria", [])
        
        prompt = ChatPromptTemplate.from_template(
            """Evaluate these options based on the given criteria.

Options:
{options}

Evaluation Criteria:
{criteria}

For each option, provide:
1. Strengths
2. Weaknesses
3. Score (1-10)

Then recommend the best option."""
        )
        
        options_text = "\n".join([f"- {opt}" for opt in options])
        criteria_text = "\n".join([f"- {crit}" for crit in criteria])
        
        chain = prompt | self.llm
        
        await self.stream_to_frontend(
            "⚖️ Evaluating options...\n",
            0
        )
        
        result = await chain.ainvoke({
            "options": options_text,
            "criteria": criteria_text
        })
        
        await self.stream_to_frontend(
            f"\n{result.content}\n",
            1
        )
        
        return {
            "options": options,
            "criteria": criteria,
            "evaluation": result.content
        }
