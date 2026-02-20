#!/usr/bin/env python3
"""
Main Entry Point for Multi-Agent RAG System

This module starts:
1. FastAPI server with WebSocket support
2. MCP server (optional)
3. Multi-agent system with all agents
4. Next.js UI webapp (optional)

Usage:
    python main.py                 # Start API server only
    python main.py --ui            # Start API server and UI
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
import subprocess
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor

# Fix PyTorch OpenMP conflict on Windows
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import uvicorn

from config.config import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_agents():
    """
    Create and register all agents.

    NOTE: Delegates to agents.agent_factory to avoid duplication with
    fast_api/app.py.  Add new agents ONLY in agents/agent_factory.py.
    """
    # Ensure DI container is bootstrapped before agents are created
    try:
        from services.container import bootstrap as _bootstrap_container
        _bootstrap_container()
    except Exception as _err:
        logger.warning(f"DI container bootstrap warning: {_err}")

    from agents.agent_factory import create_agents as _factory_create
    return await _factory_create()


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


def run_ui_server(config: Config):
    """Run the Next.js UI server"""
    ui_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
    
    if not os.path.exists(ui_path):
        logger.error(f"UI directory not found: {ui_path}")
        return
    
    logger.info(f"Starting UI server on port {config.UI_PORT}")
    
    # Check if node_modules exists
    node_modules = os.path.join(ui_path, "node_modules")
    if not os.path.exists(node_modules):
        logger.info("Installing UI dependencies...")
        subprocess.run(["npm", "install"], cwd=ui_path, shell=True)
    
    # Start the Next.js dev server
    subprocess.run(
        ["npm", "run", "dev"],
        cwd=ui_path,
        shell=True,
        env={**os.environ, "NEXT_PUBLIC_API_URL": f"http://localhost:{config.API_PORT}"}
    )


async def run_api_and_ui(config: Config):
    """Run both API and UI servers concurrently"""
    logger.info("Starting API and UI servers...")
    
    loop = asyncio.get_event_loop()
    
    # Run API server in a thread
    api_task = loop.run_in_executor(None, run_api_server, config)
    
    # Wait a moment for API to start
    await asyncio.sleep(2)
    
    # Run UI server in a thread
    ui_task = loop.run_in_executor(None, run_ui_server, config)
    
    try:
        await asyncio.gather(api_task, ui_task)
    except asyncio.CancelledError:
        logger.info("Servers shutting down...")


async def run_mcp_server():
    """Run the MCP server"""
    logger.info("Starting MCP server...")
    
    try:
        from mcp.server import MCPAgentServer
        server = MCPAgentServer()
        await server.run()
    except ImportError as e:
        logger.warning(f"MCP module not available: {e}. Skipping MCP server.")
    except Exception as e:
        logger.error(f"MCP server error: {e}")


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
    from agents.legacy.rag_agent import create_rag_agent
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
    python main.py --ui            # Start API server with UI
    python main.py --api           # Start API server only
    python main.py --mcp           # Start MCP server only
    python main.py --api --mcp     # Start both servers
    python main.py --interactive   # Run interactive CLI mode
    python main.py --query "Hello" # Single query mode
        """
    )
    
    parser.add_argument('--api', action='store_true',
                        help='Start the API server')
    parser.add_argument('--ui', action='store_true',
                        help='Start the API server with UI webapp')
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
    
    # Override config via environment variables so uvicorn reimport picks them up
    if args.host:
        os.environ["API_HOST"] = args.host
        config.API_HOST = args.host
    if args.port:
        os.environ["API_PORT"] = str(args.port)
        config.API_PORT = args.port
    if args.log_level:
        os.environ["LOG_LEVEL"] = args.log_level
        config.LOG_LEVEL = args.log_level
        logging.getLogger().setLevel(args.log_level)
    
    # Check for API key
    if not config.OPENAI_API_KEY:
        logger.warning("⚠️  OPENAI_API_KEY not set. The server will start but LLM features will fail.")
        logger.warning("⚠️  Set OPENAI_API_KEY in config/.env or via Settings in the UI.")
    
    # Determine run mode
    if args.query:
        # Single query mode
        from agents.legacy.rag_agent import create_rag_agent
        
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
        
    elif args.mcp and not args.api and not args.ui:
        # MCP server only
        asyncio.run(run_mcp_server())
        
    elif args.api and args.mcp:
        # Both API and MCP servers
        asyncio.run(run_both_servers(config))
    
    elif args.ui:
        # API server with UI
        print("="*60)
        print("🚀 Starting Agentic RAG System with UI")
        print("="*60)
        print(f"📡 API Server: http://localhost:{config.API_PORT}")
        print(f"🌐 UI Server:  http://localhost:{config.UI_PORT}")
        print("="*60)
        asyncio.run(run_api_and_ui(config))
        
    else:
        # Default: API server only
        run_api_server(config)


if __name__ == "__main__":
    main()