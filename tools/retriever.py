from typing import List, Dict, Any, Optional
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
except Exception:
    # Fallback splitter if langchain is not installed or import fails
    class RecursiveCharacterTextSplitter:
        def __init__(self, chunk_size=1000, chunk_overlap=200, separators=None):
            self.chunk_size = chunk_size
            self.chunk_overlap = chunk_overlap
            self.separators = separators or ["\n\n", "\n", " ", ""]
        def split_text(self, text: str):
            if not text:
                return []
            n = max(1, int(self.chunk_size))
            o = max(0, int(self.chunk_overlap))
            chunks = []
            i = 0
            L = len(text)
            while i < L:
                end = min(i + n, L)
                chunks.append(text[i:end])
                if end == L:
                    break
                i = max(0, end - o)
            return chunks
from langchain.schema import Document
import os

from config.config import Config


class DocumentRetriever:
    """Handles document retrieval from vector database"""
    
    def __init__(self, collection_name: str = "default"):
        self.config = Config()
        self.collection_name = collection_name
        self.embeddings = OpenAIEmbeddings(
            model=self.config.EMBEDDING_MODEL,
            api_key=self.config.OPENAI_API_KEY
        )
        self.vectorstore = None
        self._initialize_vectorstore()
    
    def _initialize_vectorstore(self):
        """Initialize or load existing vector store"""
        try:
            persist_directory = os.path.join(self.config.CHROMA_DB_PATH, self.collection_name)
            if os.path.exists(persist_directory):
                self.vectorstore = Chroma(
                    persist_directory=persist_directory,
                    collection_name=self.collection_name,
                    embedding_function=self.embeddings
                )
                print(f"Loaded existing vector store from {persist_directory}")
            else:
                # Create empty vector store
                os.makedirs(persist_directory, exist_ok=True)
                self.vectorstore = Chroma(
                    persist_directory=persist_directory,
                    collection_name=self.collection_name,
                    embedding_function=self.embeddings
                )
                print(f"Created new vector store at {persist_directory}")
        except Exception as e:
            print(f"Error initializing vector store: {e}")
            self.vectorstore = None
    
    def add_documents(self, documents: List[str], metadatas: Optional[List[Dict]] = None) -> bool:
        """Add documents to the vector store"""
        if not self.vectorstore:
            print("Vector store not initialized")
            return False
        
        try:
            # Split documents into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.config.CHUNK_SIZE,
                chunk_overlap=self.config.CHUNK_OVERLAP,
                separators=["\n\n", "\n", " ", ""]
            )
            
            # Process each document
            all_splits = []
            all_metadatas = []
            
            for i, doc in enumerate(documents):
                splits = text_splitter.split_text(doc)
                all_splits.extend(splits)
                
                # Add metadata for each chunk
                doc_metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
                for j, split in enumerate(splits):
                    chunk_metadata = {
                        **doc_metadata,
                        "chunk_id": f"doc_{i}_chunk_{j}",
                        "chunk_size": len(split)
                    }
                    all_metadatas.append(chunk_metadata)
            
            # Add to vector store
            self.vectorstore.add_texts(
                texts=all_splits,
                metadatas=all_metadatas
            )
            
            # Persist changes
            self.vectorstore.persist()
            print(f"Added {len(all_splits)} chunks from {len(documents)} documents")
            return True
            
        except Exception as e:
            print(f"Error adding documents: {e}")
            return False
    
    def add_document(self, content: str, metadata: Optional[Dict] = None) -> Optional[str]:
        """Add a single document to the vector store and return its ID"""
        if not self.vectorstore:
            print("Vector store not initialized")
            return None
        
        try:
            import uuid
            doc_id = str(uuid.uuid4())
            
            # Split content into chunks if needed
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.config.CHUNK_SIZE,
                chunk_overlap=self.config.CHUNK_OVERLAP,
                separators=["\n\n", "\n", " ", ""]
            )
            
            chunks = text_splitter.split_text(content)
            
            # Prepare metadata for each chunk
            chunk_metadatas = []
            for i, _ in enumerate(chunks):
                chunk_metadata = {
                    **(metadata or {}),
                    "doc_id": doc_id,
                    "chunk_index": i,
                    "total_chunks": len(chunks)
                }
                chunk_metadatas.append(chunk_metadata)
            
            # Add to vector store
            self.vectorstore.add_texts(
                texts=chunks,
                metadatas=chunk_metadatas
            )
            
            # Persist changes
            self.vectorstore.persist()
            print(f"Added document {doc_id} with {len(chunks)} chunks")
            return doc_id
            
        except Exception as e:
            print(f"Error adding document: {e}")
            return None
    
    def retrieve(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve relevant documents for a query"""
        if not self.vectorstore:
            print("Vector store not initialized")
            return []
        
        try:
            # Perform similarity search
            results = self.vectorstore.similarity_search_with_score(
                query=query,
                k=top_k
            )
            
            # Format results
            formatted_results = []
            for doc, score in results:
                formatted_results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": float(score)
                })
            
            return formatted_results
            
        except Exception as e:
            print(f"Error during retrieval: {e}")
            return []
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about the document collection"""
        if not self.vectorstore:
            return {"error": "Vector store not initialized"}
        
        try:
            # Get collection info
            collection = self.vectorstore._collection
            stats = {
                "total_documents": collection.count(),
                "collection_name": self.collection_name
            }
            return stats
        except Exception as e:
            return {"error": f"Error getting stats: {e}"}
    
    def get_collection_info(self) -> Dict[str, Any]:
        """Get detailed information about the collection"""
        if not self.vectorstore:
            return {"error": "Vector store not initialized"}
        
        try:
            collection = self.vectorstore._collection
            return {
                "name": self.collection_name,
                "document_count": collection.count(),
                "path": os.path.join(self.config.CHROMA_DB_PATH, self.collection_name)
            }
        except Exception as e:
            return {"error": f"Error getting collection info: {e}"}


class AdvancedRetriever(DocumentRetriever):
    """Extended retriever with advanced features"""
    
    def __init__(self, collection_name: str = "default"):
        super().__init__(collection_name=collection_name)
        self.query_history = []
    
    def hybrid_retrieve(self, query: str, top_k: int = 5, rerank: bool = True) -> List[Dict[str, Any]]:
        """Perform hybrid retrieval with optional reranking"""
        # Basic retrieval
        results = self.retrieve(query, top_k * 2)  # Get more initially
        
        if rerank and results:
            # Simple reranking based on query history and content diversity
            results = self._rerank_results(query, results)
        
        # Store query for future reranking
        self.query_history.append(query)
        if len(self.query_history) > 100:  # Keep recent queries
            self.query_history = self.query_history[-100:]
        
        return results[:top_k]
    
    def _rerank_results(self, query: str, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Simple reranking based on content diversity and relevance"""
        # For now, just return sorted by similarity score
        return sorted(results, key=lambda x: x["similarity_score"], reverse=True)
    
    def retrieve_with_filter(self, query: str, filters: Dict[str, Any], top_k: int = 5) -> List[Dict[str, Any]]:
        """Retrieve documents with metadata filters"""
        if not self.vectorstore:
            return []
        
        try:
            # Use Chroma's filter functionality
            results = self.vectorstore.similarity_search_with_score(
                query=query,
                k=top_k,
                filter=filters
            )
            
            formatted_results = []
            for doc, score in results:
                formatted_results.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": float(score)
                })
            
            return formatted_results
        except Exception as e:
            print(f"Error in filtered retrieval: {e}")
            return self.retrieve(query, top_k)  # Fallback to normal retrieval