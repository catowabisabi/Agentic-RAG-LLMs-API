"""
MCP Providers Package

Contains integrations with external services:
- Web RAG: Firecrawl, Exa, Brave Search
- Database: Supabase, Pinecone
- Code Execution: E2B
- Automation: Zapier, n8n, GitHub
"""

from .base_provider import BaseProvider
from .firecrawl_provider import FirecrawlProvider
from .exa_provider import ExaProvider
from .brave_search_provider import BraveSearchProvider
from .supabase_provider import SupabaseProvider
from .e2b_provider import E2BProvider
from .zapier_provider import ZapierProvider
from .github_provider import GitHubProvider

__all__ = [
    'BaseProvider',
    'FirecrawlProvider',
    'ExaProvider',
    'BraveSearchProvider',
    'SupabaseProvider',
    'E2BProvider',
    'ZapierProvider',
    'GitHubProvider'
]
