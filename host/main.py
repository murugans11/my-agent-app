"""
FastAPI host — serves the UI and exposes the 5 API routes.
On startup: connects to the MCP server and initialises the Agent singleton.
"""
import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

# Make sibling packages importable regardless of working directory
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from client.client import MCPClient, get_mcp_client  # noqa: E402
from agent.agent import Agent  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"
CHROMA_PATH = ROOT / "server" / "chroma_data"

_agent: Agent | None = None


# ── Lifespan ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _agent
    mcp: MCPClient = get_mcp_client()
    ok = await mcp.connect()
    if ok:
        _agent = Agent(mcp)
        logger.info("Agent ready")
    else:
        logger.error("MCP connection failed — /api/ask and /api/ingest unavailable")
    yield
    await mcp.disconnect()
    logger.info("MCP disconnected")


# ── App ───────────────────────────────────────────────────────────────

app = FastAPI(title="RAG·MCP Host", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Routes ────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.post("/api/ask")
async def ask(body: dict) -> dict[str, Any]:
    if not _agent:
        return {
            "answer": "Agent unavailable — MCP server not connected.",
            "sources": [],
            "mode": body.get("mode", "rag"),
            "chunks_used": 0,
        }
    return await _agent.answer(body["question"], body.get("mode", "rag"))


@app.post("/api/ingest")
async def ingest(
    file: UploadFile | None = File(None),
    text: str | None = Form(None),
    source: str = Form(...),
) -> dict[str, Any]:
    if not _agent:
        return {"success": False, "source": source, "chunks_stored": 0, "message": "Agent unavailable"}
    content = ""
    if file and file.filename:
        content = await _extract_text(file)
        if not source or source == file.filename:
            source = file.filename
    elif text:
        content = text
    if not content.strip():
        return {"success": False, "source": source, "chunks_stored": 0, "message": "No content provided"}
    result = await _agent.ingest(content, source)
    return {
        "success": result["success"],
        "source": result["source"],
        "chunks_stored": result["chunks_stored"],
        "message": f"Indexed {result['chunks_stored']} chunks from '{result['source']}'",
    }


@app.get("/api/documents")
async def list_documents() -> dict[str, Any]:
    counts, _ = _chroma_stats()
    now = datetime.now(timezone.utc).isoformat()
    docs = [{"name": k, "chunks": v, "indexed_at": now} for k, v in sorted(counts.items())]
    return {"documents": docs, "total": len(docs)}


@app.get("/api/health")
async def health() -> dict[str, Any]:
    _, total = _chroma_stats()
    mcp = get_mcp_client()
    return {
        "status": "ok",
        "mcp_server": "connected" if mcp.is_connected else "disconnected",
        "vector_store": "ready",
        "documents_indexed": total,
    }


# ── Helpers ───────────────────────────────────────────────────────────

async def _extract_text(file: UploadFile) -> str:
    data = await file.read()
    name = file.filename or ""
    if name.lower().endswith(".pdf"):
        import io
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if name.lower().endswith(".docx"):
        import io
        import docx
        doc = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    return data.decode("utf-8", errors="replace")


def _chroma_stats() -> tuple[dict[str, int], int]:
    """Read source counts from ChromaDB."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(CHROMA_PATH))
        collection = client.get_or_create_collection("documents")
        results = collection.get(include=["metadatas"])
        counts: dict[str, int] = {}
        for meta in results["metadatas"]:
            src = meta.get("source", "unknown")
            counts[src] = counts.get(src, 0) + 1
        return counts, collection.count()
    except Exception:
        return {}, 0


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
