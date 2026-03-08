"""
Agent — orchestrates RAG and Web-search queries via MCP tools + Claude API.
"""
import logging
import os
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-20250514"

RAG_SYSTEM = (
    "You are a helpful AI assistant with access to a private knowledge base. "
    "Answer using only the provided context. Cite sources by name. "
    "If the answer is not in the context, say so clearly."
)

WEB_SYSTEM = (
    "You are a helpful AI assistant. Synthesize the provided web search results "
    "into a clear, accurate answer. Cite sources by URL where relevant."
)

NO_DOCS_FALLBACK = (
    "No relevant documents found. Please upload documents first "
    "or switch to Web Search mode."
)


class Agent:
    def __init__(self, mcp_client: Any) -> None:
        self._mcp = mcp_client
        self._claude = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

    # ── public operations ─────────────────────────────────────────────

    async def ingest(self, text: str, source: str) -> dict[str, Any]:
        """Store document chunks in the vector store via MCP."""
        result = await self._mcp.add_document(text, source)
        return {
            "success": result.get("success", False),
            "chunks_stored": result.get("chunks_stored", 0),
            "source": result.get("source", source),
        }

    async def answer(self, question: str, mode: str) -> dict[str, Any]:
        """Route the question to RAG or web-search and return a cited answer."""
        if mode == "web":
            return await self._answer_web(question)
        return await self._answer_rag(question)

    # ── RAG ───────────────────────────────────────────────────────────

    async def _answer_rag(self, question: str) -> dict[str, Any]:
        chunks = await self._mcp.search_documents(question, top_k=3)
        if not chunks:
            return {"answer": NO_DOCS_FALLBACK, "sources": [], "mode": "rag", "chunks_used": 0}

        context = "\n\n---\n\n".join(
            f"[Source: {c['source']}]\n{c['text']}" for c in chunks
        )
        sources = list(dict.fromkeys(c["source"] for c in chunks))  # unique, ordered

        response = await self._claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=RAG_SYSTEM,
            messages=[{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
        )
        return {
            "answer": response.content[0].text,
            "sources": sources,
            "mode": "rag",
            "chunks_used": len(chunks),
        }

    # ── Web ───────────────────────────────────────────────────────────

    async def _answer_web(self, question: str) -> dict[str, Any]:
        results = await self._mcp.web_search(question)
        context = "\n\n---\n\n".join(
            f"[{r['title']}]({r['url']})\n{r['snippet']}" for r in results
        )
        urls = [r["url"] for r in results if r.get("url")]

        response = await self._claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=WEB_SYSTEM,
            messages=[
                {"role": "user", "content": f"Search Results:\n{context}\n\nQuestion: {question}"}
            ],
        )
        return {
            "answer": response.content[0].text,
            "sources": urls,
            "mode": "web",
            "results_used": len(results),
        }
