"""
ChromaDB vector store — uses sentence-transformers for semantic embeddings.

Persists to server/chroma_data/. Uses all-MiniLM-L6-v2 (384-dim vectors)
for semantic similarity search.
"""
import logging
import uuid
from pathlib import Path
from typing import Any

import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)

CHROMA_PATH = Path(__file__).parent / "chroma_data"
COLLECTION_NAME = "documents"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

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


class VectorStore:
    """
    ChromaDB-backed vector store using sentence-transformers embeddings.
    Persists to chroma_data/ directory. Seeded with sample docs on first run.
    """

    def __init__(self) -> None:
        CHROMA_PATH.mkdir(parents=True, exist_ok=True)
        self._ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        self._client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )
        if self._collection.count() == 0:
            self._seed()
        logger.info("Vector store ready — %d chunks indexed", self._collection.count())

    # ── public API ────────────────────────────────────────────────────

    def add_document(
        self, text: str, source: str, chunk_size: int = 300, chunk_overlap: int = 50
    ) -> int:
        chunks = self._chunk(text, chunk_size, chunk_overlap)
        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [{"source": source} for _ in chunks]
        self._collection.add(documents=chunks, ids=ids, metadatas=metadatas)
        logger.info("Stored %d chunks for source=%r", len(chunks), source)
        return len(chunks)

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        count = self._collection.count()
        if count == 0:
            return []
        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, count),
            include=["documents", "metadatas", "distances"],
        )
        output = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            output.append({
                "text": doc,
                "source": meta.get("source", "unknown"),
                "score": round(1 - dist, 4),  # cosine distance → similarity
            })
        return output

    def list_sources(self) -> dict[str, int]:
        results = self._collection.get(include=["metadatas"])
        counts: dict[str, int] = {}
        for meta in results["metadatas"]:
            src = meta.get("source", "unknown")
            counts[src] = counts.get(src, 0) + 1
        return counts

    def total_count(self) -> int:
        return self._collection.count()

    # ── internals ─────────────────────────────────────────────────────

    def _seed(self) -> None:
        logger.info("Seeding ChromaDB with %d sample documents", len(SEED_DOCS))
        for text, source in SEED_DOCS:
            chunks = self._chunk(text, 300, 50)
            ids = [str(uuid.uuid4()) for _ in chunks]
            metadatas = [{"source": source} for _ in chunks]
            self._collection.add(documents=chunks, ids=ids, metadatas=metadatas)

    @staticmethod
    def _chunk(text: str, size: int, overlap: int) -> list[str]:
        chunks, i = [], 0
        while i < len(text):
            chunks.append(text[i : i + size])
            if i + size >= len(text):
                break
            i += size - overlap
        return chunks
