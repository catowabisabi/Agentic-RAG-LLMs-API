"""
Exa Provider

AI-native search engine that returns content blocks instead of links.
Ideal for RAG applications that need direct content access.

Features:
- Semantic search
- Content block returns
- Neural search
- Auto-prompt enhancement
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

import httpx

from .base_provider import BaseProvider, ProviderConfig, ProviderResult

logger = logging.getLogger(__name__)


class ExaConfig(ProviderConfig):
    """Configuration for Exa"""
    base_url: str = "https://api.exa.ai"
    use_autoprompt: bool = True
    num_results: int = 10


class ExaProvider(BaseProvider):
    """
    Exa provider for AI-native search.
    
    Capabilities:
    - search: Neural/keyword search
    - find_similar: Find similar content
    - get_contents: Get full content for URLs
    """
    
    def __init__(self, config: ExaConfig = None):
        super().__init__(config or ExaConfig())
        self.config: ExaConfig = self.config
        self._client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self) -> bool:
        """Initialize the Exa client"""
        try:
            if not self.config.api_key:
                logger.warning("Exa API key not configured")
                return False
            
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={"x-api-key": self.config.api_key},
                timeout=self.config.timeout
            )
            
            self._initialized = True
            logger.info("Exa provider initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Exa: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check if Exa API is available"""
        try:
            await self.ensure_initialized()
            # Simple search to verify API
            response = await self._client.post(
                "/search",
                json={"query": "test", "numResults": 1}
            )
            self._is_healthy = response.status_code == 200
            return self._is_healthy
        except Exception as e:
            logger.error(f"Exa health check failed: {e}")
            self._is_healthy = False
            return False
    
    def get_capabilities(self) -> List[str]:
        """Get available operations"""
        return ["search", "find_similar", "get_contents", "search_and_contents"]
    
    async def search(
        self,
        query: str,
        num_results: int = None,
        type: str = "neural",  # "neural" or "keyword"
        use_autoprompt: bool = None,
        include_domains: List[str] = None,
        exclude_domains: List[str] = None,
        start_published_date: str = None,
        end_published_date: str = None
    ) -> ProviderResult:
        """
        Search the web using Exa.
        
        Args:
            query: Search query
            num_results: Number of results
            type: Search type (neural/keyword)
            use_autoprompt: Enhance query with AI
            include_domains: Only search these domains
            exclude_domains: Exclude these domains
            start_published_date: Filter by publish date
            end_published_date: Filter by publish date
            
        Returns:
            ProviderResult with search results
        """
        try:
            await self.ensure_initialized()
            
            payload = {
                "query": query,
                "numResults": num_results or self.config.num_results,
                "type": type,
                "useAutoprompt": use_autoprompt if use_autoprompt is not None else self.config.use_autoprompt
            }
            
            if include_domains:
                payload["includeDomains"] = include_domains
            if exclude_domains:
                payload["excludeDomains"] = exclude_domains
            if start_published_date:
                payload["startPublishedDate"] = start_published_date
            if end_published_date:
                payload["endPublishedDate"] = end_published_date
            
            response = await self._client.post("/search", json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="search",
                data={
                    "query": query,
                    "autoprompt_string": data.get("autopromptString"),
                    "results": [
                        {
                            "url": r.get("url"),
                            "title": r.get("title"),
                            "score": r.get("score"),
                            "published_date": r.get("publishedDate"),
                            "author": r.get("author")
                        }
                        for r in data.get("results", [])
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"Exa search error: {e}")
            return self._error("search", str(e), query=query)
    
    async def search_and_contents(
        self,
        query: str,
        num_results: int = None,
        type: str = "neural",
        text_max_characters: int = 1000,
        highlights: bool = True
    ) -> ProviderResult:
        """
        Search and get content in one call.
        
        Args:
            query: Search query
            num_results: Number of results
            type: Search type
            text_max_characters: Max chars per result
            highlights: Include highlighted excerpts
            
        Returns:
            ProviderResult with search results and content
        """
        try:
            await self.ensure_initialized()
            
            payload = {
                "query": query,
                "numResults": num_results or self.config.num_results,
                "type": type,
                "contents": {
                    "text": {"maxCharacters": text_max_characters},
                    "highlights": {"query": query} if highlights else None
                }
            }
            
            response = await self._client.post("/search", json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="search_and_contents",
                data={
                    "query": query,
                    "results": [
                        {
                            "url": r.get("url"),
                            "title": r.get("title"),
                            "score": r.get("score"),
                            "text": r.get("text", ""),
                            "highlights": r.get("highlights", [])
                        }
                        for r in data.get("results", [])
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"Exa search_and_contents error: {e}")
            return self._error("search_and_contents", str(e), query=query)
    
    async def find_similar(
        self,
        url: str,
        num_results: int = None,
        include_domains: List[str] = None,
        exclude_domains: List[str] = None
    ) -> ProviderResult:
        """
        Find content similar to a given URL.
        
        Args:
            url: Source URL
            num_results: Number of results
            include_domains: Only search these domains
            exclude_domains: Exclude these domains
            
        Returns:
            ProviderResult with similar content
        """
        try:
            await self.ensure_initialized()
            
            payload = {
                "url": url,
                "numResults": num_results or self.config.num_results
            }
            
            if include_domains:
                payload["includeDomains"] = include_domains
            if exclude_domains:
                payload["excludeDomains"] = exclude_domains
            
            response = await self._client.post("/findSimilar", json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="find_similar",
                data={
                    "source_url": url,
                    "results": [
                        {
                            "url": r.get("url"),
                            "title": r.get("title"),
                            "score": r.get("score")
                        }
                        for r in data.get("results", [])
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"Exa find_similar error: {e}")
            return self._error("find_similar", str(e), url=url)
    
    async def get_contents(
        self,
        urls: List[str],
        text_max_characters: int = 3000,
        include_summary: bool = False
    ) -> ProviderResult:
        """
        Get full content for multiple URLs.
        
        Args:
            urls: List of URLs
            text_max_characters: Max chars per result
            include_summary: Include AI summary
            
        Returns:
            ProviderResult with content for each URL
        """
        try:
            await self.ensure_initialized()
            
            payload = {
                "ids": urls,
                "text": {"maxCharacters": text_max_characters}
            }
            
            if include_summary:
                payload["summary"] = True
            
            response = await self._client.post("/contents", json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="get_contents",
                data={
                    "urls": urls,
                    "results": [
                        {
                            "url": r.get("url"),
                            "title": r.get("title"),
                            "text": r.get("text", ""),
                            "summary": r.get("summary")
                        }
                        for r in data.get("results", [])
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"Exa get_contents error: {e}")
            return self._error("get_contents", str(e), urls=urls)
    
    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
