"""
Main API Application

FastAPI application that provides:
- REST API endpoints
- WebSocket connections
- Agent system integration
"""

import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.shared_services.agent_registry import AgentRegistry
from agents.shared_services.websocket_manager import WebSocketManager

# Import routers
from fast_api.routers.websocket_router import router as websocket_router
from fast_api.routers.agent_router import router as agent_router
from fast_api.routers.rag_router import router as rag_router
from fast_api.routers.chat_router import router as chat_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_agents():
    """Create and register all agents"""
    registry = AgentRegistry()
    
    # Import agents
    from agents.core.manager_agent import ManagerAgent
    from agents.core.rag_agent import RAGAgent
    from agents.core.memory_agent import MemoryAgent
    from agents.core.notes_agent import NotesAgent
    from agents.core.validation_agent import ValidationAgent
    from agents.core.planning_agent import PlanningAgent
    from agents.core.thinking_agent import ThinkingAgent
    from agents.core.roles_agent import RolesAgent
    
    from agents.auxiliary.data_agent import DataAgent
    from agents.auxiliary.tool_agent import ToolAgent
    from agents.auxiliary.summarize_agent import SummarizeAgent
    from agents.auxiliary.translate_agent import TranslateAgent
    from agents.auxiliary.calculation_agent import CalculationAgent
    
    # Register core agents
    registry.register_agent(ManagerAgent())
    registry.register_agent(RAGAgent())
    registry.register_agent(MemoryAgent())
    registry.register_agent(NotesAgent())
    registry.register_agent(ValidationAgent())
    registry.register_agent(PlanningAgent())
    registry.register_agent(ThinkingAgent())
    registry.register_agent(RolesAgent())
    
    # Register auxiliary agents
    registry.register_agent(DataAgent())
    registry.register_agent(ToolAgent())
    registry.register_agent(SummarizeAgent())
    registry.register_agent(TranslateAgent())
    registry.register_agent(CalculationAgent())
    
    logger.info(f"Registered {len(registry.agents)} agents")
    
    return registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting API server...")
    
    # Create and start agents
    registry = create_agents()
    await registry.start_all_agents()
    
    logger.info("All agents started")
    
    yield
    
    # Shutdown
    logger.info("Shutting down API server...")
    await registry.stop_all_agents()
    logger.info("All agents stopped")


# Create FastAPI app
app = FastAPI(
    title="Agentic RAG API",
    description="Multi-agent RAG system with WebSocket support",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(websocket_router)
app.include_router(agent_router)
app.include_router(rag_router)
app.include_router(chat_router)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Agentic RAG API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    registry = AgentRegistry()
    
    return {
        "status": "healthy",
        "agents": registry.get_system_health()
    }


class QueryRequest(BaseModel):
    """Simple query request"""
    query: str
    context: Dict[str, Any] = {}


@app.post("/query")
async def process_query(request: QueryRequest):
    """Process a query through the agent system"""
    registry = AgentRegistry()
    ws_manager = WebSocketManager()
    
    manager = registry.get_agent("manager_agent")
    
    if not manager:
        raise HTTPException(status_code=500, detail="Manager agent not available")
    
    # Process query
    from agents.shared_services.message_protocol import TaskAssignment, AgentMessage, MessageType
    from datetime import datetime
    
    task = TaskAssignment(
        task_id=f"query-{datetime.now().timestamp()}",
        task_type="process_query",
        input_data={"query": request.query, "context": request.context},
        context=request.query,
        priority=1
    )
    
    message = AgentMessage(
        type=MessageType.TASK_ASSIGNED,
        source_agent="api",
        target_agent="manager_agent",
        content=task.model_dump(),
        priority=1
    )
    
    await ws_manager.send_to_agent(message)
    
    return {
        "success": True,
        "task_id": task.task_id,
        "message": "Query submitted to agent system"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
