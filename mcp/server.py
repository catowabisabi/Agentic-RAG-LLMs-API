"""
MCP Server

Model Context Protocol server implementation:
- Provides tools for agent interaction
- Exposes resources for RAG
- Handles prompts for agent system
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
    Prompt,
    PromptMessage,
    PromptArgument
)
from pydantic import AnyUrl

from agents.shared_services.agent_registry import AgentRegistry
from agents.shared_services.websocket_manager import WebSocketManager
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    TaskAssignment
)
from tools.retriever import DocumentRetriever
from config.config import Config

logger = logging.getLogger(__name__)


class MCPAgentServer:
    """
    MCP Server for the multi-agent system.
    
    Provides:
    - Tools for querying and managing agents
    - Resources for document retrieval
    - Prompts for common operations
    """
    
    def __init__(self):
        self.server = Server("agentic-rag-server")
        self.config = Config()
        self.registry = None
        self.ws_manager = None
        
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
                )
            ]
        
        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            """Handle tool calls"""
            try:
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
    
    async def run(self):
        """Run the MCP server"""
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
