"""
ChromaDB vector store with pluggable embedding backend.

Primary:  sentence-transformers all-MiniLM-L6-v2   (Python ≤ 3.13 + torch)
Fallback: character 4-gram hash embedding           (pure Python, any version)

The fallback enables keyword-level retrieval; upgrade to Python 3.12 +
sentence-transformers for full semantic search.
"""
import math
import uuid
import logging
from pathlib import Path
from typing import Any

import chromadb

logger = logging.getLogger(__name__)

CHROMA_PATH = Path(__file__).parent / "chroma_data"
COLLECTION_NAME = "rag_mvp_docs"
EMBEDDING_DIM = 256  # used by the pure-Python fallback

SEED_DOCS = [
    (
        "RAG (Retrieval-Augmented Generation) combines retrieval systems with large language "
        "models to provide factually grounded answers. It works by first retrieving relevant "
        "documents from a knowledge base, then using those documents as context for generation.",
        "seed-rag",
    ),
    (
        "MCP (Model Context Protocol) is a standard for AI tool communication developed by "
        "Anthropic. It allows AI models to call external tools and services in a structured, "
        "interoperable way via a client-server protocol over stdio or HTTP.",
        "seed-mcp",
    ),
    (
        "ChromaDB is an open-source vector database for AI applications. It stores text "
        "alongside their embeddings and supports fast semantic similarity search using "
        "approximate nearest-neighbour algorithms. It can run in-process or as a server.",
        "seed-chromadb",
    ),
    (
        "Sentence transformers convert text into dense semantic embeddings using transformer "
        "models. The all-MiniLM-L6-v2 model produces 384-dimensional vectors and is optimised "
        "for semantic similarity tasks with a good speed-quality trade-off.",
        "seed-sentence-transformers",
    ),
    (
        "FastAPI is a modern Python web framework for building APIs with automatic OpenAPI "
        "documentation. It uses type hints for validation and is built on Starlette and Pydantic, "
        "making it one of the fastest Python frameworks available.",
        "seed-fastapi",
    ),
]


# ── Embedding backend ─────────────────────────────────────────────────

def _load_model():
    """Try sentence-transformers; fall back to pure-Python hash embedder."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("Embedding backend: sentence-transformers (semantic)")
        return model
    except ImportError:
        logger.warning(
            "sentence-transformers not available (Python 3.14 compat issue). "
            "Using character n-gram fallback. Install Python 3.11/3.12 for semantic search."
        )
        return None


def _hash_embed(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Character 4-gram hash embedding — pure Python, no compiled deps."""
    vec = [0.0] * dim
    s = text.lower()
    for i in range(max(1, len(s) - 3)):
        gram = s[i : i + 4]
        vec[hash(gram) % dim] += 1.0
    mag = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / mag for x in vec]


class VectorStore:
    def __init__(self) -> None:
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        self._model = _load_model()
        self._collection = self._client.get_or_create_collection(
            COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        if self._collection.count() == 0:
            self._seed()

    # ── public API ───────────────────────────────────────────────────

    def add_document(
        self, text: str, source: str, chunk_size: int = 300, chunk_overlap: int = 50
    ) -> int:
        chunks = self._chunk(text, chunk_size, chunk_overlap)
        self._upsert(chunks, source)
        return len(chunks)

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        count = self._collection.count()
        if count == 0:
            return []
        k = min(top_k, count)
        embedding = self._embed([query])
        res = self._collection.query(
            query_embeddings=embedding,
            n_results=k,
            include=["documents", "metadatas", "distances"],
        )
        out = []
        for doc, meta, dist in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0]
        ):
            out.append({"text": doc, "source": meta.get("source", "unknown"), "score": 1.0 - dist})
        return out

    def list_sources(self) -> dict[str, int]:
        res = self._collection.get(include=["metadatas"])
        counts: dict[str, int] = {}
        for meta in res.get("metadatas") or []:
            src = meta.get("source", "unknown")
            counts[src] = counts.get(src, 0) + 1
        return counts

    def total_count(self) -> int:
        return self._collection.count()

    # ── internals ────────────────────────────────────────────────────

    def _seed(self) -> None:
        logger.info("Seeding vector store with %d sample documents", len(SEED_DOCS))
        for text, source in SEED_DOCS:
            self._upsert([text], source)

    def _embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is not None:
            return self._model.encode(texts).tolist()
        return [_hash_embed(t) for t in texts]

    def _upsert(self, chunks: list[str], source: str) -> None:
        self._collection.add(
            documents=chunks,
            embeddings=self._embed(chunks),
            metadatas=[{"source": source} for _ in chunks],
            ids=[str(uuid.uuid4()) for _ in chunks],
        )

    @staticmethod
    def _chunk(text: str, size: int, overlap: int) -> list[str]:
        chunks, i = [], 0
        while i < len(text):
            chunks.append(text[i : i + size])
            if i + size >= len(text):
                break
            i += size - overlap
        return chunks
