# RAG·MCP — Knowledge Host

Full-stack Retrieval-Augmented Generation app using the Model Context Protocol.

## Architecture

```
                    ┌─────────────────────────────────────────┐
                    │            Browser / UI                  │
                    └──────────────────┬──────────────────────┘
                                       │ HTTP
                    ┌──────────────────▼──────────────────────┐
                    │         Host  (FastAPI :8000)            │
                    │  GET /          POST /api/ask            │
                    │  GET /api/health  POST /api/ingest       │
                    │  GET /api/documents                      │
                    └──────────┬──────────────────────────────┘
                               │ async method calls
                    ┌──────────▼──────────────────────────────┐
                    │              Agent                       │
                    │  ingest(text, source)                    │
                    │  answer(question, mode)                  │
                    └──────────┬──────────────────────────────┘
                               │ tool calls
                    ┌──────────▼──────────────────────────────┐
                    │           MCP Client (stdio)             │
                    │  search_documents / add_document         │
                    │  web_search                              │
                    └──────────┬──────────────────────────────┘
                               │ subprocess (stdio)
                    ┌──────────▼──────────────────────────────┐
                    │           MCP Server                     │
                    │  ┌─────────────┐  ┌──────────────────┐  │
                    │  │  ChromaDB   │  │  DuckDuckGo      │  │
                    │  │  (RAG mode) │  │  (Web mode)      │  │
                    │  └─────────────┘  └──────────────────┘  │
                    └─────────────────────────────────────────┘
                               │
                    ┌──────────▼──────────────────────────────┐
                    │          Claude API (Anthropic)          │
                    └─────────────────────────────────────────┘
```

### RAG mode request flow
```
Browser → Host → Agent → MCP Client → MCP Server (search_documents + ChromaDB)
       → Agent → Claude API → Host → Browser
```

### Web mode request flow
```
Browser → Host → Agent → MCP Client → MCP Server (web_search + DuckDuckGo)
       → Agent → Claude API → Host → Browser
```

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

The first run downloads the `all-MiniLM-L6-v2` sentence-transformer model (~80 MB).

### 2. Configure environment
```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=sk-ant-...
```

### 3. Run
```bash
bash run.sh
# or manually:
cd host && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Open **http://localhost:8000**

---

## API Reference

| Method | Route | Description |
|--------|-------|-------------|
| `GET`  | `/` | Serve frontend UI |
| `POST` | `/api/ask` | Ask a question (RAG or Web mode) |
| `POST` | `/api/ingest` | Upload / ingest a document |
| `GET`  | `/api/documents` | List all indexed documents |
| `GET`  | `/api/health` | Health + connection status |

### POST /api/ask
```json
// Request
{ "question": "What is RAG?", "mode": "rag" }

// Response (RAG mode)
{ "answer": "RAG stands for...", "sources": ["seed-rag"], "mode": "rag", "chunks_used": 3 }

// Response (Web mode)
{ "answer": "According to recent sources...", "sources": ["https://..."], "mode": "web", "results_used": 5 }
```

### POST /api/ingest
```bash
# Text paste
curl -X POST http://localhost:8000/api/ingest \
  -F 'text=Your document text here...' \
  -F 'source=my-document'

# File upload
curl -X POST http://localhost:8000/api/ingest \
  -F 'file=@report.pdf' \
  -F 'source=report.pdf'
```
```json
// Response
{ "success": true, "source": "my-document", "chunks_stored": 12, "message": "Indexed 12 chunks from 'my-document'" }
```

### GET /api/documents
```json
{
  "documents": [
    { "name": "seed-rag", "chunks": 1, "indexed_at": "2025-01-01T00:00:00+00:00" }
  ],
  "total": 5
}
```

### GET /api/health
```json
{ "status": "ok", "mcp_server": "connected", "vector_store": "ready", "documents_indexed": 5 }
```

---

## End-to-end test with curl

```bash
# 1. Check health
curl http://localhost:8000/api/health

# 2. Upload a document
echo "Python is a high-level programming language known for simplicity." > test.txt
curl -X POST http://localhost:8000/api/ingest \
  -F 'file=@test.txt' -F 'source=test.txt'

# 3. Ask in RAG mode
curl -X POST http://localhost:8000/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"What is Python?","mode":"rag"}'

# 4. Ask in Web mode
curl -X POST http://localhost:8000/api/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"Latest news about AI agents","mode":"web"}'

# 5. List documents
curl http://localhost:8000/api/documents
```

---

## Project structure
```
rag-mcp-app/
├── host/
│   ├── main.py              ← FastAPI app (serves UI + 5 API routes)
│   ├── static/
│   │   └── index.html       ← Wired frontend UI
│   └── README.md
├── agent/
│   ├── agent.py             ← RAG orchestration + Claude API calls
│   └── README.md
├── client/
│   ├── client.py            ← MCP client (singleton, stdio transport)
│   └── README.md
├── server/
│   ├── server.py            ← MCP server (3 tools via FastMCP)
│   ├── vector_store.py      ← ChromaDB + sentence-transformers
│   └── README.md
├── requirements.txt
├── .env.example
└── run.sh
```
