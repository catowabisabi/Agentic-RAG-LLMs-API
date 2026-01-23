"""
Web Scraping Service

Unified service for web content extraction.
Combines Firecrawl, Exa, and Brave Search providers.

Features:
- Smart provider selection
- Content caching
- Rate limiting
- Fallback handling
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from mcp.providers.firecrawl_provider import FirecrawlProvider, FirecrawlConfig
from mcp.providers.exa_provider import ExaProvider, ExaConfig
from mcp.providers.brave_search_provider import BraveSearchProvider, BraveSearchConfig

logger = logging.getLogger(__name__)


class WebScrapingService:
    """
    Unified web scraping and search service.
    
    Automatically selects the best provider based on the task:
    - Firecrawl: Best for full page scraping
    - Exa: Best for semantic search with content
    - Brave: Best for general web search
    """
    
    def __init__(
        self,
        firecrawl_api_key: str = None,
        exa_api_key: str = None,
        brave_api_key: str = None
    ):
        self._firecrawl: Optional[FirecrawlProvider] = None
        self._exa: Optional[ExaProvider] = None
        self._brave: Optional[BraveSearchProvider] = None
        
        # Initialize providers with API keys
        if firecrawl_api_key:
            config = FirecrawlConfig(api_key=firecrawl_api_key)
            self._firecrawl = FirecrawlProvider(config)
        
        if exa_api_key:
            config = ExaConfig(api_key=exa_api_key)
            self._exa = ExaProvider(config)
        
        if brave_api_key:
            config = BraveSearchConfig(api_key=brave_api_key)
            self._brave = BraveSearchProvider(config)
        
        # Simple cache
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = timedelta(minutes=30)
        
        logger.info("WebScrapingService initialized")
    
    async def initialize(self):
        """Initialize all configured providers"""
        tasks = []
        
        if self._firecrawl:
            tasks.append(self._firecrawl.initialize())
        if self._exa:
            tasks.append(self._exa.initialize())
        if self._brave:
            tasks.append(self._brave.initialize())
        
        if tasks:
            await asyncio.gather(*tasks)
    
    def _get_cache(self, key: str) -> Optional[Any]:
        """Get cached result if not expired"""
        if key in self._cache:
            entry = self._cache[key]
            if datetime.now() - entry["timestamp"] < self._cache_ttl:
                return entry["data"]
            else:
                del self._cache[key]
        return None
    
    def _set_cache(self, key: str, data: Any):
        """Cache a result"""
        self._cache[key] = {
            "data": data,
            "timestamp": datetime.now()
        }
    
    async def scrape_url(
        self,
        url: str,
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Scrape a URL and return clean content.
        
        Uses Firecrawl if available, falls back to Exa.
        
        Args:
            url: URL to scrape
            use_cache: Whether to use cached results
            
        Returns:
            Dict with markdown content and metadata
        """
        cache_key = f"scrape:{url}"
        
        if use_cache:
            cached = self._get_cache(cache_key)
            if cached:
                return cached
        
        result = None
        
        # Try Firecrawl first (best for full page scraping)
        if self._firecrawl and self._firecrawl._initialized:
            try:
                result = await self._firecrawl.scrape(url)
                if result.success:
                    self._set_cache(cache_key, result.data)
                    return result.data
            except Exception as e:
                logger.warning(f"Firecrawl scrape failed: {e}")
        
        # Fall back to Exa
        if self._exa and self._exa._initialized:
            try:
                result = await self._exa.get_contents([url])
                if result.success and result.data.get("results"):
                    data = {
                        "url": url,
                        "markdown": result.data["results"][0].get("text", ""),
                        "metadata": {"source": "exa"}
                    }
                    self._set_cache(cache_key, data)
                    return data
            except Exception as e:
                logger.warning(f"Exa content fetch failed: {e}")
        
        return {"url": url, "error": "No provider available"}
    
    async def search(
        self,
        query: str,
        num_results: int = 10,
        include_content: bool = False,
        search_type: str = "auto"  # auto, semantic, keyword, news
    ) -> Dict[str, Any]:
        """
        Search the web.
        
        Args:
            query: Search query
            num_results: Number of results
            include_content: Include content in results
            search_type: Type of search
            
        Returns:
            Search results
        """
        cache_key = f"search:{query}:{num_results}:{include_content}:{search_type}"
        cached = self._get_cache(cache_key)
        if cached:
            return cached
        
        # Determine best provider based on search type
        if search_type == "semantic" or (search_type == "auto" and include_content):
            # Exa is best for semantic search with content
            if self._exa and self._exa._initialized:
                try:
                    if include_content:
                        result = await self._exa.search_and_contents(
                            query, 
                            num_results=num_results
                        )
                    else:
                        result = await self._exa.search(query, num_results=num_results)
                    
                    if result.success:
                        self._set_cache(cache_key, result.data)
                        return result.data
                except Exception as e:
                    logger.warning(f"Exa search failed: {e}")
        
        elif search_type == "news":
            # Brave for news
            if self._brave and self._brave._initialized:
                try:
                    result = await self._brave.news_search(query, count=num_results)
                    if result.success:
                        self._set_cache(cache_key, result.data)
                        return result.data
                except Exception as e:
                    logger.warning(f"Brave news search failed: {e}")
        
        # Default/fallback to Brave web search
        if self._brave and self._brave._initialized:
            try:
                result = await self._brave.web_search(query, count=num_results)
                if result.success:
                    self._set_cache(cache_key, result.data)
                    return result.data
            except Exception as e:
                logger.warning(f"Brave search failed: {e}")
        
        # Final fallback to Exa basic search
        if self._exa and self._exa._initialized:
            try:
                result = await self._exa.search(query, num_results=num_results)
                if result.success:
                    self._set_cache(cache_key, result.data)
                    return result.data
            except Exception as e:
                logger.warning(f"Exa fallback search failed: {e}")
        
        return {"query": query, "error": "No search provider available"}
    
    async def crawl_site(
        self,
        url: str,
        max_pages: int = 10,
        max_depth: int = 2
    ) -> Dict[str, Any]:
        """
        Crawl an entire website.
        
        Args:
            url: Starting URL
            max_pages: Maximum pages to crawl
            max_depth: Maximum crawl depth
            
        Returns:
            Crawled content
        """
        if not self._firecrawl or not self._firecrawl._initialized:
            return {"url": url, "error": "Firecrawl not available"}
        
        try:
            result = await self._firecrawl.crawl(
                url, 
                max_pages=max_pages, 
                max_depth=max_depth
            )
            if result.success:
                return result.data
            return {"url": url, "error": result.error}
        except Exception as e:
            logger.error(f"Crawl error: {e}")
            return {"url": url, "error": str(e)}
    
    async def find_similar(
        self,
        url: str,
        num_results: int = 5
    ) -> Dict[str, Any]:
        """
        Find content similar to a URL.
        
        Args:
            url: Source URL
            num_results: Number of results
            
        Returns:
            Similar content
        """
        if not self._exa or not self._exa._initialized:
            return {"url": url, "error": "Exa not available"}
        
        try:
            result = await self._exa.find_similar(url, num_results=num_results)
            if result.success:
                return result.data
            return {"url": url, "error": result.error}
        except Exception as e:
            logger.error(f"Find similar error: {e}")
            return {"url": url, "error": str(e)}
    
    async def smart_research(
        self,
        topic: str,
        depth: str = "normal"  # quick, normal, deep
    ) -> Dict[str, Any]:
        """
        Perform comprehensive research on a topic.
        
        Combines multiple providers for thorough research.
        
        Args:
            topic: Research topic
            depth: Research depth
            
        Returns:
            Research results
        """
        results = {
            "topic": topic,
            "search_results": [],
            "content": [],
            "related": []
        }
        
        # Number of results based on depth
        num_results = {"quick": 5, "normal": 10, "deep": 20}.get(depth, 10)
        
        # 1. Search for the topic
        search_result = await self.search(
            topic, 
            num_results=num_results, 
            include_content=True,
            search_type="semantic"
        )
        
        if "results" in search_result:
            results["search_results"] = search_result["results"]
        
        # 2. For deep research, get full content of top results
        if depth == "deep" and results["search_results"]:
            top_urls = [r.get("url") for r in results["search_results"][:3] if r.get("url")]
            
            content_tasks = [self.scrape_url(url) for url in top_urls]
            contents = await asyncio.gather(*content_tasks, return_exceptions=True)
            
            for content in contents:
                if isinstance(content, dict) and "markdown" in content:
                    results["content"].append(content)
        
        # 3. Find related content
        if results["search_results"] and self._exa:
            first_url = results["search_results"][0].get("url")
            if first_url:
                similar = await self.find_similar(first_url, num_results=3)
                if "results" in similar:
                    results["related"] = similar["results"]
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """Get service status"""
        return {
            "firecrawl": self._firecrawl.get_status() if self._firecrawl else {"available": False},
            "exa": self._exa.get_status() if self._exa else {"available": False},
            "brave": self._brave.get_status() if self._brave else {"available": False},
            "cache_size": len(self._cache)
        }
    
    async def close(self):
        """Close all providers"""
        tasks = []
        
        if self._firecrawl:
            tasks.append(self._firecrawl.close())
        if self._exa:
            tasks.append(self._exa.close())
        if self._brave:
            tasks.append(self._brave.close())
        
        if tasks:
            await asyncio.gather(*tasks)
