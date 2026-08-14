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
