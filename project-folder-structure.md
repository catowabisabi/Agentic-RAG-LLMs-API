# Agentic RAG LLMs API - Project Structure

## Overview

This is a multi-agent RAG (Retrieval-Augmented Generation) system built with:
- **LangGraph** for agent orchestration
- **LangChain** for LLM integration
- **FastAPI + WebSocket** for real-time communication
- **ChromaDB** for vector storage
- **MCP** (Model Context Protocol) for tool integration

## Directory Structure

```
Agentic-RAG-LLMs-API/
├── main.py                          # Main entry point (starts API + MCP)
├── .env.example                     # Environment configuration template
│
├── agents/                          # Multi-agent system
│   ├── __init__.py                 # Package exports
│   │
│   ├── shared_services/            # Shared agent infrastructure
│   │   ├── __init__.py
│   │   ├── message_protocol.py     # Message types and protocols
│   │   ├── websocket_manager.py    # WebSocket connection management
│   │   ├── base_agent.py           # Abstract base agent class
│   │   └── agent_registry.py       # Agent registration and lifecycle
│   │
│   ├── core/                       # Core agents (one class per file)
│   │   ├── __init__.py
│   │   ├── manager_agent.py        # Central coordinator, only interrupt authority
│   │   ├── rag_agent.py            # RAG decisions and document retrieval
│   │   ├── memory_agent.py         # Short-term and long-term memory
│   │   ├── notes_agent.py          # Note creation and organization
│   │   ├── validation_agent.py     # Data validation, retry on errors
│   │   ├── planning_agent.py       # Task planning (streams to frontend)
│   │   ├── thinking_agent.py       # Deep reasoning (streams to frontend)
│   │   └── roles_agent.py          # Role monitoring and corrections
│   │
│   ├── auxiliary/                  # Auxiliary agents
│   │   ├── __init__.py
│   │   ├── data_agent.py           # Data processing and transformation
│   │   ├── tool_agent.py           # External tool execution
│   │   ├── summarize_agent.py      # Content summarization
│   │   ├── translate_agent.py      # Language translation
│   │   └── calculation_agent.py    # Mathematical calculations
│   │
│   ├── nodes.py                    # LangGraph node definitions (legacy)
│   └── rag_agent.py                # Original RAG agent (legacy)
│
├── fast_api/                       # FastAPI application
│   ├── __init__.py
│   ├── app.py                      # Main FastAPI application
│   └── routers/
│       ├── __init__.py
│       ├── websocket_router.py     # WebSocket endpoints
│       ├── agent_router.py         # Agent management endpoints
│       ├── rag_router.py           # RAG query endpoints
│       └── chat_router.py          # Chat interface endpoints
│
├── mcp/                            # Model Context Protocol
│   ├── __init__.py
│   ├── server.py                   # MCP server implementation
│   ├── providers/                  # MCP providers
│   └── services/                   # MCP services
│
├── config/
│   └── config.py                   # Centralized configuration
│
├── tools/
│   ├── retriever.py                # Document retrieval from vector DB
│   └── memory.py                   # Memory management utilities
│
├── documents/
│   └── load_documents.py           # Document loading and embedding
│
├── rag-database/
│   └── vectordb/                   # ChromaDB storage
│       ├── index.json
│       ├── chemistry/
│       ├── market-data/
│       ├── medicine/
│       ├── personal-finance/
│       ├── pinescript/
│       ├── python-tradebot/
│       ├── short-trading/
│       └── solidworks-api/
│
├── docker/
│   ├── Dockerfile                  # Main application Dockerfile
│   ├── Dockerfile.mcp              # MCP server Dockerfile
│   └── docker-compose.yml          # Docker Compose configuration
│
├── Scripts/
│   ├── run_api.bat
│   ├── run_client.bat
│   └── setup.bat
│
└── app_docs/
    ├── PLANNING.md
    ├── README.md
    ├── requirements.txt
    ├── requirements2.txt
    └── Agentic-Rag-Examples/       # 17 notebook examples
        ├── 01_reflection.ipynb
        ├── 02_tool_use.ipynb
        ├── 03_ReAct.ipynb
        ├── 04_planning.ipynb
        ├── 05_multi_agent.ipynb
        ├── 06_PEV.ipynb
        ├── 07_blackboard.ipynb
        ├── 08_episodic_with_semantic.ipynb
        ├── 09_tree_of_thoughts.ipynb
        ├── 10_mental_loop.ipynb
        ├── 11_meta_controller.ipynb
        ├── 12_graph.ipynb
        ├── 13_ensemble.ipynb
        ├── 14_dry_run.ipynb
        ├── 15_RLHF.ipynb
        ├── 16_cellular_automata.ipynb
        └── 17_reflexive_metacognitive.ipynb
```

## Agent Architecture

### Communication Flow
```
Frontend (WebSocket) ←→ API Server ←→ Manager Agent ←→ Other Agents
                                            ↓
                                      Roles Agent (monitors all)
```

### Agent Hierarchy

1. **Manager Agent** (Top Level)
   - Central coordinator for all tasks
   - **Only agent with interrupt authority**
   - Routes tasks to appropriate agents
   - Monitors error counts per agent

2. **Roles Agent** (Under Manager)
   - Monitors all agent behavior
   - Sends role corrections when agents make mistakes
   - Reports persistent issues to manager

3. **Core Agents**
   - RAG Agent: Checks if RAG is needed, retrieves documents
   - Memory Agent: Manages short-term and long-term memory
   - Notes Agent: Creates structured notes, sends to Memory Agent
   - Validation Agent: Validates data, requests retry on errors
   - Planning Agent: Creates execution plans (streams to frontend)
   - Thinking Agent: Deep reasoning (streams to frontend)

4. **Auxiliary Agents**
   - Data Agent: Data processing and transformation
   - Tool Agent: External tool execution
   - Summarize Agent: Content summarization
   - Translate Agent: Language translation
   - Calculation Agent: Mathematical calculations

### Key Features

- **WebSocket Communication**: All agents communicate via WebSocket
- **Interrupt Capability**: Manager can interrupt any agent
- **RAG Check**: Agents check RAG before starting work
- **Streaming**: Planning and Thinking agents stream to frontend
- **Validation with Retry**: Validation agent requests retry on errors
- **Note to Memory Flow**: Notes agent sends to Memory agent

## API Endpoints

### REST Endpoints
- `GET /` - Root endpoint
- `GET /health` - System health check
- `POST /query` - Process a query

### Agent Endpoints (`/agents`)
- `GET /agents/` - List all agents
- `GET /agents/health` - System health
- `GET /agents/{name}` - Get agent info
- `POST /agents/task` - Send task to agent
- `POST /agents/interrupt` - Interrupt agent(s)
- `POST /agents/{name}/start|stop|restart` - Agent lifecycle
- `POST /agents/start-all|stop-all` - All agents

### RAG Endpoints (`/rag`)
- `POST /rag/query` - Query documents
- `POST /rag/document` - Add document
- `POST /rag/upload` - Upload file
- `GET /rag/collections` - List collections
- `GET|DELETE /rag/collections/{name}` - Collection operations

### Chat Endpoints (`/chat`)
- `POST /chat/message` - Send message
- `GET /chat/conversations` - List conversations
- `GET|DELETE /chat/conversations/{id}` - Conversation operations

### WebSocket Endpoints
- `/ws` - Main WebSocket for frontend
- `/ws/agent/{name}` - Agent-specific updates
- `/ws/stream` - Streaming agent outputs

## Usage

### Start the Server

```bash
# API server only (default)
python main.py

# API + MCP servers
python main.py --api --mcp

# Interactive mode (legacy)
python main.py --interactive

# Single query
python main.py --query "Your question here"
```

### Docker

```bash
# Build and run
cd docker
docker-compose up -d

# With standalone ChromaDB
docker-compose --profile standalone-db up -d

# Production mode (with Redis)
docker-compose --profile production up -d
```

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
OPENAI_API_KEY=your_key_here
DEFAULT_MODEL=gpt-4o-mini
API_PORT=8000
MCP_ENABLED=true
```

## MCP Tools

The MCP server provides these tools:
- `query_agents` - Send query to agent system
- `list_agents` - List all agents
- `get_agent_status` - Get agent status
- `query_rag` - Query RAG system
- `add_document` - Add document to RAG
- `interrupt_agent` - Interrupt an agent
- `create_plan` - Create execution plan
- `deep_think` - Perform deep reasoning
- `summarize` - Summarize content
- `translate` - Translate text
- `calculate` - Mathematical calculations
