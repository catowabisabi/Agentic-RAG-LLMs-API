"""
MCP Providers Package

Contains integrations with external services:
- Web RAG: Firecrawl, Exa, Brave Search
- Database: Supabase, Pinecone, SQLite, PostgreSQL
- Code Execution: E2B
- Automation: Zapier, n8n, GitHub
- File Control: Excel, TXT, PDF, CSV, JSON
- Communication: Gmail, Telegram, WhatsApp
- System: Local CMD/Terminal execution
"""

from .base_provider import BaseProvider
from .firecrawl_provider import FirecrawlProvider
from .exa_provider import ExaProvider
from .brave_search_provider import BraveSearchProvider
from .supabase_provider import SupabaseProvider
from .e2b_provider import E2BProvider
from .zapier_provider import ZapierProvider
from .github_provider import GitHubProvider

# New providers (January 2026)
from .file_control_provider import FileControlProvider
from .database_provider import DatabaseControlProvider
from .communication_provider import CommunicationProvider
from .system_command_provider import SystemCommandProvider

__all__ = [
    'BaseProvider',
    'FirecrawlProvider',
    'ExaProvider',
    'BraveSearchProvider',
    'SupabaseProvider',
    'E2BProvider',
    'ZapierProvider',
    'GitHubProvider',
    # New providers
    'FileControlProvider',
    'DatabaseControlProvider',
    'CommunicationProvider',
    'SystemCommandProvider'
]
