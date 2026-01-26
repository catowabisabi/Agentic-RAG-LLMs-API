"""
MCP Services Package

Service layers for provider integrations:
- Web Scraping Service
- Database Service
- Code Execution Service
- Automation Service
- Medical RAG Service (PubMed, Clinical Trials, Drug Lookup)
- Accounting Regulations Data (HK, China, Canada)
"""

from .web_scraping_service import WebScrapingService
from .database_service import DatabaseService
from .code_execution_service import CodeExecutionService
from .automation_service import AutomationService

# New services (January 2026)
from .medical_rag_service import MedicalRAGService
from .accounting_regulations_data import (
    get_all_regulations,
    get_regulations_by_jurisdiction,
    prepare_for_rag_ingestion,
    ingest_regulations_to_rag,
    HONG_KONG_REGULATIONS,
    CHINA_REGULATIONS,
    CANADA_REGULATIONS
)

__all__ = [
    'WebScrapingService',
    'DatabaseService',
    'CodeExecutionService',
    'AutomationService',
    # New services
    'MedicalRAGService',
    'get_all_regulations',
    'get_regulations_by_jurisdiction',
    'prepare_for_rag_ingestion',
    'ingest_regulations_to_rag',
    'HONG_KONG_REGULATIONS',
    'CHINA_REGULATIONS',
    'CANADA_REGULATIONS'
]
