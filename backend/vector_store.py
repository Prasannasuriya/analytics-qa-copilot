import os
import json
import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

try:
    import faiss
    HAS_FAISS = True
except ImportError:
    HAS_FAISS = False


class SchemaKnowledgeBase:
    """
    Manages indexing and querying of metadata, glossary, and data dictionaries
    using FAISS and Gemini Embeddings via direct Google GenerativeAI SDK.
    """

    def __init__(self, index_dir: str):
        self.index_dir = index_dir
        self.index = None          # faiss.IndexFlatL2
        self.chunks = []           # list of {"content": str, "source": str}
        self._loaded = False

    # ── Embedding via direct SDK (avoids langchain version issues) ─────────
    def _embed(self, texts: list, api_key: str) -> np.ndarray:
        if not HAS_GENAI:
            raise ImportError("google-generativeai package not installed.")
        genai.configure(api_key=api_key)
        vectors = []
        for text in texts:
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="retrieval_document",
            )
            vectors.append(result["embedding"])
        return np.array(vectors, dtype=np.float32)

    def _embed_query(self, text: str, api_key: str) -> np.ndarray:
        genai.configure(api_key=api_key)
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_query",
        )
        return np.array([result["embedding"]], dtype=np.float32)

    # ── Persistence helpers ────────────────────────────────────────────────
    def _index_path(self):
        return os.path.join(self.index_dir, "index.faiss")

    def _meta_path(self):
        return os.path.join(self.index_dir, "chunks.json")

    def _save(self):
        os.makedirs(self.index_dir, exist_ok=True)
        faiss.write_index(self.index, self._index_path())
        with open(self._meta_path(), "w", encoding="utf-8") as f:
            json.dump(self.chunks, f)

    def load_index(self, api_key: str = None) -> bool:
        if self._loaded and self.index is not None:
            return True
        if not HAS_FAISS:
            return False
        if not os.path.exists(self._index_path()):
            return False
        try:
            self.index = faiss.read_index(self._index_path())
            with open(self._meta_path(), "r", encoding="utf-8") as f:
                self.chunks = json.load(f)
            self._loaded = True
            return True
        except Exception as e:
            print(f"Error loading FAISS index: {e}")
            return False

    # ── Public API ─────────────────────────────────────────────────────────
    def add_document(self, text_content: str, source_name: str, api_key: str) -> bool:
        if not text_content.strip():
            return False
        if not HAS_FAISS:
            raise ImportError("faiss-cpu package not installed.")

        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        texts = splitter.split_text(text_content)
        if not texts:
            return False

        vectors = self._embed(texts, api_key)          # shape (N, 768)
        dim = vectors.shape[1]

        # Load or create index
        self.load_index(api_key)
        if self.index is None:
            self.index = faiss.IndexFlatL2(dim)
            self.chunks = []

        self.index.add(vectors)
        for t in texts:
            self.chunks.append({"content": t, "source": source_name})

        self._save()
        return True

    def search(self, query: str, api_key: str, k: int = 3) -> list:
        if not self.load_index(api_key):
            return []
        if self.index.ntotal == 0:
            return []
        try:
            q_vec = self._embed_query(query, api_key)
            k = min(k, self.index.ntotal)
            _, indices = self.index.search(q_vec, k)
            results = []
            for idx in indices[0]:
                if 0 <= idx < len(self.chunks):
                    results.append(self.chunks[idx])
            return results
        except Exception as e:
            print(f"Error searching vector store: {e}")
            return []

    def reset(self) -> bool:
        self.index = None
        self.chunks = []
        self._loaded = False
        if os.path.exists(self.index_dir):
            for fname in os.listdir(self.index_dir):
                try:
                    os.remove(os.path.join(self.index_dir, fname))
                except Exception:
                    pass
            try:
                os.rmdir(self.index_dir)
            except Exception:
                pass
        return True
