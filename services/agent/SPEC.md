# Climate Emissions Conversational Agent — Specification

**Status: Implementation in progress (Stage 2 — follows MCP server, Stage 1, `services/mcp-server`)**

Companion to [`services/mcp-server/SPEC.md`](../mcp-server/SPEC.md) (tool layer) and root
[`SPEC.md`](../../SPEC.md) §5.22 (API layer — corrected citation, see "Corrections applied"
below). This document covers the LangGraph agent and generative-UI layer built on top of both —
`services/agent` in the monorepo.

Brought into the repo from the original design doc (`~/Downloads/agent-spec.md`), verified
against real current state, and corrected where verification surfaced drift. See root
[`CLAUDE.md`](../../CLAUDE.md) for the scope note shared by every `services/*` sub-project —
**not internship scope**, a mentor-built post-internship expansion, Stage 2 of the
conversational-agent project that `services/mcp-server` began.

---

## Corrections applied (found during verification, not assumed)

1. **`SPEC.md` §5.21 → §5.22.** The original design doc cited root `SPEC.md` §5.21 for the API
   layer (`scope` param, sovereign-tier gas coverage, `/countries` sovereign count). Root
   `SPEC.md`'s current section for that work is §5.22 — the same stale-citation pattern
   `services/mcp-server`'s own design doc had when it arrived, corrected the same way.
2. **Choropleth prop is `locations` (ISO-3 code array), not `iso_code`.** §3.1 below says
   `get_top_emitters`'s response should carry a country's ISO code "so no separate map-only tool
   is needed" — that data-shape point stands, but the real `SyChart` prop to map it into is
   `locations: string[]` on the series object (`locationmode` defaults to `'ISO-3'`), not
   `iso_code`. `ui_selection` (§8) must emit the real prop name.
3. **`Tile` has no built-in kicker/prompt/arrow composition.** It's a plain container
   (`interactive`, `secondary`, `size`, `disabled`, `fullHeight` + spread `HTMLAttributes`).
   §4's starter-prompt grid and §6's opinion-guardrail suggested reframes both need a small local
   composition (`StarterPromptTile`) built from `Tile` + text + an icon — not a pre-built variant.
4. **Trust boundary: co-located B3, not B4.** `services/agent` is deployed on the same Mac Mini
   as `services/mcp-server` (not an external client), so it reaches `services/mcp-server` over
   `127.0.0.1:8765` unauthenticated — the same B3 boundary `services/mcp-server`→`api/` already
   uses — rather than the Cloudflare-Access-gated public URL + Service Token originally sketched
   in `services/mcp-server/SPEC.md` §8.4 for "the LangGraph agent." See
   [`ARCHITECTURE.md`](ARCHITECTURE.md) for the corrected boundary diagram.
5. **Public endpoint abuse protection: existing Cloudflare edge rate limit, not new app code.**
   `syena.io` already has a domain-level Cloudflare rate-limiting rule matching
   `http.request.uri.path contains "/ghg-emissions-analysis"` (50 requests / 10s per IP,
   confirmed live 2026-08-13). `services/agent`'s public endpoint deploys under that same path
   prefix (`labs.syena.io/ghg-emissions-analysis/agent`), so it inherits this protection
   automatically — no per-app rate-limiting code needed in `services/agent` itself.
6. **LLM test hermeticity.** Every LLM node needs `ChatAnthropic`, which needs
   `ANTHROPIC_API_KEY`. The test suite must pass with no key set (matching
   `services/mcp-server`'s own test suite, which needs no external credentials) — so the graph is
   built with an injectable LLM seam (`build_graph(llm=...)` / `get_llm()`), and unit tests for
   graph routing use a fake/stub LLM. Exactly one real-call smoke test exists
   (`tests/test_llm_smoke.py`), skipped automatically when `ANTHROPIC_API_KEY` is unset.
7. **A checkpointer + stable `thread_id` is required, not optional, for §7/§9's persistence to
   actually work.** `build_graph()` defaults to an in-process `MemorySaver` — this service is a
   single, unreplicated process, so losing in-flight conversations on restart is acceptable,
   matching this project's "no server-side caching beyond what's explicit" bias. Callers must
   invoke the compiled graph with a **partial update dict** (e.g. `{"current_query": "..."}"`),
   not a fresh `AgentState(...)` instance, under a stable
   `config={"configurable": {"thread_id": ...}}` — passing a full model instance overwrites
   every channel, including `tool_cache`, on every turn, silently defeating the whole point of
   persisting it. Confirmed empirically (`tests/test_graph.py`'s
   `test_turn_reset_fields_and_thread_scoped_cache_persist`) before this became load-bearing
   across three steps. Step 3's SSE endpoint mints/holds this `thread_id` per browser session;
   Step 4's frontend carries it across queries in the docked state.
8. **`agent`/`tools` process a whole batch of parallel tool calls per step, not one at a time.**
   §9's pseudocode shows a single `call`, but this isn't a simplification available to skip:
   Anthropic requires every `tool_use` block in an assistant message to have a matching
   `tool_result` in the very next turn, and a model routinely requests several tools in one
   response. `tools_node` iterates every entry in the last message's `tool_calls`; a call that
   the §10 cap blocks mid-batch still gets a synthetic `status="error"` `ToolMessage` (never a
   missing `tool_result`), and the guard's `scope_notes` note is written by a dedicated
   `call_cap_notice` node between `agent`'s conditional edge and `ui_selection` — a conditional-
   edge function can only choose a route, a state write inside one is silently discarded.
9. **`WidgetSpec.props` carries each tool's raw result through unshaped in Step 2.** Building
   the exact per-component prop shape (`SyChart`'s `locations`/`colorValues`, `DataTable`'s
   `columns`, etc.) is Step 4's job, once a renderer exists to consume and be tested against it —
   nothing in Step 2 exercises that shape, so it isn't built yet.
10. **A real MCP tool's successful/failed `ToolMessage.content` is a list of content blocks,
    not a plain string.** `langchain_mcp_adapters`'s wire-protocol conversion wraps a tool's
    result as `[{"type": "text", "text": "<json>"}]` (and the same shape for an error's
    message), unlike a locally-built `StructuredTool.from_function`'s plain-string content. Only
    surfaced by testing against a real `services/mcp-server` subprocess
    (`tests/test_graph.py`'s `test_data_query_against_real_mcp_server`) — a suite built only
    against local fake tools would never have caught this. `graph.py`'s
    `_tool_result_from_message` unwraps both shapes into the same raw dict/string result.
11. **§3's tool→intent table itself was missing `get_forecast_comparison`** — carried over from
    the original pasted spec, not introduced during Step 2's own implementation. Caught by
    Copilot's review of the Step 2 PR (`ui_selection.py`'s `_TOOL_INTENT` dict had the same gap,
    which would have silently produced a `text` widget instead of a `chart` for this tool); fixed
    in both places, plus a regression test pinning the correct `chart`/`line` mapping. A reminder
    that a table copied from an external design doc still needs to be cross-checked against the
    real tool catalog, not just internally consistent with itself.
12. **Progress events (§5) are read from `graph.astream(..., stream_mode="updates")` in
    `server.py`, not a callback threaded into `tools_node`.** The original Step 2 design (an
    `on_progress` callback baked into the graph at `build_graph()` time) doesn't survive contact
    with Step 3's actual serving shape: the graph is built once at startup and reused across
    every request, so a callback bound once at construction time would have concurrent requests'
    progress interleave into whichever caller's queue was bound first. `ToolCallRecord` already
    carries its own `progress_label`, so `server.py`'s `stream_query` reads it straight off the
    `tools` node's per-superstep update, diffed against what it's already streamed (that update
    always carries the full accumulated `tool_calls` list, not just the newest entries — no
    reducer on that field). One consequence: a label surfaces after that tool call finishes, not
    before it starts (`stream_mode="updates"` emits post-node), and a cache-hit's progress event
    is no longer distinguishable from a fresh fetch's (§9's pseudocode's "Reusing: ..." prefix
    has no live callback to attach to anymore) — both acceptable per §5's own "running estimate"
    framing, not a functional regression.
13. **The checkpointer needs `allowed_msgpack_modules` registered, not just a bare
    `MemorySaver()`.** `tool_cache: dict[str, ToolCallRecord]` round-tripping through a
    checkpoint logged "Deserializing unregistered type ... will be blocked in a future version"
    during Step 2's own persistence verification — filtered out as noise at the time, but it's
    exactly the field §7 requires to persist, so it would have broken outright on a future
    `langgraph` upgrade. `graph.py`'s `_default_checkpointer()` registers both `ToolCallRecord`
    and `WidgetSpec` explicitly.
14. **A client-supplied `thread_id` is a real input-validation boundary on a public,
    unauthenticated endpoint, not just a UUID nicety.** `MemorySaver` holds full `messages`
    history and `tool_cache` per thread with no eviction, so `server.py` rejects any `thread_id`
    that isn't a well-formed UUID (400) and bounds the number of distinct threads the process
    will ever track (`MAX_LIVE_THREADS`, 503 once full) — a coarse V1 stopgap, not real LRU/TTL
    eviction, explicitly flagged for Step 5's security review rather than silently deferred.
    **A real bug caught by testing this path directly**: the first version's `None`-input branch
    (minting a fresh id for a brand-new conversation — the common case, since every conversation's
    *first* query takes it) returned early without ever registering the minted id or checking the
    cap, meaning the cap only ever bounded client-supplied ids on later queries in an existing
    thread, never the primary path. Fixed and pinned with a regression test
    (`tests/test_server_validation.py`'s `test_freshly_minted_thread_id_is_also_subject_to_the_cap`).
15. **`server.py`'s `DEPLOY_BASE_PATH` handling mirrors `api/main.py`'s
    `StripDeployPrefixMiddleware`, not `services/mcp-server`'s `_streamable_http_settings`.**
    Both are real "third hand-mirrored copy" precedents in this repo, but they're different
    mechanisms for different transports — `api/`'s is the direct precedent for a FastAPI app
    (this one); `mcp-server`'s passes a path into the MCP SDK's own transport layer, which
    doesn't apply here.
16. **`stream_query` needs a terminal `error` SSE event on an unhandled exception** — Copilot's
    review of the Step 3 PR caught that a `graph.astream()`/`graph.aget_state()` failure after
    the SSE stream had already started (HTTP 200 already sent) tore the connection down with no
    machine-readable signal, leaving the client with a silently truncated stream. Fixed with a
    `try/except Exception` wrapping the generator body, yielding
    `{"event": "error", "data": {"message": str(exc)}}`. Also added `max_length=4096` on
    `QueryRequest.query` — the `MAX_LIVE_THREADS` cap (#14) bounds thread *count*, not
    per-thread payload size, and `MemorySaver` never evicts either way. **Flagged, not fixed,
    for Step 5**: this yields the raw `str(exc)` of *any* exception, broader than `api/`'s own
    convention of surfacing a specific, curated exception `.message` on a 503 — reconsider
    whether error text needs sanitizing/genericizing before it reaches a public,
    unauthenticated client.

---

## 1. Purpose

A conversational agent, surfaced as a new nav item in the React dashboard
(`climate-dashboard-react/`), restricted to the climate-emissions domain, that answers by calling
`services/mcp-server`'s tools and renders results using the existing design-system's chart/grid/
card components — not a generic chatbot.

## 2. Interaction model

**Not a chat transcript.** No message bubbles, no user/assistant turn-taking UI, no `Chatbot`
component. Two states of a single interaction:

- **Landing** — headline, a centered `PromptBar` (`variant="landing"`), and a 2×2 `Tile` grid of
  starter prompts below it (§4). Shown before the first query.
- **Docked** — on first submit, `PromptBar` switches to `variant="docked"` and moves to the top
  of the canvas; the starter-prompt grid is gone for the rest of the session. Each subsequent
  query appends a titled result section to a vertically stacked canvas below the bar, **newest
  section first** (directly under the bar, no scrolling required to see the latest result).
  Older sections remain visible, scrollable below — reads as a generated report being built
  through queries, not a conversation log.

Each result section: a small muted caption showing the query that produced it, a deterministic
title (§3), and its `widgets` array laid out responsively (one widget full-width, two side by
side, wrapping beyond that).

`PromptBar` itself is a shared design-system component — controlled, stateless with respect to
history, one prop surface for both visual states. Confirmed real and merged to `design-system`
`main` (`176401b`); prop surface: `value`, `onChange`, `onSubmit`, `variant: 'landing'|'docked'`,
`placeholder?`, `loading?`, `disabled?`, `actions?`, `ariaLabel?`, `className?`.

## 3. UI-intent schema

Four intents, each a fixed pairing with real design-system components — not generated markup:

| Intent | Component(s) | Chart kinds (if `chart`) |
|---|---|---|
| `chart` | `ChartCard` + `SyChart` | `line` (trends), `band` (forecast CI), `bar` (ranked lists, colorValues for "heatmap" bars), `choropleth` (geography), `treemap` (size+color "heatmap") |
| `grid` | `DataTable` in a `Card`/`CardHeader` | — |
| `card` | `KpiStat` (one or a small row) | — |
| `text` | Plain text in a `Card` | — |

Tool → intent mapping (fixed lookup, no LLM judgment except the one case noted):

| Tool | Intent |
|---|---|
| `get_historical_emissions`, `get_scenario_projection`, `compare_scenarios_across_countries` | `chart` (`line`) |
| `get_forecast` | `chart` (`line` + `band`) |
| `get_forecast_comparison` | `chart` (`line`) — the multi-country equivalent of `get_forecast` |
| `get_top_emitters` | `chart` (`bar`, or `choropleth`/`treemap` per §3.1 below) |
| `get_model_comparison`, `get_gas_composition_by_decade`, `get_forecast_summary`, `get_scenario_cumulative_impact` | `grid` |
| `get_country_profile` | `card`, or `card` + `chart` — **the one non-deterministic case**, see §8 `ui_selection` |
| `get_methodology_notes` | `text` |
| `list_countries` | not user-facing via `ui_selection` — used internally by `guardrail_router`/`agent` for resolution context, never produces its own widget |

Widget `title`/`as_of` captions are generated deterministically from the triggering tool call's
arguments (e.g. `"{country} forecast, {horizon}-year horizon"`), not written by the LLM per call
— same reasoning as the progress labels (§5): consistent, not subject to per-call phrasing drift.

### 3.1 Map and "heatmap" reads

`get_top_emitters`'s chart kind depends on what the query is really asking:
- Ranked list ("who are the top 10") → `bar`, with `colorValues` for magnitude-scaled color.
- Geographic spread ("where are emissions highest") → `choropleth`, with the tool response's ISO
  code carried into `SyChart`'s `locations: string[]` prop (see "Corrections applied" #2 — not
  `iso_code`).
- Size **and** a second metric at once (e.g. current volume vs. forecasted growth — the 4th
  starter prompt) → `treemap`, tile size = one metric, tile color = the other. This is what
  makes a single-widget response cover a "now vs. forecast" comparison instead of needing two
  separate charts.

All three are existing `SyChart` kinds, already proven on the dashboard's Overview page — no new
chart component work, only the kind-selection logic in `ui_selection`.

## 4. Starter prompts

Four prompts, rendered as an interactive `Tile` grid (kicker category label, prompt text, arrow
icon — via the new `StarterPromptTile` composition, see "Corrections applied" #3) on the landing
screen only:

| Category | Prompt |
|---|---|
| Historical trends | *What are `<Country>`'s historical emissions trends, and how do they compare to the top 10 sovereign emitters?* |
| Historical trends | *How has `<Country>`'s emissions grown compared to other countries?* |
| Forecasts | *What are the top 10 forecasted emitters in 2040?* |
| Forecasts | *Considering the top 10 emitters now and the forecasted ones in 2040, show the comparative trend for the countries.* |

The two `<Country>`-templated prompts prefill `PromptBar`'s value with the literal template text
and focus it, for the user to type over the placeholder — no separate country picker. The two
forecast prompts have no placeholder and submit immediately on click.

The same `StarterPromptTile` composition is reused for the opinion-guardrail's suggested reframes
(§6) — one clickable-prompt-card pattern used in two places, not two.

## 5. Progress indicator

`Progress` (labeled, not `DotTyping`) shows during the `agent`↔`tools` loop. Labels are
templated per tool, not LLM-generated per call — one entry per tool in the real 13-tool catalog
(`src/agent/progress_labels.py`, not the illustrative 3-entry excerpt this design doc originally
sketched).

Total step count isn't reliably known upfront (the plan can adapt mid-turn). Displayed
percentage is a running estimate, capped at ~90% until `finalize` completes, then jumps to 100%
— rather than promising a step count the plan might revise. Progress events stream over the same
channel as the final response (SSE), independent of the `messages`/state channel.

## 6. Guardrails

`guardrail_router` classifies every turn (not just the first) into one of four outcomes:

| Classification | Behavior | Rendering |
|---|---|---|
| `off_topic` | Fixed refusal, **no LLM call** — a Python constant, not generated, so it can't drift: *"This assistant is focused on climate emissions data, trend analysis, and forecasts — I can't help with that, but I can answer questions about historical emissions, forecasts, or scenario comparisons."* | `InlineAlert`, no widgets |
| `opinion` | Declines the subjective ask specifically, offers the nearest data-backed reframe | `InlineAlert` + a `StarterPromptTile` row of `suggested_prompts` (§4) |
| `general_climate` | Factual climate questions answerable from the model's own knowledge, constrained to factual/data-forward framing, no tool calls | `text`-intent `Card`, no chart |
| `data_query` | Continues into the `agent`↔`tools` pipeline | `chart`/`grid`/`card` — **never `text`-only**; this is "responses should be completely data driven" made structural, not aspirational |

Every response also carries `scope_notes` (trimming/resolution annotations from the MCP layer,
plus the call-count-guard notice from §10 when it fires) rendered as an `InlineAlert` above the
widgets — a distinct visual element, not folded into the narration text.

## 7. State schema

```python
from typing import Literal, Annotated
from pydantic import BaseModel
from langgraph.graph.message import add_messages

class ToolCallRecord(BaseModel):
    tool_name: str
    args: dict
    result: dict | None = None          # raw MCP tool response, incl. scope_note if present
    progress_label: str                  # templated, e.g. "Fetching historical emissions for India"

class WidgetSpec(BaseModel):
    intent: Literal["chart", "grid", "card", "text"]
    chart_kind: Literal["line", "bar", "band", "choropleth", "treemap"] | None = None
    title: str                           # deterministic, generated from tool args
    as_of: str | None = None             # deterministic, e.g. "Data as of 2024"
    source_tool_call: str                # id into tool_calls, for tracing back to raw data
    props: dict                          # shaped to match the target component's own prop type

class AgentState(BaseModel):
    messages: Annotated[list, add_messages]     # LLM's own memory -- never rendered as a transcript
    current_query: str
    classification: Literal["off_topic", "opinion", "general_climate", "data_query"] | None = None
    tool_calls: list[ToolCallRecord] = []        # this turn only -- reset at the start of every turn
    tool_call_count: int = 0                     # this turn only -- bounds the agent/tools loop, §10
    tool_cache: dict[str, ToolCallRecord] = {}   # whole thread -- never reset, §9
    scope_notes: list[str] = []
    widgets: list[WidgetSpec] = []
    suggested_prompts: list[str] = []            # opinion-pivot reframes, rendered as a Tile row
    response_text: str = ""
```

`messages` persisting across turns is the primary re-fetch avoidance mechanism (§9) — a model
that already saw a country's data two turns ago usually won't re-request it, since it's in
context. This is separate from, and cheaper than, the explicit cache.

## 8. Node catalog

| Node | Type | Reads | Writes | Routes to |
|---|---|---|---|---|
| `guardrail_router` | LLM, structured output | `current_query`, `messages` | `classification` | conditional edge |
| `off_topic` | Deterministic, no LLM call | — | `response_text` (fixed copy) | `finalize` |
| `opinion` | LLM | `current_query` | `response_text`, `suggested_prompts` | `finalize` |
| `general_climate` | LLM, tools unbound | `current_query`, `messages` | `response_text`, `widgets=[{intent:"text"}]` | `finalize` |
| `agent` | LLM, tools bound (MCP) | `messages`, `tool_calls` | next tool request, or "done" | `tools` (loop) or `ui_selection` |
| `tools` | Deterministic executor | pending tool call | `tool_calls`, `tool_cache`, `messages`, progress event | back to `agent` |
| `ui_selection` | Hybrid — templated + one LLM judgment call | `tool_calls` | `widgets` | `compose_response` |
| `compose_response` | LLM (short) | `widgets`, `scope_notes` | `response_text` | `finalize` |
| `finalize` | Deterministic | full state | streams `{widgets, response_text, scope_notes, suggested_prompts}`; appends compact assistant-turn summary to `messages` (not full widget payload, to bound context growth) | `END` |

`tool_calls`/`tool_call_count` reset at the start of every turn, before `guardrail_router` runs.
`tool_cache` is thread-scoped and never resets.

**`ui_selection`'s hybrid nature**: a fixed lookup (§3 table) handles every tool with an
unambiguous intent — no LLM call. Only `get_country_profile`-shaped results need judgment
(`KpiStat`-only vs. `KpiStat` + `chart`, based on `current_query`'s phrasing) — the one
genuinely non-deterministic step in an otherwise templated pipeline.

**Country-argument resolution is inherited for free.** Every `country`/`countries` arg passed to
an MCP tool already runs through `services/mcp-server`'s `resolution.py` guard before this agent
ever sees a result — exact match, fuzzy match above threshold, or an explicit `CountryResolutionError`
tool error below it. `langchain-mcp-adapters`' `MultiServerMCPClient` (default
`handle_tool_errors=True`) converts that error into a `ToolMessage(status="error")` automatically,
so `tools` doesn't need special-case handling — the model just sees a normal tool error and can
retry with a corrected name.

## 9. Tool-call caching

Thread-scoped, keyed by `(tool_name, normalized_args)`. Sorting list-valued args before hashing
matters — `["China","India"]` and `["India","China"]` should hit the same key.

```python
def cache_key(tool_name: str, args: dict) -> str:
    normalized = {k: sorted(v) if isinstance(v, list) else v for k, v in args.items()}
    return f"{tool_name}:{json.dumps(normalized, sort_keys=True)}"

def tools_node(state: AgentState) -> AgentState:
    call = get_pending_tool_call(state.messages)
    key = cache_key(call.tool_name, call.args)

    if key in state.tool_cache:
        record = state.tool_cache[key]
        emit_progress_event(f"Reusing: {record.progress_label}")
    else:
        result = call_mcp_tool(call.tool_name, call.args)   # MCP client of services/mcp-server
        record = ToolCallRecord(
            tool_name=call.tool_name, args=call.args, result=result,
            progress_label=PROGRESS_LABELS[call.tool_name].format(**call.args),
        )
        state.tool_cache[key] = record
        emit_progress_event(record.progress_label)

    state.tool_calls.append(record)
    state.tool_call_count += 1
    state.messages.append(ToolMessage(content=record.result, tool_call_id=call.id))
    return state
```

This is a different layer from `get_top_emitters`'s own no-cache-per-call decision at the MCP
server (that one exists to keep the MCP server stateless across replicas) — this cache lives in
the agent's thread state and doesn't touch the MCP server's statelessness at all.

**A cache hit still counts toward `tool_call_count` (§10).** Exempting hits would create a
loophole — a stuck agent could spam free cached calls without ever tripping the guard. The cache
saves the network round-trip and API cost; it doesn't grant extra loop iterations.

## 10. Call-count guard

```python
MAX_TOOL_CALLS_PER_TURN = 6  # generous headroom; tune after Stage 2 usage

def route_after_agent(state: AgentState) -> Literal["tools", "ui_selection"]:
    if not agent_requested_tool_call(state.messages[-1]):
        return "ui_selection"
    if state.tool_call_count >= MAX_TOOL_CALLS_PER_TURN:
        state.scope_notes.append(
            f"Stopped after {MAX_TOOL_CALLS_PER_TURN} tool calls -- this response may be based on partial data."
        )
        return "ui_selection"
    return "tools"
```

Hitting the cap force-exits the loop into `ui_selection` with whatever's been gathered — not an
error state. The notice reuses the existing `scope_notes` → `InlineAlert` rendering path (§6)
rather than a second "something went wrong" UI pattern.

This one counter transitively bounds total LLM calls per turn: every other node in the graph
fires at most once by structure (router, opinion, general_climate, `ui_selection`'s judgment
call, `compose_response`) — `agent`↔`tools` is the only actual cycle, so it's the only place a
runaway needs guarding.

**Deferred, not designed here**: a session-wide cumulative counter across many turns. This turn-
level cap doesn't bound total cost across a long conversation. A different kind of guard (cost
control, not runaway-loop prevention) with its own question of what happens when it's hit —
left out until real usage shows it's actually needed, rather than designed against a
hypothetical.

## 11. Dependencies

- [`services/mcp-server/SPEC.md`](../mcp-server/SPEC.md) — the full 13-tool catalog `agent` is
  bound to, and the `scope_note`/country-resolution-guard conventions this document's
  `InlineAlert` rendering assumes.
- Root [`SPEC.md`](../../SPEC.md) §5.22 — the API-layer changes (`scope` param, sovereign-tier gas
  coverage, `/countries` sovereign count) that `get_historical_emissions`/
  `get_gas_composition_by_decade` need before `scope="sovereign"` queries work end to end.
- `design-system`'s `PromptBar`, `ChartCard`, `SyChart`, `DataTable`, `Card`/`CardHeader`,
  `KpiStat`, `Tile`, `InlineAlert`, `Progress`, `Spinner` — all confirmed real, merged, exported
  as of this document's Step 1 (2026-08-13).

## 12. Open items

1. Multi-widget layout specifics (exact responsive grid breakpoints for 2 vs. 3+ widgets) — not
   yet pinned down, deferred to Step 4 frontend implementation.
2. ~~`ui_selection`'s `KpiStat`-vs-`chart` judgment call — implementation not yet decided.~~
   **Resolved in Step 2**: a dedicated `with_structured_output` call (`_CountryProfileSelection`,
   `graph.py`'s `ui_selection_node`), separate from the fixed §3 lookup table's deterministic
   path — kept the two paths distinct rather than folding them together, since only this one
   tool needs an LLM call at all and mixing it into a shared call would make every other tool's
   widget-building pay for a judgment it doesn't need.
3. `PromptBar`'s landing→docked transition animation — no existing shared motion token found in
   the design system as of this scoping pass; flagged for a future design-system session.
4. Session-wide cumulative call/cost counter (§10) — deferred pending real Stage 2 usage data.
5. `get_top_emitters`'s bar/choropleth/treemap pick (§3.1) is a keyword heuristic on
   `current_query` (`ui_selection.py`'s `select_top_emitters_chart_kind`), not an LLM call —
   matches §8's claim that only `get_country_profile` needs one. Verified against both starter
   prompts that mention "forecast" (§4): a single forecasted metric stays `bar`; only a query
   naming *both* a current-state concept and a forecast concept together becomes `treemap`.
   Revisit if real queries turn out to need finer-grained intent detection than keyword matching
   provides.
