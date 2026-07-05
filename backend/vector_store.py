"""
Knowledge base using simple text storage + keyword search.
No embedding model required — avoids all 404/API version issues on cloud.
"""
import os
import json
import re


class SchemaKnowledgeBase:
    """
    Stores knowledge-base documents as plain text chunks.
    Uses keyword/TF-IDF-style search without any embedding model.
    Works on both local and Streamlit Cloud environments.
    """

    def __init__(self, index_dir: str):
        self.index_dir = index_dir
        self.chunks = []   # list of {"content": str, "source": str}
        self._loaded = False

    # ── Persistence ──────────────────────────────────────────────────────────
    def _meta_path(self):
        return os.path.join(self.index_dir, "chunks.json")

    def _save(self):
        os.makedirs(self.index_dir, exist_ok=True)
        with open(self._meta_path(), "w", encoding="utf-8") as f:
            json.dump(self.chunks, f, ensure_ascii=False)

    def load_index(self, api_key: str = None) -> bool:
        if self._loaded:
            return True
        if not os.path.exists(self._meta_path()):
            return False
        try:
            with open(self._meta_path(), "r", encoding="utf-8") as f:
                self.chunks = json.load(f)
            self._loaded = True
            return True
        except Exception as e:
            print(f"Error loading knowledge base: {e}")
            return False

    # ── Text splitting ────────────────────────────────────────────────────────
    def _split_text(self, text: str, chunk_size: int = 500, overlap: int = 50):
        """Split text into overlapping chunks by character count."""
        chunks = []
        start = 0
        text = text.strip()
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += chunk_size - overlap
        return chunks

    # ── Keyword search ────────────────────────────────────────────────────────
    def _score(self, chunk: str, query: str) -> float:
        """Simple keyword overlap scoring (case-insensitive)."""
        query_words = set(re.findall(r'\w+', query.lower()))
        chunk_words = set(re.findall(r'\w+', chunk.lower()))
        if not query_words:
            return 0.0
        overlap = query_words & chunk_words
        return len(overlap) / len(query_words)

    # ── Public API ────────────────────────────────────────────────────────────
    def add_document(self, text_content: str, source_name: str, api_key: str = None) -> bool:
        """Chunk and store document text."""
        if not text_content.strip():
            return False

        self.load_index()
        texts = self._split_text(text_content)

        for t in texts:
            self.chunks.append({"content": t, "source": source_name})

        self._save()
        self._loaded = True
        return True

    def search(self, query: str, api_key: str = None, k: int = 3) -> list:
        """Return top-k most relevant chunks by keyword overlap."""
        self.load_index()
        if not self.chunks:
            return []

        scored = [
            (self._score(c["content"], query), c)
            for c in self.chunks
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for score, c in scored[:k] if score > 0]

    def reset(self) -> bool:
        """Delete all stored chunks."""
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
