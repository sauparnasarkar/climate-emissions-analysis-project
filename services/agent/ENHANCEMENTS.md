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

## Step 5 — Security review

An automated vulnerability scan (categories: input validation, auth/authz, crypto/secrets,
injection/RCE, data exposure) plus independent verification of every finding, covering the whole
feature (`services/agent/src/agent/*.py` + `climate-dashboard-react`'s agent integration) against
the pre-Step-1 base commit, not just the latest PR's diff.

**One real finding, already self-flagged during Step 3** (`SPEC.md` "Corrections applied" #16,
resolved here as #19): `stream_query`'s catch-all `except Exception` forwarded `str(exc)` to the
public, unauthenticated `/query` endpoint's client-facing `error` SSE event — a real information-
disclosure surface (MCP connection failures reveal `127.0.0.1:8765`; LangChain/Anthropic SDK
error text isn't meant for end users), and a direct deviation from `api/`'s own established
convention (`DataNotFoundError` → a curated `.message`, never a bare exception's own text). Fixed:
a fixed, generic `QUERY_STREAM_ERROR_MESSAGE` goes to the client; the real exception is logged
server-side via `logger.exception` instead of silently dropped. `tests/test_server.py`'s existing
`test_query_streams_error_event_on_graph_failure` updated to assert the generic message (not the
simulated exception's own text) and, via `caplog`, that the real exception is still logged.

**Everything else checked, no finding above the review's confidence threshold**: CORS (identical
allowlist to `api/main.py`'s, no wildcard/credentials), `thread_id` validation (strict UUID check
before any use; not practically guessable/enumerable), XSS in `WidgetRenderer.tsx` (no
`dangerouslySetInnerHTML` anywhere — every LLM/tool-derived string renders through plain JSX text
interpolation, which React auto-escapes), format-string injection in `progress_labels.py`
(deliberately builder functions, not `.format(**args)`), checkpoint deserialization
(`allowed_msgpack_modules` is an allowlist restricting reconstructable types, not attacker-
supplied bytes), the MCP client's localhost trust boundary (documented B3 design, read-only
public climate-data tools, no realistic high-impact path). `MAX_LIVE_THREADS`'s coarse cap (#14)
is a resource-exhaustion concern, explicitly out of this review's scope (not revisited here —
still a real V1 stopgap, not real LRU/TTL eviction, same as when #14 first flagged it).

Shipped: `server.py`'s `logger`/`QUERY_STREAM_ERROR_MESSAGE`, the updated
`test_query_streams_error_event_on_graph_failure`.

Steps 1–5 of 5 now complete. Not yet built: the Mac Mini deploy, a distinct final action after
all 5 steps land (not itself one of the 5) — see root `ARCHITECTURE.md` for current status.

## Mac Mini deploy

**Status: Running, one piece outstanding (public Cloudflare route).**

New venv (`/opt/homebrew/bin/python3.14`, not bare `python3` — a non-interactive SSH shell's
`PATH` resolves to the stale system 3.9.6 otherwise), `pip install -e '.[dev]'`, full hermetic
suite green on the Mac Mini itself (48 passed). New `com.ghgemissions.agent.plist` launchd
agent mirroring `com.ghgemissions.mcpserver.plist`'s shape (own venv path, port 8766, logs under
`~/Library/Logs/ghgemissions-agent*.log`).

**Real cross-sub-project gap found on the first live dry run, not caught by either sub-project's
own test suite**: `services/agent`'s MCP client couldn't reach the real, deployed
`services/mcp-server` — `mcp.shared.exceptions.McpError: Session terminated`. Two distinct causes,
found in order:
1. Wrong path — the module default `MCP_SERVER_URL=http://127.0.0.1:8765/mcp` assumes local dev;
   the real deploy's `services/mcp-server` runs with `DEPLOY_BASE_PATH` set, which changes its
   real path to `/ghg-emissions-analysis/mcp`. Fixed by setting `MCP_SERVER_URL` explicitly in
   this plist.
2. `services/mcp-server`'s own `transport_security.allowed_hosts` (DNS-rebinding protection,
   `services/mcp-server/SPEC.md` §8.3/§8.4) was locked to `labs.syena.io` only — a real, distinct
   gap in that sub-project, not this one. Confirmed live via curl (`421 Misdirected Request` on
   the real loopback `Host` header, `200 OK` only when spoofing `Host: labs.syena.io`). Fixed as
   its own `services/mcp-server` change (PR #146, not folded into this deploy) — see that
   sub-project's own `ENHANCEMENTS.md` Release 6 for the full writeup. `services/mcp-server`'s
   Release 5 AuthZ work had already reclassified this agent as B3 (co-located, no Cloudflare
   Access needed); that correction covered authentication only; DNS-rebinding protection is a
   separate mechanism that needed its own, independent fix.

`ANTHROPIC_API_KEY` supplied directly into the plist by the user (never handled or viewed by
Claude) — stored as a plain `EnvironmentVariables` entry (`chmod 600` plist, single-user
machine, accepted deliberately; `SPEC.md` §12 open item #6 records the Keychain-based
alternative as a deferred enhancement, not designed further until the machine's threat model
changes).

**First genuine end-to-end verification of this entire build**, once both fixes and the real key
were in place: a live `POST /query` against the running Mac Mini process returned a real SSE
`progress` event, a real `get_country_profile` tool call through `services/mcp-server` to `api/`
(actual China CO₂ data, 1990–2024), two real widgets (`card` + `chart`), and a genuine
Sonnet-generated `response_text` — the full guardrails → tool-call → widget-selection → SSE
pipeline working against live infrastructure, confirmed 2026-08-14.

**Cloudflare Tunnel route added and verified live** (2026-08-14): `labs.syena.io/ghg-emissions-
analysis/agent` → `localhost:8766`, added via the Zero Trust dashboard's Published Application
Routes above the existing unanchored `/ghg-emissions-analysis` catch-all row, same ordering
`services/mcp-server`'s own route already established. A full public-path query (`/health` and a
real `POST /query`) confirmed working from outside the Mac Mini.

**Mobile responsiveness bug, found via real device use after the route went live, fixed same
day.** The `/ask` page overflowed horizontally on an iPhone. Root-caused by reproducing in a
real (non-jsdom) narrow browser viewport rather than guessing from source: `AgentPage.tsx`'s
starter-prompt grid used `gridTemplateColumns: repeat(auto-fit, minmax(280px, 1fr))`, and
`auto-fit`'s intrinsic sizing reserves room for as many fixed-280px tracks as there are grid
items regardless of the container's actual available width — confirmed live, `<main>` rendered
at 968px wide inside a 500px viewport, with three 280px tracks laid out side by side rather than
collapsing to one column. None of the page's other content (the widget-result flex row, which
already had `minWidth: 0` and shrunk correctly) contributed to the overflow — isolated to this
one grid. Fixed with the standard responsive-grid-without-media-queries pattern,
`minmax(min(280px, 100%), 1fr)`, which caps each track's minimum at the container's own
available width instead of a hard floor; confirmed live before touching source (`<main>` dropped
to 484px in the same 500px viewport) and again after rebuild/redeploy. One new regression test
(`AgentPage.test.tsx`) pins the CSS pattern in the grid's inline style so a future edit can't
silently revert to the overflowing literal — jsdom has no real layout engine, so it can't catch
the overflow itself, only the regression of the fix.

**"No widgets generated" bug report, investigated, root cause not reproducible, gap in
observability fixed instead.** A live query ("How has India's emissions grown compared to other
countries?") produced `compose_response_node`'s generic no-data apology instead of real widgets.
Re-running the identical query against the live public endpoint immediately afterward returned
three real widgets with real data — not reliably reproducible. Checked `services/agent` and
`services/mcp-server` logs (both `.log` and `.error.log`) and `api/`'s own uvicorn log around the
relevant window: no errors, no slow requests, only clean `200 OK` churn including a successful
sovereign-scope 215-country historical fan-out. Root cause is genuinely unknowable from what was
retained, and that unknowability is itself the finding: `tools_node` built an error
`ToolCallRecord` on both its unknown-tool and real-tool-failure branches without ever logging
anything, and `ui_selection_node` silently `continue`d past every error record with no signal
that the resulting empty widget list came from every tool call failing rather than from a query
that genuinely matched nothing. Fixed both gaps rather than chasing an unreproducible one-off:
`tools_node` now logs a `logger.warning` on each tool failure; `ui_selection_node` now checks
whether *every* tool call in the turn errored and, if so, appends a scope_notes entry
distinguishing a transient backend failure from a no-match case, so `compose_response_node`
stops inventing a "try rephrasing your question" apology for what was actually a system failure.
Two new tests against a real `services/mcp-server` subprocess (deliberately unreachable
`API_BASE_URL`, matching the existing error-surfacing test's pattern): one confirms the
transient-failure note appears when every call in a turn fails, the other confirms it does
*not* appear when only some do.

**Same "no widgets" symptom, second live occurrence — two hypotheses, first one wrong, corrected
before shipping.** The user pinned the trigger precisely this time: submitting the India starter
prompt right after the China one, same conversation thread. The fix above (correction #20) didn't
cover it — `state.tool_calls` was genuinely empty, not "attempted and failed." Reproduced
reliably (not a one-off) by replaying the exact sequence against the live public endpoint with the
real `thread_id` carried across both calls.

*First hypothesis (wrong, caught by the user before merge).* Root-caused via controlled variant
testing directly against the real Anthropic API on the Mac Mini (the deployed key, handled
entirely server-side — read via `PlistBuddy` inside the SSH command, never viewed or printed):
turn 1's raw message history — including a single prior `get_historical_emissions(scope=
"sovereign")` result (~31KB, full history for all ~215 sovereign countries) — was persisting in
full into turn 2's context. Truncating just that one payload was enough on its own to make the
model call tools normally again, which read as "the large payload is confusing the model." Shipped
a first draft: `finalize_node` pruning the turn's raw agent↔tools round trip via LangGraph's
`RemoveMessage` once the turn's compact summary was written, live-verified to make turn 2 call
`get_historical_emissions` again and return a real widget.

*The user then pointed out the same sequence in Claude Desktop with the MCP connector* — turn 2
also makes zero tool calls there, and Desktop still answers correctly. That reframed everything:
the model *not* calling a tool on turn 2 was never the bug — it's the model correctly reusing
data it already fetched, exactly what an efficient MCP client should do. Confirmed directly by
tracing `agent_node`'s own turn-2 response (previously never surfaced anywhere in the pipeline):
it was a fully correct, detailed, data-grounded answer about India's growth, built from turn 1's
still-present context. The truncation experiment only "worked" because shrinking the payload
removed the data the model needed, forcing a redundant re-fetch — not because anything was
actually confusing it. The real defect: `ui_selection_node`/`compose_response_node` assumed a
`data_query` turn always has fresh `state.tool_calls` to build a response from, and silently
discarded `agent_node`'s own good answer whenever it didn't, synthesizing a "no data" apology that
directly contradicted what the model had just said.

**Reworked before merge.** Reverted the `finalize_node` pruning entirely — it "fixed" the symptom
only by removing the model's ability to reuse context, forcing a wasteful re-fetch on every
follow-up regardless of need. Fixed properly instead: `ui_selection_node` now extracts
`agent_node`'s own final message text (handling both the plain-string and content-block-list
shapes, since extended thinking makes the latter the common case) and uses it directly as
`response_text` when a turn made zero tool calls; a new `route_after_ui_selection` conditional
edge routes that case straight to `finalize`, skipping `compose_response_node` (which has no
widgets to work from and would otherwise overwrite a good answer). No widget is built in this
case — nothing new was fetched — matching `general_climate_node`'s existing text-only pattern.
Verified against the real Anthropic API with the exact repro sequence before shipping: turn 2 now
answers India's growth correctly, from reused context, with zero new tool calls — matching Claude
Desktop's behavior for the identical sequence.

**Flagged separately, not fixed here:** `get_historical_emissions(scope="sovereign")`'s ~31KB,
215-country uncapped payload is no longer "the bug," but its size is still real and still a
`services/mcp-server` concern, not `services/agent`'s — this sub-project's own convention is not
to modify `services/mcp-server` directly. Worth trimming or paginating there independently.
