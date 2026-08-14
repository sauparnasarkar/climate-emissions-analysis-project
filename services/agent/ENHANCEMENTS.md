# `services/agent` — Enhancements / Release History

Mirrors `services/mcp-server/ENHANCEMENTS.md`'s convention: one entry per shipped release, most
recent first, narrating what changed and why — not a duplicate of `SPEC.md`, which stays a
current-state design doc.

---

## Release 1 — Backend scaffold + MCP client (Step 1 of 5)

Brought `~/Downloads/agent-spec.md` into the repo as [`SPEC.md`](SPEC.md), with two corrections
found during verification (choropleth's real prop name is `locations`, not `iso_code`; `Tile`
has no built-in kicker/prompt/arrow composition) and one architecture decision (co-located B3
localhost connection to `services/mcp-server`, not the Cloudflare-Access-gated B4 path
`services/mcp-server/SPEC.md` §8.4 originally sketched for "the LangGraph agent" — see `SPEC.md`
"Corrections applied" #4).

Shipped:
- `src/agent/state.py` — `ToolCallRecord`, `WidgetSpec`, `AgentState` (`SPEC.md` §7), as Pydantic
  models. Verified the `Annotated[list, add_messages]` reducer on `messages` actually appends
  (not overwrites) via a real minimal `StateGraph` invocation, not just model construction —
  de-risked before Step 2 builds the full nine-node graph on this shape.
- `src/agent/mcp_client.py` — wraps `langchain_mcp_adapters.client.MultiServerMCPClient`,
  pointed at `MCP_SERVER_URL` (default `http://127.0.0.1:8765/mcp`). Confirmed
  `MultiServerMCPClient` cannot be used as an async context manager (as of
  `langchain-mcp-adapters` 0.1.0) — construct then `await client.get_tools()`.
- `src/agent/llm.py` — `get_llm()`, the single seam every LLM-backed graph node will take as an
  injectable argument in Step 2, so the test suite never needs a real `ANTHROPIC_API_KEY`.
- `src/agent/server.py` — bare FastAPI app + `/health`. No graph or query endpoint yet.
- Tests: state-model validation and reducer proof (`test_state.py`), a real connectivity test
  launching a `services/mcp-server` subprocess and confirming `MultiServerMCPClient.get_tools()`
  lists all 13 real tools (`test_mcp_client.py`), a `/health` check (`test_server.py`), and one
  real-network LLM smoke test that self-skips without `ANTHROPIC_API_KEY`
  (`test_llm_smoke.py`).

Not yet built: the LangGraph node catalog, SSE streaming, the frontend nav item, and the Mac
Mini deploy — Steps 2–5, `SPEC.md`'s own scope for those steps unchanged.

---

## Release 2 — LangGraph graph core (Step 2 of 5)

Brought SPEC.md §8's full node catalog to life: `guardrail_router` → `off_topic` / `opinion` /
`general_climate` / `agent`↔`tools` (looped, §10's call-count guard) → `ui_selection` →
`compose_response` → `finalize`. Four real findings surfaced during build, all now documented in
`SPEC.md`'s "Corrections applied" #7–10 and fixed before merge:

- **A checkpointer + stable `thread_id` is required for §7/§9's cross-turn persistence to
  actually work** — and invoking with a fresh `AgentState(...)` instance instead of a partial
  update dict silently defeats it (overwrites every channel, including `tool_cache`, every
  turn). Confirmed empirically before this became load-bearing across three future steps.
- **`tools_node` processes a whole batch of parallel tool calls, not one at a time** — §9's
  single-`call` pseudocode isn't a simplification available to skip; Anthropic requires a
  matching `tool_result` for every `tool_use` block in the same turn. A cap-blocked call mid-
  batch still gets a synthetic error `ToolMessage` rather than being silently dropped.
- **§10's cap notice can't be written from `route_after_agent` itself** — conditional-edge
  functions only choose a route, a state write inside one is silently discarded. Moved to a
  dedicated `call_cap_notice` node.
- **A real MCP tool's `ToolMessage.content` is a list of content blocks, not a plain string** —
  only surfaced by testing against a real `services/mcp-server` subprocess
  (`test_data_query_against_real_mcp_server`); a suite built only against local fake tools would
  never have caught this. Fixed in `_tool_result_from_message`.

Also fixed during `ui_selection_node` testing: the `get_country_profile` judgment call was
firing even for a *failed* `get_country_profile` result, wasting an LLM call on data that
`build_country_profile_widgets` was going to discard anyway — now every record is checked for an
error marker before any widget-building or judgment call happens, not just inside the widget
builders themselves.

Shipped:
- `src/agent/cache.py`, `src/agent/progress_labels.py`, `src/agent/prompts.py`,
  `src/agent/ui_selection.py`, `src/agent/graph.py`.
- Tests: one per routing path (off_topic/opinion/general_climate/data_query), a cache-hit-still-
  counts test, the call-count-guard test, a cross-turn persistence + turn-reset test, two real-
  `services/mcp-server` integration tests (one success path, one real tool-execution-error
  path), plus focused unit tests for `cache_key`, `progress_label`, and
  `select_top_emitters_chart_kind`'s heuristic against SPEC.md §4's own starter prompts.

Not yet built: SSE streaming, the frontend nav item, and the Mac Mini deploy — Steps 3–5.

---

## Release 3 — SSE streaming surface (Step 3 of 5)

`server.py` gained the real query surface: `POST /query` runs the compiled graph and streams
SPEC.md §5's progress events, then one final `result` event, over SSE
(`sse_starlette.EventSourceResponse`). `DEPLOY_BASE_PATH`-aware path prefixing mirrors
`api/main.py`'s `StripDeployPrefixMiddleware` directly (the correct precedent for a FastAPI app
— `services/mcp-server`'s `_streamable_http_settings` is a different mechanism for a different
transport, despite both being "third hand-mirrored copy" cases). CORS matches `api/`'s public
B1/B2 tier, protected by the existing Cloudflare edge rate-limit rule, not new app code.

The Step 2 design's `on_progress` callback didn't survive contact with how this service actually
serves requests — the graph is built once at startup and reused across every request, so a
callback bound at construction time would leak one request's progress into another's SSE stream
under concurrent load. Replaced with `graph.astream(..., stream_mode="updates")`: each
`ToolCallRecord` already carries its own `progress_label`, so `stream_query` reads labels
straight off the `tools` node's per-superstep update rather than a callback. Full details in
`SPEC.md`'s "Corrections applied" #12.

Two more real findings, both documented in `SPEC.md` #13–14 and fixed before merge:

- **The checkpointer's default serde silently didn't support `ToolCallRecord`/`WidgetSpec`** —
  a warning noticed but dismissed during Step 2's own persistence verification, now understood
  to be exactly the field SPEC.md §7 requires to survive across turns. Fixed by registering both
  types via `allowed_msgpack_modules`.
- **A real bug in the `thread_id` cap**: the branch that mints a fresh id for a brand-new
  conversation (the common case — every conversation's first query) returned early without ever
  registering the id or checking `MAX_LIVE_THREADS`, so the cap only ever applied to
  client-supplied ids on later queries, never the primary path. Caught by a direct unit test on
  `_validate_and_register_thread_id`, not the HTTP-level tests (which never happened to exercise
  the cap boundary).

Copilot's PR review caught two more, both fixed before merge (`SPEC.md` #16): `stream_query` had
no error handling, so a mid-stream `graph.astream()`/`graph.aget_state()` failure silently
truncated the connection with no machine-readable signal — fixed with a terminal `error` SSE
event. `QueryRequest.query` had no upper bound, letting a client pin arbitrarily large strings
into `MemorySaver` for the process lifetime (the thread-count cap doesn't bound per-thread
payload size) — fixed with `max_length=4096`. Flagged, not fixed: the error event surfaces the
raw `str(exc)` of any exception, broader than `api/`'s own convention of a curated `.message` —
worth revisiting in Step 5.

Shipped:
- `src/agent/server.py`'s real `/query` endpoint, `get_graph` dependency (overridable in tests
  without fighting FastAPI's lifespan), `_validate_and_register_thread_id`,
  `StripDeployPrefixMiddleware`.
- `graph.py`: removed `on_progress`/`ProgressCallback`, added `_default_checkpointer()`.
- Tests: SSE event-sequence assertions (progress before result, not just the final payload) via
  a fake-tool graph through the real ASGI endpoint; one true end-to-end test against a real
  `services/mcp-server` subprocess through that same endpoint; direct unit tests for
  `_validate_and_register_thread_id`'s UUID validation, cap behavior, and reuse semantics;
  `_progress_percent`/`_normalize_deploy_prefix` unit tests.

Not yet built: the Mac Mini deploy — Step 5.

## Step 4 — Frontend integration (`climate-dashboard-react/`)

A new `/ask` nav item ("Ask the Agent", `AgentPage.tsx`) consuming `services/agent`'s real
`POST /query` SSE endpoint from Step 3, rendering `WidgetSpec`s as real `design-system`
components per `SPEC.md` §3 — no generated markup, matching Stage 1/2's own convention.

One real correction made during this step, before any frontend code was written (`SPEC.md` #17):
`get_top_emitters`'s "current + forecast" query no longer resolves to `treemap`. The original
design's treemap tile size/color pair assumed two metrics; the tool's real result carries exactly
one (`co2`). `select_top_emitters_chart_kind` now falls back to `bar` for that case, and
`WidgetSpec.chart_kind`'s `Literal` dropped `"treemap"` entirely — a genuine dual-metric treemap
is deferred to `SPEC.md` §12 open item 5 (needs a merged result from two tool calls).

Shipped:
- `src/agent/useAgentStream.ts` — a hand-rolled `fetch()` + `@microsoft/fetch-event-source`
  hook consuming `POST /agent/query`'s real progress/result/error SSE shape. Request-id-guarded
  against a stale in-flight stream landing after a newer `submit()`, same discipline as
  `hooks/useAsync.ts`'s cancellation guard.
- `src/agent/WidgetRenderer.tsx` — maps every real tool's raw result shape (cross-referenced
  against `api/schemas.py` and `services/mcp-server/src/mcp_server/tools/*.py`, not guessed)
  into its exact `design-system` prop shape. `get_country_profile` dispatches on `widget.intent`
  (`card` vs `chart`), not `source_tool_call` alone — both widgets share one source id.
  `general_climate_node`'s fixed-literal `source_tool_call` (`"general_climate"`, no real tool's
  cache key) gets its own entry — without it, every `general_climate`-classified query would
  silently fall through to the "not recognized" fallback.
- `src/components/StarterPromptTile.tsx` — the `Tile` + `Icon` + text composition `SPEC.md`
  "Corrections applied" #3 called for, reused for both the landing grid (§4) and opinion-
  guardrail suggested reframes (§6).
- `src/pages/AgentPage.tsx` — landing/docked interaction model (§2): a 2×2 starter-prompt grid
  before the first query, newest-result-first stacked sections after. Sections with no widgets
  (off_topic/opinion) render `response_text` as an `InlineAlert`; a `general_climate`-shaped
  single-text-widget result skips the redundant intro paragraph, since the widget already
  carries the same text.
- `vite.config.ts` — a second `agentProxyEntry` (port 8766) alongside the existing `api/` one,
  merged into both `server.proxy` and `preview.proxy` rather than replacing it. No Workbox
  `runtimeCaching` change needed: `NetworkFirst` only intercepts GET by default, and `/query` is
  a POST.
- Tests: `useAgentStream.test.ts` (progress/result/error dispatch, stale-stream guard, non-ok
  `onopen` rethrow), `WidgetRenderer.test.tsx` (representative tools incl. the
  `get_country_profile` intent-dispatch case and the `general_climate` fixed-source case),
  `AgentPage.test.tsx` (landing/docked/loading/error/scope_notes), `StarterPromptTile.test.tsx`.

**A real bug caught by live browser verification, not just the test suite**: the nav route was
first wired as `/agent`, which collides with `vite.config.ts`'s `agentProxyEntry` proxy key
(`${base}agent`) — Vite's dev proxy matches by path prefix, so navigating to the page itself got
proxied to the (not-yet-running) agent backend instead of rendering the SPA, throwing
`ECONNREFUSED`. No test caught this, since Vitest never exercises Vite's own dev-server proxy
layer. Moved the page route to `/ask`; the proxy prefix stays `agent` (matches the already-
decided production Cloudflare route `labs.syena.io/ghg-emissions-analysis/agent`).

**Not verified live**: a real end-to-end query against a running `services/agent` (needs
`ANTHROPIC_API_KEY`, not available in this environment). Verified instead: landing render,
starter-prompt prefill vs. immediate-submit behavior, the docked transition, and the real Vite
proxy path returning a genuine `Bad Gateway` (confirming the SSE POST reaches the proxy layer
correctly) which the `error` SSE/`onopen`-reject path renders as an `InlineAlert` — not a client
crash.
