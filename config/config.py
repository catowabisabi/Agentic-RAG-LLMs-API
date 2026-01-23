"""
Configuration Module

Centralized configuration for the multi-agent RAG system.
"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    """
    Configuration class for the multi-agent RAG system.
    
    All configuration values can be overridden via environment variables.
    """
    
    # API Keys
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    
    # LLM Settings
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2000"))
    
    # Vector Database Settings
    CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./rag-database/vectordb")
    MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", "./rag-database/memory")
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    
    # RAG Settings
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "1000"))
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
    TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "5"))
    
    # Agent Settings
    MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))
    MEMORY_WINDOW = int(os.getenv("MEMORY_WINDOW", "5"))
    AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "30"))  # seconds
    
    # WebSocket Settings
    WS_HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))
    WS_MAX_CONNECTIONS = int(os.getenv("WS_MAX_CONNECTIONS", "100"))
    
    # API Settings
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    API_RELOAD = os.getenv("API_RELOAD", "false").lower() == "true"
    
    # MCP Settings
    MCP_ENABLED = os.getenv("MCP_ENABLED", "true").lower() == "true"
    MCP_HOST = os.getenv("MCP_HOST", "localhost")
    MCP_PORT = int(os.getenv("MCP_PORT", "8001"))
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Agent-specific settings
    PLANNING_STREAM_ENABLED = os.getenv("PLANNING_STREAM_ENABLED", "true").lower() == "true"
    THINKING_STREAM_ENABLED = os.getenv("THINKING_STREAM_ENABLED", "true").lower() == "true"
    
    # Validation settings
    VALIDATION_ERROR_THRESHOLD = int(os.getenv("VALIDATION_ERROR_THRESHOLD", "3"))
    ROLE_CORRECTION_THRESHOLD = int(os.getenv("ROLE_CORRECTION_THRESHOLD", "5"))
    
    @classmethod
    def get_agent_config(cls, agent_name: str) -> Dict[str, Any]:
        """Get configuration for a specific agent"""
        agent_configs = {
            "manager_agent": {
                "can_interrupt": True,
                "priority": 1
            },
            "planning_agent": {
                "stream_enabled": cls.PLANNING_STREAM_ENABLED,
                "timeout": 60
            },
            "thinking_agent": {
                "stream_enabled": cls.THINKING_STREAM_ENABLED,
                "timeout": 60,
                "check_rag": True
            },
            "validation_agent": {
                "error_threshold": cls.VALIDATION_ERROR_THRESHOLD
            },
            "roles_agent": {
                "correction_threshold": cls.ROLE_CORRECTION_THRESHOLD
            }
        }
        
        return agent_configs.get(agent_name, {})
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Export configuration as dictionary"""
        return {
            "openai_api_key": "***" if cls.OPENAI_API_KEY else None,
            "default_model": cls.DEFAULT_MODEL,
            "temperature": cls.TEMPERATURE,
            "max_tokens": cls.MAX_TOKENS,
            "chroma_db_path": cls.CHROMA_DB_PATH,
            "embedding_model": cls.EMBEDDING_MODEL,
            "chunk_size": cls.CHUNK_SIZE,
            "chunk_overlap": cls.CHUNK_OVERLAP,
            "top_k_retrieval": cls.TOP_K_RETRIEVAL,
            "max_iterations": cls.MAX_ITERATIONS,
            "memory_window": cls.MEMORY_WINDOW,
            "api_host": cls.API_HOST,
            "api_port": cls.API_PORT,
            "mcp_enabled": cls.MCP_ENABLED,
            "log_level": cls.LOG_LEVEL
        }