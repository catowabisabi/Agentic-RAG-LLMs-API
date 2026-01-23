import os
import argparse
from typing import List
from pathlib import Path

from tools.retriever import DocumentRetriever
from config.config import Config


def load_text_file(file_path: str) -> str:
    """Load content from a text file"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return ""


def load_documents_from_directory(directory: str) -> List[tuple]:
    """Load all documents from a directory"""
    documents = []
    metadatas = []
    
    supported_extensions = {'.txt', '.md', '.py', '.js', '.ts', '.html', '.css', '.json'}
    
    for file_path in Path(directory).rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in supported_extensions:
            content = load_text_file(str(file_path))
            if content.strip():  # Only add non-empty files
                documents.append(content)
                metadatas.append({
                    'filename': file_path.name,
                    'filepath': str(file_path),
                    'extension': file_path.suffix,
                    'size': len(content)
                })
                print(f"Loaded: {file_path}")
    
    return documents, metadatas


def create_sample_documents():
    """Create sample documents for testing"""
    documents_dir = Path("documents")
    documents_dir.mkdir(exist_ok=True)
    
    # Sample LangGraph documentation
    langgraph_doc = """
# LangGraph Overview

LangGraph is a low-level orchestration framework for building, managing, and deploying long-running, stateful agents.

## Core Benefits

1. **Durable execution**: Build agents that persist through failures and can run for extended periods
2. **Human-in-the-loop**: Seamlessly incorporate human oversight by inspecting and modifying agent state
3. **Comprehensive memory**: Create truly stateful agents with both short-term and long-term memory
4. **Debugging with LangSmith**: Gain deep visibility into complex agent behavior
5. **Production-ready deployment**: Deploy sophisticated agent systems confidently

## Key Features

- State management across agent interactions
- Graph-based workflow definition
- Checkpointing for fault tolerance
- Integration with LangChain ecosystem
- Support for multiple LLM providers

## Use Cases

- Multi-step reasoning agents
- Conversational AI with memory
- Tool-using agents
- Human-in-the-loop workflows
- Complex decision-making systems
    """
    
    with open(documents_dir / "langgraph_overview.md", 'w', encoding='utf-8') as f:
        f.write(langgraph_doc)
    
    # Sample RAG documentation
    rag_doc = """
# Retrieval-Augmented Generation (RAG)

RAG combines the power of retrieval systems with generative language models to provide accurate, contextual responses.

## How RAG Works

1. **Document Indexing**: Documents are processed, chunked, and stored in a vector database
2. **Query Processing**: User queries are analyzed and potentially reformulated
3. **Retrieval**: Relevant documents are retrieved based on semantic similarity
4. **Context Synthesis**: Retrieved documents are combined with conversation history
5. **Generation**: An LLM generates responses using the retrieved context

## Benefits of RAG

- Access to up-to-date information
- Reduced hallucination
- Transparent source attribution
- Domain-specific expertise
- Cost-effective compared to fine-tuning

## RAG Challenges

- Retrieval quality dependency
- Context window limitations
- Latency considerations
- Maintaining coherence across long conversations

## Advanced RAG Techniques

- Multi-modal retrieval
- Hierarchical retrieval
- Query expansion
- Result reranking
- Hybrid search approaches
    """
    
    with open(documents_dir / "rag_overview.md", 'w', encoding='utf-8') as f:
        f.write(rag_doc)
    
    # Sample agent architecture document
    agent_doc = """
# Agent Architecture Patterns

## Stateful vs Stateless Agents

### Stateful Agents
- Maintain conversation context
- Remember past interactions
- Support complex multi-turn workflows
- Examples: LangGraph agents, persistent chatbots

### Stateless Agents
- Process each request independently
- No memory between interactions
- Simpler deployment and scaling
- Examples: Function calling APIs, simple Q&A systems

## Agent Components

1. **Memory Systems**
   - Short-term working memory
   - Long-term persistent storage
   - Semantic memory organization

2. **Planning Modules**
   - Goal decomposition
   - Task scheduling
   - Resource allocation

3. **Tool Integration**
   - API calling capabilities
   - External system integration
   - Security considerations

4. **Monitoring & Observability**
   - Performance tracking
   - Error handling
   - User interaction logging

## Design Patterns

- **ReAct**: Reasoning and Acting in sequence
- **Chain of Thought**: Step-by-step reasoning
- **Tree of Thoughts**: Exploring multiple reasoning paths
- **Multi-agent**: Collaborative agent systems
    """
    
    with open(documents_dir / "agent_architecture.md", 'w', encoding='utf-8') as f:
        f.write(agent_doc)
    
    print("Created sample documents in the documents/ directory")


def main():
    parser = argparse.ArgumentParser(description='Load documents into the vector database')
    parser.add_argument('--directory', '-d', type=str, default='./documents',
                        help='Directory containing documents to load')
    parser.add_argument('--create-samples', action='store_true',
                        help='Create sample documents for testing')
    
    args = parser.parse_args()
    
    # Create sample documents if requested
    if args.create_samples:
        create_sample_documents()
    
    # Check if directory exists
    if not os.path.exists(args.directory):
        print(f"Directory {args.directory} does not exist.")
        print("Use --create-samples to create sample documents, or specify a different directory.")
        return
    
    # Load documents
    print(f"Loading documents from {args.directory}...")
    documents, metadatas = load_documents_from_directory(args.directory)
    
    if not documents:
        print("No documents found to load.")
        return
    
    # Initialize retriever and add documents
    print("Initializing document retriever...")
    retriever = DocumentRetriever()
    
    success = retriever.add_documents(documents, metadatas)
    
    if success:
        stats = retriever.get_collection_stats()
        print(f"\nSuccessfully loaded {len(documents)} documents!")
        print(f"Collection stats: {stats}")
        
        # Test retrieval
        print("\nTesting retrieval...")
        test_query = "What are the benefits of LangGraph?"
        results = retriever.retrieve(test_query, top_k=3)
        
        print(f"Test query: '{test_query}'")
        print(f"Retrieved {len(results)} documents:")
        for i, result in enumerate(results, 1):
            print(f"  {i}. Score: {result['similarity_score']:.3f}")
            print(f"     Content preview: {result['content'][:100]}...")
            if result['metadata']:
                print(f"     Source: {result['metadata'].get('filename', 'Unknown')}")
    else:
        print("Failed to load documents into vector database.")


if __name__ == "__main__":
    main()