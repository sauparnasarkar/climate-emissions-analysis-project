"""FastAPI app for the conversational agent -- /health and the SSE query endpoint (SPEC.md §5).

Run via `uvicorn agent.server:app` (matches `api/main.py`'s own run convention).
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from .graph import build_graph
from .tracing import configure_logging, new_trace_id, trace_id_var

configure_logging()
logger = logging.getLogger(__name__)

# Generic, non-identifying message for stream_query's catch-all -- SPEC.md "Corrections applied"
# #16/#19: the real exception (MCP connection failures revealing internal ports, LangChain/
# Anthropic SDK error text, etc.) goes to `logger.exception` instead, matching `api/`'s own
# convention of never surfacing a bare `str(exc)` to a public client (its routers catch a typed
# `DataNotFoundError` and raise `HTTPException(..., detail=e.message)` -- a curated message, not
# the exception's own text). This endpoint's failure modes aren't one small enumerable exception
# type the way `DataNotFoundError` is, so one fixed fallback message covers the catch-all here.
QUERY_STREAM_ERROR_MESSAGE = "Something went wrong while processing your query. Please try again."

MAX_LIVE_THREADS = 1000  # SPEC.md §5's client-supplied thread_id keys unbounded server memory
# (MemorySaver never evicts) -- a coarse V1 cap, not real LRU eviction. Flagged for Step 5.
PROGRESS_PERCENT_STEP = 15
PROGRESS_PERCENT_CAP = 90  # SPEC.md §5: capped until finalize completes, then jumps to 100


def _normalize_deploy_prefix(raw: str | None) -> str:
    """Mirrors `api/main.py`'s own `_normalize_deploy_prefix` / `vite.config.ts`'s
    normalizeBase -- reads the same `DEPLOY_BASE_PATH` env var, so this app strips the same
    prefix `api/` and the dashboard build already agree on. No trailing slash."""
    if not raw or raw == "/":
        return ""
    return "/" + raw.strip("/")


DEPLOY_PATH_PREFIX = _normalize_deploy_prefix(os.environ.get("DEPLOY_BASE_PATH"))
DEPLOY_PATH_PREFIX_BYTES = DEPLOY_PATH_PREFIX.encode("utf-8")


class StripDeployPrefixMiddleware:
    """Identical mechanism to `api/main.py`'s middleware of the same name -- see that module
    for the full Cloudflare Tunnel path-prefix rationale. A third independently-owned copy of
    this pattern (`services/mcp-server`'s `_streamable_http_settings` is the second), per this
    repo's established convention of small per-sub-project copies over a shared import."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and DEPLOY_PATH_PREFIX:
            path = scope["path"]
            if path == DEPLOY_PATH_PREFIX or path.startswith(DEPLOY_PATH_PREFIX + "/"):
                scope["path"] = path[len(DEPLOY_PATH_PREFIX) :] or "/"
                raw_path = scope.get("raw_path")
                if raw_path is not None and raw_path.startswith(DEPLOY_PATH_PREFIX_BYTES):
                    scope["raw_path"] = raw_path[len(DEPLOY_PATH_PREFIX_BYTES) :] or b"/"
        await self.app(scope, receive, send)


_live_thread_ids: set[str] = set()


def _validate_and_register_thread_id(thread_id: str | None) -> str:
    """A client-supplied `thread_id` keys unbounded server memory on a public, unauthenticated
    endpoint (`MemorySaver` holds full `messages` history plus `tool_cache` per thread, and
    nothing evicts) -- so this is a real input-validation boundary, not a UUID nicety. Rejects
    anything that isn't a well-formed UUID, and bounds the number of distinct threads this
    process will ever track. `MAX_LIVE_THREADS` is a coarse V1 stopgap, not real LRU
    eviction/TTL -- deferred deliberately, flagged for Step 5's security review rather than
    silently left unbounded."""
    if thread_id is None:
        # A freshly-minted id still goes through the same registration/cap check below -- every
        # new conversation's first query takes this branch, so skipping registration here would
        # mean the cap never actually bounds the common case, only client-supplied ids on later
        # queries in an existing thread.
        thread_id = str(uuid.uuid4())
    else:
        try:
            uuid.UUID(thread_id)
        except (ValueError, AttributeError, TypeError) as exc:
            raise HTTPException(status_code=400, detail="thread_id must be a well-formed UUID.") from exc

    if thread_id not in _live_thread_ids and len(_live_thread_ids) >= MAX_LIVE_THREADS:
        raise HTTPException(status_code=503, detail="Server is at capacity -- try again shortly.")
    _live_thread_ids.add(thread_id)
    return thread_id


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Built once at startup, reused across every request -- fetching MCP tools and constructing
    # the graph per-request would be wasteful, and a callback-per-request progress mechanism
    # isn't needed since progress is read from graph.astream() per call, not a baked-in
    # callback (graph.py's module docstring covers why that distinction matters for
    # concurrent requests). If services/mcp-server is unreachable at startup this raises and the
    # process exits loudly -- this service has no reason to exist without it, matching
    # services/mcp-server's own "no retry/backoff" posture toward api/.
    app.state.graph = await build_graph()
    yield


app = FastAPI(
    title="Climate Emissions Conversational Agent",
    root_path=DEPLOY_PATH_PREFIX,
    lifespan=lifespan,
)
app.add_middleware(StripDeployPrefixMiddleware)
app.add_middleware(
    CORSMiddleware,
    # Public, same B1/B2 tier as api/ -- dashboard-facing traffic, not the MCP tool-calling
    # surface. Protected by the existing Cloudflare edge rate-limit rule on the whole
    # /ghg-emissions-analysis path prefix (SPEC.md "Corrections applied" #5), not app-layer
    # auth -- this is a public feature, matching the rest of the dashboard.
    allow_origins=["http://localhost:5173", "https://labs.syena.io"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class HealthResponse(BaseModel):
    status: str


@app.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(status="ok")


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4096)
    thread_id: str | None = None


def _progress_percent(event_count: int) -> int:
    return min(PROGRESS_PERCENT_CAP, PROGRESS_PERCENT_STEP * event_count)


async def stream_query(graph: CompiledStateGraph, query: str, thread_id: str, trace_id: str) -> AsyncIterator[dict[str, Any]]:
    """Streams SPEC.md §5's progress events, then one final `result` event, over one SSE
    channel. Progress labels come from `tools_node`'s per-superstep update (each `ToolCallRecord`
    already carries its own `progress_label`) via `stream_mode="updates"` -- diffed against what's
    already been seen, since that update always carries the full accumulated `tool_calls` list
    (no reducer on that field), not just the newest entries. The final payload is read via
    `graph.aget_state()` after the stream reaches `END`, rather than hand-accumulating partial
    updates -- the checkpointer already has the authoritative final state.

    `trace_id_var` is set as this generator's own first statement, not by the `/query` handler
    before handing this generator to `EventSourceResponse` -- an async generator doesn't get its
    own private context, it runs in the context of whatever task actually drives its `__anext__`,
    so setting the contextvar here (rather than earlier, in the handler) guarantees every node's
    log line downstream sees the right value regardless of how sse_starlette schedules generator
    consumption relative to the request-handling task. Reset in the `finally` below so it can't
    leak into whatever runs next in that task/context.
    """
    token = trace_id_var.set(trace_id)
    start = time.monotonic()
    status = "ok"
    logger.info("query received")

    config = {"configurable": {"thread_id": thread_id}}
    seen_tool_call_count = 0
    event_count = 0

    try:
        async for update in graph.astream({"current_query": query}, config=config, stream_mode="updates"):
            tools_update = update.get("tools")
            if tools_update is None:
                continue
            tool_calls = tools_update.get("tool_calls") or []
            for record in tool_calls[seen_tool_call_count:]:
                event_count += 1
                yield {
                    "event": "progress",
                    "data": json.dumps({"label": record.progress_label, "percent": _progress_percent(event_count)}),
                }
            seen_tool_call_count = len(tool_calls)

        snapshot = await graph.aget_state(config)
        final_state = snapshot.values
        yield {
            "event": "result",
            "data": json.dumps(
                {
                    "thread_id": thread_id,
                    "trace_id": trace_id,
                    "widgets": [widget.model_dump() for widget in final_state.get("widgets", [])],
                    "response_text": final_state.get("response_text", ""),
                    "scope_notes": final_state.get("scope_notes", []),
                    "suggested_prompts": final_state.get("suggested_prompts", []),
                    "percent": 100,
                }
            ),
        }
    except Exception:
        # Full exception (including internal details like an MCP connection failure's own
        # 127.0.0.1:8765 address, or a LangChain/Anthropic SDK error string) stays server-side
        # only -- this endpoint is public and unauthenticated, so `str(exc)` must never reach the
        # client directly. See QUERY_STREAM_ERROR_MESSAGE's own comment. `trace_id` is an opaque
        # id, not exception content, so including it doesn't reopen that leak -- it lets a
        # user-reported failure be matched to this same `logger.exception` call's server-side line.
        status = "error"
        logger.exception("stream_query failed mid-stream")
        yield {"event": "error", "data": json.dumps({"message": QUERY_STREAM_ERROR_MESSAGE, "trace_id": trace_id})}
    finally:
        logger.info("query complete status=%s total_elapsed=%.3fs", status, time.monotonic() - start)
        trace_id_var.reset(token)


def get_graph(request: Request) -> CompiledStateGraph:
    # A dependency, not a bare app.state.graph read, specifically so tests can override it via
    # `app.dependency_overrides[get_graph] = ...` with a real compiled graph built from a fake
    # LLM/tools (agent.graph.build_graph(llm=..., mcp_tools=...)) -- without needing to fight
    # FastAPI's lifespan startup (which would otherwise require a real ANTHROPIC_API_KEY and a
    # reachable services/mcp-server just to construct a TestClient).
    return request.app.state.graph


@app.post("/query")
async def query(body: QueryRequest, graph: CompiledStateGraph = Depends(get_graph)):
    thread_id = _validate_and_register_thread_id(body.thread_id)
    trace_id = new_trace_id()  # per-query, distinct from thread_id (which spans a whole conversation)
    return EventSourceResponse(stream_query(graph, body.query, thread_id, trace_id))
