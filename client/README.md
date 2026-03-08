# Client — MCP Protocol Client

**Single responsibility:** Manage a persistent stdio connection to the MCP server
subprocess and expose typed async wrappers for each tool.

## Interface

```python
from client.client import get_mcp_client

mcp = get_mcp_client()      # singleton
await mcp.connect()         # spawns server.py, performs MCP handshake
                            # logs: ✅ MCP Connected. Tools: [search_documents, ...]

chunks = await mcp.search_documents("what is RAG", top_k=3)
# → [{"text": "...", "source": "seed-rag", "score": 0.92}, ...]

result = await mcp.add_document(text="...", source="my-doc")
# → {"success": True, "chunks_stored": 4, "source": "my-doc"}

hits = await mcp.web_search("latest AI news")
# → [{"title": "...", "snippet": "...", "url": "https://..."}, ...]

await mcp.disconnect()      # cleanly terminates the server subprocess
```

## Connection lifecycle

The client uses `AsyncExitStack` to manage both the `stdio_client` context and the
`ClientSession` context as a single unit. `connect()` enters both; `disconnect()`
exits both (and terminates the server process).

The FastAPI lifespan handler calls `connect()` on startup and `disconnect()` on
shutdown, so the subprocess lives exactly as long as the web server.

## Run in isolation (for debugging)

```bash
cd rag-mcp-app
python -c "
import asyncio, sys
sys.path.insert(0, '.')
from client.client import get_mcp_client

async def main():
    mcp = get_mcp_client()
    await mcp.connect()
    print(await mcp.search_documents('what is RAG'))
    await mcp.disconnect()

asyncio.run(main())
"
```

## Common errors

| Error | Fix |
|-------|-----|
| `FileNotFoundError: server/server.py` | Run from project root, not from `host/` |
| `RuntimeError: MCP client not connected` | `await mcp.connect()` must be called first |
| Tool returns `None` | Server crashed — check server logs for Python errors |
| `json.JSONDecodeError` | MCP returned unexpected format — check mcp SDK version `>=1.0.0` |
