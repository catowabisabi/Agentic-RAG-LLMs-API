"""
Brave Search Provider

Privacy-focused search engine with AI features.
Good for general web search with privacy in mind.

Features:
- Web search
- News search
- Image search
- Video search
"""

import logging
from typing import Dict, Any, List, Optional

import httpx

from .base_provider import BaseProvider, ProviderConfig, ProviderResult

logger = logging.getLogger(__name__)


class BraveSearchConfig(ProviderConfig):
    """Configuration for Brave Search"""
    base_url: str = "https://api.search.brave.com/res/v1"
    country: str = "us"
    search_lang: str = "en"
    safe_search: str = "moderate"  # off, moderate, strict


class BraveSearchProvider(BaseProvider):
    """
    Brave Search provider for web search.
    
    Capabilities:
    - web_search: General web search
    - news_search: News articles
    - image_search: Image search
    - video_search: Video search
    """
    
    def __init__(self, config: BraveSearchConfig = None):
        super().__init__(config or BraveSearchConfig())
        self.config: BraveSearchConfig = self.config
        self._client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self) -> bool:
        """Initialize the Brave Search client"""
        try:
            if not self.config.api_key:
                logger.warning("Brave Search API key not configured")
                return False
            
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={"X-Subscription-Token": self.config.api_key},
                timeout=self.config.timeout
            )
            
            self._initialized = True
            logger.info("Brave Search provider initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Brave Search: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check if Brave Search API is available"""
        try:
            await self.ensure_initialized()
            response = await self._client.get(
                "/web/search",
                params={"q": "test", "count": 1}
            )
            self._is_healthy = response.status_code == 200
            return self._is_healthy
        except Exception as e:
            logger.error(f"Brave Search health check failed: {e}")
            self._is_healthy = False
            return False
    
    def get_capabilities(self) -> List[str]:
        """Get available operations"""
        return ["web_search", "news_search", "image_search", "video_search", "suggest"]
    
    async def web_search(
        self,
        query: str,
        count: int = 10,
        offset: int = 0,
        freshness: str = None,  # pd (past day), pw (past week), pm (past month), py (past year)
        result_filter: str = None  # discussions, faq, infobox, news, query, summarizer, videos, web
    ) -> ProviderResult:
        """
        Search the web.
        
        Args:
            query: Search query
            count: Number of results (max 20)
            offset: Result offset
            freshness: Time filter
            result_filter: Type of results to include
            
        Returns:
            ProviderResult with search results
        """
        try:
            await self.ensure_initialized()
            
            params = {
                "q": query,
                "count": min(count, 20),
                "offset": offset,
                "country": self.config.country,
                "search_lang": self.config.search_lang,
                "safesearch": self.config.safe_search
            }
            
            if freshness:
                params["freshness"] = freshness
            if result_filter:
                params["result_filter"] = result_filter
            
            response = await self._client.get("/web/search", params=params)
            response.raise_for_status()
            
            data = response.json()
            
            web_results = data.get("web", {}).get("results", [])
            
            return self._success(
                operation="web_search",
                data={
                    "query": query,
                    "total_results": data.get("web", {}).get("total", 0),
                    "results": [
                        {
                            "title": r.get("title"),
                            "url": r.get("url"),
                            "description": r.get("description"),
                            "age": r.get("age"),
                            "language": r.get("language")
                        }
                        for r in web_results
                    ],
                    "infobox": data.get("infobox"),
                    "faq": data.get("faq", {}).get("results", [])
                }
            )
            
        except Exception as e:
            logger.error(f"Brave web_search error: {e}")
            return self._error("web_search", str(e), query=query)
    
    async def news_search(
        self,
        query: str,
        count: int = 10,
        freshness: str = None
    ) -> ProviderResult:
        """
        Search for news articles.
        
        Args:
            query: Search query
            count: Number of results
            freshness: Time filter
            
        Returns:
            ProviderResult with news results
        """
        try:
            await self.ensure_initialized()
            
            params = {
                "q": query,
                "count": min(count, 20),
                "country": self.config.country,
                "search_lang": self.config.search_lang
            }
            
            if freshness:
                params["freshness"] = freshness
            
            response = await self._client.get("/news/search", params=params)
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="news_search",
                data={
                    "query": query,
                    "results": [
                        {
                            "title": r.get("title"),
                            "url": r.get("url"),
                            "description": r.get("description"),
                            "source": r.get("meta_url", {}).get("hostname"),
                            "age": r.get("age"),
                            "thumbnail": r.get("thumbnail", {}).get("src")
                        }
                        for r in data.get("results", [])
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"Brave news_search error: {e}")
            return self._error("news_search", str(e), query=query)
    
    async def image_search(
        self,
        query: str,
        count: int = 10
    ) -> ProviderResult:
        """
        Search for images.
        
        Args:
            query: Search query
            count: Number of results
            
        Returns:
            ProviderResult with image results
        """
        try:
            await self.ensure_initialized()
            
            params = {
                "q": query,
                "count": min(count, 20),
                "country": self.config.country,
                "search_lang": self.config.search_lang,
                "safesearch": self.config.safe_search
            }
            
            response = await self._client.get("/images/search", params=params)
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="image_search",
                data={
                    "query": query,
                    "results": [
                        {
                            "title": r.get("title"),
                            "url": r.get("url"),
                            "source": r.get("source"),
                            "thumbnail": r.get("thumbnail", {}).get("src"),
                            "properties": r.get("properties", {})
                        }
                        for r in data.get("results", [])
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"Brave image_search error: {e}")
            return self._error("image_search", str(e), query=query)
    
    async def video_search(
        self,
        query: str,
        count: int = 10,
        freshness: str = None
    ) -> ProviderResult:
        """
        Search for videos.
        
        Args:
            query: Search query
            count: Number of results
            freshness: Time filter
            
        Returns:
            ProviderResult with video results
        """
        try:
            await self.ensure_initialized()
            
            params = {
                "q": query,
                "count": min(count, 20),
                "country": self.config.country,
                "search_lang": self.config.search_lang
            }
            
            if freshness:
                params["freshness"] = freshness
            
            response = await self._client.get("/videos/search", params=params)
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="video_search",
                data={
                    "query": query,
                    "results": [
                        {
                            "title": r.get("title"),
                            "url": r.get("url"),
                            "description": r.get("description"),
                            "age": r.get("age"),
                            "creator": r.get("meta_url", {}).get("hostname"),
                            "thumbnail": r.get("thumbnail", {}).get("src"),
                            "video": r.get("video", {})
                        }
                        for r in data.get("results", [])
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"Brave video_search error: {e}")
            return self._error("video_search", str(e), query=query)
    
    async def suggest(self, query: str) -> ProviderResult:
        """
        Get search suggestions.
        
        Args:
            query: Partial query
            
        Returns:
            ProviderResult with suggestions
        """
        try:
            await self.ensure_initialized()
            
            response = await self._client.get(
                "/suggest/search",
                params={"q": query, "count": 10}
            )
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="suggest",
                data={
                    "query": query,
                    "suggestions": [
                        r.get("query") for r in data.get("results", [])
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"Brave suggest error: {e}")
            return self._error("suggest", str(e), query=query)
    
    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
