"""
Pure-Python vector store — no C/Rust extensions required.

Persists to a JSON file. Uses character 4-gram hash embedding for similarity
search (keyword-level retrieval). Replaces ChromaDB to support Python 3.14+.
"""
import json
import math
import uuid
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_PATH = Path(__file__).parent / "vector_data"
DATA_FILE = DATA_PATH / "store.json"
EMBEDDING_DIM = 256

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


# ── Embedding ─────────────────────────────────────────────────────────

def _hash_embed(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Character 4-gram hash embedding — pure Python, no compiled deps."""
    vec = [0.0] * dim
    s = text.lower()
    for i in range(max(1, len(s) - 3)):
        gram = s[i : i + 4]
        vec[hash(gram) % dim] += 1.0
    mag = math.sqrt(sum(x * x for x in vec)) or 1.0
    return [x / mag for x in vec]


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    ma = math.sqrt(sum(x * x for x in a)) or 1.0
    mb = math.sqrt(sum(x * x for x in b)) or 1.0
    return dot / (ma * mb)


# ── VectorStore ───────────────────────────────────────────────────────

class VectorStore:
    """
    In-process vector store backed by a JSON file.
    Each record: {"id": str, "text": str, "source": str, "embedding": [...]}
    """

    def __init__(self) -> None:
        DATA_PATH.mkdir(parents=True, exist_ok=True)
        self._records: list[dict] = []
        self._load()
        if not self._records:
            self._seed()
        logger.info("Vector store ready — %d chunks indexed", len(self._records))

    # ── public API ───────────────────────────────────────────────────

    def add_document(
        self, text: str, source: str, chunk_size: int = 300, chunk_overlap: int = 50
    ) -> int:
        chunks = self._chunk(text, chunk_size, chunk_overlap)
        for chunk in chunks:
            self._records.append(
                {
                    "id": str(uuid.uuid4()),
                    "text": chunk,
                    "source": source,
                    "embedding": _hash_embed(chunk),
                }
            )
        self._save()
        return len(chunks)

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        if not self._records:
            return []
        q_emb = _hash_embed(query)
        scored = [(_cosine(q_emb, r["embedding"]), r) for r in self._records]
        scored.sort(key=lambda x: -x[0])
        return [
            {"text": r["text"], "source": r["source"], "score": score}
            for score, r in scored[:top_k]
        ]

    def list_sources(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self._records:
            src = r.get("source", "unknown")
            counts[src] = counts.get(src, 0) + 1
        return counts

    def total_count(self) -> int:
        return len(self._records)

    # ── internals ────────────────────────────────────────────────────

    def _load(self) -> None:
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, encoding="utf-8") as f:
                    self._records = json.load(f)
                logger.info("Loaded %d chunks from %s", len(self._records), DATA_FILE)
            except Exception as exc:
                logger.warning("Could not load store: %s — starting fresh", exc)
                self._records = []

    def _save(self) -> None:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self._records, f)

    def _seed(self) -> None:
        logger.info("Seeding vector store with %d sample documents", len(SEED_DOCS))
        for text, source in SEED_DOCS:
            for chunk in self._chunk(text, 300, 50):
                self._records.append(
                    {
                        "id": str(uuid.uuid4()),
                        "text": chunk,
                        "source": source,
                        "embedding": _hash_embed(chunk),
                    }
                )
        self._save()

    @staticmethod
    def _chunk(text: str, size: int, overlap: int) -> list[str]:
        chunks, i = [], 0
        while i < len(text):
            chunks.append(text[i : i + size])
            if i + size >= len(text):
                break
            i += size - overlap
        return chunks
