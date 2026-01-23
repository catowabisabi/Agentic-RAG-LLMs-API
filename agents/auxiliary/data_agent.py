"""
Data Agent

Handles data processing and transformation:
- Data cleaning and normalization
- Format conversion
- Data extraction
"""

import asyncio
import logging
import json
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


class DataTransformation(BaseModel):
    """Result of data transformation"""
    success: bool = Field(description="Whether transformation was successful")
    transformed_data: Any = Field(description="The transformed data")
    format: str = Field(description="Output format (json, csv, text, etc.)")
    changes_made: List[str] = Field(description="List of changes applied")


class DataAgent(BaseAgent):
    """
    Data Agent for the multi-agent system.
    
    Responsibilities:
    - Process and transform data
    - Clean and normalize data
    - Convert between formats
    - Extract specific information
    """
    
    def __init__(self, agent_name: str = "data_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Data Specialist",
            agent_description="Handles data processing and transformation"
        )
        
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0,
            api_key=self.config.OPENAI_API_KEY
        )
        
        logger.info("DataAgent initialized")
    
    async def process_task(self, task: TaskAssignment) -> Any:
        """Process a data-related task"""
        task_type = task.task_type
        
        if task_type == "transform":
            return await self._transform_data(task)
        elif task_type == "clean":
            return await self._clean_data(task)
        elif task_type == "extract":
            return await self._extract_data(task)
        elif task_type == "convert":
            return await self._convert_format(task)
        elif task_type == "validate":
            return await self._validate_data(task)
        else:
            return await self._process_generic(task)
    
    async def _transform_data(self, task: TaskAssignment) -> Dict[str, Any]:
        """Transform data according to specifications"""
        data = task.input_data.get("data", {})
        transformation = task.input_data.get("transformation", "")
        
        prompt = ChatPromptTemplate.from_template(
            """Transform the following data according to the specified transformation.

Input Data:
{data}

Transformation Required:
{transformation}

Provide the transformed data in a structured format."""
        )
        
        chain = prompt | self.llm
        
        result = chain.invoke({
            "data": json.dumps(data, indent=2) if isinstance(data, (dict, list)) else str(data),
            "transformation": transformation
        })
        
        return {
            "success": True,
            "original_data": data,
            "transformed_data": result.content,
            "transformation": transformation
        }
    
    async def _clean_data(self, task: TaskAssignment) -> Dict[str, Any]:
        """Clean and normalize data"""
        data = task.input_data.get("data", {})
        rules = task.input_data.get("rules", [])
        
        changes_made = []
        cleaned_data = data
        
        # Apply cleaning rules
        if isinstance(data, dict):
            cleaned_data = {}
            for key, value in data.items():
                # Remove None values
                if value is None:
                    changes_made.append(f"Removed null value for key: {key}")
                    continue
                
                # Strip whitespace from strings
                if isinstance(value, str):
                    cleaned_value = value.strip()
                    if cleaned_value != value:
                        changes_made.append(f"Trimmed whitespace for key: {key}")
                    cleaned_data[key] = cleaned_value
                else:
                    cleaned_data[key] = value
        
        elif isinstance(data, list):
            cleaned_data = []
            for i, item in enumerate(data):
                # Remove None items
                if item is None:
                    changes_made.append(f"Removed null item at index {i}")
                    continue
                
                if isinstance(item, str):
                    cleaned_data.append(item.strip())
                else:
                    cleaned_data.append(item)
        
        return {
            "success": True,
            "original_data": data,
            "cleaned_data": cleaned_data,
            "changes_made": changes_made
        }
    
    async def _extract_data(self, task: TaskAssignment) -> Dict[str, Any]:
        """Extract specific information from data"""
        data = task.input_data.get("data", "")
        fields = task.input_data.get("fields", [])
        
        prompt = ChatPromptTemplate.from_template(
            """Extract the following fields from the provided data.

Data:
{data}

Fields to Extract:
{fields}

Return a JSON object with the extracted fields."""
        )
        
        chain = prompt | self.llm
        
        result = chain.invoke({
            "data": str(data),
            "fields": ", ".join(fields) if fields else "all relevant fields"
        })
        
        # Try to parse as JSON
        try:
            extracted = json.loads(result.content)
        except:
            extracted = {"raw_extraction": result.content}
        
        return {
            "success": True,
            "extracted_data": extracted,
            "fields_requested": fields
        }
    
    async def _convert_format(self, task: TaskAssignment) -> Dict[str, Any]:
        """Convert data between formats"""
        data = task.input_data.get("data", "")
        source_format = task.input_data.get("source_format", "auto")
        target_format = task.input_data.get("target_format", "json")
        
        # Auto-detect source format
        if source_format == "auto":
            if isinstance(data, dict):
                source_format = "json"
            elif isinstance(data, str):
                if data.strip().startswith("{") or data.strip().startswith("["):
                    source_format = "json"
                elif "," in data and "\n" in data:
                    source_format = "csv"
                else:
                    source_format = "text"
        
        prompt = ChatPromptTemplate.from_template(
            """Convert the following data from {source_format} to {target_format}.

Input Data:
{data}

Return only the converted data in {target_format} format."""
        )
        
        chain = prompt | self.llm
        
        result = chain.invoke({
            "data": str(data),
            "source_format": source_format,
            "target_format": target_format
        })
        
        return {
            "success": True,
            "original_data": data,
            "converted_data": result.content,
            "source_format": source_format,
            "target_format": target_format
        }
    
    async def _validate_data(self, task: TaskAssignment) -> Dict[str, Any]:
        """Validate data against a schema or rules"""
        data = task.input_data.get("data", {})
        schema = task.input_data.get("schema", {})
        rules = task.input_data.get("rules", [])
        
        errors = []
        warnings = []
        
        # Basic validation
        if isinstance(schema, dict) and schema:
            required_fields = schema.get("required", [])
            
            if isinstance(data, dict):
                for field in required_fields:
                    if field not in data:
                        errors.append(f"Missing required field: {field}")
        
        # Type validation
        if isinstance(schema, dict) and "properties" in schema:
            for field, spec in schema.get("properties", {}).items():
                if field in data:
                    expected_type = spec.get("type")
                    actual_value = data[field]
                    
                    if expected_type == "string" and not isinstance(actual_value, str):
                        errors.append(f"Field {field} should be string, got {type(actual_value).__name__}")
                    elif expected_type == "number" and not isinstance(actual_value, (int, float)):
                        errors.append(f"Field {field} should be number, got {type(actual_value).__name__}")
        
        is_valid = len(errors) == 0
        
        return {
            "is_valid": is_valid,
            "data": data,
            "errors": errors,
            "warnings": warnings
        }
    
    async def _process_generic(self, task: TaskAssignment) -> Dict[str, Any]:
        """Process a generic data task"""
        data = task.input_data.get("data", "")
        instructions = task.input_data.get("instructions", task.context)
        
        prompt = ChatPromptTemplate.from_template(
            """Process the following data according to these instructions.

Data:
{data}

Instructions:
{instructions}

Provide the processed result."""
        )
        
        chain = prompt | self.llm
        
        result = chain.invoke({
            "data": str(data),
            "instructions": instructions
        })
        
        return {
            "success": True,
            "result": result.content
        }
