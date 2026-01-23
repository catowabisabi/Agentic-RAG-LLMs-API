# Agentic RAG UI

Next.js demo interface for the Agentic RAG API.

## Features

- **Dashboard**: System overview and agent status
- **Agents**: View and interact with AI agents
- **Chat**: Interactive chat with the agent system
- **RAG Query**: Query and manage vector database documents
- **WebSocket**: Real-time WebSocket testing
- **Settings**: Configure API connection

## Getting Started

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

```bash
cd ui
npm install
```

### Development

```bash
npm run dev
```

The app will be available at http://localhost:1131

### Login Credentials

- **Username**: `guest`
- **Password**: `beourguest`

### Configuration

The UI connects to the FastAPI server at `http://localhost:1130` by default.
You can change this in the Settings page.

## Build for Production

```bash
npm run build
npm start
```

## Docker

The UI is included in the docker-compose setup and will be built automatically.
