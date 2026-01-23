# Multi-Agent RAG System Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY app_docs/requirements.txt /app/requirements.txt
COPY app_docs/requirements2.txt /app/requirements2.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt || true
RUN pip install --no-cache-dir -r requirements2.txt || true

# Install additional dependencies for the multi-agent system
RUN pip install --no-cache-dir \
    fastapi \
    uvicorn[standard] \
    websockets \
    chromadb \
    langchain \
    langchain-openai \
    langchain-community \
    langgraph \
    pydantic>=2.0 \
    python-dotenv \
    python-multipart \
    mcp

# Copy application code
COPY . /app

# Create data directories
RUN mkdir -p /app/data/vectordb /app/data/memory

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Expose ports
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["python", "main.py"]