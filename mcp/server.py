"""
MCP Server

Model Context Protocol server implementation:
- Provides tools for agent interaction
- Exposes resources for RAG
- Handles prompts for agent system
- File/Database/Communication/System control
- Medical RAG and Accounting Regulations
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional

from mcp.server import Server
try:
    from mcp.server.stdio import stdio_server  # type: ignore
except Exception:
    # stdio_server may not be available in the current environment (linter/CI or missing package).
    # Set to None and handle at runtime to provide a clear error message when attempting to run.
    stdio_server = None  # type: ignore
from pydantic import AnyUrl

# Attempt a runtime import to avoid static analyzer unresolved-import errors in editors;
# fall back to local dataclass definitions if mcp.types is not available.
try:
    import importlib
    mcp_types = importlib.import_module("mcp.types")
    Resource = getattr(mcp_types, "Resource")
    Tool = getattr(mcp_types, "Tool")
    TextContent = getattr(mcp_types, "TextContent")
    ImageContent = getattr(mcp_types, "ImageContent")
    EmbeddedResource = getattr(mcp_types, "EmbeddedResource")
    Prompt = getattr(mcp_types, "Prompt")
    PromptMessage = getattr(mcp_types, "PromptMessage")
    PromptArgument = getattr(mcp_types, "PromptArgument")
except Exception:
    # Fallback definitions for environments without 'mcp.types'
    from dataclasses import dataclass
    from typing import Optional, List, Dict, Any

    @dataclass
    class Resource:
        uri: AnyUrl
        name: str = ""
        description: str = ""
        mimeType: Optional[str] = None

    @dataclass
    class Tool:
        name: str
        description: str = ""
        inputSchema: Dict[str, Any] = None

    @dataclass
    class TextContent:
        type: str
        text: str

    @dataclass
    class ImageContent:
        type: str
        url: str
        alt: Optional[str] = None

    @dataclass
    class EmbeddedResource:
        uri: AnyUrl
        description: Optional[str] = None

    @dataclass
    class Prompt:
        name: str
        description: str = ""
        arguments: List[Any] = None

    @dataclass
    class PromptMessage:
        role: str
        content: Any

    @dataclass
    class PromptArgument:
        name: str
        description: str = ""
        required: bool = False

from agents.shared_services.agent_registry import AgentRegistry
from agents.shared_services.websocket_manager import WebSocketManager
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    TaskAssignment
)
from tools.retriever import DocumentRetriever
from config.config import Config

# Import new providers
from mcp.providers import (
    FileControlProvider,
    DatabaseControlProvider,
    CommunicationProvider,
    SystemCommandProvider
)
# Import new services
from mcp.services import MedicalRAGService
from mcp.services.accounting_regulations_data import (
    get_all_regulations,
    get_regulations_by_jurisdiction,
    ingest_regulations_to_rag
)

logger = logging.getLogger(__name__)


class MCPAgentServer:
    """
    MCP Server for the multi-agent system.
    
    Provides:
    - Tools for querying and managing agents
    - Resources for document retrieval
    - Prompts for common operations
    - File/Database/Communication/System control
    - Medical RAG and Accounting Regulations
    """
    
    def __init__(self):
        self.server = Server("agentic-rag-server")
        self.config = Config()
        self.registry = None
        self.ws_manager = None
        
        # Initialize new providers
        self.file_provider = FileControlProvider()
        self.db_provider = DatabaseControlProvider()
        self.comm_provider = CommunicationProvider()
        self.system_provider = SystemCommandProvider()
        self.medical_service = MedicalRAGService()
        
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Set up MCP handlers"""
        
        @self.server.list_resources()
        async def list_resources() -> list[Resource]:
            """List available resources"""
            resources = []
            
            # Add document collections as resources
            try:
                retriever = DocumentRetriever()
                collections = ["default", "chemistry", "medicine", "personal-finance",
                             "pinescript", "python-tradebot", "short-trading",
                             "solidworks-api", "market-data"]
                
                for collection in collections:
                    resources.append(Resource(
                        uri=AnyUrl(f"rag://{collection}"),
                        name=f"Document Collection: {collection}",
                        description=f"RAG collection for {collection} documents",
                        mimeType="application/json"
                    ))
            except Exception as e:
                logger.error(f"Error listing resources: {e}")
            
            return resources
        
        @self.server.read_resource()
        async def read_resource(uri: AnyUrl) -> str:
            """Read a resource"""
            uri_str = str(uri)
            
            if uri_str.startswith("rag://"):
                collection = uri_str.replace("rag://", "")
                try:
                    retriever = DocumentRetriever(collection_name=collection)
                    info = retriever.get_collection_info()
                    
                    import json
                    return json.dumps(info, indent=2)
                except Exception as e:
                    return f"Error reading collection {collection}: {e}"
            
            return f"Unknown resource: {uri}"
        
        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            """List available tools"""
            return [
                Tool(
                    name="query_agents",
                    description="Send a query to the multi-agent system",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The query to process"
                            },
                            "context": {
                                "type": "object",
                                "description": "Additional context"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="list_agents",
                    description="List all available agents and their status",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                Tool(
                    name="get_agent_status",
                    description="Get the status of a specific agent",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "agent_name": {
                                "type": "string",
                                "description": "Name of the agent"
                            }
                        },
                        "required": ["agent_name"]
                    }
                ),
                Tool(
                    name="query_rag",
                    description="Query the RAG system for relevant documents",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Query string"
                            },
                            "collection": {
                                "type": "string",
                                "description": "Collection to query"
                            },
                            "top_k": {
                                "type": "integer",
                                "description": "Number of results"
                            }
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="add_document",
                    description="Add a document to the RAG system",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Document content"
                            },
                            "collection": {
                                "type": "string",
                                "description": "Target collection"
                            },
                            "metadata": {
                                "type": "object",
                                "description": "Document metadata"
                            }
                        },
                        "required": ["content"]
                    }
                ),
                Tool(
                    name="interrupt_agent",
                    description="Send an interrupt signal to an agent",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "agent_name": {
                                "type": "string",
                                "description": "Agent to interrupt"
                            },
                            "reason": {
                                "type": "string",
                                "description": "Reason for interrupt"
                            }
                        },
                        "required": ["agent_name"]
                    }
                ),
                Tool(
                    name="create_plan",
                    description="Create an execution plan for a task",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "Task description"
                            },
                            "constraints": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "Constraints for planning"
                            }
                        },
                        "required": ["task"]
                    }
                ),
                Tool(
                    name="deep_think",
                    description="Perform deep reasoning on a problem",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "problem": {
                                "type": "string",
                                "description": "Problem to analyze"
                            },
                            "context": {
                                "type": "string",
                                "description": "Additional context"
                            }
                        },
                        "required": ["problem"]
                    }
                ),
                Tool(
                    name="summarize",
                    description="Summarize content",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "content": {
                                "type": "string",
                                "description": "Content to summarize"
                            },
                            "max_length": {
                                "type": "integer",
                                "description": "Maximum summary length"
                            }
                        },
                        "required": ["content"]
                    }
                ),
                Tool(
                    name="translate",
                    description="Translate text to another language",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "text": {
                                "type": "string",
                                "description": "Text to translate"
                            },
                            "target_language": {
                                "type": "string",
                                "description": "Target language"
                            }
                        },
                        "required": ["text", "target_language"]
                    }
                ),
                Tool(
                    name="calculate",
                    description="Perform mathematical calculations",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "expression": {
                                "type": "string",
                                "description": "Math expression or problem"
                            }
                        },
                        "required": ["expression"]
                    }
                ),
                # ============================================
                # FILE CONTROL TOOLS
                # ============================================
                Tool(
                    name="read_file",
                    description="Read content from TXT, JSON, CSV, Excel, or PDF files",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to the file"},
                            "file_type": {"type": "string", "enum": ["txt", "json", "csv", "excel", "pdf"], "description": "Type of file"},
                            "sheet_name": {"type": "string", "description": "Sheet name for Excel files (optional)"}
                        },
                        "required": ["file_path", "file_type"]
                    }
                ),
                Tool(
                    name="write_file",
                    description="Write content to TXT, JSON, CSV, or Excel files",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "file_path": {"type": "string", "description": "Path to the file"},
                            "file_type": {"type": "string", "enum": ["txt", "json", "csv", "excel"], "description": "Type of file"},
                            "content": {"type": "string", "description": "Content to write (string or JSON for structured data)"}
                        },
                        "required": ["file_path", "file_type", "content"]
                    }
                ),
                Tool(
                    name="list_files",
                    description="List files in a directory with optional pattern matching",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "directory": {"type": "string", "description": "Directory path"},
                            "pattern": {"type": "string", "description": "Glob pattern (e.g., *.txt)"}
                        },
                        "required": ["directory"]
                    }
                ),
                # ============================================
                # DATABASE CONTROL TOOLS
                # ============================================
                Tool(
                    name="query_database",
                    description="Execute SELECT query on SQLite or PostgreSQL database",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "db_type": {"type": "string", "enum": ["sqlite", "postgres"], "description": "Database type"},
                            "db_path": {"type": "string", "description": "Path for SQLite or connection string for PostgreSQL"},
                            "query": {"type": "string", "description": "SQL SELECT query"},
                            "params": {"type": "array", "description": "Query parameters"}
                        },
                        "required": ["db_type", "db_path", "query"]
                    }
                ),
                Tool(
                    name="execute_database",
                    description="Execute INSERT/UPDATE/DELETE on database",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "db_type": {"type": "string", "enum": ["sqlite", "postgres"]},
                            "db_path": {"type": "string"},
                            "query": {"type": "string"},
                            "params": {"type": "array"}
                        },
                        "required": ["db_type", "db_path", "query"]
                    }
                ),
                Tool(
                    name="list_database_tables",
                    description="List all tables in a database",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "db_type": {"type": "string", "enum": ["sqlite", "postgres"]},
                            "db_path": {"type": "string"}
                        },
                        "required": ["db_type", "db_path"]
                    }
                ),
                # ============================================
                # COMMUNICATION TOOLS
                # ============================================
                Tool(
                    name="send_email",
                    description="Send email via Gmail",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Recipient email"},
                            "subject": {"type": "string"},
                            "body": {"type": "string"},
                            "require_confirmation": {"type": "boolean", "default": True}
                        },
                        "required": ["to", "subject", "body"]
                    }
                ),
                Tool(
                    name="send_telegram",
                    description="Send message via Telegram",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "chat_id": {"type": "string"},
                            "message": {"type": "string"},
                            "require_confirmation": {"type": "boolean", "default": True}
                        },
                        "required": ["chat_id", "message"]
                    }
                ),
                Tool(
                    name="send_whatsapp",
                    description="Send WhatsApp message via Twilio",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "to": {"type": "string", "description": "Phone number with country code"},
                            "message": {"type": "string"},
                            "require_confirmation": {"type": "boolean", "default": True}
                        },
                        "required": ["to", "message"]
                    }
                ),
                # ============================================
                # SYSTEM COMMAND TOOLS
                # ============================================
                Tool(
                    name="execute_command",
                    description="Execute shell command (with security controls)",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "command": {"type": "string"},
                            "args": {"type": "array", "items": {"type": "string"}},
                            "working_dir": {"type": "string"},
                            "require_confirmation": {"type": "boolean", "default": True}
                        },
                        "required": ["command"]
                    }
                ),
                Tool(
                    name="run_python_code",
                    description="Execute Python code snippet safely",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "code": {"type": "string"},
                            "timeout": {"type": "integer", "default": 30}
                        },
                        "required": ["code"]
                    }
                ),
                Tool(
                    name="get_system_info",
                    description="Get system information (CPU, memory, disk)",
                    inputSchema={
                        "type": "object",
                        "properties": {}
                    }
                ),
                # ============================================
                # MEDICAL RAG TOOLS
                # ============================================
                Tool(
                    name="search_pubmed",
                    description="Search PubMed for medical literature",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "max_results": {"type": "integer", "default": 10}
                        },
                        "required": ["query"]
                    }
                ),
                Tool(
                    name="search_clinical_trials",
                    description="Search ClinicalTrials.gov for studies",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "condition": {"type": "string"},
                            "intervention": {"type": "string"},
                            "status": {"type": "string", "enum": ["recruiting", "completed", "active"]}
                        },
                        "required": ["condition"]
                    }
                ),
                Tool(
                    name="lookup_drug",
                    description="Look up drug information from OpenFDA",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "drug_name": {"type": "string"}
                        },
                        "required": ["drug_name"]
                    }
                ),
                # ============================================
                # ACCOUNTING REGULATIONS TOOLS
                # ============================================
                Tool(
                    name="get_accounting_regulations",
                    description="Get accounting regulations for Hong Kong, China, or Canada",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "jurisdiction": {"type": "string", "enum": ["Hong Kong", "China", "Canada", "all"]}
                        },
                        "required": ["jurisdiction"]
                    }
                ),
                Tool(
                    name="ingest_accounting_to_rag",
                    description="Ingest accounting regulations into RAG system",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "jurisdictions": {"type": "array", "items": {"type": "string"}},
                            "collection_name": {"type": "string", "default": "accounting"}
                        }
                    }
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool calls"""
            try:
                # Original agent tools
                if name == "query_agents":
                    result = await self._query_agents(arguments)
                elif name == "list_agents":
                    result = await self._list_agents()
                elif name == "get_agent_status":
                    result = await self._get_agent_status(arguments)
                elif name == "query_rag":
                    result = await self._query_rag(arguments)
                elif name == "add_document":
                    result = await self._add_document(arguments)
                elif name == "interrupt_agent":
                    result = await self._interrupt_agent(arguments)
                elif name == "create_plan":
                    result = await self._create_plan(arguments)
                elif name == "deep_think":
                    result = await self._deep_think(arguments)
                elif name == "summarize":
                    result = await self._summarize(arguments)
                elif name == "translate":
                    result = await self._translate(arguments)
                elif name == "calculate":
                    result = await self._calculate(arguments)
                
                # File control tools
                elif name == "read_file":
                    result = await self._handle_file_read(arguments)
                elif name == "write_file":
                    result = await self._handle_file_write(arguments)
                elif name == "list_files":
                    result = await self._handle_list_files(arguments)
                
                # Database control tools
                elif name == "query_database":
                    result = await self._handle_db_query(arguments)
                elif name == "execute_database":
                    result = await self._handle_db_execute(arguments)
                elif name == "list_database_tables":
                    result = await self._handle_list_tables(arguments)
                
                # Communication tools
                elif name == "send_email":
                    result = await self._handle_send_email(arguments)
                elif name == "send_telegram":
                    result = await self._handle_send_telegram(arguments)
                elif name == "send_whatsapp":
                    result = await self._handle_send_whatsapp(arguments)
                
                # System command tools
                elif name == "execute_command":
                    result = await self._handle_execute_command(arguments)
                elif name == "run_python_code":
                    result = await self._handle_run_python(arguments)
                elif name == "get_system_info":
                    result = await self._handle_system_info(arguments)
                
                # Medical RAG tools
                elif name == "search_pubmed":
                    result = await self._handle_search_pubmed(arguments)
                elif name == "search_clinical_trials":
                    result = await self._handle_search_trials(arguments)
                elif name == "lookup_drug":
                    result = await self._handle_lookup_drug(arguments)
                
                # Accounting regulations tools
                elif name == "get_accounting_regulations":
                    result = await self._handle_get_regulations(arguments)
                elif name == "ingest_accounting_to_rag":
                    result = await self._handle_ingest_regulations(arguments)
                
                else:
                    result = {"error": f"Unknown tool: {name}"}
                
                import json
                return [TextContent(type="text", text=json.dumps(result, indent=2))]
                
            except Exception as e:
                logger.error(f"Tool error {name}: {e}")
                return [TextContent(type="text", text=f"Error: {e}")]
        
        @self.server.list_prompts()
        async def list_prompts() -> list[Prompt]:
            """List available prompts"""
            return [
                Prompt(
                    name="analyze",
                    description="Analyze a topic using the agent system",
                    arguments=[
                        PromptArgument(
                            name="topic",
                            description="Topic to analyze",
                            required=True
                        )
                    ]
                ),
                Prompt(
                    name="research",
                    description="Research a question using RAG and agents",
                    arguments=[
                        PromptArgument(
                            name="question",
                            description="Research question",
                            required=True
                        )
                    ]
                )
            ]
        
        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: dict) -> list[PromptMessage]:
            """Get a prompt"""
            if name == "analyze":
                topic = arguments.get("topic", "")
                return [
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=f"Analyze the following topic using deep reasoning and relevant documents: {topic}"
                        )
                    )
                ]
            elif name == "research":
                question = arguments.get("question", "")
                return [
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=f"Research and answer the following question using all available resources: {question}"
                        )
                    )
                ]
            else:
                return []
    
    async def _query_agents(self, args: dict) -> dict:
        """Send query to agent system"""
        query = args.get("query", "")
        context = args.get("context", {})
        
        registry = AgentRegistry()
        ws_manager = WebSocketManager()
        
        manager = registry.get_agent("manager_agent")
        if not manager:
            return {"error": "Manager agent not available"}
        
        from datetime import datetime
        
        task = TaskAssignment(
            task_id=f"mcp-{datetime.now().timestamp()}",
            task_type="process_query",
            input_data={"query": query, "context": context},
            context=query,
            priority=1
        )
        
        message = AgentMessage(
            type=MessageType.TASK_ASSIGNED,
            source_agent="mcp",
            target_agent="manager_agent",
            content=task.model_dump(),
            priority=1
        )
        
        await ws_manager.send_to_agent(message)
        
        return {
            "success": True,
            "task_id": task.task_id,
            "message": "Query sent to agent system"
        }
    
    async def _list_agents(self) -> dict:
        """List all agents"""
        registry = AgentRegistry()
        return registry.get_system_health()
    
    async def _get_agent_status(self, args: dict) -> dict:
        """Get agent status"""
        agent_name = args.get("agent_name", "")
        registry = AgentRegistry()
        
        health = registry.get_agent_health(agent_name)
        if not health:
            return {"error": f"Agent {agent_name} not found"}
        
        return health
    
    async def _query_rag(self, args: dict) -> dict:
        """Query RAG system"""
        query = args.get("query", "")
        collection = args.get("collection", "default")
        top_k = args.get("top_k", 5)
        
        retriever = DocumentRetriever(collection_name=collection)
        results = retriever.retrieve(query, top_k=top_k)
        
        return {
            "query": query,
            "collection": collection,
            "results": results
        }
    
    async def _add_document(self, args: dict) -> dict:
        """Add document to RAG"""
        content = args.get("content", "")
        collection = args.get("collection", "default")
        metadata = args.get("metadata", {})
        
        retriever = DocumentRetriever(collection_name=collection)
        doc_id = retriever.add_document(content=content, metadata=metadata)
        
        return {
            "success": True,
            "document_id": doc_id,
            "collection": collection
        }
    
    async def _interrupt_agent(self, args: dict) -> dict:
        """Interrupt an agent"""
        agent_name = args.get("agent_name", "")
        reason = args.get("reason", "MCP interrupt request")
        
        registry = AgentRegistry()
        manager = registry.get_agent("manager_agent")
        
        if not manager:
            return {"error": "Manager agent not available"}
        
        await manager.interrupt_agent(agent_name, reason)
        
        return {
            "success": True,
            "interrupted": agent_name,
            "reason": reason
        }
    
    async def _create_plan(self, args: dict) -> dict:
        """Create execution plan"""
        task = args.get("task", "")
        constraints = args.get("constraints", [])
        
        registry = AgentRegistry()
        ws_manager = WebSocketManager()
        
        planning_agent = registry.get_agent("planning_agent")
        if not planning_agent:
            return {"error": "Planning agent not available"}
        
        from datetime import datetime
        
        task_assignment = TaskAssignment(
            task_id=f"plan-{datetime.now().timestamp()}",
            task_type="plan",
            input_data={"task": task, "constraints": constraints},
            context=task,
            priority=1
        )
        
        message = AgentMessage(
            type=MessageType.TASK_ASSIGNED,
            source_agent="mcp",
            target_agent="planning_agent",
            content=task_assignment.model_dump(),
            priority=1
        )
        
        await ws_manager.send_to_agent(message)
        
        return {
            "success": True,
            "task_id": task_assignment.task_id,
            "message": "Planning task submitted"
        }
    
    async def _deep_think(self, args: dict) -> dict:
        """Deep reasoning"""
        problem = args.get("problem", "")
        context = args.get("context", "")
        
        registry = AgentRegistry()
        ws_manager = WebSocketManager()
        
        thinking_agent = registry.get_agent("thinking_agent")
        if not thinking_agent:
            return {"error": "Thinking agent not available"}
        
        from datetime import datetime
        
        task = TaskAssignment(
            task_id=f"think-{datetime.now().timestamp()}",
            task_type="reason",
            input_data={"problem": problem, "context": context},
            context=problem,
            priority=1
        )
        
        message = AgentMessage(
            type=MessageType.TASK_ASSIGNED,
            source_agent="mcp",
            target_agent="thinking_agent",
            content=task.model_dump(),
            priority=1
        )
        
        await ws_manager.send_to_agent(message)
        
        return {
            "success": True,
            "task_id": task.task_id,
            "message": "Thinking task submitted"
        }
    
    async def _summarize(self, args: dict) -> dict:
        """Summarize content"""
        content = args.get("content", "")
        max_length = args.get("max_length", 200)
        
        registry = AgentRegistry()
        ws_manager = WebSocketManager()
        
        summarize_agent = registry.get_agent("summarize_agent")
        if not summarize_agent:
            return {"error": "Summarize agent not available"}
        
        from datetime import datetime
        
        task = TaskAssignment(
            task_id=f"sum-{datetime.now().timestamp()}",
            task_type="summarize",
            input_data={"content": content, "max_length": max_length},
            context=content[:100],
            priority=1
        )
        
        message = AgentMessage(
            type=MessageType.TASK_ASSIGNED,
            source_agent="mcp",
            target_agent="summarize_agent",
            content=task.model_dump(),
            priority=1
        )
        
        await ws_manager.send_to_agent(message)
        
        return {
            "success": True,
            "task_id": task.task_id,
            "message": "Summarization task submitted"
        }
    
    async def _translate(self, args: dict) -> dict:
        """Translate text"""
        text = args.get("text", "")
        target_language = args.get("target_language", "English")
        
        registry = AgentRegistry()
        ws_manager = WebSocketManager()
        
        translate_agent = registry.get_agent("translate_agent")
        if not translate_agent:
            return {"error": "Translate agent not available"}
        
        from datetime import datetime
        
        task = TaskAssignment(
            task_id=f"trans-{datetime.now().timestamp()}",
            task_type="translate",
            input_data={"text": text, "target_language": target_language},
            context=text[:100],
            priority=1
        )
        
        message = AgentMessage(
            type=MessageType.TASK_ASSIGNED,
            source_agent="mcp",
            target_agent="translate_agent",
            content=task.model_dump(),
            priority=1
        )
        
        await ws_manager.send_to_agent(message)
        
        return {
            "success": True,
            "task_id": task.task_id,
            "message": "Translation task submitted"
        }
    
    async def _calculate(self, args: dict) -> dict:
        """Calculate expression"""
        expression = args.get("expression", "")
        
        registry = AgentRegistry()
        ws_manager = WebSocketManager()
        
        calculation_agent = registry.get_agent("calculation_agent")
        if not calculation_agent:
            return {"error": "Calculation agent not available"}
        
        from datetime import datetime
        
        task = TaskAssignment(
            task_id=f"calc-{datetime.now().timestamp()}",
            task_type="calculate",
            input_data={"expression": expression},
            context=expression,
            priority=1
        )
        
        message = AgentMessage(
            type=MessageType.TASK_ASSIGNED,
            source_agent="mcp",
            target_agent="calculation_agent",
            content=task.model_dump(),
            priority=1
        )
        
        await ws_manager.send_to_agent(message)
        
        return {
            "success": True,
            "task_id": task.task_id,
            "message": "Calculation task submitted"
        }
    
    # ============================================
    # FILE CONTROL HANDLERS
    # ============================================
    
    async def _handle_file_read(self, args: dict) -> dict:
        """Handle file read operations"""
        file_path = args.get("file_path", "")
        file_type = args.get("file_type", "txt")
        sheet_name = args.get("sheet_name")
        
        try:
            if file_type == "txt":
                result = self.file_provider.read_txt(file_path)
            elif file_type == "json":
                result = self.file_provider.read_json(file_path)
            elif file_type == "csv":
                result = self.file_provider.read_csv(file_path)
            elif file_type == "excel":
                result = self.file_provider.read_excel(file_path, sheet_name)
            elif file_type == "pdf":
                result = self.file_provider.read_pdf(file_path)
            else:
                return {"error": f"Unsupported file type: {file_type}"}
            
            return {"success": True, "content": result}
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_file_write(self, args: dict) -> dict:
        """Handle file write operations"""
        file_path = args.get("file_path", "")
        file_type = args.get("file_type", "txt")
        content = args.get("content", "")
        
        try:
            import json as json_module
            
            if file_type == "txt":
                result = self.file_provider.write_txt(file_path, content)
            elif file_type == "json":
                data = json_module.loads(content) if isinstance(content, str) else content
                result = self.file_provider.write_json(file_path, data)
            elif file_type == "csv":
                data = json_module.loads(content) if isinstance(content, str) else content
                result = self.file_provider.write_csv(file_path, data)
            elif file_type == "excel":
                data = json_module.loads(content) if isinstance(content, str) else content
                result = self.file_provider.write_excel(file_path, data)
            else:
                return {"error": f"Unsupported file type: {file_type}"}
            
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_list_files(self, args: dict) -> dict:
        """Handle list files operation"""
        directory = args.get("directory", ".")
        pattern = args.get("pattern", "*")
        
        try:
            result = self.file_provider.list_files(directory, pattern)
            return result
        except Exception as e:
            return {"error": str(e)}
    
    # ============================================
    # DATABASE CONTROL HANDLERS
    # ============================================
    
    async def _handle_db_query(self, args: dict) -> dict:
        """Handle database query"""
        db_type = args.get("db_type", "sqlite")
        db_path = args.get("db_path", "")
        query = args.get("query", "")
        params = args.get("params", [])
        
        try:
            if db_type == "sqlite":
                result = self.db_provider.query_sqlite(db_path, query, tuple(params) if params else None)
            elif db_type == "postgres":
                result = await self.db_provider.query_postgres(db_path, query, tuple(params) if params else None)
            else:
                return {"error": f"Unsupported database type: {db_type}"}
            
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_db_execute(self, args: dict) -> dict:
        """Handle database execute"""
        db_type = args.get("db_type", "sqlite")
        db_path = args.get("db_path", "")
        query = args.get("query", "")
        params = args.get("params", [])
        
        try:
            if db_type == "sqlite":
                result = self.db_provider.execute_sqlite(db_path, query, tuple(params) if params else None)
            else:
                return {"error": "Execute only supported for SQLite currently"}
            
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_list_tables(self, args: dict) -> dict:
        """Handle list tables"""
        db_type = args.get("db_type", "sqlite")
        db_path = args.get("db_path", "")
        
        try:
            result = self.db_provider.list_tables(db_path, db_type)
            return result
        except Exception as e:
            return {"error": str(e)}
    
    # ============================================
    # COMMUNICATION HANDLERS
    # ============================================
    
    async def _handle_send_email(self, args: dict) -> dict:
        """Handle send email"""
        to = args.get("to", "")
        subject = args.get("subject", "")
        body = args.get("body", "")
        require_confirmation = args.get("require_confirmation", True)
        
        try:
            result = await self.comm_provider.send_email(
                to=to,
                subject=subject,
                body=body,
                require_confirmation=require_confirmation
            )
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_send_telegram(self, args: dict) -> dict:
        """Handle send telegram"""
        chat_id = args.get("chat_id", "")
        message = args.get("message", "")
        require_confirmation = args.get("require_confirmation", True)
        
        try:
            result = await self.comm_provider.send_telegram(
                chat_id=chat_id,
                message=message,
                require_confirmation=require_confirmation
            )
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_send_whatsapp(self, args: dict) -> dict:
        """Handle send whatsapp"""
        to = args.get("to", "")
        message = args.get("message", "")
        require_confirmation = args.get("require_confirmation", True)
        
        try:
            result = await self.comm_provider.send_whatsapp(
                to=to,
                message=message,
                require_confirmation=require_confirmation
            )
            return result
        except Exception as e:
            return {"error": str(e)}
    
    # ============================================
    # SYSTEM COMMAND HANDLERS
    # ============================================
    
    async def _handle_execute_command(self, args: dict) -> dict:
        """Handle execute command"""
        command = args.get("command", "")
        cmd_args = args.get("args", [])
        working_dir = args.get("working_dir")
        require_confirmation = args.get("require_confirmation", True)
        
        try:
            result = await self.system_provider.execute_command(
                command=command,
                args=cmd_args,
                working_dir=working_dir,
                require_confirmation=require_confirmation
            )
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_run_python(self, args: dict) -> dict:
        """Handle run python code"""
        code = args.get("code", "")
        timeout = args.get("timeout", 30)
        
        try:
            result = await self.system_provider.run_python(code, timeout=timeout)
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_system_info(self, args: dict) -> dict:
        """Handle get system info"""
        try:
            result = self.system_provider.get_system_info()
            return result
        except Exception as e:
            return {"error": str(e)}
    
    # ============================================
    # MEDICAL RAG HANDLERS
    # ============================================
    
    async def _handle_search_pubmed(self, args: dict) -> dict:
        """Handle search pubmed"""
        query = args.get("query", "")
        max_results = args.get("max_results", 10)
        
        try:
            result = await self.medical_service.search_pubmed(query, max_results)
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_search_trials(self, args: dict) -> dict:
        """Handle search clinical trials"""
        condition = args.get("condition", "")
        intervention = args.get("intervention")
        status = args.get("status")
        
        try:
            result = await self.medical_service.search_clinical_trials(
                condition=condition,
                intervention=intervention,
                status=status
            )
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_lookup_drug(self, args: dict) -> dict:
        """Handle lookup drug"""
        drug_name = args.get("drug_name", "")
        
        try:
            result = await self.medical_service.lookup_drug(drug_name)
            return result
        except Exception as e:
            return {"error": str(e)}
    
    # ============================================
    # ACCOUNTING REGULATIONS HANDLERS
    # ============================================
    
    async def _handle_get_regulations(self, args: dict) -> dict:
        """Handle get accounting regulations"""
        jurisdiction = args.get("jurisdiction", "all")
        
        try:
            if jurisdiction == "all":
                regulations = get_all_regulations()
            else:
                regulations = get_regulations_by_jurisdiction(jurisdiction)
            
            # Return summary instead of full content
            summaries = []
            for reg in regulations:
                summaries.append({
                    "id": reg["id"],
                    "jurisdiction": reg["jurisdiction"],
                    "title": reg["title"],
                    "title_local": reg.get("title_local", ""),
                    "category": reg["category"],
                    "authority": reg["authority"],
                    "effective_date": reg["effective_date"]
                })
            
            return {
                "success": True,
                "count": len(summaries),
                "regulations": summaries
            }
        except Exception as e:
            return {"error": str(e)}
    
    async def _handle_ingest_regulations(self, args: dict) -> dict:
        """Handle ingest accounting regulations to RAG"""
        jurisdictions = args.get("jurisdictions")
        collection_name = args.get("collection_name", "accounting")
        
        try:
            result = await ingest_regulations_to_rag(
                collection_name=collection_name,
                jurisdictions=jurisdictions
            )
            return result
        except Exception as e:
            return {"error": str(e)}
    
    async def run(self):
        """Run the MCP server"""
        if stdio_server is None:
            raise RuntimeError(
                "stdio_server is unavailable; install the 'mcp' package that provides mcp.server.stdio "
                "or provide an alternative stdio server implementation."
            )
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options()
            )


async def main():
    """Main entry point for MCP server"""
    server = MCPAgentServer()
    await server.run()


if __name__ == "__main__":
    asyncio.run(main())
