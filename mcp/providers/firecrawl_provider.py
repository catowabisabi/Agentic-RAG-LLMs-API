"""
Firecrawl Provider

Converts web pages to clean Markdown for RAG.
Excellent for extracting content from complex websites.

Features:
- Full page crawling
- Clean Markdown output
- JavaScript rendering
- Rate limiting support
"""

import logging
import asyncio
from typing import Dict, Any, List, Optional

import httpx

from .base_provider import BaseProvider, ProviderConfig, ProviderResult

logger = logging.getLogger(__name__)


class FirecrawlConfig(ProviderConfig):
    """Configuration for Firecrawl"""
    base_url: str = "https://api.firecrawl.dev/v0"
    include_raw_html: bool = False
    wait_for_selector: Optional[str] = None
    screenshot: bool = False


class FirecrawlProvider(BaseProvider):
    """
    Firecrawl provider for web scraping and content extraction.
    
    Capabilities:
    - scrape: Scrape a single URL
    - crawl: Crawl entire website
    - search: Search and scrape
    """
    
    def __init__(self, config: FirecrawlConfig = None):
        super().__init__(config or FirecrawlConfig())
        self.config: FirecrawlConfig = self.config
        self._client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self) -> bool:
        """Initialize the Firecrawl client"""
        try:
            if not self.config.api_key:
                logger.warning("Firecrawl API key not configured")
                return False
            
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                timeout=self.config.timeout
            )
            
            self._initialized = True
            logger.info("Firecrawl provider initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Firecrawl: {e}")
            return False
    
    async def health_check(self) -> bool:
        """Check if Firecrawl API is available"""
        try:
            await self.ensure_initialized()
            # Simple health check by checking if we can reach the API
            response = await self._client.get("/")
            self._is_healthy = response.status_code < 500
            return self._is_healthy
        except Exception as e:
            logger.error(f"Firecrawl health check failed: {e}")
            self._is_healthy = False
            return False
    
    def get_capabilities(self) -> List[str]:
        """Get available operations"""
        return ["scrape", "crawl", "search", "map"]
    
    async def scrape(
        self, 
        url: str,
        formats: List[str] = None,
        only_main_content: bool = True,
        include_tags: List[str] = None,
        exclude_tags: List[str] = None
    ) -> ProviderResult:
        """
        Scrape a single URL and convert to Markdown.
        
        Args:
            url: URL to scrape
            formats: Output formats (markdown, html, rawHtml, links)
            only_main_content: Extract only main content
            include_tags: HTML tags to include
            exclude_tags: HTML tags to exclude
            
        Returns:
            ProviderResult with scraped content
        """
        try:
            await self.ensure_initialized()
            
            payload = {
                "url": url,
                "formats": formats or ["markdown"],
                "onlyMainContent": only_main_content
            }
            
            if include_tags:
                payload["includeTags"] = include_tags
            if exclude_tags:
                payload["excludeTags"] = exclude_tags
            
            response = await self._client.post("/scrape", json=payload)
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="scrape",
                data={
                    "url": url,
                    "markdown": data.get("data", {}).get("markdown", ""),
                    "metadata": data.get("data", {}).get("metadata", {}),
                    "links": data.get("data", {}).get("links", [])
                }
            )
            
        except httpx.HTTPError as e:
            logger.error(f"Firecrawl scrape error: {e}")
            return self._error("scrape", str(e), url=url)
        except Exception as e:
            logger.error(f"Firecrawl scrape error: {e}")
            return self._error("scrape", str(e), url=url)
    
    async def crawl(
        self,
        url: str,
        max_depth: int = 2,
        max_pages: int = 10,
        include_patterns: List[str] = None,
        exclude_patterns: List[str] = None
    ) -> ProviderResult:
        """
        Crawl an entire website.
        
        Args:
            url: Starting URL
            max_depth: Maximum crawl depth
            max_pages: Maximum pages to crawl
            include_patterns: URL patterns to include
            exclude_patterns: URL patterns to exclude
            
        Returns:
            ProviderResult with crawled content
        """
        try:
            await self.ensure_initialized()
            
            payload = {
                "url": url,
                "maxDepth": max_depth,
                "limit": max_pages
            }
            
            if include_patterns:
                payload["includePaths"] = include_patterns
            if exclude_patterns:
                payload["excludePaths"] = exclude_patterns
            
            # Start crawl job
            response = await self._client.post("/crawl", json=payload)
            response.raise_for_status()
            
            job_data = response.json()
            job_id = job_data.get("id")
            
            if not job_id:
                return self._error("crawl", "No job ID returned")
            
            # Poll for completion
            pages = []
            for _ in range(60):  # Max 60 seconds
                status_response = await self._client.get(f"/crawl/{job_id}")
                status_data = status_response.json()
                
                if status_data.get("status") == "completed":
                    pages = status_data.get("data", [])
                    break
                elif status_data.get("status") == "failed":
                    return self._error("crawl", "Crawl job failed")
                
                await asyncio.sleep(1)
            
            return self._success(
                operation="crawl",
                data={
                    "url": url,
                    "pages_crawled": len(pages),
                    "pages": [
                        {
                            "url": p.get("metadata", {}).get("sourceURL"),
                            "title": p.get("metadata", {}).get("title"),
                            "markdown": p.get("markdown", "")[:500]  # Preview
                        }
                        for p in pages
                    ]
                }
            )
            
        except Exception as e:
            logger.error(f"Firecrawl crawl error: {e}")
            return self._error("crawl", str(e), url=url)
    
    async def map_site(self, url: str) -> ProviderResult:
        """
        Get a sitemap of all URLs on a website.
        
        Args:
            url: Website URL
            
        Returns:
            ProviderResult with list of URLs
        """
        try:
            await self.ensure_initialized()
            
            response = await self._client.post("/map", json={"url": url})
            response.raise_for_status()
            
            data = response.json()
            
            return self._success(
                operation="map",
                data={
                    "url": url,
                    "links": data.get("links", [])
                }
            )
            
        except Exception as e:
            logger.error(f"Firecrawl map error: {e}")
            return self._error("map", str(e), url=url)
    
    async def close(self):
        """Close the HTTP client"""
        if self._client:
            await self._client.aclose()
