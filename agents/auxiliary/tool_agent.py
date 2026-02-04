"""
Tool Agent

Executes external tools and APIs:
- Tool discovery and selection
- Tool execution
- Result processing
- MCP integrations (File Control, System Commands, Medical RAG)
"""

import asyncio
import logging
import json
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain.tools import BaseTool
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


class ToolDefinition(BaseModel):
    """Definition of an available tool"""
    name: str = Field(description="Tool name")
    description: str = Field(description="Tool description")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")
    is_async: bool = Field(default=False, description="Whether tool is async")


class ToolExecutionResult(BaseModel):
    """Result of tool execution"""
    success: bool = Field(description="Whether execution was successful")
    tool_name: str = Field(description="Name of the executed tool")
    result: Any = Field(description="Tool output")
    execution_time: float = Field(description="Execution time in seconds")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class ToolAgent(BaseAgent):
    """
    Tool Agent for the multi-agent system.
    
    Responsibilities:
    - Manage and execute external tools
    - Select appropriate tools for tasks
    - Process and validate tool results
    """
    
    def __init__(self, agent_name: str = "tool_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="Tool Specialist",
            agent_description="Executes external tools and APIs"
        )
        
        # Load prompt configuration
        self.prompt_template = self.prompt_manager.get_prompt("tool_agent")
        
        # Tool registry
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()
        
        logger.info("ToolAgent initialized")
    
    def _register_default_tools(self):
        """Register default built-in tools"""
        
        # Calculator tool
        self.register_tool(
            name="calculator",
            description="Perform mathematical calculations",
            parameters={"expression": "string"},
            handler=self._calculator_handler
        )
        
        # JSON parser tool
        self.register_tool(
            name="json_parser",
            description="Parse and validate JSON strings",
            parameters={"json_string": "string"},
            handler=self._json_parser_handler
        )
        
        # Text analysis tool
        self.register_tool(
            name="text_analyzer",
            description="Analyze text for statistics (word count, character count, etc.)",
            parameters={"text": "string"},
            handler=self._text_analyzer_handler
        )
        
        # Register MCP tools
        self._register_mcp_tools()
    
    def _register_mcp_tools(self):
        """Register MCP-based tools (File Control, System Commands, Medical RAG)"""
        
        # File Control Tool
        self.register_tool(
            name="file_control",
            description="Read/write files: txt, json, csv, excel, pdf. Use for file operations.",
            parameters={
                "operation": "read_txt|write_txt|read_json|write_json|read_csv|read_excel|read_pdf|list_files",
                "file_path": "string",
                "content": "string (for write operations)",
                "encoding": "string (default: utf-8)"
            },
            handler=self._file_control_handler,
            is_async=True
        )
        
        # System Commands Tool
        self.register_tool(
            name="system_command",
            description="Execute safe system commands (echo, ls, dir, pwd, cat, grep, python, pip, git, etc.)",
            parameters={
                "command": "string",
                "timeout": "int (default: 30)"
            },
            handler=self._system_command_handler,
            is_async=True
        )
        
        # Medical RAG Tool
        self.register_tool(
            name="medical_rag",
            description="Search PubMed and medical regulations. Use for medical/health queries.",
            parameters={
                "operation": "search_pubmed|get_article|search_regulations",
                "query": "string",
                "max_results": "int (default: 5)"
            },
            handler=self._medical_rag_handler,
            is_async=True
        )
        
        logger.info("MCP tools registered: file_control, system_command, medical_rag")
    
    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable,
        is_async: bool = False
    ):
        """Register a new tool"""
        self.tools[name] = {
            "definition": ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                is_async=is_async
            ),
            "handler": handler
        }
        logger.info(f"Registered tool: {name}")
    
    def register_langchain_tool(self, tool: BaseTool):
        """Register a LangChain tool"""
        self.tools[tool.name] = {
            "definition": ToolDefinition(
                name=tool.name,
                description=tool.description,
                parameters=tool.args_schema.schema() if tool.args_schema else {},
                is_async=tool.is_async if hasattr(tool, 'is_async') else False
            ),
            "handler": tool.run,
            "langchain_tool": tool
        }
        logger.info(f"Registered LangChain tool: {tool.name}")
    
    async def process_task(self, task: TaskAssignment) -> Any:
        """Process a tool-related task"""
        task_type = task.task_type
        
        if task_type == "execute":
            return await self._execute_tool(task)
        elif task_type == "list":
            return await self._list_tools(task)
        elif task_type == "select":
            return await self._select_tool(task)
        else:
            return await self._auto_execute(task)
    
    async def _execute_tool(self, task: TaskAssignment) -> Dict[str, Any]:
        """Execute a specific tool"""
        tool_name = task.input_data.get("tool_name", "")
        parameters = task.input_data.get("parameters", {})
        
        if tool_name not in self.tools:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
                "available_tools": list(self.tools.keys())
            }
        
        tool = self.tools[tool_name]
        handler = tool["handler"]
        
        start_time = datetime.now()
        
        try:
            # Execute the tool
            if tool["definition"].is_async:
                result = await handler(**parameters)
            else:
                result = handler(**parameters)
            
            execution_time = (datetime.now() - start_time).total_seconds()
            
            return ToolExecutionResult(
                success=True,
                tool_name=tool_name,
                result=result,
                execution_time=execution_time
            ).model_dump()
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"Tool execution failed: {e}")
            
            return ToolExecutionResult(
                success=False,
                tool_name=tool_name,
                result=None,
                execution_time=execution_time,
                error=str(e)
            ).model_dump()
    
    async def _list_tools(self, task: TaskAssignment) -> Dict[str, Any]:
        """List available tools"""
        tool_list = []
        
        for name, tool in self.tools.items():
            definition = tool["definition"]
            tool_list.append({
                "name": definition.name,
                "description": definition.description,
                "parameters": definition.parameters
            })
        
        return {
            "success": True,
            "tool_count": len(tool_list),
            "tools": tool_list
        }
    
    async def _select_tool(self, task: TaskAssignment) -> Dict[str, Any]:
        """Select the best tool for a task"""
        task_description = task.input_data.get("task_description", task.description)
        
        # Get tool descriptions
        tool_descriptions = "\n".join([
            f"- {name}: {t['definition'].description}"
            for name, t in self.tools.items()
        ])
        
        prompt = ChatPromptTemplate.from_template(
            """Given the following task and available tools, select the most appropriate tool.

Task:
{task_description}

Available Tools:
{tool_descriptions}

Return the name of the best tool, or 'none' if no tool is suitable."""
        )
        
        chain = prompt | self.llm
        
        result = await chain.ainvoke({
            "task_description": task_description,
            "tool_descriptions": tool_descriptions
        })
        
        selected_tool = result.content.strip().lower()
        
        if selected_tool in self.tools:
            return {
                "success": True,
                "selected_tool": selected_tool,
                "tool_info": self.tools[selected_tool]["definition"].model_dump()
            }
        else:
            return {
                "success": False,
                "message": "No suitable tool found",
                "suggestion": result.content
            }
    
    async def _auto_execute(self, task: TaskAssignment) -> Dict[str, Any]:
        """Automatically select and execute a tool"""
        # First, select the tool
        selection = await self._select_tool(task)
        
        if not selection.get("success"):
            return selection
        
        tool_name = selection["selected_tool"]
        
        # Prepare parameters using LLM
        tool_def = self.tools[tool_name]["definition"]
        
        prompt = ChatPromptTemplate.from_template(
            """Given the task and tool, provide the parameters for the tool as JSON.

Task:
{task_description}

Tool: {tool_name}
Parameters Schema: {parameters}

Return only valid JSON with the parameter values."""
        )
        
        chain = prompt | self.llm
        
        result = await chain.ainvoke({
            "task_description": task.description,
            "tool_name": tool_name,
            "parameters": json.dumps(tool_def.parameters)
        })
        
        try:
            parameters = json.loads(result.content)
        except:
            parameters = {"input": result.content}
        
        # Execute with the parameters
        task.input_data["tool_name"] = tool_name
        task.input_data["parameters"] = parameters
        
        return await self._execute_tool(task)
    
    # Default tool handlers
    
    def _calculator_handler(self, expression: str) -> Dict[str, Any]:
        """Handle calculator operations"""
        try:
            # Safe evaluation (basic math only)
            allowed = set("0123456789+-*/().^ ")
            if not all(c in allowed for c in expression):
                raise ValueError("Invalid characters in expression")
            
            # Replace ^ with ** for power
            expression = expression.replace("^", "**")
            
            result = eval(expression)
            return {"expression": expression, "result": result}
        except Exception as e:
            raise ValueError(f"Calculation error: {e}")
    
    def _json_parser_handler(self, json_string: str) -> Dict[str, Any]:
        """Handle JSON parsing"""
        try:
            parsed = json.loads(json_string)
            return {
                "valid": True,
                "parsed": parsed,
                "type": type(parsed).__name__
            }
        except json.JSONDecodeError as e:
            return {
                "valid": False,
                "error": str(e),
                "position": e.pos
            }
    
    def _text_analyzer_handler(self, text: str) -> Dict[str, Any]:
        """Handle text analysis"""
        words = text.split()
        lines = text.split("\n")
        
        return {
            "character_count": len(text),
            "word_count": len(words),
            "line_count": len(lines),
            "average_word_length": sum(len(w) for w in words) / len(words) if words else 0
        }
    
    # MCP Tool Handlers
    
    async def _file_control_handler(
        self,
        operation: str,
        file_path: str = "",
        content: str = "",
        encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        """Handle file control operations via MCP"""
        try:
            from mcp.providers.file_control_provider import FileControlProvider, FileControlConfig
            
            config = FileControlConfig()
            provider = FileControlProvider(config)
            await provider.initialize()
            
            if operation == "read_txt":
                result = await provider.read_txt(file_path, encoding)
            elif operation == "write_txt":
                result = await provider.write_txt(file_path, content, encoding)
            elif operation == "read_json":
                result = await provider.read_json(file_path)
            elif operation == "write_json":
                result = await provider.write_json(file_path, json.loads(content))
            elif operation == "read_csv":
                result = await provider.read_csv(file_path)
            elif operation == "read_excel":
                result = await provider.read_excel(file_path)
            elif operation == "read_pdf":
                result = await provider.read_pdf(file_path)
            elif operation == "list_files":
                result = await provider.list_files(file_path)
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
            
            return result.model_dump() if hasattr(result, 'model_dump') else result
            
        except Exception as e:
            logger.error(f"File control error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _system_command_handler(
        self,
        command: str,
        timeout: int = 30
    ) -> Dict[str, Any]:
        """Handle system command execution via MCP"""
        try:
            from mcp.providers.system_command_provider import SystemCommandProvider, SystemCommandConfig
            
            # Disable HITL for agent execution
            config = SystemCommandConfig(require_confirmation=False)
            provider = SystemCommandProvider(config)
            await provider.initialize()
            
            result = await provider.execute_command(command, timeout=timeout)
            return result.model_dump() if hasattr(result, 'model_dump') else result
            
        except Exception as e:
            logger.error(f"System command error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _medical_rag_handler(
        self,
        operation: str,
        query: str = "",
        max_results: int = 5
    ) -> Dict[str, Any]:
        """Handle medical RAG operations via MCP"""
        try:
            from mcp.services.medical_rag_service import MedicalRAGService
            
            service = MedicalRAGService()
            await service.initialize()
            
            if operation == "search_pubmed":
                results = await service.search_pubmed(query, max_results=max_results)
                return {"success": True, "results": results, "count": len(results)}
            elif operation == "get_article":
                result = await service.get_article_details(query)  # query = article_id
                return {"success": True, "article": result}
            elif operation == "search_regulations":
                results = await service.search_regulations(query)
                return {"success": True, "regulations": results}
            else:
                return {"success": False, "error": f"Unknown operation: {operation}"}
                
        except Exception as e:
            logger.error(f"Medical RAG error: {e}")
            return {"success": False, "error": str(e)}
