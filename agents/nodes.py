"""
Node definitions for the RAG agent graph.

This module contains individual node functions that can be used
in different graph configurations.
"""

from typing import Dict, Any
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI

from config.config import Config


def create_query_analyzer(llm: ChatOpenAI):
    """Create a query analysis node"""
    def analyze_query_node(state: Dict[str, Any]) -> Dict[str, Any]:
        query = state["query"]
        chat_history = state.get("chat_history", [])
        
        if chat_history:
            prompt = f"""
            Based on the conversation history, analyze and potentially reformulate this query to be more specific:
            
            Recent conversation:
            {chat_history[-2:] if len(chat_history) >= 2 else chat_history}
            
            New query: {query}
            
            If the query references something from the conversation ('it', 'that', 'the previous'), 
            reformulate it to be standalone. Otherwise, return the original query.
            
            Reformulated query:"""
            
            response = llm.invoke([HumanMessage(content=prompt)])
            reformulated = response.content.strip()
        else:
            reformulated = query
        
        return {
            "analyzed_query": reformulated,
            "analysis_metadata": {
                "original_query": query,
                "was_reformulated": reformulated != query
            }
        }
    
    return analyze_query_node


def create_document_retriever_node(retriever):
    """Create a document retrieval node"""
    def retrieve_documents_node(state: Dict[str, Any]) -> Dict[str, Any]:
        query = state.get("analyzed_query", state["query"])
        
        try:
            docs = retriever.retrieve(query, top_k=5)
            return {
                "retrieved_documents": docs,
                "retrieval_metadata": {
                    "num_retrieved": len(docs),
                    "query_used": query
                }
            }
        except Exception as e:
            return {
                "retrieved_documents": [],
                "retrieval_metadata": {
                    "error": str(e),
                    "num_retrieved": 0
                }
            }
    
    return retrieve_documents_node


def create_context_synthesizer(llm: ChatOpenAI):
    """Create a context synthesis node"""
    def synthesize_context_node(state: Dict[str, Any]) -> Dict[str, Any]:
        docs = state.get("retrieved_documents", [])
        chat_history = state.get("chat_history", [])
        
        # Format documents
        doc_texts = []
        for i, doc in enumerate(docs, 1):
            doc_texts.append(f"Document {i}:\n{doc['content'][:500]}...")
        
        # Format history
        history_text = ""
        if chat_history:
            recent_history = chat_history[-2:]  # Last 2 exchanges
            history_parts = []
            for exchange in recent_history:
                history_parts.append(f"Human: {exchange.get('human', '')}")
                history_parts.append(f"Assistant: {exchange.get('assistant', '')}")
            history_text = "\n".join(history_parts)
        
        # Combine contexts
        full_context = []
        if history_text:
            full_context.append(f"Conversation History:\n{history_text}")
        if doc_texts:
            full_context.append(f"Retrieved Documents:\n\n".join(doc_texts))
        
        synthesized_context = "\n\n---\n\n".join(full_context)
        
        return {
            "synthesized_context": synthesized_context,
            "context_metadata": {
                "num_docs_used": len(docs),
                "has_history": bool(history_text),
                "context_length": len(synthesized_context)
            }
        }
    
    return synthesize_context_node


def create_answer_generator(llm: ChatOpenAI):
    """Create an answer generation node"""
    def generate_answer_node(state: Dict[str, Any]) -> Dict[str, Any]:
        query = state.get("analyzed_query", state["query"])
        context = state.get("synthesized_context", "")
        
        prompt = f"""
        You are a helpful AI assistant. Answer the user's question based on the provided context.
        
        Instructions:
        - Use the context to provide accurate, detailed answers
        - If the context doesn't contain enough information, say so clearly
        - Cite specific documents when referencing information
        - Be concise but comprehensive
        
        Context:
        {context}
        
        Question: {query}
        
        Answer:"""
        
        try:
            response = llm.invoke([HumanMessage(content=prompt)])
            answer = response.content.strip()
            
            return {
                "final_answer": answer,
                "generation_metadata": {
                    "model_used": llm.model_name,
                    "context_provided": bool(context),
                    "answer_length": len(answer)
                }
            }
        except Exception as e:
            return {
                "final_answer": f"I encountered an error generating the answer: {str(e)}",
                "generation_metadata": {
                    "error": str(e)
                }
            }
    
    return generate_answer_node


def create_quality_checker(llm: ChatOpenAI):
    """Create a quality checking node"""
    def quality_check_node(state: Dict[str, Any]) -> Dict[str, Any]:
        answer = state.get("final_answer", "")
        query = state.get("analyzed_query", state["query"])
        
        # Basic quality metrics
        quality_score = 1.0
        issues = []
        
        # Length check
        if len(answer) < 50:
            quality_score -= 0.3
            issues.append("Answer seems too short")
        
        # Relevance check (simple keyword matching)
        query_words = set(query.lower().split())
        answer_words = set(answer.lower().split())
        overlap_ratio = len(query_words.intersection(answer_words)) / len(query_words)
        
        if overlap_ratio < 0.2:
            quality_score -= 0.4
            issues.append("Low relevance to query")
        
        # Uncertainty indicators
        uncertainty_phrases = ["i don't know", "not sure", "unclear", "not provided"]
        if any(phrase in answer.lower() for phrase in uncertainty_phrases):
            quality_score -= 0.2
            issues.append("Contains uncertainty indicators")
        
        return {
            "quality_assessment": {
                "score": max(0.0, quality_score),
                "issues": issues,
                "word_count": len(answer.split()),
                "relevance_score": overlap_ratio
            }
        }
    
    return quality_check_node