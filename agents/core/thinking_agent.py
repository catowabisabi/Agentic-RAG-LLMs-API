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

from pydantic import BaseModel, Field

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    MessageProtocol,
    TaskAssignment,
    ValidationResult
)

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
        
        # Load prompt configuration from YAML
        self.prompt_template = self.prompt_manager.get_prompt("thinking_agent")
        
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
        chat_history = task.input_data.get("chat_history", [])
        
        # Format chat history for context
        history_context = ""
        if chat_history:
            history_parts = []
            for exchange in chat_history[-5:]:  # Last 5 exchanges
                if "human" in exchange:
                    history_parts.append(f"User: {exchange['human']}")
                if "assistant" in exchange:
                    history_parts.append(f"Assistant: {exchange['assistant']}")
            if history_parts:
                history_context = "\n=== Previous Conversation ===\n" + "\n".join(history_parts) + "\n=== End Previous Conversation ===\n\n"
        
        # Get RAG context if available
        rag_context = task.input_data.get("rag_context", "")
        if not rag_context and hasattr(self, '_rag_result') and self._rag_result.get("should_use"):
            docs = self._rag_result.get("documents", [])
            rag_context = "\n\n".join([
                f"Document {i+1}:\n{doc.get('content', '')}"
                for i, doc in enumerate(docs[:3])
            ])
        
        # Combine all context
        full_context = history_context + (rag_context or context)
        
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
            reasoning = await self._step_reason(comp, full_context)
            reasonings.append(reasoning)
            await self.stream_to_frontend(
                f"   Component {i+1}: {reasoning[:200]}...\n",
                12 + i
            )
        
        # Step 4: Synthesize conclusion (include chat history context)
        await self.stream_to_frontend(
            "\n✨ Step 4: Synthesizing conclusion...\n",
            20
        )
        
        conclusion = await self._step_conclude(query, reasonings, history_context)
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
        prompt = f"""Analyze this question briefly. What type of question is it? 
What knowledge domains does it touch? What approach would be best?

Question: {query}

Brief analysis (2-3 sentences):"""
        
        result = await self.llm_service.generate(
            prompt=prompt,
            system_message="You are an analytical thinking assistant.",
            temperature=0.4,
            session_id=self.agent_name
        )
        return result.content.strip()
    
    async def _step_decompose(self, query: str, analysis: str) -> List[str]:
        """Decompose into components"""
        prompt = f"""Break down this question into smaller components or sub-questions.

Question: {query}
Analysis: {analysis}

List 2-4 key components (one per line):"""
        
        result = await self.llm_service.generate(
            prompt=prompt,
            system_message="You are an analytical thinking assistant.",
            temperature=0.4,
            session_id=self.agent_name
        )
        
        lines = result.content.strip().split("\n")
        return [line.strip().lstrip("0123456789.-) ") for line in lines if line.strip()]
    
    async def _step_reason(self, component: str, context: str) -> str:
        """Reason about a component"""
        prompt = f"""Reason about this component/sub-question.

Component: {component}

Available Context:
{context[:2000] if context else "No additional context"}

Your reasoning (2-4 sentences):"""
        
        result = await self.llm_service.generate(
            prompt=prompt,
            system_message="You are a reasoning specialist.",
            temperature=0.4,
            session_id=self.agent_name
        )
        return result.content.strip()
    
    async def _step_conclude(self, query: str, reasonings: List[str], history_context: str = "") -> str:
        """Synthesize final conclusion"""
        reasonings_text = "\n".join([
            f"{i+1}. {r}" for i, r in enumerate(reasonings)
        ])
        
        prompt = f"""Based on the reasoning about each component and conversation history, synthesize a final answer.
{history_context}
Original Question: {query}

Component Reasonings:
{reasonings_text}

Provide a comprehensive, well-reasoned answer that takes into account the conversation context.
IMPORTANT: Respond in the SAME LANGUAGE as the original question above."""
        
        result = await self.llm_service.generate(
            prompt=prompt,
            system_message=self.prompt_template.system_prompt,
            temperature=self.prompt_template.temperature,
            session_id=self.agent_name
        )
        return result.content.strip()
    
    async def _analyze(self, task: TaskAssignment) -> Dict[str, Any]:
        """Perform analysis on content"""
        content = task.input_data.get("content", task.description)
        analysis_type = task.input_data.get("analysis_type", "general")
        
        prompt = f"""Perform a {analysis_type} analysis of this content.

Content:
{content}

Provide:
1. Key insights
2. Important patterns or themes
3. Conclusions and recommendations"""
        
        await self.stream_to_frontend(
            f"🔬 Performing {analysis_type} analysis...\n",
            0
        )
        
        result = await self.llm_service.generate(
            prompt=prompt,
            system_message=self.prompt_template.system_prompt,
            temperature=self.prompt_template.temperature,
            session_id=task.task_id
        )
        
        await self.stream_to_frontend(
            f"\n{result}\n",
            1
        )
        
        return {
            "analysis_type": analysis_type,
            "result": result
        }
    
    async def _evaluate(self, task: TaskAssignment) -> Dict[str, Any]:
        """Evaluate options or decisions"""
        options = task.input_data.get("options", [])
        criteria = task.input_data.get("criteria", [])
        
        options_text = "\n".join([f"- {opt}" for opt in options])
        criteria_text = "\n".join([f"- {crit}" for crit in criteria])
        
        prompt = f"""Evaluate these options based on the given criteria.

Options:
{options_text}

Evaluation Criteria:
{criteria_text}

For each option, provide:
1. Strengths
2. Weaknesses
3. Score (1-10)

Then recommend the best option."""
        
        await self.stream_to_frontend(
            "⚖️ Evaluating options...\n",
            0
        )
        
        result = await self.llm_service.generate(
            prompt=prompt,
            system_message=self.prompt_template.system_prompt,
            temperature=self.prompt_template.temperature,
            session_id=task.task_id
        )
        
        await self.stream_to_frontend(
            f"\n{result}\n",
            1
        )
        
        return {
            "options": options,
            "criteria": criteria,
            "evaluation": result
        }
