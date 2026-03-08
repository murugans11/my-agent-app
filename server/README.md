# Server — MCP Tool Server

**Single responsibility:** Expose three MCP tools over stdio transport that
the MCP Client can call. Manages the ChromaDB vector store and DuckDuckGo
web search.

## Tools

### `search_documents(query, top_k=3)`
Embeds `query` using `all-MiniLM-L6-v2`, queries the `rag_mvp_docs` ChromaDB
collection, returns the top-k semantically similar chunks.

```json
// Returns
[{"text": "RAG combines retrieval...", "source": "seed-rag", "score": 0.93}]
```

### `add_document(text, source, chunk_size=300, chunk_overlap=50)`
Splits `text` into overlapping chunks, embeds each chunk, stores in ChromaDB.

```json
// Returns
{"success": true, "chunks_stored": 8, "source": "my-doc"}
```

### `web_search(query)`
Queries DuckDuckGo (no API key needed) and returns top 5 results.

```json
// Returns
[{"title": "...", "snippet": "...", "url": "https://..."}]
```

## Startup seeding

On first run (empty collection), seeds 5 documents about RAG, MCP, ChromaDB,
sentence-transformers, and FastAPI so the system works immediately.

## Storage

ChromaDB persists to `server/chroma_data/` (path relative to `server.py`).
This directory is created automatically.

## Run in isolation (for debugging)

```bash
cd rag-mcp-app/server
python server.py
# Waits for MCP JSON-RPC messages on stdin
# Type Ctrl-C to exit
```

To inspect the vector store directly:
```python
from server.vector_store import VectorStore
vs = VectorStore()
print(vs.list_sources())    # {source: chunk_count}
print(vs.total_count())     # total chunks
print(vs.search("RAG"))     # semantic search
```

## Common errors

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: vector_store` | `sys.path` insertion handles this — run via `python server.py` |
| Slow first start | `all-MiniLM-L6-v2` is being downloaded (~80 MB) |
| `DuckDuckGoSearchException` | Rate limited — wait a few seconds and retry |
| ChromaDB lock error | Another process holds the SQLite lock — stop the other process |
