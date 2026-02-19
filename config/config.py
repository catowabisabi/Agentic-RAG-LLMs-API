
"""
Configuration Module 配置模組

Centralized configuration for the multi-agent RAG system.
多智能體 RAG 系統的集中式配置。
"""


# 導入標準庫與第三方庫
import os
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv


# 優先從 config 目錄載入 .env 檔案，否則退回專案根目錄
config_dir = Path(__file__).parent
env_path = config_dir / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Fallback to project root
    load_dotenv()



class Config:
    """
    Configuration class for the multi-agent RAG system.
    多智能體 RAG 系統的配置類。
    
    All configuration values can be overridden via environment variables.
    所有設定都可用環境變數覆蓋。
    """
    
    # API Keys - API 金鑰
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")  # OpenAI 金鑰
    ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")  # Anthropic 金鑰
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # Google 金鑰
    
    # LLM Settings - 大語言模型設定
    DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")  # 預設模型名稱
    TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))  # 溫度（隨機性）
    MAX_TOKENS = int(os.getenv("MAX_TOKENS", "2000"))  # 最大回應 token 數
    
    # Vector Database Settings - 向量資料庫設定
    CHROMA_DB_PATH = os.getenv("CHROMA_DB_PATH", "./rag-database/vectordb")  # Chroma DB 路徑
    MEMORY_DB_PATH = os.getenv("MEMORY_DB_PATH", "./rag-database/memory")  # 記憶資料庫路徑
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")  # 嵌入模型名稱
    
    # RAG Settings - RAG 相關設定
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "2000"))  # 分塊大小 (Phase 2: 1000→2000)
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "400"))  # 分塊重疊 (Phase 2: 200→400)
    PARENT_CHUNK_SIZE = int(os.getenv("PARENT_CHUNK_SIZE", "6000"))  # 父級分塊大小 (Phase 2)
    TOP_K_RETRIEVAL = int(os.getenv("TOP_K_RETRIEVAL", "5"))  # 最終返回前 K 筆
    TOP_K_CANDIDATES = int(os.getenv("TOP_K_CANDIDATES", "20"))  # 粗檢索候選數 (Phase 1)
    
    # Reranking & Filtering - 重排序與過濾設定 (Phase 1)
    RERANK_ENABLED = os.getenv("RERANK_ENABLED", "true").lower() == "true"  # 是否啟用 Cross-Encoder Reranking
    RERANK_MODEL = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-12-v2")  # Reranking 模型
    MIN_SIMILARITY = float(os.getenv("MIN_SIMILARITY", "0.25"))  # 最低相似度門檻
    
    # Context Window - 上下文限制 (Phase 3)
    MAX_CONTEXT_CHARS = int(os.getenv("MAX_CONTEXT_CHARS", "16000"))  # 最大上下文字元數 (Phase 3: 3000→16000)
    
    # Agent Settings - 智能體設定
    MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))  # 最大迭代次數
    MEMORY_WINDOW = int(os.getenv("MEMORY_WINDOW", "5"))  # 記憶視窗大小
    AGENT_TIMEOUT = int(os.getenv("AGENT_TIMEOUT", "30"))  # 智能體逾時（秒）
    
    # WebSocket Settings - WebSocket 相關設定
    WS_HEARTBEAT_INTERVAL = int(os.getenv("WS_HEARTBEAT_INTERVAL", "30"))  # 心跳間隔
    WS_MAX_CONNECTIONS = int(os.getenv("WS_MAX_CONNECTIONS", "100"))  # 最大連線數
    
    # API Settings - API 伺服器設定
    API_HOST = os.getenv("API_HOST", "0.0.0.0")  # API 綁定主機
    API_PORT = int(os.getenv("API_PORT", "1130"))  # API 埠號
    API_RELOAD = os.getenv("API_RELOAD", "false").lower() == "true"  # 是否自動重載
    
    # UI Settings - 前端 UI 設定
    UI_ENABLED = os.getenv("UI_ENABLED", "true").lower() == "true"  # 是否啟用 UI
    UI_PORT = int(os.getenv("UI_PORT", "1131"))  # UI 埠號
    UI_PATH = os.getenv("UI_PATH", "./ui")  # UI 路徑
    
    # MCP Settings - MCP 相關設定
    MCP_ENABLED = os.getenv("MCP_ENABLED", "true").lower() == "true"  # 是否啟用 MCP
    MCP_HOST = os.getenv("MCP_HOST", "localhost")  # MCP 主機
    MCP_PORT = int(os.getenv("MCP_PORT", "8001"))  # MCP 埠號
    
    # Redis Settings - Redis 設定
    REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"  # 是否啟用 Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")  # Redis 連線字串
    REDIS_PREFIX = os.getenv("REDIS_PREFIX", "agentic_rag:")  # Redis key 前綴
    REDIS_TTL = int(os.getenv("REDIS_TTL", "86400"))  # Redis 預設 TTL（秒）
    
    # Celery Settings - 任務佇列 Celery 設定
    CELERY_ENABLED = os.getenv("CELERY_ENABLED", "false").lower() == "true"  # 是否啟用 Celery
    CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")  # Celery broker
    CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")  # Celery 結果儲存
    
    # Debug Mode - 偵錯模式
    DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"  # 偵錯模式（生產環境設 false）
    
    # Authentication - 驗證設定
    AUTH_ADMIN_USER = os.getenv("AUTH_ADMIN_USER", "admin")
    AUTH_ADMIN_PASSWORD = os.getenv("AUTH_ADMIN_PASSWORD", "")
    AUTH_GUEST_USER = os.getenv("AUTH_GUEST_USER", "guest")
    AUTH_GUEST_PASSWORD = os.getenv("AUTH_GUEST_PASSWORD", "")
    
    # Logging - 日誌設定
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")  # 日誌等級
    LOG_FORMAT = os.getenv(
        "LOG_FORMAT",
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )  # 日誌格式
    
    # Agent-specific settings - 智能體細部設定
    PLANNING_STREAM_ENABLED = os.getenv("PLANNING_STREAM_ENABLED", "true").lower() == "true"  # 規劃流啟用
    THINKING_STREAM_ENABLED = os.getenv("THINKING_STREAM_ENABLED", "true").lower() == "true"  # 思考流啟用
    
    # Validation settings - 驗證相關設定
    VALIDATION_ERROR_THRESHOLD = int(os.getenv("VALIDATION_ERROR_THRESHOLD", "3"))  # 驗證錯誤閾值
    ROLE_CORRECTION_THRESHOLD = int(os.getenv("ROLE_CORRECTION_THRESHOLD", "5"))  # 角色修正閾值
    
    @classmethod
    def get_agent_config(cls, agent_name: str) -> Dict[str, Any]:
        """Get configuration for a specific agent
        取得特定智能體的設定
        """
        agent_configs = {
            "manager_agent": {
                "can_interrupt": True,  # 可中斷
                "priority": 1  # 優先級
            },
            "planning_agent": {
                "stream_enabled": cls.PLANNING_STREAM_ENABLED,  # 是否啟用規劃流
                "timeout": 60  # 逾時秒數
            },
            "thinking_agent": {
                "stream_enabled": cls.THINKING_STREAM_ENABLED,  # 是否啟用思考流
                "timeout": 60,
                "check_rag": True  # 是否檢查 RAG
            },
            "validation_agent": {
                "error_threshold": cls.VALIDATION_ERROR_THRESHOLD  # 錯誤閾值
            },
            "roles_agent": {
                "correction_threshold": cls.ROLE_CORRECTION_THRESHOLD  # 角色修正閾值
            }
        }
        
        return agent_configs.get(agent_name, {})
    
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Export configuration as dictionary
        匯出設定為字典
        """
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