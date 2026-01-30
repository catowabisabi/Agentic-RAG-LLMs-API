"""
Calculation Agent

Performs mathematical calculations:
- Arithmetic operations
- Statistical calculations
- Formula evaluation
"""

import asyncio
import logging
import math
import statistics
from typing import Dict, Any, List, Optional, Union
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    MessageProtocol,
    TaskAssignment
)
from config.config import Config

logger = logging.getLogger(__name__)


class CalculationResult(BaseModel):
    """A calculation result"""
    expression: str = Field(description="The expression calculated")
    result: Union[float, int, str] = Field(description="The calculation result")
    steps: List[str] = Field(default_factory=list, description="Calculation steps")
    unit: Optional[str] = Field(default=None, description="Result unit if applicable")


class CalculationAgent(BaseAgent):
    """
    Calculation Agent for the multi-agent system.
    
    Responsibilities:
    - Perform mathematical calculations
    - Show calculation steps
    - Handle complex formulas
    """
    
    def __init__(self, agent_name: str = "calculation_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Calculation Specialist",
            agent_description="Performs mathematical calculations"
        )
        
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0,
            api_key=self.config.OPENAI_API_KEY
        )
        
        # Safe math functions
        self.safe_math = {
            'abs': abs,
            'round': round,
            'min': min,
            'max': max,
            'sum': sum,
            'pow': pow,
            'sqrt': math.sqrt,
            'log': math.log,
            'log10': math.log10,
            'sin': math.sin,
            'cos': math.cos,
            'tan': math.tan,
            'pi': math.pi,
            'e': math.e,
            'ceil': math.ceil,
            'floor': math.floor,
            'factorial': math.factorial,
        }
        
        logger.info("CalculationAgent initialized")
    
    async def process_task(self, task: TaskAssignment) -> Any:
        """Process a calculation task"""
        task_type = task.task_type
        
        if task_type == "calculate":
            return await self._calculate(task)
        elif task_type == "statistics":
            return await self._statistics(task)
        elif task_type == "formula":
            return await self._evaluate_formula(task)
        elif task_type == "convert":
            return await self._convert_units(task)
        elif task_type == "solve":
            return await self._solve_problem(task)
        else:
            return await self._calculate(task)
    
    async def _calculate(self, task: TaskAssignment) -> Dict[str, Any]:
        """Perform a mathematical calculation"""
        expression = task.input_data.get("expression", task.description)
        show_steps = task.input_data.get("show_steps", True)
        
        try:
            # Sanitize expression
            sanitized = self._sanitize_expression(expression)
            
            # Evaluate
            result = eval(sanitized, {"__builtins__": {}}, self.safe_math)
            
            steps = []
            if show_steps:
                steps = [
                    f"Original expression: {expression}",
                    f"Sanitized expression: {sanitized}",
                    f"Result: {result}"
                ]
            
            return {
                "success": True,
                "expression": expression,
                "result": result,
                "steps": steps
            }
            
        except Exception as e:
            # Try using LLM for complex expressions
            return await self._llm_calculate(expression, show_steps)
    
    def _sanitize_expression(self, expression: str) -> str:
        """Sanitize expression for safe evaluation"""
        # Replace common math symbols
        expression = expression.replace("^", "**")
        expression = expression.replace("×", "*")
        expression = expression.replace("÷", "/")
        expression = expression.replace("√", "sqrt")
        
        # Check for dangerous patterns
        dangerous = ["import", "exec", "eval", "__", "open", "file"]
        for pattern in dangerous:
            if pattern in expression.lower():
                raise ValueError(f"Unsafe expression: contains '{pattern}'")
        
        return expression
    
    async def _llm_calculate(self, expression: str, show_steps: bool) -> Dict[str, Any]:
        """Use LLM for complex calculations"""
        prompt = ChatPromptTemplate.from_template(
            """Calculate the following mathematical expression step by step.

Expression: {expression}

Show your work and provide the final numerical answer."""
        )
        
        chain = prompt | self.llm
        
        result = await chain.ainvoke({"expression": expression})
        
        # Extract the final answer
        content = result.content
        
        return {
            "success": True,
            "expression": expression,
            "result": content,
            "steps": content.split("\n") if show_steps else [],
            "method": "llm"
        }
    
    async def _statistics(self, task: TaskAssignment) -> Dict[str, Any]:
        """Calculate statistics for a dataset"""
        data = task.input_data.get("data", [])
        operations = task.input_data.get("operations", ["mean", "median", "std"])
        
        if not isinstance(data, list):
            return {
                "success": False,
                "error": "Data must be a list of numbers"
            }
        
        # Convert to floats
        try:
            numbers = [float(x) for x in data]
        except (ValueError, TypeError) as e:
            return {
                "success": False,
                "error": f"Invalid data: {e}"
            }
        
        results = {}
        
        for op in operations:
            try:
                if op == "mean":
                    results["mean"] = statistics.mean(numbers)
                elif op == "median":
                    results["median"] = statistics.median(numbers)
                elif op == "mode":
                    results["mode"] = statistics.mode(numbers)
                elif op == "std" or op == "stdev":
                    results["std"] = statistics.stdev(numbers) if len(numbers) > 1 else 0
                elif op == "variance":
                    results["variance"] = statistics.variance(numbers) if len(numbers) > 1 else 0
                elif op == "min":
                    results["min"] = min(numbers)
                elif op == "max":
                    results["max"] = max(numbers)
                elif op == "sum":
                    results["sum"] = sum(numbers)
                elif op == "count":
                    results["count"] = len(numbers)
                elif op == "range":
                    results["range"] = max(numbers) - min(numbers)
            except Exception as e:
                results[op] = f"Error: {e}"
        
        return {
            "success": True,
            "data_count": len(numbers),
            "statistics": results
        }
    
    async def _evaluate_formula(self, task: TaskAssignment) -> Dict[str, Any]:
        """Evaluate a formula with variables"""
        formula = task.input_data.get("formula", "")
        variables = task.input_data.get("variables", {})
        
        try:
            # Create context with variables and safe math
            context = {**self.safe_math, **variables}
            
            # Sanitize
            sanitized = self._sanitize_expression(formula)
            
            result = eval(sanitized, {"__builtins__": {}}, context)
            
            return {
                "success": True,
                "formula": formula,
                "variables": variables,
                "result": result
            }
            
        except Exception as e:
            return {
                "success": False,
                "formula": formula,
                "variables": variables,
                "error": str(e)
            }
    
    async def _convert_units(self, task: TaskAssignment) -> Dict[str, Any]:
        """Convert between units"""
        value = task.input_data.get("value", 0)
        from_unit = task.input_data.get("from_unit", "")
        to_unit = task.input_data.get("to_unit", "")
        
        # Common conversion factors
        conversions = {
            # Length
            ("m", "cm"): 100,
            ("m", "mm"): 1000,
            ("m", "km"): 0.001,
            ("m", "ft"): 3.28084,
            ("m", "in"): 39.3701,
            ("km", "mile"): 0.621371,
            
            # Weight
            ("kg", "g"): 1000,
            ("kg", "lb"): 2.20462,
            ("kg", "oz"): 35.274,
            
            # Temperature (special handling needed)
            
            # Time
            ("hour", "min"): 60,
            ("hour", "sec"): 3600,
            ("day", "hour"): 24,
            ("year", "day"): 365,
            
            # Volume
            ("L", "mL"): 1000,
            ("L", "gal"): 0.264172,
        }
        
        # Try direct conversion
        key = (from_unit, to_unit)
        reverse_key = (to_unit, from_unit)
        
        if key in conversions:
            result = value * conversions[key]
        elif reverse_key in conversions:
            result = value / conversions[reverse_key]
        elif from_unit == to_unit:
            result = value
        else:
            # Use LLM for complex conversions
            prompt = ChatPromptTemplate.from_template(
                """Convert {value} {from_unit} to {to_unit}.
Provide only the numerical answer."""
            )
            
            chain = prompt | self.llm
            response = await chain.ainvoke({
                "value": value,
                "from_unit": from_unit,
                "to_unit": to_unit
            })
            
            try:
                result = float(response.content.strip())
            except:
                return {
                    "success": False,
                    "error": f"Could not convert {from_unit} to {to_unit}"
                }
        
        return {
            "success": True,
            "original_value": value,
            "original_unit": from_unit,
            "converted_value": result,
            "target_unit": to_unit
        }
    
    async def _solve_problem(self, task: TaskAssignment) -> Dict[str, Any]:
        """Solve a math problem described in natural language"""
        problem = task.input_data.get("problem", task.description)
        
        prompt = ChatPromptTemplate.from_template(
            """Solve the following mathematical problem step by step.
Show your work clearly.

Problem:
{problem}

Solution:"""
        )
        
        chain = prompt | self.llm
        
        result = await chain.ainvoke({"problem": problem})
        
        # Parse the solution
        lines = result.content.strip().split("\n")
        steps = [line for line in lines if line.strip()]
        
        # Try to extract final answer
        final_answer = steps[-1] if steps else "See solution"
        
        return {
            "success": True,
            "problem": problem,
            "solution": result.content,
            "steps": steps,
            "final_answer": final_answer
        }
