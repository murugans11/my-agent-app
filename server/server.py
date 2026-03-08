"""
MCP Server — exposes search_documents, add_document, web_search via stdio transport.
Run directly: python server.py
"""
import logging
import sys
from pathlib import Path

# Ensure server directory is on path so vector_store can be imported
sys.path.insert(0, str(Path(__file__).parent))

from duckduckgo_search import DDGS
from mcp.server.fastmcp import FastMCP

from vector_store import VectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

mcp = FastMCP("RAG-MCP-Server")
vector_store = VectorStore()
logger.info("Vector store ready — %d chunks indexed", vector_store.total_count())


# ── Tool 1: search_documents ──────────────────────────────────────────

@mcp.tool()
def search_documents(query: str, top_k: int = 3) -> list[dict]:
    """Search the vector store for chunks relevant to the query."""
    logger.info("[MCP] → search_documents(query=%r, top_k=%d)", query, top_k)
    results = vector_store.search(query, top_k)
    unique_sources = len({r["source"] for r in results})
    logger.info("[MCP] ← %d chunks returned from %d sources", len(results), unique_sources)
    return results


# ── Tool 2: add_document ─────────────────────────────────────────────

@mcp.tool()
def add_document(
    text: str,
    source: str,
    chunk_size: int = 300,
    chunk_overlap: int = 50,
) -> dict:
    """Split text into chunks and store them in the vector store."""
    logger.info("[MCP] → add_document(source=%r, text_len=%d)", source, len(text))
    count = vector_store.add_document(text, source, chunk_size, chunk_overlap)
    logger.info("[MCP] ← %d chunks stored for %r", count, source)
    return {"success": True, "chunks_stored": count, "source": source}


# ── Tool 3: web_search ───────────────────────────────────────────────

@mcp.tool()
def web_search(query: str) -> list[dict]:
    """Search the web via DuckDuckGo and return top 5 results."""
    logger.info("[MCP] → web_search(query=%r)", query)
    results: list[dict] = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                results.append(
                    {
                        "title": r.get("title", ""),
                        "snippet": r.get("body", ""),
                        "url": r.get("href", ""),
                    }
                )
    except Exception as exc:
        logger.error("[MCP] web_search error: %s", exc)
    logger.info("[MCP] ← %d web results returned", len(results))
    return results


if __name__ == "__main__":
    mcp.run()
