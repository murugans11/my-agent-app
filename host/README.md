# Host — FastAPI Web Server

**Single responsibility:** Serve the frontend UI and expose the 5 HTTP API routes that
bridge the browser to the Agent/MCP layer.

## Interface

| In | Out |
|----|-----|
| HTTP requests from the browser | JSON responses matching the UI's contract |
| `UploadFile` (multipart) for `/api/ingest` | Extracted text passed to the Agent |
| Startup event | Spawns MCP server via `MCPClient.connect()` |
| Shutdown event | Calls `MCPClient.disconnect()` |

## Routes

| Route | Handler | Notes |
|-------|---------|-------|
| `GET /` | `root()` | Serves `static/index.html` |
| `POST /api/ask` | `ask()` | Delegates to `agent.answer()` |
| `POST /api/ingest` | `ingest()` | Extracts text, delegates to `agent.ingest()` |
| `GET /api/documents` | `list_documents()` | Reads ChromaDB directly (no sentence-transformer) |
| `GET /api/health` | `health()` | Returns MCP + vector store status |

## Run in isolation (for debugging)
```bash
cd host
ANTHROPIC_API_KEY=sk-ant-... uvicorn main:app --reload --port 8000
```

If the MCP server fails to connect, `/api/ask` and `/api/ingest` return graceful
error messages — the server stays up.

## Common errors

| Error | Fix |
|-------|-----|
| `ModuleNotFoundError: client` | Run from `host/` directory, or use `run.sh` |
| `MCP connection failed` | Check that `python server/server.py` is runnable (dependencies installed) |
| `ANTHROPIC_API_KEY not set` | Add key to `.env` file |
| PDF/DOCX extraction fails | Ensure `PyPDF2` and `python-docx` are installed |
