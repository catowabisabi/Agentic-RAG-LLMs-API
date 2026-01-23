"""
Base Provider

Abstract base class for all MCP providers.
Defines common interface and utility methods.
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from datetime import datetime

from pydantic import BaseModel


logger = logging.getLogger(__name__)


class ProviderConfig(BaseModel):
    """Base configuration for providers"""
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    timeout: int = 30
    max_retries: int = 3
    enabled: bool = True


class ProviderResult(BaseModel):
    """Standard result from provider operations"""
    success: bool
    data: Any = None
    error: Optional[str] = None
    provider: str
    operation: str
    timestamp: datetime = None
    metadata: Dict[str, Any] = {}
    
    def __init__(self, **data):
        if 'timestamp' not in data or data['timestamp'] is None:
            data['timestamp'] = datetime.now()
        super().__init__(**data)


class BaseProvider(ABC):
    """
    Abstract base class for MCP providers.
    
    All providers must implement:
    - initialize(): Setup the provider
    - health_check(): Check if provider is available
    - get_capabilities(): List available operations
    """
    
    def __init__(self, config: ProviderConfig = None):
        self.config = config or ProviderConfig()
        self.provider_name = self.__class__.__name__
        self._initialized = False
        self._last_health_check = None
        self._is_healthy = False
        
        logger.info(f"Provider created: {self.provider_name}")
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the provider. Must be called before use."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the provider is available and working."""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[str]:
        """Get list of operations this provider supports."""
        pass
    
    def _success(self, operation: str, data: Any, **metadata) -> ProviderResult:
        """Create a success result"""
        return ProviderResult(
            success=True,
            data=data,
            provider=self.provider_name,
            operation=operation,
            metadata=metadata
        )
    
    def _error(self, operation: str, error: str, **metadata) -> ProviderResult:
        """Create an error result"""
        return ProviderResult(
            success=False,
            error=error,
            provider=self.provider_name,
            operation=operation,
            metadata=metadata
        )
    
    async def ensure_initialized(self):
        """Ensure provider is initialized before operations"""
        if not self._initialized:
            self._initialized = await self.initialize()
            if not self._initialized:
                raise RuntimeError(f"Failed to initialize {self.provider_name}")
    
    def is_enabled(self) -> bool:
        """Check if provider is enabled"""
        return self.config.enabled
    
    def get_status(self) -> Dict[str, Any]:
        """Get provider status"""
        return {
            "provider": self.provider_name,
            "enabled": self.config.enabled,
            "initialized": self._initialized,
            "healthy": self._is_healthy,
            "last_health_check": self._last_health_check.isoformat() if self._last_health_check else None,
            "capabilities": self.get_capabilities() if self._initialized else []
        }
