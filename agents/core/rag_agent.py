"""
RAG Agent

Handles Retrieval-Augmented Generation:
- Determines if RAG is needed for a task
- Performs document retrieval
- Provides retrieved context to other agents
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    MessageProtocol,
    TaskAssignment,
    ValidationResult
)
from tools.retriever import DocumentRetriever
from config.config import Config

logger = logging.getLogger(__name__)


class RAGDecision(BaseModel):
    """Decision on whether RAG is needed"""
    should_use_rag: bool = Field(description="Whether RAG retrieval is needed")
    reasoning: str = Field(description="Reasoning for the decision")
    search_queries: List[str] = Field(
        default_factory=list,
        description="Search queries to use if RAG is needed"
    )


class RAGAgent(BaseAgent):
    """
    RAG Agent for the multi-agent system.
    
    Responsibilities:
    - Determine if queries need RAG retrieval
    - Perform document retrieval
    - Check notes/memory before embedding
    - Provide retrieved context to requesting agents
    """
    
    def __init__(self, agent_name: str = "rag_agent"):
        super().__init__(
            agent_name=agent_name,
            agent_role="RAG Specialist",
            agent_description="Handles document retrieval and RAG decisions"
        )
        
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=0.1,
            api_key=self.config.OPENAI_API_KEY
        )
        self.retriever = DocumentRetriever()
        
        # Add custom message handlers
        self._message_handlers[MessageType.RAG_CHECK] = self._handle_rag_check
        
        logger.info("RAGAgent initialized")
    
    async def process_task(self, task: TaskAssignment) -> Any:
        """Process a RAG-related task"""
        task_type = task.task_type
        
        if task_type == "rag_check":
            return await self._check_if_rag_needed(task)
        elif task_type == "retrieve":
            return await self._retrieve_documents(task)
        elif task_type == "embed_and_store":
            return await self._embed_and_store(task)
        else:
            return await self._retrieve_documents(task)
    
    async def _check_if_rag_needed(self, task: TaskAssignment) -> Dict[str, Any]:
        """Check if RAG is needed for a query"""
        query = task.input_data.get("query", "")
        
        prompt = ChatPromptTemplate.from_template(
            """Analyze this query and determine if it requires retrieving information from a knowledge base.

Query: {query}

Consider:
1. Is this a factual question that requires specific knowledge?
2. Does it reference documents, data, or stored information?
3. Would retrieved context improve the answer quality?
4. Is this just a general conversation/greeting that doesn't need retrieval?

Respond with your decision."""
        )
        
        chain = prompt | self.llm.with_structured_output(RAGDecision)
        
        try:
            decision = await chain.ainvoke({"query": query})
            
            result = {
                "should_use_rag": decision.should_use_rag,
                "reasoning": decision.reasoning,
                "search_queries": decision.search_queries or [query]
            }
            
            # If RAG is needed, perform retrieval
            if decision.should_use_rag:
                # First check notes/memory
                notes_result = await self._check_notes_first(query)
                
                if notes_result:
                    result["notes"] = notes_result
                
                # Then perform document retrieval
                docs = await self._perform_retrieval(
                    decision.search_queries or [query]
                )
                result["documents"] = docs
            
            return result
            
        except Exception as e:
            logger.error(f"Error in RAG check: {e}")
            return {
                "should_use_rag": True,  # Default to yes on error
                "reasoning": f"Error in decision: {e}",
                "documents": []
            }
    
    async def _check_notes_first(self, query: str) -> Optional[List[Dict]]:
        """Check notes agent for relevant notes before retrieval"""
        # Request notes from notes agent
        message = AgentMessage(
            type=MessageType.QUERY,
            source_agent=self.agent_name,
            target_agent="notes_agent",
            content={"action": "search_notes", "query": query}
        )
        
        await self.ws_manager.send_to_agent(message)
        
        # Wait briefly for response (non-blocking continuation)
        await asyncio.sleep(0.5)
        
        # In a full implementation, we'd wait for the response
        # For now, return None and let retrieval proceed
        return None
    
    async def _perform_retrieval(
        self, 
        queries: List[str], 
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Perform document retrieval"""
        all_docs = []
        seen_ids = set()
        
        for query in queries:
            try:
                docs = self.retriever.retrieve(query=query, top_k=top_k)
                
                for doc in docs:
                    doc_id = doc.get("chunk_id", doc.get("content", "")[:50])
                    if doc_id not in seen_ids:
                        seen_ids.add(doc_id)
                        all_docs.append(doc)
                        
            except Exception as e:
                logger.error(f"Error retrieving for query '{query}': {e}")
        
        return all_docs[:top_k * 2]  # Limit total results
    
    async def _retrieve_documents(self, task: TaskAssignment) -> Dict[str, Any]:
        """Retrieve documents for a task"""
        query = task.input_data.get("query", task.description)
        top_k = task.input_data.get("top_k", self.config.TOP_K_RETRIEVAL)
        
        docs = await self._perform_retrieval([query], top_k)
        
        # Build context from retrieved documents
        context_parts = []
        sources = []
        
        for doc in docs:
            content = doc.get("content", "")
            metadata = doc.get("metadata", {})
            
            context_parts.append(content)
            sources.append({
                "content": content[:500],  # Truncate for sources
                "title": metadata.get("title", "Unknown"),
                "source": metadata.get("source", "RAG Database"),
                "doc_id": metadata.get("doc_id", ""),
                "score": doc.get("similarity_score", 0)
            })
        
        context = "\n\n---\n\n".join(context_parts) if context_parts else ""
        
        logger.info(f"[RAG] Retrieved {len(docs)} documents for query: {query[:50]}...")
        
        return {
            "query": query,
            "context": context,  # Combined context for thinking agent
            "sources": sources,  # Source metadata for response
            "documents": docs,   # Raw documents
            "count": len(docs)
        }
    
    async def _embed_and_store(self, task: TaskAssignment) -> Dict[str, Any]:
        """Embed and store new documents"""
        documents = task.input_data.get("documents", [])
        metadata = task.input_data.get("metadata", [])
        
        try:
            success = self.retriever.add_documents(documents, metadata)
            
            return {
                "success": success,
                "documents_added": len(documents) if success else 0
            }
            
        except Exception as e:
            logger.error(f"Error embedding documents: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _handle_rag_check(self, message: AgentMessage):
        """Handle RAG check requests from other agents"""
        query = message.content.get("query", "")
        requesting_agent = message.source_agent
        correlation_id = message.correlation_id or message.id
        
        logger.info(f"RAG check request from {requesting_agent}: {query[:50]}...")
        
        task = TaskAssignment(
            task_type="rag_check",
            description=f"Check if RAG needed for: {query}",
            input_data={"query": query}
        )
        
        result = await self._check_if_rag_needed(task)
        
        # Send result back to requesting agent
        response = AgentMessage(
            type=MessageType.RAG_RESULT,
            source_agent=self.agent_name,
            target_agent=requesting_agent,
            content=result,
            correlation_id=correlation_id
        )
        
        await self.ws_manager.send_to_agent(response)
        
        # Also notify frontend
        await self.ws_manager.broadcast_to_clients({
            "type": "rag_result",
            "requesting_agent": requesting_agent,
            "should_use_rag": result.get("should_use_rag", False),
            "document_count": len(result.get("documents", [])),
            "timestamp": message.timestamp.isoformat() if message.timestamp else None
        })
    
    async def validate_result(self, result: Any) -> ValidationResult:
        """Validate retrieval results"""
        if isinstance(result, dict):
            if "documents" in result:
                # Check if we got any documents
                if len(result["documents"]) == 0:
                    return ValidationResult(
                        is_valid=True,  # Empty results are valid
                        warnings=["No documents retrieved"]
                    )
            return ValidationResult(is_valid=True)
        
        return ValidationResult(
            is_valid=False,
            errors=["Invalid result format"]
        )
