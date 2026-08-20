# CLAUDE.md — Climate Emissions Conversational Agent (`services/agent`)

## Scope note

This sub-project is **not internship scope** — see the root [`CLAUDE.md`](../../CLAUDE.md)'s
scope note and [`SPEC.md`](SPEC.md). Like `api/`, `climate-dashboard-react/`, and
`services/mcp-server/`, it's a mentor-built post-internship expansion: Stage 2 of the
conversational-agent project `services/mcp-server` began as Stage 1. Don't treat it as an
intern deliverable, and don't imply interns are expected to build or extend it.

## What This Directory Is

A LangGraph agent, surfaced as a new nav item in `climate-dashboard-react/`, that answers
climate-emissions questions by calling `services/mcp-server`'s tools (as an MCP client) and
renders results using real `design-system` components — never generated markup.

Full design (interaction model, UI-intent schema, guardrails, state schema, node catalog,
tool-call caching, call-count guard) is in [`SPEC.md`](SPEC.md) — read that before making
design changes here, not just this file.

## Key Design Decisions (see `SPEC.md` for full rationale)

- **MCP client of `services/mcp-server`, via `langchain-mcp-adapters`' `MultiServerMCPClient`**
  (`src/agent/mcp_client.py`) — not a raw HTTP client of `api/` directly. The whole point of
  Stage 1 was the composed/guarded tool layer (country resolution, trimming); this agent
  inherits those guarantees for free by staying at the MCP layer.
- **Co-located, unauthenticated localhost connection (`SPEC.md` "Corrections applied" #4).**
  This agent and `services/mcp-server` run on the same Mac Mini, so the connection is the same
  B3 trust boundary `services/mcp-server`→`api/` already uses — no Cloudflare Access headers on
  this leg. `MCP_SERVER_URL` env var, default `http://127.0.0.1:8765/mcp`.
- **`CountryResolutionError` propagation is free.** `MultiServerMCPClient`'s default
  `handle_tool_errors=True` converts an MCP tool's `isError=True` result into a
  `ToolMessage(status="error")` fed back to the model automatically — no special-case handling
  needed in the `tools` graph node.
- **Injectable LLM seam (`src/agent/llm.py`'s `get_llm()`), for test hermeticity.** Every
  LLM-backed graph node takes `llm` as an argument. The test suite must pass with no
  `ANTHROPIC_API_KEY` set, matching `services/mcp-server`'s own suite — graph-routing tests
  inject a stub LLM; exactly one test (`tests/test_llm_smoke.py`) makes a real call and skips
  itself when the key is absent. Never add a second, ungated real-network LLM test.
- **`AgentState` is a Pydantic `BaseModel`, not a `TypedDict`** (`src/agent/state.py`).
  Confirmed the `Annotated[list, add_messages]` reducer on `messages` actually works on this
  shape via a real `StateGraph` invocation (not just model construction) before building the
  full node catalog on top of it — see `tests/test_state.py`'s
  `test_add_messages_reducer_appends_across_nodes`.
- **Model: Claude Sonnet 5 (`claude-sonnet-5`) via `langchain-anthropic`**, for every LLM node.
  This is a public-dashboard-facing feature with potentially high query volume; Sonnet is this
  project's own "production traffic" default. An opt-in `LLM_PROVIDER=ollama` seam (`llm.py`)
  exists for local-model experimentation and is currently running as an active trial on the
  deployed instance (`qwen2.5:14b-ctx8k`) — see [`OLLAMA_EVALUATION.md`](OLLAMA_EVALUATION.md)
  for the model comparison, correctness/latency findings, and why this doesn't yet supersede the
  Sonnet default documented here.
- **Public endpoint, no app-layer rate limiting.** The Mac Mini's Cloudflare edge already rate-
  limits the whole `/ghg-emissions-analysis` path prefix (50 req/10s per IP) — `services/agent`
  deploys under that same prefix and inherits the protection. Don't add per-app rate-limiting
  code unless that edge rule changes.
- **Own isolated `pyproject.toml`**, same pattern as `services/mcp-server`'s isolation from the
  root `requirements.txt` — this sub-project's deps (`langgraph`, `langchain-mcp-adapters`,
  `langchain-anthropic`) don't belong in the shared notebook/Streamlit dependency set.
- **A checkpointer + stable `thread_id` is mandatory, not optional** (`graph.py`'s
  `build_graph()`, default `MemorySaver`). Invoke the compiled graph with a **partial update
  dict** (e.g. `{"current_query": "..."}"`) under `config={"configurable": {"thread_id": ...}}`
  — never a fresh `AgentState(...)` instance, which overwrites every channel including the
  thread-scoped `tool_cache` on every single turn. See `SPEC.md` "Corrections applied" #7.
- **`tools_node` processes every tool call in a batch**, not one at a time, and a call blocked
  by the §10 cap mid-batch still gets a synthetic error `ToolMessage` — Anthropic requires a
  `tool_result` for every `tool_use` block in the same turn, no exceptions. See `SPEC.md`
  "Corrections applied" #8.
- **A real MCP tool's `ToolMessage.content` is a list of content blocks, not a plain string** —
  `graph.py`'s `_tool_result_from_message` unwraps both that shape and a local fake tool's
  plain-string shape into the same result. Only ever verify this kind of adapter-level shape
  against a real `services/mcp-server` subprocess, not a hand-built fake tool — see `SPEC.md`
  "Corrections applied" #10 for how this one was actually caught.
- **Progress events come from `graph.astream(..., stream_mode="updates")`, not a callback.**
  `graph.py` has no `on_progress` parameter — it was removed after Step 2's design didn't survive
  contact with Step 3's serving shape (one graph built at startup, reused across every request; a
  callback bound at construction time would leak between concurrent requests). `server.py`'s
  `stream_query` reads each `ToolCallRecord.progress_label` straight off the `tools` node's
  per-superstep update instead. See `SPEC.md` "Corrections applied" #12.
- **The checkpointer's serde must register `ToolCallRecord`/`WidgetSpec`** — a bare
  `MemorySaver()` logs (and a future `langgraph` version will hard-fail on) deserializing
  `tool_cache`'s values. Always build checkpointers via `graph.py`'s `_default_checkpointer()`,
  never a bare `MemorySaver()`, if you ever need a second one (e.g. in a test).
- **`thread_id` is a real input-validation boundary, not a UUID nicety** — `server.py`'s
  `/query` is public and unauthenticated, and `MemorySaver` never evicts. Any change to
  `_validate_and_register_thread_id` needs a direct unit test on the cap/registration behavior,
  not just an HTTP-level test — the one real bug found here (freshly-minted ids skipping
  registration entirely) was invisible at the HTTP level and only caught by testing the function
  directly. See `SPEC.md` "Corrections applied" #14.
- **`stream_query`'s `error` event never carries a raw exception's own text.** `except Exception`
  logs the real exception via `logger.exception` and yields the fixed `QUERY_STREAM_ERROR_MESSAGE`
  to the client instead — same reasoning as `thread_id` validation above: a public, unauthenticated
  endpoint, so exception text (which can reveal internal details like an MCP connection failure's
  own address) must never reach an anonymous caller. See `SPEC.md` "Corrections applied" #19.
- **The `climate-dashboard-react/` nav route is `/ask`, not `/agent`.** `/agent` collides with
  `vite.config.ts`'s `agentProxyEntry` proxy key (`${base}agent`, pointed at this service's own
  port 8766) — Vite's dev proxy matches by path prefix, so a page route literally named `/agent`
  would itself get proxied to this backend instead of ever rendering the SPA. Confirmed live, not
  hypothetical: navigating to a `/agent` page route threw `ECONNREFUSED` against this service
  before it was even running. The backend's own proxy prefix (`agent`) stays as-is — it matches
  the already-decided production Cloudflare route `labs.syena.io/ghg-emissions-analysis/agent`.
- **`get_top_emitters`'s "now vs. forecast" query no longer produces a `treemap`.** Found while
  building the Step 4 renderer: the tool's real result carries one metric (`co2`), so there's no
  second dimension for a treemap's tile color to encode — see `SPEC.md` "Corrections applied"
  #17. `WidgetSpec.chart_kind`'s `Literal` no longer includes `"treemap"` at all.
- **Scope:** classical build discipline, same as the rest of this repo — no scope creep beyond
  `SPEC.md`'s node catalog and UI-intent schema.

## When Helping With This Sub-Project

- Reference `SPEC.md` before adding, removing, or changing a graph node, tool mapping, or
  widget intent.
- This sub-project makes **no changes to `services/mcp-server` or `api/`** — if a fix seems to
  belong there instead, flag it as a separate, independent change rather than folding it in
  here.
- Use the same feature-branch-per-section workflow as the rest of this repo: branch → implement
  → tests → PR → review → merge, one step at a time — see root `CLAUDE.md`.
- Real-data-over-mocks testing philosophy applies here too: `tests/test_mcp_client.py` launches
  a real `services/mcp-server` subprocess rather than mocking `MultiServerMCPClient`.
