"""
MCP Client — async singleton that wraps all three MCP server tools.
Manages subprocess lifecycle via AsyncExitStack.
"""
import json
import logging
import os
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

logger = logging.getLogger(__name__)

SERVER_PATH = Path(__file__).parent.parent / "server" / "server.py"

# Use the venv Python if available; otherwise fall back to python3 / python
def _python_cmd() -> str:
    root = Path(__file__).parent.parent
    # Windows venv
    win_py = root / ".venv" / "Scripts" / "python.exe"
    if win_py.exists():
        return str(win_py)
    # Unix venv
    unix_py = root / ".venv" / "bin" / "python3"
    if unix_py.exists():
        return str(unix_py)
    import shutil
    return shutil.which("python3") or shutil.which("python") or "python3"


class MCPClient:
    def __init__(self) -> None:
        self._session: ClientSession | None = None
        self._exit_stack: AsyncExitStack | None = None
        self._connected = False

    # ── lifecycle ────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """Spawn the MCP server subprocess and perform the MCP handshake."""
        try:
            env = os.environ.copy()
            server_params = StdioServerParameters(
                command=_python_cmd(),
                args=[str(SERVER_PATH)],
                env=env,
            )
            self._exit_stack = AsyncExitStack()
            read, write = await self._exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            self._session = await self._exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await self._session.initialize()

            tools_result = await self._session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            logger.info("✅ MCP Connected. Tools: %s", tool_names)
            self._connected = True
            return True
        except Exception as exc:
            logger.error("MCP connection failed: %s", exc)
            self._connected = False
            return False

    async def disconnect(self) -> None:
        """Cleanly close the MCP session and terminate the server subprocess."""
        try:
            if self._exit_stack:
                await self._exit_stack.aclose()
        except Exception as exc:
            logger.error("Error during MCP disconnect: %s", exc)
        finally:
            self._connected = False
            self._session = None
            self._exit_stack = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    # ── tool wrappers ────────────────────────────────────────────────

    async def search_documents(self, query: str, top_k: int = 3) -> list[dict]:
        logger.info("[MCP] → search_documents(query=%r, top_k=%d)", query, top_k)
        result = await self._call("search_documents", {"query": query, "top_k": top_k})
        chunks = result if isinstance(result, list) else []
        logger.info("[MCP] ← %d chunks returned", len(chunks))
        return chunks

    async def add_document(self, text: str, source: str) -> dict:
        logger.info("[MCP] → add_document(source=%r)", source)
        result = await self._call("add_document", {"text": text, "source": source})
        logger.info("[MCP] ← %s", result)
        return result if isinstance(result, dict) else {}

    async def web_search(self, query: str) -> list[dict]:
        logger.info("[MCP] → web_search(query=%r)", query)
        result = await self._call("web_search", {"query": query})
        hits = result if isinstance(result, list) else []
        logger.info("[MCP] ← %d web results", len(hits))
        return hits

    # ── internal ─────────────────────────────────────────────────────

    async def _call(self, name: str, args: dict) -> Any:
        if not self._connected or self._session is None:
            raise RuntimeError("MCP client is not connected")
        tool_result = await self._session.call_tool(name, arguments=args)
        if not tool_result.content:
            return None

        # mcp ≥1.x returns each list element as a separate TextContent item.
        # Parse every item and return a list when there are multiple, or a
        # scalar when there is only one.
        parsed = []
        for item in tool_result.content:
            text = getattr(item, "text", None)
            if text is None:
                continue
            try:
                parsed.append(json.loads(text))
            except (json.JSONDecodeError, TypeError):
                parsed.append(text)

        if not parsed:
            return None
        return parsed if len(parsed) > 1 else parsed[0]


# ── singleton ─────────────────────────────────────────────────────────

_instance: MCPClient | None = None


def get_mcp_client() -> MCPClient:
    global _instance
    if _instance is None:
        _instance = MCPClient()
    return _instance
