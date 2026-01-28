from typing_extensions import TypedDict
from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import HumanMessage, AIMessage
import json

from config.config import Config
from tools.retriever import DocumentRetriever
from tools.memory import ConversationMemory


class RAGState(TypedDict):
    """State definition for the RAG agent"""
    query: str
    chat_history: List[Dict[str, str]]
    retrieved_docs: List[Dict[str, Any]]
    context: str
    answer: str
    metadata: Dict[str, Any]
    iteration: int


class RAGAgent:
    def __init__(self):
        self.config = Config()
        self.llm = ChatOpenAI(
            model=self.config.DEFAULT_MODEL,
            temperature=self.config.TEMPERATURE,
            max_tokens=self.config.MAX_TOKENS,
            api_key=self.config.OPENAI_API_KEY
        )
        self.retriever = DocumentRetriever()
        self.memory = ConversationMemory(window_size=self.config.MEMORY_WINDOW)
        self.graph = self._build_graph()
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state graph for RAG"""
        graph = StateGraph(RAGState)
        
        # Add nodes
        graph.add_node("analyze_query", self.analyze_query)
        graph.add_node("retrieve_documents", self.retrieve_documents)
        graph.add_node("synthesize_context", self.synthesize_context)
        graph.add_node("generate_answer", self.generate_answer)
        graph.add_node("quality_check", self.quality_check)
        
        # Define the flow
        graph.add_edge(START, "analyze_query")
        graph.add_edge("analyze_query", "retrieve_documents")
        graph.add_edge("retrieve_documents", "synthesize_context")
        graph.add_edge("synthesize_context", "generate_answer")
        graph.add_edge("generate_answer", "quality_check")
        graph.add_edge("quality_check", END)
        
        return graph.compile()
    
    def analyze_query(self, state: RAGState) -> Dict[str, Any]:
        """Analyze and potentially reformulate the user query"""
        query = state["query"]
        chat_history = state.get("chat_history", [])
        
        # If we have chat history, consider context for query reformulation
        if chat_history:
            context_prompt = f"""
            Given the conversation history and the new query, reformulate the query to be more specific and standalone.
            
            Conversation History:
            {json.dumps(chat_history[-3:], indent=2)}
            
            New Query: {query}
            
            Reformulated Query:"""
            
            response = self.llm.invoke([HumanMessage(content=context_prompt)])
            reformulated_query = response.content.strip()
        else:
            reformulated_query = query
        
        return {
            "query": reformulated_query,
            "metadata": {
                "original_query": query,
                "reformulated": reformulated_query != query
            }
        }
    
    def retrieve_documents(self, state: RAGState) -> Dict[str, Any]:
        """Retrieve relevant documents from the vector store"""
        query = state["query"]
        
        try:
            retrieved_docs = self.retriever.retrieve(
                query=query,
                top_k=self.config.TOP_K_RETRIEVAL
            )
            
            return {
                "retrieved_docs": retrieved_docs,
                "metadata": {
                    **state.get("metadata", {}),
                    "num_docs_retrieved": len(retrieved_docs)
                }
            }
        except Exception as e:
            print(f"Retrieval error: {e}")
            return {
                "retrieved_docs": [],
                "metadata": {
                    **state.get("metadata", {}),
                    "retrieval_error": str(e)
                }
            }
    
    def synthesize_context(self, state: RAGState) -> Dict[str, Any]:
        """Combine retrieved documents with conversation history"""
        retrieved_docs = state.get("retrieved_docs", [])
        chat_history = state.get("chat_history", [])
        
        # Format retrieved documents
        doc_context = "\n\n".join([
            f"Document {i+1}:\n{doc.get('content', '')}"
            for i, doc in enumerate(retrieved_docs)
        ])
        
        # Format chat history
        history_context = ""
        if chat_history:
            history_context = "Previous Conversation:\n" + "\n".join([
                f"Human: {exchange.get('human', '')}\nAssistant: {exchange.get('assistant', '')}"
                for exchange in chat_history[-2:]  # Last 2 exchanges
            ])
        
        # Combine contexts
        full_context = []
        if history_context:
            full_context.append(history_context)
        if doc_context:
            full_context.append("Retrieved Documents:\n" + doc_context)
        
        context = "\n\n---\n\n".join(full_context)
        
        return {"context": context}
    
    def generate_answer(self, state: RAGState) -> Dict[str, Any]:
        """Generate an answer using the LLM with retrieved context"""
        query = state["query"]
        context = state.get("context", "")
        
        prompt = f"""
        You are a helpful assistant that answers questions based on the provided context and conversation history.
        
        Instructions:
        1. Use the context provided to answer the question accurately
        2. If the context doesn't contain relevant information, say so clearly
        3. Be concise but comprehensive in your response
        4. Reference specific documents when applicable
        
        Context:
        {context}
        
        Question: {query}
        
        Answer:"""
        
        try:
            response = self.llm.invoke([HumanMessage(content=prompt)])
            answer = response.content.strip()
            
            return {
                "answer": answer,
                "metadata": {
                    **state.get("metadata", {}),
                    "answer_generated": True
                }
            }
        except Exception as e:
            return {
                "answer": f"I apologize, but I encountered an error generating the answer: {str(e)}",
                "metadata": {
                    **state.get("metadata", {}),
                    "generation_error": str(e)
                }
            }
    
    def quality_check(self, state: RAGState) -> Dict[str, Any]:
        """Perform a quality check on the generated answer"""
        answer = state.get("answer", "")
        query = state["query"]
        
        # Simple quality checks
        quality_score = 1.0
        issues = []
        
        if len(answer) < 50:
            quality_score -= 0.3
            issues.append("Answer too short")
        
        if "I don't know" in answer.lower() or "not provided" in answer.lower():
            quality_score -= 0.2
            issues.append("Insufficient information")
        
        if query.lower() not in answer.lower():
            # Check if key terms from query appear in answer
            query_words = set(query.lower().split())
            answer_words = set(answer.lower().split())
            overlap = len(query_words.intersection(answer_words))
            if overlap < len(query_words) * 0.3:
                quality_score -= 0.2
                issues.append("Low query-answer relevance")
        
        return {
            "metadata": {
                **state.get("metadata", {}),
                "quality_score": max(0.0, quality_score),
                "quality_issues": issues
            }
        }
    
    def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Run the RAG agent with the given input"""
        # Initialize state
        initial_state = {
            "query": input_data["query"],
            "chat_history": input_data.get("chat_history", []),
            "retrieved_docs": [],
            "context": "",
            "answer": "",
            "metadata": {},
            "iteration": 0
        }
        
        # Execute the graph
        result = self.graph.invoke(initial_state)
        
        # Update conversation memory
        self.memory.add_exchange(
            human_input=input_data["query"],
            assistant_response=result["answer"]
        )
        
        return result


def create_rag_agent() -> RAGAgent:
    """Factory function to create a RAG agent"""
    return RAGAgent()


if __name__ == "__main__":
    # Test the agent
    agent = create_rag_agent()
    
    test_query = {
        "query": "What are the key features of LangGraph?",
        "chat_history": []
    }
    
    result = agent.invoke(test_query)
    
    print("Query:", result["query"])
    print("Answer:", result["answer"])
    print("Metadata:", json.dumps(result["metadata"], indent=2))