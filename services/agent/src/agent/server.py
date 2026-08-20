"""FastAPI app for the conversational agent -- /health and the SSE query endpoint (SPEC.md §5).

Run via `uvicorn agent.server:app` (matches `api/main.py`'s own run convention).
"""

from __future__ import annotations

import asyncio
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

from . import settings
from .graph import _default_checkpointer, build_graph
from .llm import get_llm
from .mcp_client import get_mcp_tools
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


class LlmChoiceResponse(BaseModel):
    provider: str
    model: str
    label: str
    updated_at: str


class LlmChoiceRequest(BaseModel):
    id: str


def _llm_choice_response(allowed: settings.AllowedChoice, updated_at: str) -> LlmChoiceResponse:
    return LlmChoiceResponse(provider=allowed.provider, model=allowed.model, label=allowed.label, updated_at=updated_at)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Built once at startup, reused across every request -- fetching MCP tools and constructing
    # the graph per-request would be wasteful, and a callback-per-request progress mechanism
    # isn't needed since progress is read from graph.astream() per call, not a baked-in
    # callback (graph.py's module docstring covers why that distinction matters for
    # concurrent requests). If services/mcp-server is unreachable at startup this raises and the
    # process exits loudly -- this service has no reason to exist without it, matching
    # services/mcp-server's own "no retry/backoff" posture toward api/.
    #
    # checkpointer/mcp_tools are captured on app.state (not just closed over locally) so
    # SPEC.md §14's admin-triggered graph rebuild can reuse both -- a pure model swap needs
    # neither refetched, and reusing the *same* checkpointer instance is what keeps live
    # conversations' history intact across a swap (see _apply_llm_choice below).
    checkpointer = _default_checkpointer()
    mcp_tools = await get_mcp_tools()
    allowed = settings.resolve_active_choice()
    llm = get_llm(allowed.model, provider=allowed.provider)

    app.state.checkpointer = checkpointer
    app.state.mcp_tools = mcp_tools
    app.state.llm_choice = _llm_choice_response(allowed, settings.now_iso())
    app.state.graph = await build_graph(llm=llm, mcp_tools=mcp_tools, checkpointer=checkpointer)
    yield


# Serializes two near-simultaneous admin writes -- last-write-wins, which is fine for a
# single-admin-user UI with no conflict-resolution UX needed. One process-wide lock, not
# per-app, since this service only ever runs one app instance.
_llm_choice_lock = asyncio.Lock()


async def _apply_llm_choice(app: FastAPI, allowed: settings.AllowedChoice) -> LlmChoiceResponse:
    """Rebuilds the graph with the new LLM, reusing the *same* cached `mcp_tools` and
    `checkpointer` instance -- a pure model swap needs neither refetched, and reusing the same
    checkpointer is what keeps every live thread's `messages`/`tool_cache` intact across the
    swap (a fresh checkpointer would silently drop them, SPEC.md §14.5).

    Ordered build -> persist -> swap, not build -> swap -> persist: `app.state` is only mutated
    after *both* the rebuild and the store write succeed, so a failure at either step leaves
    runtime state and the persisted file consistent with each other (a swap-then-persist order
    would let a disk-full/permissions failure on the write leave the process running the new
    model while the store file -- and therefore the next restart -- still names the old one,
    with no signal to the admin that the two had diverged). Either failure returns a curated
    error naming the still-running model, never the raw exception text, matching this module's
    `stream_query` precedent for not leaking internal details to a public endpoint.
    """
    async with _llm_choice_lock:
        llm = get_llm(allowed.model, provider=allowed.provider)
        try:
            new_graph = await build_graph(llm=llm, mcp_tools=app.state.mcp_tools, checkpointer=app.state.checkpointer)
        except Exception as exc:
            previous_label = app.state.llm_choice.label
            logger.exception("failed to rebuild graph for LLM choice %s", allowed.id)
            raise HTTPException(
                status_code=502,
                detail=f"Could not switch models -- the new configuration failed to initialize. Still running: {previous_label}.",
            ) from exc

        updated_at = settings.now_iso()
        stored_choice = settings.LlmChoice(provider=allowed.provider, model=allowed.model, updated_at=updated_at)
        try:
            settings.write_stored_choice(stored_choice)
        except OSError as exc:
            previous_label = app.state.llm_choice.label
            logger.exception("failed to persist LLM choice %s", allowed.id)
            raise HTTPException(
                status_code=502,
                detail=f"Could not switch models -- the new choice could not be saved. Still running: {previous_label}.",
            ) from exc

        app.state.graph = new_graph
        app.state.llm_choice = _llm_choice_response(allowed, updated_at)
        return app.state.llm_choice


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


@app.get("/admin/llm", response_model=LlmChoiceResponse)
def get_llm_choice(request: Request) -> LlmChoiceResponse:
    # Reports the live in-memory choice, not the store file -- the two can diverge (a
    # hand-edited file, or a process older than the file), and the live value is the useful
    # answer for an admin UI.
    return request.app.state.llm_choice


@app.post("/admin/llm", response_model=LlmChoiceResponse)
async def set_llm_choice(body: LlmChoiceRequest, request: Request) -> LlmChoiceResponse:
    allowed = settings.choice_by_id(body.id)
    if allowed is None:
        raise HTTPException(status_code=422, detail=f"Unknown LLM choice id {body.id!r}.")
    return await _apply_llm_choice(request.app, allowed)


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
