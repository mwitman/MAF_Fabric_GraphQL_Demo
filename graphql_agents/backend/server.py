"""FastAPI backend for the GraphQL Agents chat UI.

Exposes:
    POST /api/chat          — SSE stream of agent responses
    DELETE /api/chat/{id}   — delete a conversation thread
    GET  /api/health        — healthcheck
    GET  /                  — serves the built React frontend (static files)
"""

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

# ---------------------------------------------------------------------------
# Ensure the parent graphql_agents dir is on sys.path so we can import
# orchestrator_agent as a package.
# ---------------------------------------------------------------------------
_backend_dir = Path(__file__).resolve().parent
_graphql_agents_dir = _backend_dir.parent
if str(_graphql_agents_dir) not in sys.path:
    sys.path.insert(0, str(_graphql_agents_dir))

# Load .env from graphql_agents/
load_dotenv(_graphql_agents_dir / ".env")

# Import the pre-built orchestrator agent
from orchestrator_agent import agent  # noqa: E402
from agent_framework._types import (  # noqa: E402
    FunctionCallContent,
    FunctionResultContent,
    TextContent,
)
from agent_framework._threads import AgentThread  # noqa: E402
from backend.memory import create_memory  # noqa: E402

# ---------------------------------------------------------------------------
# Mem0 memory layer — long-term context across sessions
# ---------------------------------------------------------------------------
import logging as _logging
_mem0_logger = _logging.getLogger("mem0")
try:
    memory = create_memory()
    _mem0_logger.info("Mem0 memory layer initialised")
except Exception as _e:
    _mem0_logger.warning("Mem0 unavailable — running without memory: %s", _e)
    memory = None

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Fabric GraphQL Agents")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tightened in production via env var
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# In-memory conversation threads  {conversation_id: AgentThread}
# ---------------------------------------------------------------------------
_threads: dict[str, AgentThread] = {}


def _get_or_create_thread(conversation_id: str) -> AgentThread:
    if conversation_id not in _threads:
        _threads[conversation_id] = AgentThread()
    return _threads[conversation_id]


# ---------------------------------------------------------------------------
# SSE helpers
# ---------------------------------------------------------------------------
def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ---------------------------------------------------------------------------
# SSE streaming endpoint
# ---------------------------------------------------------------------------
@app.post("/api/chat")
async def chat(request: Request):
    body = await request.json()
    message: str = body.get("message", "")
    conversation_id: str = body.get("conversation_id") or str(uuid.uuid4())
    user_id: str = body.get("user_id") or "default_user"

    if not message.strip():
        return {"error": "message is required"}, 400

    # --- Mem0: retrieve relevant memories and prepend as context ---
    enriched_message = message
    if memory:
        try:
            results = memory.search(query=message, filters={"user_id": user_id}, limit=5)
            memories_list = results.get("results", []) if isinstance(results, dict) else results
            if memories_list:
                mem_lines = "\n".join(f"- {m['memory']}" for m in memories_list)
                enriched_message = (
                    f"[Relevant context from previous conversations]\n{mem_lines}\n\n"
                    f"{message}"
                )
        except Exception as exc:
            _mem0_logger.warning("Mem0 search failed: %s", exc)

    thread = _get_or_create_thread(conversation_id)

    async def event_stream():
        yield _sse({"type": "meta", "conversation_id": conversation_id})

        full_response = []  # collect text chunks for Mem0 storage
        try:
            async for update in agent.run_stream(enriched_message, thread=thread):
                for content in update.contents:
                    if isinstance(content, TextContent) and content.text:
                        full_response.append(content.text)
                        yield _sse({
                            "type": "text",
                            "content": content.text,
                        })
                    elif isinstance(content, FunctionCallContent):
                        yield _sse({
                            "type": "tool_call",
                            "name": content.name,
                            "call_id": content.call_id,
                        })
                    elif isinstance(content, FunctionResultContent):
                        yield _sse({
                            "type": "tool_result",
                            "call_id": content.call_id,
                        })
        except Exception as exc:
            yield _sse({"type": "error", "content": str(exc)})

        yield _sse({"type": "done"})

        # --- Mem0: store the exchange for future recall ---
        if memory and full_response:
            try:
                exchange = [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": "".join(full_response)},
                ]
                memory.add(exchange, user_id=user_id)
            except Exception as exc:
                _mem0_logger.warning("Mem0 add failed: %s", exc)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


_static_dir = _backend_dir / "static"
if _static_dir.is_dir():
    # Serve static assets (JS, CSS, etc.)
    app.mount("/assets", StaticFiles(directory=str(_static_dir / "assets")), name="assets")

    # Catch-all: serve index.html for any non-API route (SPA support)
    from fastapi.responses import FileResponse

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = _static_dir / full_path
        if full_path and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(_static_dir / "index.html")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8080")),
        reload=False,
    )
