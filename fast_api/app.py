"""
Main API Application

FastAPI application that provides:
- REST API endpoints
- WebSocket connections (including streaming chat)
- Agent system integration
- Authentication & Rate Limiting
- Memory & Metacognition integration
"""

import logging
import asyncio
import os
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
from fast_api.routers.session_router import router as session_router
from fast_api.routers.memory_router import router as memory_router
from fast_api.routers.intent_router import router as intent_router
from fast_api.routers.ws_chat_router import router as ws_chat_router
from fast_api.routers.sw_skill_router import router as sw_skill_router
from fast_api.routers.config_router import router as config_router

# Import middleware
from fast_api.middleware.auth import (
    AuthMiddleware,
    get_api_key_manager,
    get_rate_limiter,
    get_request_logger
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def create_agents():
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
    from agents.core.casual_chat_agent import CasualChatAgent
    from agents.core.entry_classifier import EntryClassifier
    
    from agents.auxiliary.data_agent import DataAgent
    from agents.auxiliary.tool_agent import ToolAgent
    from agents.auxiliary.summarize_agent import SummarizeAgent
    from agents.auxiliary.translate_agent import TranslateAgent
    from agents.auxiliary.calculation_agent import CalculationAgent
    from agents.auxiliary.memory_capture_agent import MemoryCaptureAgent
    from agents.auxiliary.sw_agent import SWAgent
    
    # Register core agents
    await registry.register_agent(EntryClassifier())  # First-line classifier
    await registry.register_agent(ManagerAgent())
    await registry.register_agent(RAGAgent())
    await registry.register_agent(MemoryAgent())
    await registry.register_agent(NotesAgent())
    await registry.register_agent(ValidationAgent())
    await registry.register_agent(PlanningAgent())
    await registry.register_agent(ThinkingAgent())
    await registry.register_agent(RolesAgent())
    await registry.register_agent(CasualChatAgent())
    
    # Register auxiliary agents
    await registry.register_agent(DataAgent())
    await registry.register_agent(ToolAgent())
    await registry.register_agent(SummarizeAgent())
    await registry.register_agent(TranslateAgent())
    await registry.register_agent(CalculationAgent())
    await registry.register_agent(MemoryCaptureAgent())
    await registry.register_agent(SWAgent())
    
    logger.info(f"Registered {len(registry._agents)} agents")
    
    return registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    logger.info("Starting API server...")
    
    # Create and start agents
    registry = await create_agents()
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
    description="""
Multi-agent RAG system with:
- ReAct Loop (Reason + Act) for iterative reasoning
- WebSocket streaming for real-time updates
- Memory integration for personalized responses
- Metacognition for self-evaluation
- Rate limiting and API key authentication
    """,
    version="2.0.0",
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

# Add Auth middleware (optional - can be disabled for development)
ENABLE_AUTH = os.environ.get("ENABLE_AUTH", "false").lower() == "true"
if ENABLE_AUTH:
    app.add_middleware(
        AuthMiddleware,
        api_key_manager=get_api_key_manager(),
        rate_limiter=get_rate_limiter(),
        request_logger=get_request_logger()
    )
    logger.info("Authentication middleware enabled")
else:
    logger.info("Authentication middleware disabled (set ENABLE_AUTH=true to enable)")

# Include routers
app.include_router(websocket_router)
app.include_router(ws_chat_router)  # New streaming chat WebSocket
app.include_router(agent_router)
app.include_router(rag_router)
app.include_router(chat_router)
app.include_router(session_router)
app.include_router(memory_router)
app.include_router(intent_router)
app.include_router(sw_skill_router)  # SolidWorks Skill DB (structured 689MB)
app.include_router(config_router)  # Configuration management


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Agentic RAG API",
        "version": "2.0.0",
        "status": "running",
        "features": {
            "react_loop": "Iterative reasoning with Think->Act->Observe",
            "websocket_streaming": "Real-time updates via /ws/chat",
            "memory": "Episodic and working memory integration",
            "metacognition": "Self-evaluation and strategy adaptation",
            "authentication": ENABLE_AUTH
        },
        "endpoints": {
            "chat": "/chat/message",
            "ws_chat": "/ws/chat",
            "rag": "/rag/query",
            "docs": "/docs"
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint - includes Redis & Celery status"""
    registry = AgentRegistry()
    
    health = {
        "status": "healthy",
        "agents": registry.get_system_health(),
        "auth_enabled": ENABLE_AUTH
    }
    
    # Redis health check
    try:
        from services.redis_service import get_redis_service
        redis = get_redis_service()
        health["redis"] = await redis.health_check()
    except Exception as e:
        health["redis"] = {"status": "error", "error": str(e)}
    
    # Celery health check
    try:
        from services.celery_service import get_celery_service
        celery = get_celery_service()
        health["celery"] = celery.health_check()
    except Exception as e:
        health["celery"] = {"status": "error", "error": str(e)}
    
    return health


@app.get("/api/stats")
async def api_stats():
    """Get API usage statistics"""
    request_logger = get_request_logger()
    return {
        "stats": request_logger.get_stats(),
        "recent_requests": len(request_logger.logs)
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
    uvicorn.run(app, host="0.0.0.0", port=1130)
