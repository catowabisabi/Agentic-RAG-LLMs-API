# Agentic RAG Multi-Agent System - Complete Documentation

## Overview

This is a sophisticated Multi-Agent RAG (Retrieval-Augmented Generation) system built with FastAPI, LangGraph, and ChromaDB. It features a Next.js web interface for managing agents, vector databases, and real-time chat.

## System Architecture

### Core Components

1. **FastAPI Backend** (Port 1130)
   - REST API endpoints for all operations
   - WebSocket support for real-time communication
   - CORS enabled for cross-origin requests

2. **Next.js UI** (Port 1131)
   - Modern web interface built with React and Tailwind CSS
   - Real-time agent monitoring
   - Vector database management
   - Chat interface with persistent sessions

3. **Multi-Agent System**
   - 13 specialized agents working collaboratively
   - Concurrency control (max 5 simultaneous agents)
   - Message-based inter-agent communication

4. **Vector Database**
   - ChromaDB for vector storage
   - Multiple collections/databases support
   - Semantic search capabilities

## Agents

### Core Agents

1. **ManagerAgent** - Orchestrates all other agents, task distribution
2. **RAGAgent** - Handles document retrieval and context injection
3. **MemoryAgent** - Manages conversation history and context
4. **NotesAgent** - Note-taking and information organization
5. **ValidationAgent** - Validates responses and data
6. **PlanningAgent** - Creates execution plans for complex tasks
7. **ThinkingAgent** - Deep reasoning and analysis
8. **RolesAgent** - Monitors and assigns agent roles

### Auxiliary Agents

9. **DataAgent** - Data processing and transformation
10. **ToolAgent** - Tool execution (calculator, JSON parser, text analyzer)
11. **SummarizeAgent** - Text summarization
12. **TranslateAgent** - Language translation
13. **CalculationAgent** - Mathematical computations

## API Endpoints

### Health & Status
- `GET /` - Root endpoint, system info
- `GET /health` - Health check

### Agents (`/agents`)
- `GET /agents/` - List all agents
- `GET /agents/health` - System health status
- `GET /agents/{name}` - Get specific agent details
- `GET /agents/{name}/activity` - Get agent message history
- `GET /agents/activity/all` - Get all agents activity
- `POST /agents/task` - Send task to agent
- `POST /agents/interrupt` - Interrupt agent(s)
- `POST /agents/{name}/start` - Start agent
- `POST /agents/{name}/stop` - Stop agent
- `POST /agents/{name}/restart` - Restart agent
- `POST /agents/start-all` - Start all agents
- `POST /agents/stop-all` - Stop all agents

### Chat (`/chat`)
- `POST /chat/message` - Send chat message
- `GET /chat/conversation/{id}` - Get conversation
- `GET /chat/conversations` - List conversations

### RAG (`/rag`)
- `POST /rag/query` - Query documents
- `POST /rag/document` - Add document
- `POST /rag/upload` - Upload document file
- `GET /rag/collections` - List collections
- `GET /rag/collections/{name}` - Collection info
- `DELETE /rag/collections/{name}` - Delete collection
- `GET /rag/databases` - List databases
- `POST /rag/databases` - Create database
- `GET /rag/databases/{name}` - Database info
- `DELETE /rag/databases/{name}` - Delete database
- `GET /rag/databases/{name}/documents` - List documents
- `DELETE /rag/databases/{name}/documents/{id}` - Delete document
- `POST /rag/databases/insert` - Insert document
- `POST /rag/databases/query` - Query database
- `POST /rag/databases/query-all` - Query all databases

### WebSocket (`/ws`)
- `WS /ws/{client_id}` - WebSocket connection for real-time updates

## Running the System

### Prerequisites
- Python 3.10+
- Node.js 18+
- pip packages: fastapi, uvicorn, langchain, chromadb, openai

### Quick Start

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install UI dependencies
cd ui && npm install && cd ..

# Set environment variables
# Edit .env file with your API keys

# Run with UI
python main.py --ui
```

### Environment Variables

```env
OPENAI_API_KEY=your_openai_key
API_PORT=1130
UI_PORT=1131
UI_ENABLED=true
CHROMA_DB_PATH=./rag-database/vectordb
```

### Docker

```bash
docker-compose -f docker/docker-compose.yml up
```

## UI Features

### Dashboard
- System health status
- Agent count and status
- Quick actions

### Agents Page
- List all agents with status
- Send tasks to specific agents
- View Chain of Thought (COT) - real-time activity log
- Agent message history
- Interrupt controls

### RAG Page
- **Databases Tab**: Create, view, delete vector databases
- **Documents Tab**: Browse documents, view content, delete
- **Query Tab**: Semantic search across documents
- **Add Document Tab**: Insert new documents with optional summarization

### Chat Page
- Conversational interface
- Persistent sessions (localStorage)
- Shows involved agents
- Clear chat functionality

### Settings Page
- API status
- Configuration display
- Connection testing

## Login Credentials

- **Username**: guest
- **Password**: beourguest

## Project Structure

```
Agentic-RAG-LLMs-API/
├── main.py                 # Entry point with --ui flag
├── config/
│   └── config.py          # Configuration class
├── fast_api/
│   ├── app.py             # FastAPI app setup
│   └── routers/
│       ├── agent_router.py
│       ├── chat_router.py
│       ├── rag_router.py
│       └── websocket_router.py
├── agents/
│   ├── core/              # Core agents
│   ├── auxiliary/         # Auxiliary agents
│   └── shared_services/   # Shared utilities
│       ├── agent_registry.py
│       ├── base_agent.py
│       ├── message_protocol.py
│       └── websocket_manager.py
├── tools/
│   ├── retriever.py       # Document retrieval
│   └── memory.py          # Memory tools
├── services/
│   └── vectordb_manager.py # Vector DB management
├── documents/
│   └── load_documents.py  # Document loader
├── ui/                    # Next.js frontend
│   ├── app/              # Pages
│   ├── components/       # React components
│   └── lib/              # API utilities
└── docker/               # Docker configuration
```

## Message Protocol

Agents communicate using structured messages:

```python
class AgentMessage:
    type: MessageType      # TASK_ASSIGNED, AGENT_COMPLETED, etc.
    source_agent: str      # Sender agent name
    target_agent: str      # Receiver agent name
    content: Dict          # Message payload
    timestamp: str         # ISO format timestamp
    priority: int          # 1-10, higher = more urgent
```

### Message Types
- `TASK_ASSIGNED` - New task for agent
- `AGENT_STARTED` - Agent began processing
- `AGENT_COMPLETED` - Task finished
- `STATUS_UPDATE` - Status change
- `ERROR` - Error occurred
- `INTERRUPT` - Stop processing
- `RAG_RESULT` - RAG query result

## Concurrency Model

- Maximum 5 agents can work simultaneously
- Additional tasks are queued
- Priority-based scheduling
- Graceful interruption support

## Best Practices

1. **Document Management**
   - Use meaningful database names
   - Add metadata to documents
   - Use summarization for large documents

2. **Agent Interaction**
   - Monitor activity log for debugging
   - Use appropriate task types
   - Set priorities for urgent tasks

3. **Performance**
   - Keep vector databases organized
   - Delete unused collections
   - Monitor agent queue status

## Troubleshooting

### Common Issues

1. **Port already in use**
   ```bash
   # Kill process on port
   netstat -ano | findstr :1130
   taskkill /PID <pid> /F
   ```

2. **Import errors**
   - Ensure all dependencies installed
   - Check Python environment

3. **API connection failed**
   - Verify server is running
   - Check CORS settings
   - Confirm port configuration

4. **Agents not responding**
   - Check agent status in dashboard
   - Restart agents if needed
   - Review activity log for errors
