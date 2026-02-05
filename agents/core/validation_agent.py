"""
Validation Agent

Validates data and responses for accuracy:
- Checks output quality
- Detects errors and inconsistencies
- Requests retries when needed
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


class DetailedValidation(BaseModel):
    """Detailed validation result"""
    is_valid: bool = Field(description="Whether the content passes validation")
    confidence: float = Field(
        default=0.5, 
        ge=0, 
        le=1, 
        description="Confidence in the validation"
    )
    errors: List[str] = Field(
        default_factory=list, 
        description="List of errors found"
    )
    warnings: List[str] = Field(
        default_factory=list, 
        description="List of warnings"
    )
    suggestions: List[str] = Field(
        default_factory=list, 
        description="Suggestions for improvement"
    )
    should_retry: bool = Field(
        default=False, 
        description="Whether the task should be retried"
    )


class ValidationAgent(BaseAgent):
    """
    Validation Agent for the multi-agent system.
    
    Responsibilities:
    - Validate outputs from other agents
    - Check for errors and inconsistencies
    - Request retries when data quality is poor
    - Report to manager when errors are excessive
    """
    
    def __init__(self, agent_name: str = "validation_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Validation Specialist",
            agent_description="Validates data and responses for accuracy"
        )
        
        # Load prompt configuration
        self.prompt_template = self.prompt_manager.get_prompt("validation_agent")
        
        # Error tracking
        self.validation_history: List[Dict[str, Any]] = []
        self.error_threshold = 5  # Errors before escalation
        
        logger.info("ValidationAgent initialized")
    
    async def process_task(self, task: TaskAssignment) -> Any:
        """Process a validation task"""
        task_type = task.task_type
        
        if task_type == "validate_response":
            return await self._validate_response(task)
        elif task_type == "validate_data":
            return await self._validate_data(task)
        elif task_type == "validate_plan":
            return await self._validate_plan(task)
        else:
            return await self._validate_response(task)
    
    async def _validate_response(self, task: TaskAssignment) -> Dict[str, Any]:
        """Validate an agent's response"""
        response = task.input_data.get("response", "")
        original_query = task.input_data.get("query", "")
        source_agent = task.input_data.get("source_agent", "unknown")
        context = task.input_data.get("context", "")
        
        try:
            validation = await self.llm_service.generate_with_structured_output(
                prompt_key="validation_agent",
                output_schema=DetailedValidation,
                variables={
                    "query": original_query,
                    "response": response,
                    "context": context or "No context provided"
                }
            )
            
            # Track validation
            self._track_validation(source_agent, validation)
            
            # Check if errors are excessive
            await self._check_error_threshold(source_agent)
            
            result = {
                "is_valid": validation.is_valid,
                "confidence": validation.confidence,
                "errors": validation.errors,
                "warnings": validation.warnings,
                "suggestions": validation.suggestions,
                "should_retry": validation.should_retry
            }
            
            # Notify frontend of validation result
            await self.ws_manager.broadcast_to_clients({
                "type": "validation_result",
                "source_agent": source_agent,
                "is_valid": validation.is_valid,
                "error_count": len(validation.errors),
                "timestamp": datetime.now().isoformat()
            })
            
            return result
            
        except Exception as e:
            logger.error(f"Error in validation: {e}")
            return {
                "is_valid": True,  # Default to valid on error
                "confidence": 0.3,
                "errors": [f"Validation error: {e}"],
                "warnings": [],
                "suggestions": [],
                "should_retry": False
            }
    
    async def _validate_data(self, task: TaskAssignment) -> Dict[str, Any]:
        """Validate structured data"""
        data = task.input_data.get("data", {})
        schema = task.input_data.get("schema", {})
        rules = task.input_data.get("rules", [])
        
        errors = []
        warnings = []
        
        # Check required fields
        for field, field_schema in schema.items():
            if field_schema.get("required") and field not in data:
                errors.append(f"Missing required field: {field}")
            
            if field in data:
                # Type checking
                expected_type = field_schema.get("type")
                if expected_type:
                    actual_type = type(data[field]).__name__
                    if expected_type != actual_type:
                        warnings.append(
                            f"Field '{field}' expected {expected_type}, got {actual_type}"
                        )
        
        # Apply custom rules
        for rule in rules:
            rule_type = rule.get("type")
            field = rule.get("field")
            
            if rule_type == "min_length" and field in data:
                if len(str(data[field])) < rule.get("value", 0):
                    errors.append(f"Field '{field}' is too short")
            
            elif rule_type == "max_length" and field in data:
                if len(str(data[field])) > rule.get("value", float("inf")):
                    errors.append(f"Field '{field}' is too long")
            
            elif rule_type == "pattern" and field in data:
                import re
                if not re.match(rule.get("value", ""), str(data[field])):
                    errors.append(f"Field '{field}' doesn't match pattern")
        
        is_valid = len(errors) == 0
        
        return {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "should_retry": not is_valid and len(errors) <= 3
        }
    
    async def _validate_plan(self, task: TaskAssignment) -> Dict[str, Any]:
        """Validate a plan from Planning Agent"""
        plan = task.input_data.get("plan", [])
        available_agents = task.input_data.get("available_agents", [])
        
        errors = []
        warnings = []
        
        if not plan:
            errors.append("Plan is empty")
        
        for i, step in enumerate(plan):
            # Check if step has required fields
            if "agent" not in step:
                errors.append(f"Step {i+1}: Missing target agent")
            elif step["agent"] not in available_agents:
                errors.append(f"Step {i+1}: Unknown agent '{step['agent']}'")
            
            if "action" not in step:
                warnings.append(f"Step {i+1}: Missing action description")
            
            if "dependencies" in step:
                for dep in step["dependencies"]:
                    if dep >= i:
                        errors.append(
                            f"Step {i+1}: Invalid dependency on future step"
                        )
        
        is_valid = len(errors) == 0
        
        return {
            "is_valid": is_valid,
            "errors": errors,
            "warnings": warnings,
            "should_retry": not is_valid
        }
    
    def _track_validation(self, source_agent: str, validation: DetailedValidation):
        """Track validation results for error monitoring"""
        self.validation_history.append({
            "source_agent": source_agent,
            "is_valid": validation.is_valid,
            "error_count": len(validation.errors),
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only recent history
        if len(self.validation_history) > 100:
            self.validation_history = self.validation_history[-50:]
    
    async def _check_error_threshold(self, source_agent: str):
        """Check if an agent has too many errors"""
        # Get recent errors for this agent
        recent_errors = [
            v for v in self.validation_history[-20:]
            if v["source_agent"] == source_agent and not v["is_valid"]
        ]
        
        if len(recent_errors) >= self.error_threshold:
            # Notify manager
            await self.ws_manager.send_to_agent(
                AgentMessage(
                    type=MessageType.VALIDATION_ERROR,
                    source_agent=self.agent_name,
                    target_agent="manager_agent",
                    content={
                        "problematic_agent": source_agent,
                        "error_count": len(recent_errors),
                        "message": f"Agent {source_agent} has {len(recent_errors)} validation failures"
                    },
                    priority=2
                )
            )
            
            logger.warning(
                f"Agent {source_agent} exceeded error threshold: "
                f"{len(recent_errors)} errors"
            )
