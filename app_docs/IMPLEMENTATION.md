# Agentic RAG API - Implementation Guide

This guide explains how to integrate the Agentic RAG API into your applications, UIs, or other software.

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+ (for UI only)
- OpenAI API Key

### Starting the Server

```bash
# Start API only
start_api.bat

# Start UI only (requires API running)
start_ui.bat

# Start both API and UI
start_local.bat
```

The API will be available at `http://localhost:1130`

---

## API Endpoints

### 1. Health Check

```
GET /health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "agents": ["manager", "planning", "rag", "tool", ...],
  "vectordb": "connected"
}
```

---

### 2. Chat (Main Endpoint)

The primary endpoint for interacting with the multi-agent system.

```
POST /api/agent/chat
```

**Request:**
```json
{
  "message": "What are the benefits of RAG systems?",
  "session_id": "optional-session-id",
  "context": {
    "language": "en",
    "domain": "technology"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message_id": "msg_123456",
  "response": "RAG (Retrieval Augmented Generation) systems offer several benefits...",
  "sources": [
    {
      "document": "rag_overview.pdf",
      "chunk": "RAG combines retrieval with generation...",
      "relevance": 0.92
    }
  ],
  "agents_used": ["planning_agent", "rag_agent", "thinking_agent"],
  "tokens_used": 1234
}
```

---

### 3. Query (RAG-specific)

Direct access to the RAG retrieval system.

```
POST /api/agent/query
```

**Request:**
```json
{
  "query": "machine learning techniques",
  "collection": "technical-docs",
  "top_k": 5,
  "filters": {
    "file_type": "pdf"
  }
}
```

---

### 4. VectorDB Management

#### List Collections
```
GET /api/vectordb/collections
```

#### Add Documents
```
POST /api/vectordb/add
```

**Request:**
```json
{
  "collection": "my-docs",
  "documents": [
    {
      "content": "Document content here...",
      "metadata": {
        "source": "manual",
        "category": "technical"
      }
    }
  ]
}
```

#### Search Documents
```
POST /api/vectordb/search
```

**Request:**
```json
{
  "collection": "my-docs",
  "query": "search term",
  "top_k": 10
}
```

---

## WebSocket Integration

For real-time streaming responses:

```
WS /ws/{client_id}
```

### JavaScript Example

```javascript
const ws = new WebSocket('ws://localhost:1130/ws/my-client-123');

ws.onopen = () => {
  ws.send(JSON.stringify({
    type: 'chat',
    message: 'Tell me about AI',
    stream: true
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  
  switch (data.type) {
    case 'thinking':
      console.log('Agent thinking:', data.content);
      break;
    case 'chunk':
      process.stdout.write(data.content);
      break;
    case 'complete':
      console.log('\nResponse complete:', data.response);
      break;
    case 'error':
      console.error('Error:', data.message);
      break;
  }
};
```

### Python Example

```python
import asyncio
import websockets
import json

async def chat_with_agent():
    uri = "ws://localhost:1130/ws/my-client-123"
    
    async with websockets.connect(uri) as ws:
        # Send message
        await ws.send(json.dumps({
            "type": "chat",
            "message": "Explain quantum computing",
            "stream": True
        }))
        
        # Receive streaming response
        while True:
            response = await ws.recv()
            data = json.loads(response)
            
            if data["type"] == "chunk":
                print(data["content"], end="", flush=True)
            elif data["type"] == "complete":
                print("\n\nDone!")
                break

asyncio.run(chat_with_agent())
```

---

## Integration Examples

### 1. Flutter/Dart

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

class AgenticRAGClient {
  final String baseUrl;
  
  AgenticRAGClient({this.baseUrl = 'http://localhost:1130'});
  
  Future<Map<String, dynamic>> chat(String message, {String? sessionId}) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/agent/chat'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'message': message,
        'session_id': sessionId,
      }),
    );
    
    if (response.statusCode == 200) {
      return jsonDecode(response.body);
    } else {
      throw Exception('Failed to chat: ${response.statusCode}');
    }
  }
}
```

### 2. React/TypeScript

```typescript
interface ChatResponse {
  success: boolean;
  response: string;
  sources: Array<{
    document: string;
    chunk: string;
    relevance: number;
  }>;
}

async function chatWithAgent(message: string): Promise<ChatResponse> {
  const response = await fetch('http://localhost:1130/api/agent/chat', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message }),
  });
  
  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }
  
  return response.json();
}

// Usage with React
function ChatComponent() {
  const [response, setResponse] = useState('');
  
  const handleSend = async (message: string) => {
    const result = await chatWithAgent(message);
    setResponse(result.response);
  };
  
  return (
    <div>
      <input onKeyPress={(e) => e.key === 'Enter' && handleSend(e.target.value)} />
      <div>{response}</div>
    </div>
  );
}
```

### 3. Python Application

```python
import requests

class AgenticRAGClient:
    def __init__(self, base_url: str = "http://localhost:1130"):
        self.base_url = base_url
    
    def chat(self, message: str, session_id: str = None) -> dict:
        """Send a chat message to the agent"""
        response = requests.post(
            f"{self.base_url}/api/agent/chat",
            json={
                "message": message,
                "session_id": session_id
            }
        )
        response.raise_for_status()
        return response.json()
    
    def search(self, query: str, collection: str = "default", top_k: int = 5) -> dict:
        """Search the vector database"""
        response = requests.post(
            f"{self.base_url}/api/vectordb/search",
            json={
                "collection": collection,
                "query": query,
                "top_k": top_k
            }
        )
        response.raise_for_status()
        return response.json()

# Usage
client = AgenticRAGClient()
result = client.chat("What is machine learning?")
print(result["response"])
```

### 4. cURL Examples

```bash
# Health check
curl http://localhost:1130/health

# Chat
curl -X POST http://localhost:1130/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, how are you?"}'

# Search VectorDB
curl -X POST http://localhost:1130/api/vectordb/search \
  -H "Content-Type: application/json" \
  -d '{"collection": "docs", "query": "AI", "top_k": 3}'
```

---

## Configuration

### Environment Variables

Edit `config/.env`:

```env
# Required
OPENAI_API_KEY=sk-your-key-here

# API Settings
API_PORT=1130           # Change API port
UI_PORT=1131           # Change UI port

# LLM Settings
DEFAULT_MODEL=gpt-4o-mini    # or gpt-4o, gpt-4-turbo
TEMPERATURE=0.7
MAX_TOKENS=2000

# RAG Settings
TOP_K_RETRIEVAL=5      # Number of documents to retrieve
CHUNK_SIZE=1000        # Document chunk size
```

---

## Advanced: Tool Agent Integration

The API includes MCP (Model Context Protocol) tools accessible via the Tool Agent:

### Available Tools

| Tool | Description |
|------|-------------|
| `file_control` | Read/write txt, json, csv, excel, pdf files |
| `system_command` | Execute safe system commands |
| `medical_rag` | Search PubMed and medical regulations |
| `calculator` | Mathematical calculations |
| `json_parser` | Parse and validate JSON |
| `text_analyzer` | Text statistics analysis |

### Using Tools via API

```json
POST /api/agent/chat
{
  "message": "Read the file README.md and summarize it",
  "tools_enabled": true
}
```

The agent will automatically select and use appropriate tools.

---

## Error Handling

All endpoints return consistent error format:

```json
{
  "success": false,
  "error": {
    "code": "INVALID_REQUEST",
    "message": "Missing required field: message",
    "details": {}
  }
}
```

### Common Error Codes

| Code | Description |
|------|-------------|
| `INVALID_REQUEST` | Malformed request body |
| `UNAUTHORIZED` | Missing or invalid API key |
| `RATE_LIMIT` | Too many requests |
| `AGENT_ERROR` | Agent processing failed |
| `VECTORDB_ERROR` | Vector database error |

---

## Best Practices

1. **Session Management**: Use consistent `session_id` for conversation continuity
2. **Streaming**: Use WebSocket for long responses to improve UX
3. **Error Handling**: Always handle errors gracefully
4. **Rate Limiting**: Implement client-side rate limiting
5. **Caching**: Cache frequent queries when appropriate

---

## Support

- Documentation: `app_docs/`
- Issues: GitHub Issues
- API Reference: `http://localhost:1130/docs` (Swagger UI)
