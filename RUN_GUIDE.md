# RAG·MCP Project — Complete Setup & Run Guide

---

## 1. Architecture Overview

```
Browser UI
    ↓  HTTP (port 8000)
Host — FastAPI  (host/main.py)
    ↓  Python import
Agent           (agent/agent.py)
    ↓  Python call
MCP Client      (client/client.py)
    ↓  stdio subprocess (auto-spawned)
MCP Server      (server/server.py)
    ├── ChromaDB vector store  (server/vector_store.py → server/chroma_data/)
    └── DuckDuckGo web search
    ↓  HTTPS
Claude API (Anthropic)  ← model: claude-sonnet-4-20250514
```

**Key design fact:** The MCP Server is NOT started manually.
The MCP Client spawns it as a subprocess over stdio when FastAPI starts.
You only ever run **one command**.

---

## 2. Folder Structure

```
my-agent-app/               ← root (run all commands from here)
├── .env                    ← your secrets (create from .env.example)
├── .env.example            ← template
├── requirements.txt        ← all Python dependencies
├── run.sh                  ← optional one-liner launcher
├── agent/
│   └── agent.py            ← orchestrates RAG/web via MCP + Claude API
├── client/
│   └── client.py           ← MCP Client (spawns server subprocess)
├── host/
│   ├── main.py             ← FastAPI app, entry point
│   └── static/
│       └── index.html      ← Browser UI
└── server/
    ├── server.py           ← MCP Server (tools: search_docs, add_doc, web_search)
    ├── vector_store.py     ← ChromaDB wrapper
    └── chroma_data/        ← ChromaDB persistence (auto-created)
```

One shared `.venv/` is created at the root — all components use it.

---

## 3. Prerequisites

| Requirement | Version | Check command |
|---|---|---|
| Python | 3.9 + | `python --version` |
| pip | latest | `pip --version` |
| Internet | required | for DuckDuckGo + Claude API |

No Node.js or frontend build step is needed — the UI is plain HTML.

---

## 4. One-Time Setup

Run every command from the **project root** (`my-agent-app/`).

### Step 1 — Create the virtual environment

```bash
# Windows (Git Bash / PowerShell / CMD)
python -m venv .venv

# Linux / macOS
python3 -m venv .venv
```

### Step 2 — Activate the virtual environment

```bash
# Git Bash on Windows
source .venv/Scripts/activate

# Windows CMD
.\.venv\Scripts\activate.bat

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate
```

Your prompt will change to `(.venv) ...` when active.
**You must re-activate every time you open a new terminal.**

### Step 3 — Install all dependencies

```bash
pip install -r requirements.txt
```

This installs: `fastapi`, `uvicorn`, `mcp`, `chromadb`, `sentence-transformers`,
`anthropic`, `duckduckgo-search`, `PyPDF2`, `python-docx`, `python-dotenv`, `httpx`.

> First install is slow (~2–5 min) because `sentence-transformers` downloads an
> embedding model. Subsequent starts are fast.

### Step 4 — Create your `.env` file

```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Open `.env` and fill in your real key:

```dotenv
ANTHROPIC_API_KEY=sk-ant-api03-YOUR-REAL-KEY-HERE
CHROMA_PERSIST_DIR=./chroma_data
MCP_SERVER_PATH=./server/server.py
HOST=0.0.0.0
PORT=8000
```

Get your key from: https://console.anthropic.com/settings/api-keys

> **Security:** Never commit `.env` to git. It is already in `.gitignore`.
> Never put a real key in `.env.example` either — that file IS committed.

---

## 5. Running the Application

### Single command to start everything

```bash
uvicorn host.main:app --host 0.0.0.0 --port 8000 --reload
```

What this starts (in order):
1. FastAPI + Uvicorn on port 8000
2. MCPClient connects → spawns `server/server.py` as a subprocess
3. MCP handshake completes → tools registered: `search_documents`, `add_document`, `web_search`
4. Agent singleton is created
5. Browser UI is served at `http://localhost:8000`

### Expected startup output

```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Vector store ready — 0 chunks indexed
INFO:     ✅ MCP Connected. Tools: ['search_documents', 'add_document', 'web_search']
INFO:     Agent ready
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

If you see `MCP connection failed` instead, see Section 8 (Debugging).

### Port assignments

| Component | Port | Notes |
|---|---|---|
| FastAPI Host | `8000` | browser connects here |
| MCP Server | N/A | stdio subprocess, no port |
| ChromaDB | N/A | embedded library, no port |
| DuckDuckGo | N/A | outbound HTTPS only |
| Claude API | N/A | outbound HTTPS only |

---

## 6. Using the Application

Open your browser: **http://localhost:8000**

---

## 7. Testing Each Feature

### Test A — Health check (verify all components are up)

```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "ok",
  "mcp_server": "connected",
  "vector_store": "ready",
  "documents_indexed": 0
}
```

### Test B — Ingest a document into ChromaDB (RAG mode)

**Via the UI:**
1. In the browser, find the **"Ingest Document"** panel
2. Paste some text (or upload a `.txt`, `.pdf`, or `.docx` file)
3. Enter a **Source Name** (e.g., `my_notes.txt`)
4. Click **"Ingest"**
5. The **"Indexed Documents"** list updates to show your document and chunk count

**Via curl:**
```bash
curl -X POST http://localhost:8000/api/ingest \
  -F "text=The capital of France is Paris. It is known for the Eiffel Tower." \
  -F "source=test_fact.txt"
```

Expected response:
```json
{"success": true, "source": "test_fact.txt", "chunks_stored": 1, "message": "Indexed 1 chunks from 'test_fact.txt'"}
```

### Test C — Ask a question in RAG mode

**Via the UI:**
1. Set mode dropdown to **"RAG"**
2. Type: `What is the capital of France?`
3. Click **"Ask"**
4. You will see the answer and which chunks/sources were used

**Via curl:**
```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the capital of France?", "mode": "rag"}'
```

Expected response:
```json
{
  "answer": "The capital of France is Paris, known for the Eiffel Tower.",
  "sources": ["test_fact.txt"],
  "mode": "rag",
  "chunks_used": 1
}
```

### Test D — Ask a question in Web Search mode

**Via the UI:**
1. Set mode dropdown to **"Web Search"**
2. Type: `What is the latest version of Python?`
3. Click **"Ask"**

**Via curl:**
```bash
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the latest version of Python?", "mode": "web"}'
```

The agent will:
- Call `web_search` tool via MCP → DuckDuckGo → returns top 5 results
- Pass results as context to Claude API
- Return a synthesized answer with source URLs

### Test E — List indexed documents

```bash
curl http://localhost:8000/api/documents
```

### Test F — Data flow trace (watch the logs)

With `--reload` active, the terminal shows every hop:

```
# RAG request flow:
INFO  [MCP] → search_documents(query='capital of France', top_k=3)
INFO  [MCP] ← 1 chunks returned from 1 sources
# then Claude API is called, answer returned to browser

# Web search flow:
INFO  [MCP] → web_search(query='latest Python version')
INFO  [MCP] ← 5 web results returned
# then Claude API is called, answer returned to browser

# Ingest flow:
INFO  [MCP] → add_document(source='test_fact.txt', text_len=68)
INFO  [MCP] ← 1 chunks stored for 'test_fact.txt'
```

---

## 8. Changing the Port

If port 8000 is in use:

```bash
uvicorn host.main:app --host 0.0.0.0 --port 8001 --reload
```

Then open: http://localhost:8001

---

## 9. Windows vs Linux Differences

| Topic | Windows | Linux / macOS |
|---|---|---|
| Activate venv | `source .venv/Scripts/activate` (Git Bash) | `source .venv/bin/activate` |
| venv Python path | `.venv\Scripts\python.exe` | `.venv/bin/python3` |
| Copy env file | `copy .env.example .env` | `cp .env.example .env` |
| Line endings | Use Git Bash or WSL to avoid CRLF issues | native |
| Python command | `python` | `python3` |

The Python source code itself is fully cross-platform.

---

## 10. Debugging Common Issues

### "Agent unavailable — MCP server not connected"

The MCP Server subprocess failed to start. Causes:

```bash
# Check: can the venv Python run the server directly?
python server/server.py
# Should print: Vector store ready — 0 chunks indexed
# Then hang (waiting for MCP stdin) — that's correct. Ctrl+C to exit.
```

If that fails, the dependency install may be incomplete:
```bash
pip install -r requirements.txt --force-reinstall
```

### "ANTHROPIC_API_KEY" error or empty responses

```bash
# Verify the key is loaded
python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('ANTHROPIC_API_KEY', 'NOT SET')[:20])"
```

Should print: `sk-ant-api03-...` (first 20 chars)

### ChromaDB / sentence-transformers slow on first run

Normal — downloading the `all-MiniLM-L6-v2` embedding model (~90 MB).
It is cached to `~/.cache/huggingface/` after first download.

### Port already in use

```bash
# Windows — find what is using port 8000
netstat -ano | findstr :8000

# Kill by PID (replace 12345)
taskkill /PID 12345 /F

# Or just use a different port
uvicorn host.main:app --port 8001 --reload
```

### "ModuleNotFoundError: No module named 'X'"

The venv is not activated, or the wrong Python is being used:

```bash
# Confirm you are using the venv Python
which python      # should point to .venv/...
python --version  # should be 3.9+
pip list | grep fastapi  # should show fastapi
```

### DuckDuckGo rate limit (429 / empty results)

DuckDuckGo may temporarily rate-limit. Wait 30–60 seconds and retry.
No API key is required for DuckDuckGo.

---

## 11. Stopping the Application

Press `Ctrl+C` in the terminal running uvicorn.
FastAPI's lifespan handler will gracefully disconnect the MCP client
and terminate the server subprocess automatically.

---

## 12. Quick Reference Card

```bash
# 1. Navigate to project root
cd my-agent-app

# 2. Activate venv (every new terminal)
source .venv/Scripts/activate        # Windows Git Bash
# OR
source .venv/bin/activate            # Linux / macOS

# 3. (First time only) Install deps
pip install -r requirements.txt

# 4. (First time only) Create .env
copy .env.example .env               # Windows
# edit .env, add ANTHROPIC_API_KEY

# 5. Run the full stack
uvicorn host.main:app --host 0.0.0.0 --port 8000 --reload

# 6. Open browser
# http://localhost:8000

# 7. Health check
curl http://localhost:8000/api/health
```
