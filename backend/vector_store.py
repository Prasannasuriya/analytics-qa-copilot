import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_core.documents import Document

class SchemaKnowledgeBase:
    """
    Manages indexing and querying of metadata, glossary, and data dictionaries
    using FAISS and Gemini Embeddings.
    """
    def __init__(self, index_dir: str):
        self.index_dir = index_dir
        self.db = None
        
    def _get_embeddings(self, api_key: str) -> GoogleGenerativeAIEmbeddings:
        """
        Creates a Google GenAI Embeddings instance using the provided API key.
        """
        if not api_key:
            raise ValueError("Google API Key is required to initialize embeddings.")
        return GoogleGenerativeAIEmbeddings(
            model="text-embedding-004",
            google_api_key=api_key
        )

    def load_index(self, api_key: str) -> bool:
        """
        Attempts to load the FAISS index from the local directory.
        """
        if self.db is not None:
            return True
            
        if not os.path.exists(self.index_dir):
            return False
            
        try:
            embeddings = self._get_embeddings(api_key)
            self.db = FAISS.load_local(
                self.index_dir, 
                embeddings, 
                allow_dangerous_deserialization=True
            )
            return True
        except Exception as e:
            print(f"Error loading index: {e}")
            return False

    def add_document(self, text_content: str, source_name: str, api_key: str) -> bool:
        """
        Chunks and adds text content to the FAISS vector database.
        Saves the database locally.
        """
        if not text_content.strip():
            return False
            
        try:
            embeddings = self._get_embeddings(api_key)
            
            # Split text into chunks
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=500,
                chunk_overlap=50
            )
            chunks = text_splitter.split_text(text_content)
            
            # Create documents with metadata
            docs = [
                Document(page_content=chunk, metadata={"source": source_name})
                for chunk in chunks
            ]
            
            # Check if index exists or create new
            if self.load_index(api_key):
                self.db.add_documents(docs)
            else:
                self.db = FAISS.from_documents(docs, embeddings)
                
            # Save index locally
            os.makedirs(self.index_dir, exist_ok=True)
            self.db.save_local(self.index_dir)
            return True
        except Exception as e:
            print(f"Error adding document to vector store: {e}")
            raise e

    def search(self, query: str, api_key: str, k: int = 3) -> list:
        """
        Searches the FAISS vector database for relevant chunks matching the query.
        Returns a list of dicts with content and source metadata.
        """
        if not self.load_index(api_key):
            return []
            
        try:
            results = self.db.similarity_search(query, k=k)
            return [
                {
                    "content": doc.page_content,
                    "source": doc.metadata.get("source", "Unknown")
                }
                for doc in results
            ]
        except Exception as e:
            print(f"Error searching vector store: {e}")
            return []

    def reset(self) -> bool:
        """
        Deletes the local FAISS index files and resets the DB in memory.
        """
        self.db = None
        if os.path.exists(self.index_dir):
            for file in os.listdir(self.index_dir):
                try:
                    os.remove(os.path.join(self.index_dir, file))
                except Exception as e:
                    print(f"Error deleting file {file}: {e}")
            try:
                os.rmdir(self.index_dir)
            except Exception as e:
                print(f"Error removing directory {self.index_dir}: {e}")
        return True
