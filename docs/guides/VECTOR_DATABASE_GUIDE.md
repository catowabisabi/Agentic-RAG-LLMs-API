# Vector Database Guide

This guide explains how to create, manage, and use vector databases in the Agentic RAG API.

## Overview

The system supports multiple vector databases for different data categories. Each database is independent and can be selected at runtime. This allows you to:

- Separate different types of data (e.g., finance, medical, technical)
- Provide different RAG contexts for different use cases
- Quickly switch between databases without restarting
- Sell the same API to multiple companies with separate data stores

## Quick Start

### 1. Create a New Database

```bash
# Using API
curl -X POST http://localhost:8000/rag/databases \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-company-data",
    "description": "Company knowledge base",
    "category": "corporate"
  }'
```

### 2. Switch to the Database

```bash
curl -X POST http://localhost:8000/rag/databases/my-company-data/activate
```

### 3. Insert Documents

```bash
# With LLM summarization (recommended for long documents)
curl -X POST http://localhost:8000/rag/databases/insert \
  -H "Content-Type: application/json" \
  -d '{
    "database": "my-company-data",
    "content": "Your full document content here...",
    "title": "Document Title",
    "category": "policy",
    "tags": ["hr", "benefits"],
    "summarize": true
  }'

# Without summarization (for short/precise content)
curl -X POST http://localhost:8000/rag/databases/insert \
  -H "Content-Type: application/json" \
  -d '{
    "database": "my-company-data",
    "content": "Short FAQ answer",
    "title": "FAQ Item",
    "summarize": false
  }'
```

### 4. Query the Database

```bash
curl -X POST http://localhost:8000/rag/databases/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the employee benefits?",
    "database": "my-company-data",
    "n_results": 5
  }'
```

## API Reference

### Database Management

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/rag/databases` | POST | Create new database |
| `/rag/databases` | GET | List all databases |
| `/rag/databases/{name}` | GET | Get database info |
| `/rag/databases/{name}/activate` | POST | Switch to database |
| `/rag/databases/{name}` | DELETE | Delete database |

### Document Operations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/rag/databases/insert` | POST | Insert document |
| `/rag/databases/upload` | POST | Upload file |
| `/rag/databases/query` | POST | Query database |
| `/rag/databases/query-all` | POST | Query all databases |

## Database Structure

Each database is stored as a separate ChromaDB instance:

```
rag-database/
└── vectordb/
    ├── db_metadata.json      # All database metadata
    ├── company-a/            # Database for Company A
    │   ├── chroma.sqlite3
    │   └── ...
    ├── company-b/            # Database for Company B
    │   ├── chroma.sqlite3
    │   └── ...
    └── default/              # Default database
        ├── chroma.sqlite3
        └── ...
```

## For Different Companies (Multi-Tenant Setup)

When selling to multiple companies, create separate databases for each:

```python
# Create database for each company
companies = ["acme-corp", "tech-inc", "retail-co"]

for company in companies:
    response = requests.post(
        "http://localhost:8000/rag/databases",
        json={
            "name": company,
            "description": f"Knowledge base for {company}",
            "category": "corporate"
        }
    )
```

### API Key Authentication (Recommended)

For production, implement API key authentication that maps to specific databases:

```python
# In your middleware
def get_database_for_api_key(api_key: str) -> str:
    """Map API key to company database"""
    api_key_mapping = {
        "key_acme_xxx": "acme-corp",
        "key_tech_xxx": "tech-inc",
        "key_retail_xxx": "retail-co"
    }
    return api_key_mapping.get(api_key, "default")
```

## Document Insertion Best Practices

### When to Use Summarization

| Document Type | Summarize | Reason |
|---------------|-----------|--------|
| Long reports (>2000 words) | ✅ Yes | Reduces noise, captures key points |
| Technical documentation | ✅ Yes | Focuses on main concepts |
| FAQ answers | ❌ No | Already concise |
| Code snippets | ❌ No | Precision important |
| Legal text | ❌ No | Every word matters |

### Metadata for Better Retrieval

Always include rich metadata:

```python
{
    "database": "my-database",
    "content": "...",
    "title": "Descriptive Title",
    "source": "internal-wiki",
    "category": "engineering",
    "tags": ["python", "api", "best-practices"],
    "summarize": true
}
```

### Bulk Document Loading

For loading many documents:

```python
import requests
import os

def load_directory(directory: str, database: str):
    """Load all files from a directory into a database"""
    
    for filename in os.listdir(directory):
        filepath = os.path.join(directory, filename)
        
        with open(filepath, 'r') as f:
            content = f.read()
        
        # Determine if summarization is needed
        should_summarize = len(content) > 2000
        
        response = requests.post(
            "http://localhost:8000/rag/databases/insert",
            json={
                "database": database,
                "content": content,
                "title": filename,
                "source": directory,
                "category": os.path.basename(directory),
                "summarize": should_summarize
            }
        )
        
        print(f"Loaded {filename}: {response.json()}")
```

## Python SDK Usage

```python
from services.vectordb_manager import vectordb_manager

# Create database
db_info = vectordb_manager.create_database(
    db_name="my-data",
    description="My data store",
    category="custom"
)

# Switch to database
vectordb_manager.switch_database("my-data")

# Insert with summarization
await vectordb_manager.insert_with_summary(
    db_name="my-data",
    content="Long document content...",
    title="Document Title",
    category="reports"
)

# Insert without summarization
await vectordb_manager.insert_full_text(
    db_name="my-data",
    content="Short content",
    title="FAQ"
)

# Query
results = await vectordb_manager.query(
    query="What is the policy?",
    db_name="my-data",
    n_results=5
)

# Query all databases
all_results = await vectordb_manager.query_all_databases(
    query="General question",
    n_results=3
)
```

## Switching Databases at Runtime

The active database can be changed instantly:

```python
# In agent code
async def handle_company_query(company_id: str, query: str):
    # Switch to company's database
    vectordb_manager.switch_database(company_id)
    
    # Query is now against that company's data
    results = await vectordb_manager.query(query)
    
    return results
```

## Environment Variables

Add these to your `.env`:

```bash
# Vector Database Configuration
CHROMA_DB_PATH=./rag-database/vectordb
EMBEDDING_MODEL=text-embedding-3-small

# For summarization
OPENAI_API_KEY=your_key_here
DEFAULT_MODEL=gpt-4o-mini
```

## Troubleshooting

### Database Not Found

```python
# List all databases first
databases = vectordb_manager.list_databases()
print([db['name'] for db in databases])

# Check if database exists
if vectordb_manager.get_database_info("my-db"):
    vectordb_manager.switch_database("my-db")
else:
    vectordb_manager.create_database("my-db", "New database")
```

### Empty Query Results

1. Check if documents were inserted correctly
2. Verify the database is active
3. Try a simpler query
4. Check document metadata filters

### Slow Insertion

For large documents, summarization takes time. Options:
- Use `summarize: false` for faster insertion
- Batch insert documents during off-peak hours
- Use background job queue for large uploads

## Data Migration

To migrate data between databases:

```python
async def migrate_data(source_db: str, target_db: str):
    """Migrate all documents from one database to another"""
    
    # Get all documents from source
    source_collection = vectordb_manager._get_collection(source_db)
    all_docs = source_collection.get()
    
    # Insert into target
    for i, doc in enumerate(all_docs['documents']):
        await vectordb_manager.insert_full_text(
            db_name=target_db,
            content=doc,
            metadata=all_docs['metadatas'][i] if all_docs['metadatas'] else {}
        )
```

## Security Considerations

1. **Database Isolation**: Each company's data is in a separate ChromaDB instance
2. **API Key Mapping**: Map API keys to specific databases
3. **Access Control**: Implement authorization middleware
4. **Audit Logging**: Log all database operations
5. **Backup**: Regularly backup the `rag-database/vectordb` directory
