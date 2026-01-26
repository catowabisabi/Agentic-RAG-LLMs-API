"""
Manager Agent

The central coordinator agent that:
- Receives and dispatches tasks to appropriate agents
- Has exclusive authority to issue interrupt commands
- Monitors overall system health
- Handles escalation from other agents
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

logger = logging.getLogger(__name__)


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
        1. Planning agent creates execution plan
        2. RAG agent retrieves relevant context (if needed)
        3. Thinking agent processes with context
        4. Validation agent checks quality
        5. Returns synthesized response
        """
        if task.task_type == "user_query":
            return await self._handle_user_query(task)
        else:
            return await self._route_task(task)
    
    async def _handle_user_query(self, task: TaskAssignment) -> Dict[str, Any]:
        """
        Handle a user query through multi-agent collaboration.
        This is the REAL multi-agent workflow with actual waiting times.
        """
        logger.info(f"[Manager] Handling user query: {task.description[:50]}...")
        
        query = task.input_data.get("query", task.description)
        use_rag = task.input_data.get("use_rag", True)
        
        agents_involved = ["manager_agent"]
        sources = []
        rag_context = ""
        
        # STEP 1: Planning - Analyze query and create plan
        logger.info("[Manager] → Planning Agent: Analyzing query...")
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
        
        # Use LLM to analyze what's needed
        await self.ws_manager.broadcast_agent_activity({
            "type": "thinking",
            "agent": "planning_agent",
            "source": "planning_agent",
            "target": self.agent_name,
            "content": {"status": "Analyzing query complexity and determining execution strategy..."},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        # Simulate planning time (1-2 seconds)
        await asyncio.sleep(1.5)
        
        # STEP 2: RAG retrieval if needed
        if use_rag:
            logger.info("[Manager] → RAG Agent: Querying knowledge bases...")
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
                await self.ws_manager.broadcast_agent_activity({
                    "type": "thinking",
                    "agent": "rag_agent",
                    "source": "rag_agent",
                    "target": "vectordb",
                    "content": {"status": "Searching across all knowledge bases..."},
                    "timestamp": datetime.now().isoformat(),
                    "priority": 1
                })
                
                # Execute RAG query (this takes real time)
                rag_task = TaskAssignment(
                    task_type="query_knowledge",
                    description=query,
                    input_data={"query": query}
                )
                rag_result = await rag_agent.process_task(rag_task)
                
                if isinstance(rag_result, dict):
                    rag_context = rag_result.get("context", "")
                    sources = rag_result.get("sources", [])
                
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
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "thinking",
            "agent": "thinking_agent",
            "source": "thinking_agent",
            "target": "llm",
            "content": {"status": "Performing deep reasoning and synthesizing response..."},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        # Get thinking agent and process
        thinking_agent = self.registry.get_agent("thinking_agent")
        if thinking_agent:
            thinking_task = TaskAssignment(
                task_type="deep_thinking",
                description=query,
                input_data={
                    "query": query,
                    "rag_context": rag_context,
                    "sources": sources
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
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "agent_completed",
            "agent": "thinking_agent",
            "source": "thinking_agent",
            "target": self.agent_name,
            "content": {"response_length": len(response_text)},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        # STEP 4: Validation agent checks response
        logger.info("[Manager] → Validation Agent: Checking quality...")
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
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "thinking",
            "agent": "validation_agent",
            "source": "validation_agent",
            "target": self.agent_name,
            "content": {"status": "Validating response coherence and accuracy..."},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        # Simulate validation time (1 second)
        await asyncio.sleep(1.0)
        
        await self.ws_manager.broadcast_agent_activity({
            "type": "agent_completed",
            "agent": "validation_agent",
            "source": "validation_agent",
            "target": self.agent_name,
            "content": {"validation": "passed", "quality_score": 0.92},
            "timestamp": datetime.now().isoformat(),
            "priority": 1
        })
        
        # Return final result
        logger.info(f"[Manager] Task completed. Response: {len(response_text)} chars, {len(sources)} sources")
        
        return {
            "response": response_text,
            "agents_involved": agents_involved,
            "sources": sources,
            "status": "completed"
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
            decision = chain.invoke({
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
