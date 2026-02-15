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

from langchain.tools import BaseTool
from pydantic import BaseModel, Field

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    MessageProtocol,
    TaskAssignment
)

# Import MCP Providers
try:
    from mcp.providers.excel_provider import ExcelProvider
    HAS_EXCEL_PROVIDER = True
except ImportError:
    HAS_EXCEL_PROVIDER = False
    ExcelProvider = None

try:
    from mcp.providers.brave_search_provider import BraveSearchProvider, BraveSearchConfig
    HAS_BRAVE_SEARCH = True
except ImportError:
    HAS_BRAVE_SEARCH = False
    BraveSearchProvider = None

try:
    from mcp.providers.communication_provider import CommunicationProvider, CommunicationConfig
    HAS_COMMUNICATION = True
except ImportError:
    HAS_COMMUNICATION = False
    CommunicationProvider = None

try:
    from mcp.providers.file_control_provider import FileControlProvider, FileControlConfig
    HAS_FILE_CONTROL = True
except ImportError:
    HAS_FILE_CONTROL = False
    FileControlProvider = None

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
        
        # Initialize MCP Providers
        self._init_providers()
        
        self._register_default_tools()
        
        logger.info("ToolAgent initialized")
    
    def _init_providers(self):
        """Initialize all MCP providers"""
        # Excel Provider (for dedicated Excel operations)
        if HAS_EXCEL_PROVIDER:
            try:
                self.excel_provider = ExcelProvider(base_path="./excel_files")
                logger.info("Excel Provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Excel Provider: {e}")
                self.excel_provider = None
        else:
            self.excel_provider = None
        
        # File Control Provider (for TXT, JSON, PDF, CSV)
        if HAS_FILE_CONTROL:
            try:
                self.file_provider = FileControlProvider()
                # Initialize asynchronously later
                logger.info("File Control Provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize File Control Provider: {e}")
                self.file_provider = None
        else:
            self.file_provider = None
        
        # Brave Search Provider
        if HAS_BRAVE_SEARCH:
            try:
                # Try to load API key from environment
                import os
                api_key = os.getenv('BRAVE_API_KEY')
                config = BraveSearchConfig(api_key=api_key) if api_key else BraveSearchConfig()
                self.brave_provider = BraveSearchProvider(config)
                logger.info("Brave Search Provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Brave Search Provider: {e}")
                self.brave_provider = None
        else:
            self.brave_provider = None
        
        # Communication Provider
        if HAS_COMMUNICATION:
            try:
                self.comm_provider = CommunicationProvider()
                logger.info("Communication Provider initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Communication Provider: {e}")
                self.comm_provider = None
        else:
            self.comm_provider = None
    
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
        """Register MCP-based tools (File Control, System Commands, Medical RAG, Excel)"""
        
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
        
        # File Control Tools (if available)
        if self.file_provider:
            self._register_file_control_tools()
        
        # Excel Tools (if available)
        if self.excel_provider:
            self._register_excel_tools()
        
        # Brave Search Tools (if available)
        if self.brave_provider:
            self._register_brave_search_tools()
        
        # Communication Tools (if available)
        if self.comm_provider:
            self._register_communication_tools()
        
        logger.info("MCP tools registered")
    
    def _register_excel_tools(self):
        """Register Excel operation tools"""
        
        # Create Excel workbook
        self.register_tool(
            name="excel_create",
            description="Create a new Excel workbook with optional sheet name",
            parameters={
                "filepath": "string - Excel file path (e.g., 'report.xlsx')",
                "sheet_name": "string - Initial sheet name (default: 'Sheet1')"
            },
            handler=self._excel_create_handler,
            is_async=True
        )
        
        # Read Excel data
        self.register_tool(
            name="excel_read",
            description="Read data from Excel file range",
            parameters={
                "filepath": "string - Excel file path",
                "sheet_name": "string - Sheet name",
                "start_cell": "string - Start cell (e.g., 'A1', default: 'A1')",
                "end_cell": "string - End cell (optional, reads all if not specified)"
            },
            handler=self._excel_read_handler,
            is_async=True
        )
        
        # Write Excel data
        self.register_tool(
            name="excel_write",
            description="Write data to Excel file",
            parameters={
                "filepath": "string - Excel file path",
                "sheet_name": "string - Sheet name",
                "data": "array - 2D array of data [[row1], [row2], ...]",
                "start_cell": "string - Start cell (default: 'A1')"
            },
            handler=self._excel_write_handler,
            is_async=True
        )
        
        # Apply Excel formula
        self.register_tool(
            name="excel_formula",
            description="Apply Excel formula to a cell",
            parameters={
                "filepath": "string - Excel file path",
                "sheet_name": "string - Sheet name",
                "cell": "string - Cell address (e.g., 'D2')",
                "formula": "string - Excel formula (e.g., '=SUM(A1:A10)' or 'SUM(A1:A10)')"
            },
            handler=self._excel_formula_handler,
            is_async=True
        )
        
        # Format Excel cells
        self.register_tool(
            name="excel_format",
            description="Format Excel cells (font, color, border)",
            parameters={
                "filepath": "string - Excel file path",
                "sheet_name": "string - Sheet name",
                "cell_range": "string - Cell range (e.g., 'A1:D10')",
                "font_bold": "boolean - Make text bold (optional)",
                "font_color": "string - Font color in HEX (e.g., 'FF0000' for red, optional)",
                "bg_color": "string - Background color in HEX (e.g., 'FFFF00' for yellow, optional)",
                "border": "boolean - Add border (optional)"
            },
            handler=self._excel_format_handler,
            is_async=True
        )
        
        # Get Excel info
        self.register_tool(
            name="excel_info",
            description="Get information about Excel workbook (sheets, size, etc.)",
            parameters={
                "filepath": "string - Excel file path"
            },
            handler=self._excel_info_handler,
            is_async=True
        )
        
        logger.info("Excel tools registered: create, read, write, formula, format, info")
    
    def _register_file_control_tools(self):
        """Register file control tools (TXT, JSON, PDF, CSV)"""
        
        # Read text file
        self.register_tool(
            name="read_text",
            description="Read content from TXT, MD, or text files",
            parameters={
                "file_path": "string - File path",
                "encoding": "string - File encoding (default: utf-8)"
            },
            handler=self._file_read_text_handler,
            is_async=True
        )
        
        # Write text file
        self.register_tool(
            name="write_text",
            description="Write content to TXT or MD files",
            parameters={
                "file_path": "string - File path",
                "content": "string - Content to write",
                "append": "boolean - Append mode (default: False)"
            },
            handler=self._file_write_text_handler,
            is_async=True
        )
        
        # Read JSON
        self.register_tool(
            name="read_json",
            description="Read and parse JSON file",
            parameters={
                "file_path": "string - JSON file path"
            },
            handler=self._file_read_json_handler,
            is_async=True
        )
        
        # Write JSON
        self.register_tool(
            name="write_json",
            description="Write data to JSON file",
            parameters={
                "file_path": "string - JSON file path",
                "data": "object - Data to write"
            },
            handler=self._file_write_json_handler,
            is_async=True
        )
        
        # Read PDF
        self.register_tool(
            name="read_pdf",
            description="Extract text content from PDF file",
            parameters={
                "file_path": "string - PDF file path"
            },
            handler=self._file_read_pdf_handler,
            is_async=True
        )
        
        logger.info("File control tools registered: read_text, write_text, read_json, write_json, read_pdf")
    
    def _register_brave_search_tools(self):
        """Register Brave Search tools"""
        
        # Web search
        self.register_tool(
            name="web_search",
            description="Search the web using Brave Search (privacy-focused). Returns web results, FAQs, and infoboxes.",
            parameters={
                "query": "string - Search query",
                "count": "int - Number of results (default: 10, max: 20)",
                "freshness": "string - Time filter: 'pd' (past day), 'pw' (week), 'pm' (month), 'py' (year)"
            },
            handler=self._brave_web_search_handler,
            is_async=True
        )
        
        # News search
        self.register_tool(
            name="news_search",
            description="Search for news articles using Brave",
            parameters={
                "query": "string - Search query",
                "count": "int - Number of results (default: 10)"
            },
            handler=self._brave_news_search_handler,
            is_async=True
        )
        
        logger.info("Brave Search tools registered: web_search, news_search")
    
    def _register_communication_tools(self):
        """Register communication tools (Gmail, Telegram)"""
        
        # Send email
        self.register_tool(
            name="send_email",
            description="Send email via Gmail (requires OAuth2 setup)",
            parameters={
                "to": "string - Recipient email",
                "subject": "string - Email subject",
                "body": "string - Email body",
                "html": "boolean - Use HTML format (default: False)"
            },
            handler=self._comm_send_email_handler,
            is_async=True
        )
        
        # Read emails
        self.register_tool(
            name="read_emails",
            description="Read recent emails from Gmail inbox",
            parameters={
                "max_results": "int - Maximum emails to fetch (default: 10)",
                "unread_only": "boolean - Only unread emails (default: False)"
            },
            handler=self._comm_read_emails_handler,
            is_async=True
        )
        
        logger.info("Communication tools registered: send_email, read_emails")
    
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
        
        prompt = f"""Given the following task and available tools, select the most appropriate tool.

Task:
{task_description}

Available Tools:
{tool_descriptions}

Return the name of the best tool, or 'none' if no tool is suitable."""
        
        result = await self.llm_service.generate(
            prompt_key="tool_agent",
            user_input=prompt
        )
        
        selected_tool = result.get("content", "").strip().lower()
        
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
                "suggestion": result.get("content", "")
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
        
        prompt = f"""Given the task and tool, provide the parameters for the tool as JSON.

Task:
{task.description}

Tool: {tool_name}
Parameters Schema: {json.dumps(tool_def.parameters)}

Return only valid JSON with the parameter values."""
        
        result = await self.llm_service.generate(
            prompt_key="tool_agent",
            user_input=prompt
        )
        
        try:
            parameters = json.loads(result.get("content", "{}"))
        except:
            parameters = {"input": result.get("content", "")}
        
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
    
    # Excel Tool Handlers
    
    async def _excel_create_handler(
        self,
        filepath: str,
        sheet_name: str = "Sheet1"
    ) -> Dict[str, Any]:
        """Handle Excel workbook creation"""
        try:
            if not self.excel_provider:
                return {"success": False, "error": "Excel Provider not available"}
            
            result = self.excel_provider.create_workbook(filepath, sheet_name)
            return {"success": True, **result}
            
        except Exception as e:
            logger.error(f"Excel create error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _excel_read_handler(
        self,
        filepath: str,
        sheet_name: str,
        start_cell: str = "A1",
        end_cell: str = None
    ) -> Dict[str, Any]:
        """Handle Excel data reading"""
        try:
            if not self.excel_provider:
                return {"success": False, "error": "Excel Provider not available"}
            
            data = self.excel_provider.read_range(
                filepath, sheet_name, start_cell, end_cell
            )
            return {
                "success": True,
                "data": data,
                "rows": len(data),
                "cols": len(data[0]) if data else 0
            }
            
        except Exception as e:
            logger.error(f"Excel read error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _excel_write_handler(
        self,
        filepath: str,
        sheet_name: str,
        data: list,
        start_cell: str = "A1"
    ) -> Dict[str, Any]:
        """Handle Excel data writing"""
        try:
            if not self.excel_provider:
                return {"success": False, "error": "Excel Provider not available"}
            
            result = self.excel_provider.write_data(
                filepath, sheet_name, data, start_cell
            )
            return {"success": True, **result}
            
        except Exception as e:
            logger.error(f"Excel write error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _excel_formula_handler(
        self,
        filepath: str,
        sheet_name: str,
        cell: str,
        formula: str
    ) -> Dict[str, Any]:
        """Handle Excel formula application"""
        try:
            if not self.excel_provider:
                return {"success": False, "error": "Excel Provider not available"}
            
            result = self.excel_provider.apply_formula(
                filepath, sheet_name, cell, formula
            )
            return {"success": True, **result}
            
        except Exception as e:
            logger.error(f"Excel formula error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _excel_format_handler(
        self,
        filepath: str,
        sheet_name: str,
        cell_range: str,
        font_bold: bool = None,
        font_color: str = None,
        bg_color: str = None,
        border: bool = None
    ) -> Dict[str, Any]:
        """Handle Excel cell formatting"""
        try:
            if not self.excel_provider:
                return {"success": False, "error": "Excel Provider not available"}
            
            # Build style kwargs
            style_kwargs = {}
            if font_bold is not None:
                style_kwargs["font_bold"] = font_bold
            if font_color:
                style_kwargs["font_color"] = font_color
            if bg_color:
                style_kwargs["bg_color"] = bg_color
            if border is not None:
                style_kwargs["border"] = border
            
            result = self.excel_provider.format_cells(
                filepath, sheet_name, cell_range, **style_kwargs
            )
            return {"success": True, **result}
            
        except Exception as e:
            logger.error(f"Excel format error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _excel_info_handler(
        self,
        filepath: str
    ) -> Dict[str, Any]:
        """Handle Excel workbook info retrieval"""
        try:
            if not self.excel_provider:
                return {"success": False, "error": "Excel Provider not available"}
            
            info = self.excel_provider.get_workbook_info(filepath)
            return {"success": True, **info}
            
        except Exception as e:
            logger.error(f"Excel info error: {e}")
            return {"success": False, "error": str(e)}
    
    # File Control Tool Handlers
    
    async def _file_read_text_handler(
        self,
        file_path: str,
        encoding: str = "utf-8"
    ) -> Dict[str, Any]:
        """Handle text file reading"""
        try:
            if not self.file_provider:
                return {"success": False, "error": "File Control Provider not available"}
            
            await self.file_provider.initialize()
            result = await self.file_provider.read_txt(file_path, encoding)
            return result.model_dump() if hasattr(result, 'model_dump') else result.__dict__
            
        except Exception as e:
            logger.error(f"File read text error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _file_write_text_handler(
        self,
        file_path: str,
        content: str,
        append: bool = False
    ) -> Dict[str, Any]:
        """Handle text file writing"""
        try:
            if not self.file_provider:
                return {"success": False, "error": "File Control Provider not available"}
            
            await self.file_provider.initialize()
            result = await self.file_provider.write_txt(file_path, content, append=append)
            return result.model_dump() if hasattr(result, 'model_dump') else result.__dict__
            
        except Exception as e:
            logger.error(f"File write text error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _file_read_json_handler(
        self,
        file_path: str
    ) -> Dict[str, Any]:
        """Handle JSON file reading"""
        try:
            if not self.file_provider:
                return {"success": False, "error": "File Control Provider not available"}
            
            await self.file_provider.initialize()
            result = await self.file_provider.read_json(file_path)
            return result.model_dump() if hasattr(result, 'model_dump') else result.__dict__
            
        except Exception as e:
            logger.error(f"File read JSON error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _file_write_json_handler(
        self,
        file_path: str,
        data: Any
    ) -> Dict[str, Any]:
        """Handle JSON file writing"""
        try:
            if not self.file_provider:
                return {"success": False, "error": "File Control Provider not available"}
            
            await self.file_provider.initialize()
            result = await self.file_provider.write_json(file_path, data)
            return result.model_dump() if hasattr(result, 'model_dump') else result.__dict__
            
        except Exception as e:
            logger.error(f"File write JSON error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _file_read_pdf_handler(
        self,
        file_path: str
    ) -> Dict[str, Any]:
        """Handle PDF text extraction"""
        try:
            if not self.file_provider:
                return {"success": False, "error": "File Control Provider not available"}
            
            await self.file_provider.initialize()
            result = await self.file_provider.read_pdf(file_path)
            return result.model_dump() if hasattr(result, 'model_dump') else result.__dict__
            
        except Exception as e:
            logger.error(f"File read PDF error: {e}")
            return {"success": False, "error": str(e)}
    
    # Brave Search Tool Handlers
    
    async def _brave_web_search_handler(
        self,
        query: str,
        count: int = 10,
        freshness: str = None
    ) -> Dict[str, Any]:
        """Handle Brave web search"""
        try:
            if not self.brave_provider:
                return {"success": False, "error": "Brave Search not available. Set BRAVE_API_KEY environment variable."}
            
            await self.brave_provider.initialize()
            result = await self.brave_provider.web_search(query, count, freshness=freshness)
            return result.model_dump() if hasattr(result, 'model_dump') else result.__dict__
            
        except Exception as e:
            logger.error(f"Brave web search error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _brave_news_search_handler(
        self,
        query: str,
        count: int = 10
    ) -> Dict[str, Any]:
        """Handle Brave news search"""
        try:
            if not self.brave_provider:
                return {"success": False, "error": "Brave Search not available"}
            
            await self.brave_provider.initialize()
            result = await self.brave_provider.news_search(query, count)
            return result.model_dump() if hasattr(result, 'model_dump') else result.__dict__
            
        except Exception as e:
            logger.error(f"Brave news search error: {e}")
            return {"success": False, "error": str(e)}
    
    # Communication Tool Handlers
    
    async def _comm_send_email_handler(
        self,
        to: str,
        subject: str,
        body: str,
        html: bool = False
    ) -> Dict[str, Any]:
        """Handle email sending"""
        try:
            if not self.comm_provider:
                return {"success": False, "error": "Communication Provider not available. Configure Gmail credentials."}
            
            await self.comm_provider.initialize()
            result = await self.comm_provider.send_email(
                to=to, subject=subject, body=body, html=html, confirm=False
            )
            return result.model_dump() if hasattr(result, 'model_dump') else result.__dict__
            
        except Exception as e:
            logger.error(f"Send email error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _comm_read_emails_handler(
        self,
        max_results: int = 10,
        unread_only: bool = False
    ) -> Dict[str, Any]:
        """Handle email reading"""
        try:
            if not self.comm_provider:
                return {"success": False, "error": "Communication Provider not available"}
            
            await self.comm_provider.initialize()
            result = await self.comm_provider.read_emails(
                max_results=max_results, unread_only=unread_only
            )
            return result.model_dump() if hasattr(result, 'model_dump') else result.__dict__
            
        except Exception as e:
            logger.error(f"Read emails error: {e}")
            return {"success": False, "error": str(e)}
