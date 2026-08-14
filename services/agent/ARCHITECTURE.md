# `services/agent` — Architecture

A current-state description of how this sub-project is actually built, updated on
architecturally-significant changes (new node, new data flow, new deploy pattern) — not a
history log (`ENHANCEMENTS.md`) or a design rationale doc (`SPEC.md`). Read `SPEC.md` first for
*why*; this is *what exists and how the pieces connect*.

**Status: Step 3 of 5 complete.** Sections below marked *(planned, Step N)* describe target
shape from `SPEC.md`, not yet-built code — kept here rather than only in `SPEC.md` so this
document stays the single "what actually connects to what" reference as later steps land.

---

## Process topology

```
climate-dashboard-react/  (browser)
        │  HTTPS, public, no auth
        ▼
services/agent            (this sub-project — FastAPI + LangGraph, own venv/process/port)
        │  HTTP, localhost only, unauthenticated (B3 boundary)
        ▼
services/mcp-server        (Stage 1 — FastMCP, own venv/process, port 8765)
        │  HTTP, localhost only, unauthenticated (B3 boundary)
        ▼
api/                       (FastAPI, own process, port 8081)
        │  pandas over gitignored data/ CSVs
        ▼
data/*.csv
```

`services/agent` and `services/mcp-server` are co-located on the same deploy host (the Mac
Mini) — see "Corrections applied" #4 in `SPEC.md`. That's why the `agent`→`mcp-server` leg is
plain localhost HTTP rather than the Cloudflare-Access-gated public URL
`services/mcp-server/SPEC.md` §8.4 originally sketched for an external LangGraph client: a
co-located agent never leaves the machine, so it's the same B3 trust boundary
`services/mcp-server`→`api/` already uses, not the B4 case Access was built for.

## Module map (current)

| Module | Responsibility |
|---|---|
| `src/agent/state.py` | `AgentState`/`ToolCallRecord`/`WidgetSpec` — the LangGraph state schema (`SPEC.md` §7). Pydantic `BaseModel`, `messages` uses the `add_messages` reducer. |
| `src/agent/mcp_client.py` | Builds a `MultiServerMCPClient` pointed at `services/mcp-server` (`MCP_SERVER_URL`, default `http://127.0.0.1:8765/mcp`) and exposes `get_mcp_tools()` for LangGraph's tool-binding. |
| `src/agent/llm.py` | `get_llm()` — the single `ChatAnthropic` construction point. Every graph-building function takes `llm` as an injectable argument so tests never require a real API key. |
| `src/agent/server.py` | FastAPI app. Currently just `/health`; gains the SSE query endpoint in Step 3. |
| `src/agent/cache.py` | `cache_key()` — SPEC.md §9's thread-scoped tool-call cache key, list-arg-order-independent. |
| `src/agent/progress_labels.py` | `progress_label(tool_name, args)` — one builder function per real tool (not `.format()` templates; every tool has an optional arg a bare template can't handle safely). |
| `src/agent/prompts.py` | Every fixed/system prompt (`SPEC.md` §6's off-topic copy, guardrail classifier, opinion/general_climate/agent/ui_selection/compose_response system prompts). |
| `src/agent/ui_selection.py` | The fixed §3 tool→intent lookup, `get_top_emitters`'s bar/choropleth/treemap keyword heuristic (§3.1), and the `get_country_profile` card/card+chart widget builder. `WidgetSpec.props` carries each tool's raw result through unshaped — Step 4's renderer builds the real per-component prop shape. |
| `src/agent/graph.py` | The full node catalog (`SPEC.md` §8): `guardrail_router` → `off_topic` / `opinion` / `general_climate` / `agent`↔`tools` (looped, `call_cap_notice` on cap trip) → `ui_selection` → `compose_response` → `finalize`. `build_graph()` is async (fetches MCP tools once), takes injectable `llm`/`mcp_tools`/`checkpointer`, and requires a checkpointer + `thread_id` for cross-turn `tool_cache`/`messages` persistence to work at all — see `SPEC.md` "Corrections applied" #7. `_default_checkpointer()` registers `ToolCallRecord`/`WidgetSpec` for msgpack (#13). No `on_progress` callback (removed in Step 3, #12) — progress is read from `graph.astream(..., stream_mode="updates")` by whichever caller is running the graph. |

`server.py`'s `POST /query` runs the compiled graph (injected via the `get_graph` FastAPI
dependency, resolved from `app.state.graph` in production, overridable in tests) and streams
SPEC.md §5's progress events, then one final `result` event
(`{thread_id, widgets, response_text, scope_notes, suggested_prompts, percent: 100}`), over SSE
(`sse_starlette.EventSourceResponse`). `DEPLOY_BASE_PATH`-aware path prefixing mirrors
`api/main.py`'s `StripDeployPrefixMiddleware` directly (the correct precedent for a FastAPI app
— `services/mcp-server`'s `_streamable_http_settings()` is a different mechanism for a
different transport, despite both being "third hand-mirrored copy" cases, #15). `thread_id` is
either client-supplied (validated as a well-formed UUID) or server-minted on a client's first
query; either way it's registered against a coarse `MAX_LIVE_THREADS` cap (#14) — a real
input-validation boundary on this public, unauthenticated endpoint, not a nicety, since
`MemorySaver` never evicts.

## Trust boundaries

Extends the four-boundary model `services/mcp-server/SPEC.md` §8 established:

| Boundary | Leg | Auth |
|---|---|---|
| B1/B2 | Browser → `services/agent` | None — public, same tier as `api/`. Protected at the Cloudflare edge by an existing domain-level rate-limit rule matching `/ghg-emissions-analysis*` (50 req/10s per IP), not app-layer code. |
| B3 | `services/agent` → `services/mcp-server` | None — localhost-only, co-located (see above). |
| B3 | `services/mcp-server` → `api/` | None — unchanged from Stage 1. |
| B4 | External MCP clients (Claude Desktop, testers) → `services/mcp-server` | Cloudflare Access, Service Tokens — unchanged from Stage 1; `services/agent` does **not** use this path. |

## Deploy topology (Mac Mini)

*(planned, Step 6)* `com.ghgemissions.agent.plist` launchd agent, mirroring
`com.ghgemissions.mcpserver.plist` — own venv (`/opt/homebrew/bin/python3.14`, not bare
`python3` — a non-interactive SSH shell's `PATH` resolves to the stale system 3.9.6 otherwise),
own port, own logs under `~/Library/Logs/ghgemissions-agent*.log`, `ANTHROPIC_API_KEY` set via
the plist's `EnvironmentVariables` (never committed to git — the plist itself lives only on the
Mac Mini, handed off as deploy instructions, same as `services/mcp-server`'s own plist).

## See also

- [`SPEC.md`](SPEC.md) — full design rationale, state schema, node catalog, guardrails.
- [`CLAUDE.md`](CLAUDE.md) — agent-facing conventions for this sub-project.
- [`ENHANCEMENTS.md`](ENHANCEMENTS.md) — release history.
- Root [`ARCHITECTURE.md`](../../ARCHITECTURE.md) — the whole-system view this document extends.
