# LangGraph RAG Demo

A demonstration of building a Retrieval-Augmented Generation (RAG) system using LangGraph for stateful agent workflows.

## Features

- **Stateful RAG Agent**: Uses LangGraph for persistent state management
- **Vector Database Integration**: Supports ChromaDB and FAISS for document retrieval
- **Human-in-the-loop**: Allows human intervention in the RAG process
- **Memory Management**: Maintains conversation history and context
- **Flexible LLM Support**: Works with OpenAI, Anthropic, and other providers

## Quick Start

1. **Install Dependencies**:
```bash
pip install -r requirements.txt
```

2. **Setup Environment**:
```bash
cp .env.example .env
# Edit .env with your API keys
```

3. **Run the Demo**:
```bash
python main.py
```

4. **Load Documents**:
```bash
python load_documents.py --directory ./documents
```

## Project Structure

```
rag-demo/
├── main.py              # Main RAG agent implementation
├── load_documents.py    # Document loading and indexing
├── config.py           # Configuration settings
├── agents/
│   ├── rag_agent.py    # LangGraph RAG agent definition
│   └── nodes.py        # Individual agent nodes
├── tools/
│   ├── retriever.py    # Document retrieval tools
│   └── memory.py       # Memory management tools
├── documents/          # Sample documents directory
└── vectordb/          # Vector database storage
```

## Usage Examples

### Basic RAG Query
```python
from agents.rag_agent import create_rag_agent

agent = create_rag_agent()
result = agent.invoke({
    "query": "What are the key features of LangGraph?",
    "chat_history": []
})
print(result["answer"])
```

### Stateful Conversation
```python
# The agent maintains state across multiple queries
result1 = agent.invoke({"query": "Tell me about LangGraph"})
result2 = agent.invoke({"query": "What are its main benefits?"})  # References previous context
```

## LangGraph Architecture

This demo implements a multi-node graph with the following nodes:

1. **Query Analysis**: Analyzes and reformulates user queries
2. **Document Retrieval**: Retrieves relevant documents from vector store
3. **Context Synthesis**: Combines retrieved documents with conversation history
4. **Answer Generation**: Generates comprehensive answers using LLM
5. **Quality Check**: Validates answer quality and completeness

## Configuration

Edit `config.py` to customize:

- Vector database settings
- LLM model selection
- Retrieval parameters
- Memory configuration

## Contributing

Feel free to extend this demo with additional features like:

- Multi-modal RAG (images, audio)
- Advanced retrieval strategies
- Custom embedding models
- Integration with external APIs