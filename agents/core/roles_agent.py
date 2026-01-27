"""
Roles Agent

Monitors other agents and provides role corrections:
- Monitors agent behavior
- Sends role corrections when agents make mistakes
- Reports persistent issues to manager
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
    RoleAssignment
)
from config.config import Config

logger = logging.getLogger(__name__)


class RoleCorrection(BaseModel):
    """A role correction for an agent"""
    should_correct: bool = Field(description="Whether correction is needed")
    role_clarification: str = Field(description="Clarified role description")
    error_type: str = Field(description="Type of error made")
    correction_guidance: str = Field(description="Specific guidance to correct behavior")
    severity: str = Field(description="low, medium, or high")


class RolesAgent(BaseAgent):
    """
    Roles Agent for the multi-agent system.
    
    Responsibilities:
    - Monitor agent behavior
    - Provide role corrections when agents make mistakes
    - Report persistent issues to manager
    """
    
    def __init__(self, agent_name: str = "roles_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Roles Monitor",
            agent_description="Monitors agents and provides role corrections"
        )
        
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.1,
            api_key=self.config.OPENAI_API_KEY
        )
        
        # Agent role definitions
        self.agent_roles = {
            "rag_agent": RoleAssignment(
                role_name="RAG Specialist",
                role_description="Handles document retrieval and RAG decisions. Should retrieve relevant documents and provide context.",
                expected_output="Retrieved documents with relevance scores",
                constraints=["Should not generate content directly", "Must check for existing notes first"]
            ),
            "memory_agent": RoleAssignment(
                role_name="Memory Specialist",
                role_description="Manages conversation memory and context. Stores and retrieves memories.",
                expected_output="Stored memory confirmations or retrieved memory content",
                constraints=["Should persist important information", "Must not exceed memory limits"]
            ),
            "notes_agent": RoleAssignment(
                role_name="Notes Specialist",
                role_description="Creates structured notes from information. Transforms data into organized notes.",
                expected_output="Structured notes with title, summary, and key points",
                constraints=["Notes must be concise", "Must send notes to memory agent"]
            ),
            "validation_agent": RoleAssignment(
                role_name="Validation Specialist",
                role_description="Validates data and responses. Checks for errors and quality issues.",
                expected_output="Validation result with is_valid status and any errors",
                constraints=["Must be thorough", "Should suggest fixes for errors"]
            ),
            "planning_agent": RoleAssignment(
                role_name="Planning Specialist",
                role_description="Creates step-by-step plans for complex tasks. Decomposes tasks into steps.",
                expected_output="Execution plan with ordered steps and agent assignments",
                constraints=["Steps must be atomic", "Must validate plan before sending"]
            ),
            "thinking_agent": RoleAssignment(
                role_name="Thinking Specialist",
                role_description="Performs deep reasoning and analysis. Breaks down complex problems.",
                expected_output="Reasoned analysis with conclusion",
                constraints=["Must show thinking process", "Should check RAG for context"]
            ),
            "data_agent": RoleAssignment(
                role_name="Data Specialist",
                role_description="Handles data processing and transformation.",
                expected_output="Processed or transformed data",
                constraints=["Must validate data format", "Should handle errors gracefully"]
            ),
            "tool_agent": RoleAssignment(
                role_name="Tool Specialist",
                role_description="Executes external tools and APIs.",
                expected_output="Tool execution results",
                constraints=["Must handle tool failures", "Should validate tool inputs"]
            ),
            "summarize_agent": RoleAssignment(
                role_name="Summary Specialist",
                role_description="Creates summaries and condensed information.",
                expected_output="Concise summary of content",
                constraints=["Must preserve key information", "Should respect length limits"]
            ),
            "translate_agent": RoleAssignment(
                role_name="Translation Specialist",
                role_description="Handles language translation.",
                expected_output="Translated content",
                constraints=["Must maintain meaning", "Should preserve formatting"]
            ),
            "calculation_agent": RoleAssignment(
                role_name="Calculation Specialist",
                role_description="Performs mathematical calculations.",
                expected_output="Calculation results with working",
                constraints=["Must show calculation steps", "Should validate inputs"]
            )
        }
        
        # Error tracking per agent
        self.agent_errors: Dict[str, List[Dict]] = {}
        self.correction_history: Dict[str, List[Dict]] = {}
        
        logger.info("RolesAgent initialized")
    
    async def process_task(self, task: TaskAssignment) -> Any:
        """Process a roles-related task"""
        task_type = task.task_type
        
        if task_type == "correct_agent":
            return await self._correct_agent(task)
        elif task_type == "analyze_error":
            return await self._analyze_error(task)
        elif task_type == "get_role":
            return await self._get_role(task)
        else:
            return await self._analyze_error(task)
    
    async def _correct_agent(self, task: TaskAssignment) -> Dict[str, Any]:
        """Analyze errors and send role correction to an agent"""
        target_agent = task.input_data.get("target_agent", "")
        errors = task.input_data.get("errors", [])
        
        if target_agent not in self.agent_roles:
            return {
                "success": False,
                "error": f"Unknown agent: {target_agent}"
            }
        
        role = self.agent_roles[target_agent]
        
        # Analyze the errors
        correction = await self._analyze_and_correct(target_agent, role, errors)
        
        if correction.should_correct:
            # Send role correction to the agent
            message = MessageProtocol.create_role_correction(
                self.agent_name,
                target_agent,
                role,
                correction.correction_guidance
            )
            
            await self.ws_manager.send_to_agent(message)
            
            # Track correction
            if target_agent not in self.correction_history:
                self.correction_history[target_agent] = []
            
            self.correction_history[target_agent].append({
                "timestamp": datetime.now().isoformat(),
                "error_type": correction.error_type,
                "guidance": correction.correction_guidance,
                "severity": correction.severity
            })
            
            # Notify frontend
            await self.ws_manager.broadcast_to_clients({
                "type": "role_correction_sent",
                "target_agent": target_agent,
                "error_type": correction.error_type,
                "severity": correction.severity,
                "timestamp": datetime.now().isoformat()
            })
            
            # Check if agent has too many corrections
            await self._check_correction_threshold(target_agent)
        
        return {
            "success": True,
            "correction_sent": correction.should_correct,
            "correction": correction.model_dump() if correction.should_correct else None
        }
    
    async def _analyze_and_correct(
        self, 
        agent_name: str, 
        role: RoleAssignment,
        errors: List[Dict]
    ) -> RoleCorrection:
        """Analyze errors and determine correction"""
        
        prompt = ChatPromptTemplate.from_template(
            """Analyze these errors from an AI agent and determine if role correction is needed.

Agent: {agent_name}
Role: {role_name}
Description: {role_description}
Expected Output: {expected_output}
Constraints: {constraints}

Recent Errors:
{errors}

Determine:
1. Is role correction needed? (Only if the agent is misunderstanding its role)
2. What type of error is this? (role_confusion, constraint_violation, output_format, other)
3. What specific guidance would help?
4. How severe is this? (low, medium, high)

Provide your analysis."""
        )
        
        errors_text = "\n".join([
            f"- {e.get('error', 'Unknown')}: {e.get('details', {})}"
            for e in errors
        ])
        
        chain = prompt | self.llm.with_structured_output(RoleCorrection)
        
        try:
            correction = await chain.ainvoke({
                "agent_name": agent_name,
                "role_name": role.role_name,
                "role_description": role.role_description,
                "expected_output": role.expected_output,
                "constraints": ", ".join(role.constraints),
                "errors": errors_text
            })
            return correction
        except Exception as e:
            logger.error(f"Error analyzing correction: {e}")
            return RoleCorrection(
                should_correct=False,
                role_clarification="",
                error_type="analysis_error",
                correction_guidance="",
                severity="low"
            )
    
    async def _analyze_error(self, task: TaskAssignment) -> Dict[str, Any]:
        """Analyze an error without sending correction"""
        target_agent = task.input_data.get("target_agent", "")
        error = task.input_data.get("error", "")
        
        if target_agent not in self.agent_roles:
            return {
                "analysis": "Unknown agent",
                "recommendation": "Check agent registration"
            }
        
        role = self.agent_roles[target_agent]
        
        prompt = ChatPromptTemplate.from_template(
            """Analyze this error in the context of the agent's role.

Agent: {agent_name}
Role: {role_name}
Role Description: {role_description}

Error: {error}

Provide:
1. Root cause analysis
2. Is this a role violation or execution error?
3. Recommendations"""
        )
        
        chain = prompt | self.llm
        
        result = await chain.ainvoke({
            "agent_name": target_agent,
            "role_name": role.role_name,
            "role_description": role.role_description,
            "error": error
        })
        
        return {
            "agent": target_agent,
            "error": error,
            "analysis": result.content
        }
    
    async def _get_role(self, task: TaskAssignment) -> Dict[str, Any]:
        """Get role definition for an agent"""
        agent_name = task.input_data.get("agent_name", "")
        
        if agent_name not in self.agent_roles:
            return {
                "found": False,
                "error": f"Unknown agent: {agent_name}"
            }
        
        role = self.agent_roles[agent_name]
        
        return {
            "found": True,
            "agent": agent_name,
            "role": role.model_dump()
        }
    
    async def _check_correction_threshold(self, agent_name: str):
        """Check if agent has received too many corrections"""
        if agent_name not in self.correction_history:
            return
        
        # Get corrections in last hour
        recent = [
            c for c in self.correction_history[agent_name]
            if (datetime.now() - datetime.fromisoformat(c["timestamp"])).seconds < 3600
        ]
        
        high_severity = [c for c in recent if c["severity"] == "high"]
        
        if len(recent) >= 5 or len(high_severity) >= 2:
            # Report to manager
            message = AgentMessage(
                type=MessageType.QUERY,
                source_agent=self.agent_name,
                target_agent="manager_agent",
                content={
                    "action": "agent_needs_attention",
                    "agent": agent_name,
                    "correction_count": len(recent),
                    "high_severity_count": len(high_severity),
                    "recommendation": "Consider interrupting or restarting agent"
                },
                priority=2
            )
            
            await self.ws_manager.send_to_agent(message)
            
            logger.warning(
                f"Agent {agent_name} has received {len(recent)} corrections in the last hour"
            )
