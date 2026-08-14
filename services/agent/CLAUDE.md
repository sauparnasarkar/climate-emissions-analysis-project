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
  project's own "production traffic" default.
- **Public endpoint, no app-layer rate limiting.** The Mac Mini's Cloudflare edge already rate-
  limits the whole `/ghg-emissions-analysis` path prefix (50 req/10s per IP) — `services/agent`
  deploys under that same prefix and inherits the protection. Don't add per-app rate-limiting
  code unless that edge rule changes.
- **Own isolated `pyproject.toml`**, same pattern as `services/mcp-server`'s isolation from the
  root `requirements.txt` — this sub-project's deps (`langgraph`, `langchain-mcp-adapters`,
  `langchain-anthropic`) don't belong in the shared notebook/Streamlit dependency set.
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
