"""
Load project documentation into RAG vector database.
Run this script after the API is running to populate the documentation database.
"""

import requests
import os

API_URL = "http://localhost:1130"

# Documentation content to load
DOCS = [
    {
        "title": "System Overview",
        "category": "documentation",
        "content": """
# Agentic RAG Multi-Agent System

A sophisticated Multi-Agent RAG (Retrieval-Augmented Generation) system built with FastAPI, LangGraph, and ChromaDB.

## Core Components
1. FastAPI Backend (Port 1130) - REST API endpoints for all operations
2. Next.js UI (Port 1131) - Modern web interface with React and Tailwind CSS
3. Multi-Agent System - 13 specialized agents working collaboratively
4. Vector Database - ChromaDB for vector storage with multiple collections

## Key Features
- Real-time agent monitoring via WebSocket
- Vector database management with insert/delete capabilities
- Chat interface with persistent sessions
- Chain of Thought (COT) visualization
- Concurrency control (max 5 simultaneous agents)
"""
    },
    {
        "title": "Agents Guide",
        "category": "documentation",
        "content": """
# Multi-Agent System Guide

## Core Agents
1. ManagerAgent - Orchestrates all other agents, handles task distribution
2. RAGAgent - Handles document retrieval and context injection from vector databases
3. MemoryAgent - Manages conversation history and maintains context
4. NotesAgent - Note-taking and information organization
5. ValidationAgent - Validates responses and data quality
6. PlanningAgent - Creates execution plans for complex multi-step tasks
7. ThinkingAgent - Deep reasoning, analysis, and problem solving
8. RolesAgent - Monitors and assigns appropriate agent roles

## Auxiliary Agents
9. DataAgent - Data processing and transformation operations
10. ToolAgent - Executes tools like calculator, JSON parser, text analyzer
11. SummarizeAgent - Text summarization for long documents
12. TranslateAgent - Language translation between different languages
13. CalculationAgent - Mathematical computations and numeric operations

## Agent Communication
Agents communicate using structured messages with type, source, target, content, timestamp, and priority.
Maximum 5 agents can work simultaneously, with additional tasks queued.
"""
    },
    {
        "title": "API Reference",
        "category": "documentation", 
        "content": """
# API Endpoints Reference

## Agent Endpoints (/agents)
- GET /agents/ - List all registered agents
- GET /agents/health - Get system health status
- GET /agents/{name} - Get specific agent details
- GET /agents/{name}/activity - Get agent message history for debugging
- GET /agents/activity/all - Get activity from all agents
- POST /agents/task - Send task to specific agent
- POST /agents/interrupt - Interrupt agent or all agents
- POST /agents/{name}/start - Start specific agent
- POST /agents/{name}/stop - Stop specific agent
- POST /agents/start-all - Start all registered agents
- POST /agents/stop-all - Stop all running agents

## RAG Endpoints (/rag)
- POST /rag/query - Query documents using semantic search
- POST /rag/document - Add new document to vector store
- GET /rag/databases - List all vector databases
- POST /rag/databases - Create new database
- GET /rag/databases/{name}/documents - List documents in database
- DELETE /rag/databases/{name}/documents/{id} - Delete specific document
- POST /rag/databases/insert - Insert document with optional summarization

## Chat Endpoints (/chat)
- POST /chat/message - Send chat message and get AI response
- GET /chat/conversation/{id} - Get specific conversation history
"""
    },
    {
        "title": "UI Guide",
        "category": "documentation",
        "content": """
# Web Interface Guide

## Login
- URL: http://localhost:1131
- Username: guest
- Password: beourguest

## Dashboard
- Shows system health status (Online/Offline)
- Displays total agent count
- Quick navigation to all features

## Agents Page
- View all 13 agents with their status
- Send tasks to specific agents
- Real-time Chain of Thought (COT) activity log
- View detailed agent message history
- Interrupt controls for stopping agents

## RAG Page
- Databases Tab: Create, view, and delete vector databases
- Documents Tab: Browse documents, view full content, delete individual docs
- Query Tab: Perform semantic search across documents
- Add Document Tab: Insert new documents with optional summarization

## Chat Page
- Conversational interface with AI
- Sessions persist across page refreshes (localStorage)
- Shows which agents were involved in responses
- Clear chat button to start fresh

## Settings Page
- View API connection status
- Display current configuration
- Test API connectivity
"""
    },
    {
        "title": "Quick Start Guide",
        "category": "documentation",
        "content": """
# Quick Start Guide

## Prerequisites
- Python 3.10 or higher
- Node.js 18 or higher
- OpenAI API key

## Installation Steps

1. Clone the repository
2. Install Python dependencies:
   pip install -r requirements.txt

3. Install UI dependencies:
   cd ui && npm install && cd ..

4. Configure environment:
   Edit .env file with your OPENAI_API_KEY

5. Run the system:
   python main.py --ui

6. Access the UI:
   Open http://localhost:1131
   Login with guest / beourguest

## Docker Deployment
docker-compose -f docker/docker-compose.yml up

## Environment Variables
- OPENAI_API_KEY: Your OpenAI API key
- API_PORT: Backend port (default 1130)
- UI_PORT: Frontend port (default 1131)
- UI_ENABLED: Enable UI server (true/false)
- CHROMA_DB_PATH: Vector database storage path
"""
    },
    {
        "title": "Troubleshooting Guide",
        "category": "documentation",
        "content": """
# Troubleshooting Guide

## Common Issues

### Port Already in Use
If you see "Address already in use" error:
1. Find the process: netstat -ano | findstr :1130
2. Kill it: taskkill /PID <pid> /F

### Import Errors
- Ensure all dependencies installed: pip install -r requirements.txt
- Check you're using correct Python environment
- Required packages: fastapi, uvicorn, langchain, chromadb, openai, langchain-community

### API Connection Failed
- Verify server is running (check terminal for errors)
- Confirm port configuration in .env matches expectations
- Check CORS settings if calling from different origin

### Agents Not Responding
- Check agent status in the Agents dashboard
- Use "Restart All" to restart agents
- Review Chain of Thought activity log for errors
- Check if max concurrency (5) is reached

### Vector Database Issues
- Ensure CHROMA_DB_PATH is writable
- Delete corrupted collections if needed
- Check disk space for large document sets

### UI Not Loading
- Verify Next.js dependencies: cd ui && npm install
- Check for compilation errors in terminal
- Clear browser cache and localStorage
"""
    }
]

def create_database():
    """Create the documentation database if it doesn't exist"""
    try:
        response = requests.post(
            f"{API_URL}/rag/databases",
            json={
                "name": "system-docs",
                "description": "Agentic RAG System Documentation",
                "category": "documentation"
            }
        )
        print(f"Create database: {response.status_code}")
        return True
    except Exception as e:
        print(f"Error creating database: {e}")
        return False

def insert_document(doc):
    """Insert a document into the database"""
    try:
        response = requests.post(
            f"{API_URL}/rag/databases/insert",
            json={
                "database": "system-docs",
                "content": doc["content"],
                "title": doc["title"],
                "category": doc["category"],
                "summarize": False  # Don't summarize documentation
            }
        )
        print(f"Insert '{doc['title']}': {response.status_code}")
        return response.status_code == 200
    except Exception as e:
        print(f"Error inserting '{doc['title']}': {e}")
        return False

def main():
    print("Loading documentation into RAG database...")
    print(f"API URL: {API_URL}")
    print()
    
    # Check API health
    try:
        response = requests.get(f"{API_URL}/health")
        if response.status_code != 200:
            print("API not healthy, exiting")
            return
        print("API is healthy")
    except Exception as e:
        print(f"Cannot connect to API: {e}")
        print("Make sure the server is running with: python main.py --ui")
        return
    
    # Create database
    print("\nCreating documentation database...")
    create_database()
    
    # Insert documents
    print("\nInserting documentation...")
    for doc in DOCS:
        insert_document(doc)
    
    print("\nDone! Documentation loaded into 'system-docs' database.")
    print("You can query it in the RAG page of the UI.")

if __name__ == "__main__":
    main()
