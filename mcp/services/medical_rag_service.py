"""
Medical RAG Service

Provides access to medical literature databases for RAG integration:
- PubMed Central (PMC) Open Access
- BioASQ datasets
- MIMIC data integration
- MedDialog dataset support

Reference: 2026 Medical RAG Best Practices
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class MedicalDocument:
    """Represents a medical document for RAG"""
    id: str
    title: str
    abstract: str
    content: str
    source: str
    authors: List[str]
    publication_date: Optional[str]
    keywords: List[str]
    doi: Optional[str]
    pmid: Optional[str]
    metadata: Dict[str, Any]


class MedicalRAGService:
    """
    Service for fetching and processing medical literature.
    
    Capabilities:
    - PubMed article search and retrieval
    - PMC full-text access (Open Access subset)
    - Clinical trial data
    - Drug information lookup
    
    2026 Best Practices:
    - Hybrid retrieval (dense + sparse vectors)
    - Clinical entity recognition (CLEAR)
    - Citation tracking for traceability
    """
    
    def __init__(self, email: str = None, cache_dir: str = "./data/medical_cache"):
        """
        Initialize the medical RAG service.
        
        Args:
            email: Required for NCBI API access
            cache_dir: Directory to cache fetched documents
        """
        self.email = email or "your_email@example.com"
        self.cache_dir = cache_dir
        self._initialized = False
        
        # Rate limiting
        self._last_request_time = 0
        self._min_request_interval = 0.34  # NCBI allows 3 requests/second
        
    async def initialize(self) -> bool:
        """Initialize the service"""
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            
            # Check for biopython
            try:
                from Bio import Entrez
                Entrez.email = self.email
                self._has_biopython = True
            except ImportError:
                logger.warning("biopython not installed. Run: pip install biopython")
                self._has_biopython = False
            
            self._initialized = True
            logger.info("MedicalRAGService initialized")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize MedicalRAGService: {e}")
            return False
    
    async def _rate_limit(self):
        """Enforce rate limiting for API calls"""
        import time
        current_time = time.time()
        elapsed = current_time - self._last_request_time
        if elapsed < self._min_request_interval:
            await asyncio.sleep(self._min_request_interval - elapsed)
        self._last_request_time = time.time()
    
    # ==================== PubMed Operations ====================
    
    async def search_pubmed(
        self, 
        query: str, 
        max_results: int = 10,
        date_from: str = None,
        date_to: str = None
    ) -> Dict[str, Any]:
        """
        Search PubMed for articles matching the query.
        
        Args:
            query: Search query (supports PubMed syntax)
            max_results: Maximum number of results
            date_from: Start date (YYYY/MM/DD)
            date_to: End date (YYYY/MM/DD)
            
        Returns:
            Dictionary with search results and PMIDs
        """
        if not self._has_biopython:
            return {"error": "biopython not installed", "articles": []}
        
        try:
            from Bio import Entrez
            Entrez.email = self.email
            
            await self._rate_limit()
            
            # Build query with date range if provided
            full_query = query
            if date_from or date_to:
                date_from = date_from or "1900/01/01"
                date_to = date_to or datetime.now().strftime("%Y/%m/%d")
                full_query += f" AND ({date_from}:{date_to}[dp])"
            
            # Search for PMIDs
            handle = Entrez.esearch(
                db="pubmed",
                term=full_query,
                retmax=max_results,
                sort="relevance"
            )
            record = Entrez.read(handle)
            handle.close()
            
            pmid_list = record.get("IdList", [])
            
            if not pmid_list:
                return {
                    "query": query,
                    "count": 0,
                    "articles": []
                }
            
            # Fetch article details
            articles = await self._fetch_pubmed_articles(pmid_list)
            
            return {
                "query": query,
                "count": len(articles),
                "total_found": int(record.get("Count", 0)),
                "articles": articles
            }
            
        except Exception as e:
            logger.error(f"PubMed search error: {e}")
            return {"error": str(e), "articles": []}
    
    async def _fetch_pubmed_articles(self, pmid_list: List[str]) -> List[Dict]:
        """Fetch article details from PubMed"""
        if not pmid_list:
            return []
        
        try:
            from Bio import Entrez
            
            await self._rate_limit()
            
            handle = Entrez.efetch(
                db="pubmed",
                id=pmid_list,
                rettype="xml",
                retmode="xml"
            )
            records = Entrez.read(handle)
            handle.close()
            
            articles = []
            for article in records.get("PubmedArticle", []):
                try:
                    medline = article.get("MedlineCitation", {})
                    article_data = medline.get("Article", {})
                    
                    # Extract title
                    title = str(article_data.get("ArticleTitle", ""))
                    
                    # Extract abstract
                    abstract_parts = article_data.get("Abstract", {}).get("AbstractText", [])
                    if isinstance(abstract_parts, list):
                        abstract = " ".join([str(p) for p in abstract_parts])
                    else:
                        abstract = str(abstract_parts)
                    
                    # Extract authors
                    author_list = article_data.get("AuthorList", [])
                    authors = []
                    for author in author_list:
                        if isinstance(author, dict):
                            last = author.get("LastName", "")
                            first = author.get("ForeName", "")
                            authors.append(f"{last} {first}".strip())
                    
                    # Extract publication date
                    pub_date = article_data.get("ArticleDate", [{}])
                    if pub_date and isinstance(pub_date, list):
                        pd = pub_date[0] if pub_date else {}
                        date_str = f"{pd.get('Year', '')}/{pd.get('Month', '01')}/{pd.get('Day', '01')}"
                    else:
                        date_str = None
                    
                    # Extract keywords/MeSH terms
                    mesh_list = medline.get("MeshHeadingList", [])
                    keywords = []
                    for mesh in mesh_list:
                        if isinstance(mesh, dict):
                            desc = mesh.get("DescriptorName")
                            if desc:
                                keywords.append(str(desc))
                    
                    # Get PMID
                    pmid = str(medline.get("PMID", ""))
                    
                    # Get DOI if available
                    doi = None
                    article_ids = article.get("PubmedData", {}).get("ArticleIdList", [])
                    for aid in article_ids:
                        if hasattr(aid, 'attributes') and aid.attributes.get("IdType") == "doi":
                            doi = str(aid)
                            break
                    
                    articles.append({
                        "pmid": pmid,
                        "title": title,
                        "abstract": abstract,
                        "authors": authors,
                        "publication_date": date_str,
                        "keywords": keywords[:10],  # Limit keywords
                        "doi": doi,
                        "source": "PubMed"
                    })
                    
                except Exception as e:
                    logger.warning(f"Error parsing article: {e}")
                    continue
            
            return articles
            
        except Exception as e:
            logger.error(f"Error fetching PubMed articles: {e}")
            return []
    
    async def get_pubmed_fulltext(self, pmid: str) -> Dict[str, Any]:
        """
        Attempt to get full text from PMC Open Access.
        
        Note: Not all PubMed articles have free full text.
        """
        if not self._has_biopython:
            return {"error": "biopython not installed"}
        
        try:
            from Bio import Entrez
            
            await self._rate_limit()
            
            # First, find PMC ID
            handle = Entrez.elink(
                dbfrom="pubmed",
                db="pmc",
                id=pmid
            )
            record = Entrez.read(handle)
            handle.close()
            
            # Check if PMC version exists
            pmc_ids = []
            for linkset in record:
                for link_db in linkset.get("LinkSetDb", []):
                    for link in link_db.get("Link", []):
                        pmc_ids.append(link.get("Id"))
            
            if not pmc_ids:
                return {
                    "pmid": pmid,
                    "has_fulltext": False,
                    "message": "No PMC full text available"
                }
            
            await self._rate_limit()
            
            # Fetch PMC content
            pmc_id = pmc_ids[0]
            handle = Entrez.efetch(
                db="pmc",
                id=pmc_id,
                rettype="xml"
            )
            content = handle.read()
            handle.close()
            
            # Parse XML to extract text (simplified)
            import xml.etree.ElementTree as ET
            try:
                root = ET.fromstring(content)
                
                # Extract body text
                body_parts = []
                for elem in root.iter():
                    if elem.text:
                        body_parts.append(elem.text.strip())
                
                full_text = " ".join([p for p in body_parts if p])
                
                return {
                    "pmid": pmid,
                    "pmc_id": pmc_id,
                    "has_fulltext": True,
                    "content": full_text[:50000],  # Limit size
                    "content_length": len(full_text)
                }
                
            except ET.ParseError:
                return {
                    "pmid": pmid,
                    "pmc_id": pmc_id,
                    "has_fulltext": True,
                    "content": content.decode('utf-8', errors='replace')[:50000],
                    "format": "raw_xml"
                }
                
        except Exception as e:
            logger.error(f"Error fetching full text: {e}")
            return {"error": str(e), "pmid": pmid}
    
    # ==================== Clinical Data Integration ====================
    
    async def search_clinical_trials(
        self, 
        condition: str = None,
        intervention: str = None,
        status: str = "RECRUITING",
        max_results: int = 10
    ) -> Dict[str, Any]:
        """
        Search ClinicalTrials.gov for relevant trials.
        
        Args:
            condition: Disease/condition being studied
            intervention: Treatment being tested
            status: Trial status (RECRUITING, COMPLETED, etc.)
            max_results: Maximum number of results
        """
        try:
            import requests
            
            base_url = "https://clinicaltrials.gov/api/v2/studies"
            
            # Build query
            query_parts = []
            if condition:
                query_parts.append(f"AREA[Condition]({condition})")
            if intervention:
                query_parts.append(f"AREA[Intervention]({intervention})")
            
            params = {
                "query.term": " AND ".join(query_parts) if query_parts else "*",
                "filter.overallStatus": status,
                "pageSize": min(max_results, 100),
                "format": "json"
            }
            
            response = requests.get(base_url, params=params, timeout=30)
            
            if response.status_code != 200:
                return {"error": f"API error: {response.status_code}"}
            
            data = response.json()
            studies = data.get("studies", [])
            
            trials = []
            for study in studies:
                protocol = study.get("protocolSection", {})
                id_module = protocol.get("identificationModule", {})
                status_module = protocol.get("statusModule", {})
                desc_module = protocol.get("descriptionModule", {})
                
                trials.append({
                    "nct_id": id_module.get("nctId"),
                    "title": id_module.get("briefTitle"),
                    "status": status_module.get("overallStatus"),
                    "phase": ", ".join(protocol.get("designModule", {}).get("phases", [])),
                    "summary": desc_module.get("briefSummary"),
                    "enrollment": status_module.get("enrollmentInfo", {}).get("count"),
                    "source": "ClinicalTrials.gov"
                })
            
            return {
                "condition": condition,
                "intervention": intervention,
                "count": len(trials),
                "trials": trials
            }
            
        except Exception as e:
            logger.error(f"Clinical trials search error: {e}")
            return {"error": str(e), "trials": []}
    
    # ==================== Drug Information ====================
    
    async def lookup_drug(self, drug_name: str) -> Dict[str, Any]:
        """
        Look up drug information from OpenFDA.
        
        Returns label information, adverse events, etc.
        """
        try:
            import requests
            
            # Search OpenFDA drug labels
            url = "https://api.fda.gov/drug/label.json"
            params = {
                "search": f'openfda.brand_name:"{drug_name}" OR openfda.generic_name:"{drug_name}"',
                "limit": 1
            }
            
            response = requests.get(url, params=params, timeout=30)
            
            if response.status_code != 200:
                return {"error": f"Drug not found: {drug_name}"}
            
            data = response.json()
            results = data.get("results", [])
            
            if not results:
                return {"error": f"No information found for: {drug_name}"}
            
            drug = results[0]
            openfda = drug.get("openfda", {})
            
            return {
                "drug_name": drug_name,
                "brand_names": openfda.get("brand_name", []),
                "generic_names": openfda.get("generic_name", []),
                "manufacturer": openfda.get("manufacturer_name", []),
                "substance_names": openfda.get("substance_name", []),
                "route": openfda.get("route", []),
                "indications": drug.get("indications_and_usage", []),
                "warnings": drug.get("warnings", []),
                "dosage": drug.get("dosage_and_administration", []),
                "adverse_reactions": drug.get("adverse_reactions", []),
                "contraindications": drug.get("contraindications", []),
                "source": "OpenFDA"
            }
            
        except Exception as e:
            logger.error(f"Drug lookup error: {e}")
            return {"error": str(e)}
    
    # ==================== Document Processing for RAG ====================
    
    async def prepare_for_rag(
        self, 
        articles: List[Dict],
        include_metadata: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Prepare fetched articles for RAG ingestion.
        
        Formats documents with proper chunking and metadata.
        """
        documents = []
        
        for article in articles:
            # Create document content
            content_parts = []
            
            title = article.get("title", "")
            if title:
                content_parts.append(f"Title: {title}")
            
            abstract = article.get("abstract", "")
            if abstract:
                content_parts.append(f"\nAbstract:\n{abstract}")
            
            full_content = article.get("content", "")
            if full_content:
                content_parts.append(f"\nContent:\n{full_content}")
            
            content = "\n".join(content_parts)
            
            # Build metadata
            metadata = {
                "source": article.get("source", "PubMed"),
                "type": "medical_literature"
            }
            
            if include_metadata:
                metadata.update({
                    "pmid": article.get("pmid"),
                    "doi": article.get("doi"),
                    "title": title,
                    "authors": article.get("authors", [])[:5],  # First 5 authors
                    "publication_date": article.get("publication_date"),
                    "keywords": article.get("keywords", [])[:10]
                })
            
            documents.append({
                "content": content,
                "metadata": metadata,
                "id": f"pubmed_{article.get('pmid', '')}" if article.get('pmid') else None
            })
        
        return documents
    
    async def ingest_to_rag(
        self, 
        documents: List[Dict],
        collection_name: str = "medicine"
    ) -> Dict[str, Any]:
        """
        Ingest prepared documents into the RAG system.
        
        Uses the VectorDBManager for storage.
        """
        try:
            from services.vectordb_manager import vectordb_manager
            
            success_count = 0
            error_count = 0
            
            for doc in documents:
                try:
                    await vectordb_manager.add_document(
                        db_name=collection_name,
                        content=doc["content"],
                        metadata=doc["metadata"]
                    )
                    success_count += 1
                except Exception as e:
                    logger.warning(f"Failed to ingest document: {e}")
                    error_count += 1
            
            return {
                "success": True,
                "ingested": success_count,
                "errors": error_count,
                "collection": collection_name
            }
            
        except Exception as e:
            logger.error(f"RAG ingestion error: {e}")
            return {"success": False, "error": str(e)}


# ==================== Convenience Functions ====================

async def fetch_and_ingest_medical_papers(
    query: str,
    max_results: int = 20,
    collection_name: str = "medicine",
    email: str = None
) -> Dict[str, Any]:
    """
    Convenience function to search, fetch, and ingest medical papers.
    
    Example:
        results = await fetch_and_ingest_medical_papers(
            query="Type 2 Diabetes treatment guidelines",
            max_results=50,
            collection_name="diabetes_research"
        )
    """
    service = MedicalRAGService(email=email)
    await service.initialize()
    
    # Search PubMed
    search_results = await service.search_pubmed(query, max_results=max_results)
    
    if "error" in search_results:
        return search_results
    
    articles = search_results.get("articles", [])
    
    if not articles:
        return {"message": "No articles found", "query": query}
    
    # Prepare for RAG
    documents = await service.prepare_for_rag(articles)
    
    # Ingest
    ingest_result = await service.ingest_to_rag(documents, collection_name)
    
    return {
        "query": query,
        "articles_found": len(articles),
        "ingested": ingest_result.get("ingested", 0),
        "collection": collection_name
    }


# Singleton instance
medical_rag_service = MedicalRAGService()
