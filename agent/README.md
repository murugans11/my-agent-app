# Agent — RAG Orchestration

**Single responsibility:** Receive a question and mode from the Host, call the
appropriate MCP tools, build a prompt, call the Claude API, and return a
structured answer with source citations.

## Interface

```python
agent = Agent(mcp_client)

# Ingest a document
result = await agent.ingest(text="...", source="my-doc")
# → { "success": True, "chunks_stored": 12, "source": "my-doc" }

# Answer a question (RAG mode)
result = await agent.answer(question="What is RAG?", mode="rag")
# → { "answer": "...", "sources": ["seed-rag"], "mode": "rag", "chunks_used": 3 }

# Answer a question (Web mode)
result = await agent.answer(question="Latest AI news", mode="web")
# → { "answer": "...", "sources": ["https://..."], "mode": "web", "results_used": 5 }
```

## What it receives / returns

| Operation | Input | MCP tool called | Claude model | Output |
|-----------|-------|-----------------|--------------|--------|
| `ingest` | text + source | `add_document` | — | `{success, chunks_stored, source}` |
| `answer` (rag) | question | `search_documents` | claude-sonnet-4-20250514 | `{answer, sources, mode, chunks_used}` |
| `answer` (web) | question | `web_search` | claude-sonnet-4-20250514 | `{answer, sources, mode, results_used}` |

## Run in isolation (for debugging)

```python
import asyncio
from client.client import get_mcp_client
from agent.agent import Agent

async def test():
    mcp = get_mcp_client()
    await mcp.connect()
    agent = Agent(mcp)
    print(await agent.answer("What is RAG?", "rag"))
    await mcp.disconnect()

asyncio.run(test())
```

## Common errors

| Error | Fix |
|-------|-----|
| `AuthenticationError` | Check `ANTHROPIC_API_KEY` in `.env` |
| `RuntimeError: MCP client not connected` | Call `mcp.connect()` before creating the Agent |
| Empty `sources` list | No matching chunks in ChromaDB — upload documents first |
