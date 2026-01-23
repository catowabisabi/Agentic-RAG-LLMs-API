#!/usr/bin/env python3
"""
Main Entry Point for Multi-Agent RAG System

This module starts:
1. FastAPI server with WebSocket support
2. MCP server (optional)
3. Multi-agent system with all agents

Usage:
    python main.py                 # Start API server
    python main.py --mcp           # Start MCP server only
    python main.py --api --mcp     # Start both servers
"""

import sys
import os
import json
import asyncio
import logging
import argparse
import signal
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

import uvicorn

from config.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_agents():
    """Create and register all agents"""
    from agents.shared_services.agent_registry import AgentRegistry
    
    registry = AgentRegistry()
    
    # Import core agents
    from agents.core.manager_agent import ManagerAgent
    from agents.core.rag_agent import RAGAgent
    from agents.core.memory_agent import MemoryAgent
    from agents.core.notes_agent import NotesAgent
    from agents.core.validation_agent import ValidationAgent
    from agents.core.planning_agent import PlanningAgent
    from agents.core.thinking_agent import ThinkingAgent
    from agents.core.roles_agent import RolesAgent
    
    # Import auxiliary agents
    from agents.auxiliary.data_agent import DataAgent
    from agents.auxiliary.tool_agent import ToolAgent
    from agents.auxiliary.summarize_agent import SummarizeAgent
    from agents.auxiliary.translate_agent import TranslateAgent
    from agents.auxiliary.calculation_agent import CalculationAgent
    
    # Register core agents
    logger.info("Registering core agents...")
    registry.register_agent(ManagerAgent())
    registry.register_agent(RAGAgent())
    registry.register_agent(MemoryAgent())
    registry.register_agent(NotesAgent())
    registry.register_agent(ValidationAgent())
    registry.register_agent(PlanningAgent())
    registry.register_agent(ThinkingAgent())
    registry.register_agent(RolesAgent())
    
    # Register auxiliary agents
    logger.info("Registering auxiliary agents...")
    registry.register_agent(DataAgent())
    registry.register_agent(ToolAgent())
    registry.register_agent(SummarizeAgent())
    registry.register_agent(TranslateAgent())
    registry.register_agent(CalculationAgent())
    
    logger.info(f"Registered {len(registry.agents)} agents")
    
    return registry


async def start_agents(registry):
    """Start all registered agents"""
    logger.info("Starting all agents...")
    await registry.start_all_agents()
    logger.info("All agents started successfully")


async def stop_agents(registry):
    """Stop all agents"""
    logger.info("Stopping all agents...")
    await registry.stop_all_agents()
    logger.info("All agents stopped")


def run_api_server(config: Config):
    """Run the FastAPI server"""
    logger.info(f"Starting API server on {config.API_HOST}:{config.API_PORT}")
    
    # Import the app
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    uvicorn.run(
        "fast_api.app:app",
        host=config.API_HOST,
        port=config.API_PORT,
        reload=config.API_RELOAD,
        log_level=config.LOG_LEVEL.lower()
    )


async def run_mcp_server():
    """Run the MCP server"""
    logger.info("Starting MCP server...")
    
    from mcp.server import MCPAgentServer
    
    server = MCPAgentServer()
    await server.run()


async def run_both_servers(config: Config):
    """Run both API and MCP servers concurrently"""
    logger.info("Starting both API and MCP servers...")
    
    # Create tasks
    api_task = asyncio.create_task(
        asyncio.to_thread(run_api_server, config)
    )
    
    mcp_task = asyncio.create_task(run_mcp_server())
    
    # Wait for both
    try:
        await asyncio.gather(api_task, mcp_task)
    except asyncio.CancelledError:
        logger.info("Servers shutting down...")


def run_interactive_mode(config: Config):
    """Run in interactive CLI mode (legacy support)"""
    from agents.rag_agent import create_rag_agent
    from tools.retriever import DocumentRetriever
    
    print("🤖 Initializing RAG Agent...")
    
    try:
        agent = create_rag_agent()
        retriever = DocumentRetriever()
        
        print("🚀 RAG Agent ready!")
        print("\n" + "="*60)
        print("🧠 LangGraph RAG Demo - Interactive Chat")
        print("="*60)
        print("Type 'quit' to exit, 'clear' to clear history")
        print("="*60 + "\n")
        
        chat_history = []
        
        while True:
            try:
                user_input = input("🧑 You: ").strip()
                
                if not user_input:
                    continue
                    
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                    
                if user_input.lower() == 'clear':
                    chat_history = []
                    print("🗑️  Chat history cleared.")
                    continue
                
                print("\n🤔 Thinking...")
                
                result = agent.invoke({
                    "query": user_input,
                    "chat_history": chat_history.copy()
                })
                
                print("\n🤖 Assistant:")
                print("-" * 50)
                print(result["answer"])
                print("-" * 50 + "\n")
                
                chat_history.append({
                    "human": user_input,
                    "assistant": result["answer"]
                })
                
                if len(chat_history) > config.MEMORY_WINDOW:
                    chat_history = chat_history[-config.MEMORY_WINDOW:]
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
                
    except Exception as e:
        logger.error(f"Error in interactive mode: {e}")
        sys.exit(1)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Multi-Agent RAG System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                 # Start API server (default)
    python main.py --api           # Start API server only
    python main.py --mcp           # Start MCP server only
    python main.py --api --mcp     # Start both servers
    python main.py --interactive   # Run interactive CLI mode
    python main.py --query "Hello" # Single query mode
        """
    )
    
    parser.add_argument('--api', action='store_true',
                        help='Start the API server')
    parser.add_argument('--mcp', action='store_true',
                        help='Start the MCP server')
    parser.add_argument('--interactive', '-i', action='store_true',
                        help='Run in interactive CLI mode')
    parser.add_argument('--query', '-q', type=str,
                        help='Run a single query')
    parser.add_argument('--json', action='store_true',
                        help='Output results in JSON format')
    parser.add_argument('--host', type=str, default=None,
                        help='Override API host')
    parser.add_argument('--port', type=int, default=None,
                        help='Override API port')
    parser.add_argument('--log-level', type=str, default=None,
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Set log level')
    
    args = parser.parse_args()
    
    # Load configuration
    config = Config()
    
    # Override config with command line args
    if args.host:
        config.API_HOST = args.host
    if args.port:
        config.API_PORT = args.port
    if args.log_level:
        config.LOG_LEVEL = args.log_level
        logging.getLogger().setLevel(args.log_level)
    
    # Check for API key
    if not config.OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not set. Please set it in .env file.")
        sys.exit(1)
    
    # Determine run mode
    if args.query:
        # Single query mode
        from agents.rag_agent import create_rag_agent
        
        try:
            agent = create_rag_agent()
            result = agent.invoke({
                "query": args.query,
                "chat_history": []
            })
            
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(f"Query: {args.query}")
                print(f"Answer: {result.get('answer', 'No answer')}")
                
        except Exception as e:
            if args.json:
                print(json.dumps({"error": str(e)}))
            else:
                print(f"Error: {e}")
            sys.exit(1)
            
    elif args.interactive:
        # Interactive CLI mode
        run_interactive_mode(config)
        
    elif args.mcp and not args.api:
        # MCP server only
        asyncio.run(run_mcp_server())
        
    elif args.api and args.mcp:
        # Both servers
        asyncio.run(run_both_servers(config))
        
    else:
        # Default: API server only
        run_api_server(config)


if __name__ == "__main__":
    main()