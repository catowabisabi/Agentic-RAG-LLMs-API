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

from pydantic import BaseModel, Field

from config.config import Config
from agents.shared_services.base_agent import BaseAgent
from agents.shared_services.message_protocol import (
    AgentMessage,
    MessageType,
    MessageProtocol,
    TaskAssignment,
    ValidationResult
)
# Replaces incompatible DocumentRetriever with native VectorDBManager
from services.vectordb_manager import vectordb_manager

logger = logging.getLogger(__name__)


class RAGDecision(BaseModel):
    """Decision on whether RAG is needed - Enhanced with Agentic capabilities"""
    should_use_rag: bool = Field(description="Whether RAG retrieval is needed")
    confidence: float = Field(default=0.5, description="Confidence in this decision (0-1)")
    reasoning: str = Field(description="Reasoning for the decision")
    search_queries: List[str] = Field(
        default_factory=list,
        description="Search queries to use if RAG is needed"
    )
    # Agentic enhancements
    complexity_level: str = Field(
        default="simple", 
        description="Query complexity: simple, moderate, complex, multi_hop"
    )
    suggested_strategy: str = Field(
        default="direct",
        description="Strategy: direct (answer without RAG), rag_once (single retrieval), rag_iterative (ReAct loop)"
    )
    requires_verification: bool = Field(
        default=False,
        description="Whether the answer should go through PEV verification"
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
        
        # Load configuration
        self.config = Config()
        
        # Load prompt configuration
        self.prompt_template = self.prompt_manager.get_prompt("rag_agent")
        
        self.vectordb = vectordb_manager
        
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
        """
        Enhanced RAG decision with Agentic capabilities
        
        考慮因素：
        1. 歷史對話 - 是否已有相關上下文
        2. 用戶偏好 - 是否偏好詳細/簡潔回答
        3. 問題複雜度 - 簡單問候 vs 多步驟推理
        4. 知識需求 - 是否需要事實性資訊
        5. 時效性 - 是否需要最新資訊
        """
        query = task.input_data.get("query", "")
        chat_history = task.input_data.get("chat_history", [])
        user_context = task.input_data.get("user_context", "")
        
        # 構建歷史對話摘要
        history_summary = ""
        if chat_history:
            recent_history = chat_history[-5:]  # 最近5條對話
            history_parts = []
            for msg in recent_history:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:100]
                history_parts.append(f"{role}: {content}")
            history_summary = "\n".join(history_parts)
        
        prompt = f"""You are an intelligent RAG decision engine. Analyze this query and decide the optimal strategy.

Query: {query}

Recent Chat History:
{history_summary or "No previous conversation."}

User Context: {user_context or "No user context provided."}

**Decision Criteria:**

1. **NO RAG NEEDED** (suggest_strategy: "direct"):
   - Greetings, casual chat, simple questions
   - Questions already answered in chat history
   - General knowledge the LLM can answer confidently
   - Opinion requests, creative tasks

2. **SINGLE RAG** (suggest_strategy: "rag_once"):
   - Simple factual questions about specific documents
   - When query clearly mentions documents/files/data
   - Basic lookup queries

3. **ITERATIVE RAG / ReAct** (suggest_strategy: "rag_iterative"):
   - Multi-hop questions requiring connecting multiple facts
   - Complex analysis requiring multiple document sources
   - Questions where initial retrieval might be insufficient
   - Questions with ambiguous terms needing refinement

4. **Complexity Assessment:**
   - simple: Single, clear question
   - moderate: Requires some reasoning
   - complex: Multi-part question
   - multi_hop: Requires chaining multiple pieces of information

5. **Verification Needed:**
   - Set to true for high-stakes topics (medical, legal, financial)
   - Set to true for complex calculations or data analysis
   - Set to true when accuracy is critical

Respond with your decision as JSON with these fields: should_use_rag, confidence, reasoning, search_queries, complexity_level, suggested_strategy, requires_verification."""
        
        try:
            # Use llm_service for structured output
            result_text = await self.llm_service.generate(
                prompt=prompt,
                system_message=self.prompt_template.system_prompt,
                temperature=self.prompt_template.temperature,
                session_id=task.task_id,
                response_format={"type": "json_object"}
            )
            
            # Parse JSON response
            import json
            decision_data = json.loads(result_text)
            
            decision = RAGDecision(
                should_use_rag=decision_data.get("should_use_rag", True),
                confidence=decision_data.get("confidence", 0.5),
                reasoning=decision_data.get("reasoning", ""),
                search_queries=decision_data.get("search_queries", [query]),
                complexity_level=decision_data.get("complexity_level", "simple"),
                suggested_strategy=decision_data.get("suggested_strategy", "rag_once"),
                requires_verification=decision_data.get("requires_verification", False)
            )
            
            result = {
                "should_use_rag": decision.should_use_rag,
                "confidence": decision.confidence,
                "reasoning": decision.reasoning,
                "search_queries": decision.search_queries or [query],
                "complexity_level": decision.complexity_level,
                "suggested_strategy": decision.suggested_strategy,
                "requires_verification": decision.requires_verification
            }
            
            logger.info(
                f"[RAG Decision] should_use_rag={decision.should_use_rag}, "
                f"strategy={decision.suggested_strategy}, "
                f"complexity={decision.complexity_level}"
            )
            
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
                
                # Build context from retrieved documents
                context_parts = []
                for doc in docs:
                    content = doc.get("content", "")
                    if content:
                        context_parts.append(content)
                result["context"] = "\n\n---\n\n".join(context_parts)
            
            return result
            
        except Exception as e:
            logger.error(f"Error in RAG check: {e}")
            return {
                "should_use_rag": True,  # Default to yes on error
                "confidence": 0.3,
                "reasoning": f"Error in decision: {e}",
                "complexity_level": "simple",
                "suggested_strategy": "rag_once",
                "requires_verification": False,
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
        """
        Perform document retrieval with Skills-based DB routing + Reranking (Phase 1).
        
        Pipeline:
        1. Use KB Skills to identify relevant databases (instead of ALL DBs)
        2. Query only targeted DBs with more candidates
        3. Rerank results with cross-encoder
        4. Return top_k most relevant results
        """
        all_docs = []
        seen_ids = set()
        
        try:
            # Phase 1: Skills-based DB routing
            targeted_dbs = await self._route_to_relevant_dbs(queries[0] if queries else "")
            
            if not targeted_dbs:
                # Fallback: get all non-empty DBs
                db_list = self.vectordb.list_databases()
                targeted_dbs = [db["name"] for db in db_list if db.get("document_count", 0) > 0]
            
            if not targeted_dbs:
                logger.warning("No active RAG databases found")
                return []
            
            logger.info(f"[RAG] Querying targeted DBs: {targeted_dbs} (instead of all)")
            
            # Phase 1: Use query_targeted_dbs with reranking
            for query in queries:
                try:
                    result = await self.vectordb.query_targeted_dbs(
                        query=query,
                        db_names=targeted_dbs,
                        top_k=top_k
                    )
                    
                    for doc in result.get("results", []):
                        doc_id = doc.get("id", doc.get("content", "")[:50])
                        if doc_id not in seen_ids:
                            seen_ids.add(doc_id)
                            
                            if "metadata" not in doc:
                                doc["metadata"] = {}
                            
                            # Use rerank_score if available, else similarity
                            if "rerank_score" in doc:
                                doc["similarity_score"] = max(0, min(1, (doc["rerank_score"] + 5) / 10))
                            elif "similarity" in doc:
                                doc["similarity_score"] = doc["similarity"]
                            elif "distance" in doc:
                                doc["similarity_score"] = 1.0 / (1.0 + doc["distance"])
                            else:
                                doc["similarity_score"] = 0.5
                            
                            all_docs.append(doc)
                except Exception as e:
                    logger.warning(f"Error in targeted retrieval: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error in retrieval pipeline: {e}")
            
        # Sort by similarity score descending
        all_docs.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)
        
        return all_docs[:top_k]
    
    async def _route_to_relevant_dbs(self, query: str) -> List[str]:
        """
        Use KB Skills metadata to identify relevant databases for a query (Phase 1).
        Returns list of database names most relevant to the query.
        """
        try:
            skills = self.vectordb.get_skills_summary()
            if not skills:
                return []
            
            # Build skills description for LLM
            skills_text = []
            for s in skills:
                if s.get("doc_count", 0) == 0:
                    continue
                skills_text.append(
                    f"- {s['name']}: {s['description']} "
                    f"(keywords: {', '.join(s.get('keywords', [])[:8])}, "
                    f"topics: {', '.join(s.get('topics', [])[:5])}, "
                    f"docs: {s.get('doc_count', 0)})"
                )
            
            if not skills_text:
                return []
            
            prompt = f"""Given this user query, select the 1-3 most relevant knowledge bases to search.

Query: {query}

Available Knowledge Bases:
{chr(10).join(skills_text)}

Return ONLY a JSON array of database names, e.g. ["db1", "db2"].
Select the fewest databases needed to answer the query. If unsure, include up to 3.
"""
            
            result = await self.llm_service.generate(
                prompt=prompt,
                system_message="You are a database routing agent. Return only a JSON array of database names.",
                temperature=0.1
            )
            
            import json
            response = result.content.strip()
            # Clean markdown
            if response.startswith("```"):
                response = response.split("\n", 1)[-1].rsplit("```", 1)[0]
            
            db_names = json.loads(response)
            
            # Validate against actual DBs
            valid_dbs = {s["name"] for s in skills if s.get("doc_count", 0) > 0}
            filtered = [db for db in db_names if db in valid_dbs]
            
            if filtered:
                logger.info(f"[RAG Routing] Query routed to: {filtered}")
                return filtered
            else:
                logger.warning(f"[RAG Routing] No valid DBs matched, falling back to all")
                return list(valid_dbs)[:3]
                
        except Exception as e:
            logger.warning(f"[RAG Routing] Skills routing failed: {e}, falling back")
            return []
    
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
        """Embed and store new documents using VectorDBManager"""
        documents = task.input_data.get("documents", [])
        metadatas = task.input_data.get("metadata", [])
        collection_name = task.input_data.get("collection_name", "documents")
        
        try:
            # Ensure database exists
            await self.vectordb.create_database(collection_name)
            
            count = 0
            for i, doc_content in enumerate(documents):
                meta = metadatas[i] if i < len(metadatas) else {}
                await self.vectordb.add_document(collection_name, doc_content, meta)
                count += 1
            
            return {
                "success": True,
                "documents_added": count,
                "collection": collection_name
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
