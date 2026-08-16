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
17. **`get_top_emitters`'s "current + forecast" query no longer resolves to `treemap`.** Found
    while building Step 4's widget renderer: the original design's treemap tile size/color pair
    assumed two metrics, but `get_top_emitters`'s real result (`composed.py`) carries exactly one
    (`co2`) — coloring tiles by the value that already sizes them isn't a second dimension, it's
    decoration. `select_top_emitters_chart_kind` now falls back to `bar` for that case (same as
    any other non-geographic query); `WidgetSpec.chart_kind`'s `Literal` no longer includes
    `"treemap"`. A genuine dual-metric treemap is deferred to §12 open item 5 — it needs a merged
    result from two tool calls, which `ui_selection` doesn't build.
18. **Resolved (was: `PromptBar` has no imperative focus API, so the §4 starter-prompt "prefill
    and focus" behavior only prefills).** `PromptBar`'s prop surface at the time was `value`,
    `onChange`, `onSubmit`, `variant`, `placeholder`, `loading`, `disabled`, `actions`,
    `ariaLabel`, `className` — no ref forwarding, no exposed `.focus()`; `AgentPage.tsx`'s
    `handleStarterClick` could only set `value`, not move focus, and this repo's own
    against-hacks convention ruled out a DOM-query workaround keyed to `design-system`'s internal
    CSS class names. Fixed properly instead of worked around: `PromptBar` now exposes its
    textarea via `React.forwardRef<HTMLTextAreaElement, ...>` (design-system PR #44, same
    pattern `Textarea` itself already used) — see §4's current text for how `handleStarterClick`
    uses it.
19. **`stream_query`'s terminal `error` event no longer surfaces `str(exc)` directly (Step 5,
    resolving #16's own "flagged, not fixed" item).** A Step 5 security review (automated
    vulnerability scan + independent verification, not just the earlier Copilot pass) confirmed
    the risk #16 already named: a bare `except Exception as exc: ... str(exc)` on a public,
    unauthenticated endpoint can leak internal details (an MCP connection failure's own
    `127.0.0.1:8765` address, LangChain/Anthropic SDK error text) to any client. Fixed by
    replacing the client-facing message with a fixed, generic `QUERY_STREAM_ERROR_MESSAGE`
    (`server.py`) and logging the real exception server-side via `logger.exception` instead —
    matching `api/`'s own established convention of never forwarding a bare exception's text,
    just a curated one (`DataNotFoundError` → `HTTPException(..., detail=e.message)`), adapted
    here since this endpoint's failure modes aren't one small enumerable exception type the way
    `DataNotFoundError` is. `tests/test_server.py`'s `test_query_streams_error_event_on_graph_failure`
    now asserts the generic message *and* (via `caplog`) that the real exception was logged, not
    silently dropped.
20. **A turn where every tool call fails was indistinguishable from one that genuinely matched no
    widget.** Found investigating a live "no widgets generated" bug report that turned out not to
    be reliably reproducible, and — because `tools_node` logged nothing on either of its error
    branches — not diagnosable from logs either. Fixed on both sides: `tools_node` now logs a
    `logger.warning` when a tool is unknown or a real tool call errors; `ui_selection_node` now
    checks whether every `ToolCallRecord` in the turn errored and, if so, appends a `scope_notes`
    entry naming it a transient backend failure, so `compose_response_node` stops synthesizing a
    generic "try rephrasing" apology that looks identical to an honest no-match case. See
    `ENHANCEMENTS.md`'s "Mac Mini deploy" section for the full investigation.
21. **A `data_query` turn with zero tool calls isn't a bug — the model reusing already-fetched
    context is correct, expected behavior, and the pipeline discarding its answer was the actual
    defect.** Found reproducing a second, live "no widgets" report the user pinned to a specific
    sequence (India query submitted right after the China starter prompt, same thread) —
    correction #20's fix didn't cover it, since `state.tool_calls` was genuinely empty (zero tool
    calls attempted, not "attempted and failed"). The first hypothesis, root-caused via controlled
    variant testing directly against the real Anthropic API (Mac Mini, key handled server-side
    only), was that a single prior turn's `get_historical_emissions(scope="sovereign")` result
    (~31KB, all ~215 sovereign countries' full history) left in context was confusing the model
    into skipping tool calls — truncating that one payload in isolation, everything else
    untouched, did flip the model back to calling tools. **That hypothesis was wrong**, caught by
    the user comparing against Claude Desktop's own MCP client: the identical two-turn sequence
    there also produces zero tool calls on turn 2, and Desktop still answers correctly — because
    it *reuses* turn 1's already-fetched sovereign data rather than re-fetching it, exactly the
    efficient behavior a model should exhibit. Confirmed directly: `agent_node`'s own discarded
    turn-2 text (captured via tracing, never previously surfaced anywhere) was a fully correct,
    detailed, data-grounded answer about India's growth built from turn 1's context. The truncation
    experiment "worked" only because shrinking the payload removed the *data* the model needed,
    forcing a redundant re-fetch — not because it fixed a defect in the model's judgment. The real
    defect: `ui_selection_node`/`compose_response_node` assumed a data_query turn always produces
    fresh `state.tool_calls` to build widgets and a response from, and silently discarded
    `agent_node`'s own answer whenever it didn't, synthesizing a misleading "no data" apology that
    actively contradicted what the model had just said. Fixed by giving that answer somewhere to
    go instead of erasing it: `ui_selection_node` now extracts `agent_node`'s final message text
    (handling both plain-string and content-block-list shapes, since extended thinking makes the
    latter the common case) and sets it as `response_text` directly when `state.tool_calls` is
    empty; a new `route_after_ui_selection` conditional edge sends that case straight to
    `finalize`, skipping `compose_response_node` entirely (it has no widgets to synthesize from
    and would otherwise overwrite a good answer). **A first draft of this fix pruned all
    prior-turn tool history in `finalize_node` instead** (via `RemoveMessage`), which also
    "worked" empirically but for the wrong reason: it prevented the model from ever having old
    context to reuse, forcing a fresh tool call on every follow-up regardless of whether one was
    actually needed. Reverted once the reuse behavior was understood to be correct and worth
    preserving — see `ENHANCEMENTS.md` for the full sequence of both hypotheses. (Correction #22
    below adds a widget to this path after all, for a frontend reason unrelated to this point.)
22. **A widget-free zero-tool-call answer (correction #21) rendered inside `climate-dashboard-
    react`'s InlineAlert — off_topic/opinion's short guardrail-text component — instead of as a
    normal response, and with raw markdown syntax showing through.** `AgentPage.tsx`'s
    `!hasWidgets` check was written when the only zero-widget shape was off_topic/opinion's brief
    apology text; correction #21 introduced a second, unrelated zero-widget shape (a substantive,
    often markdown-table-rich answer) that the same check couldn't distinguish. Fixed on both
    sides: `ui_selection_node` now builds a `WidgetSpec(intent="text", source_tool_call=
    "context_reuse", ...)` for this path — a distinct tag from `general_climate_node`'s
    `"general_climate"` (semantically different: this path did reuse tool data at some point;
    general_climate never calls a tool at all) even though both render identically — so
    `hasWidgets` is true and the normal response path renders it instead of InlineAlert.
    Separately, neither `response_text` nor any text widget was ever rendered as markdown
    anywhere in the frontend; agent_node's largely unconstrained answers on this path routinely
    include headers/bold/GFM tables (confirmed live), unlike `compose_response_node`'s
    tightly-scoped plain-prose summaries, so the raw `##`/`**`/`|---|` syntax showed through as
    literal text. Fixed via a new `MarkdownText` component (`react-markdown` + `remark-gfm`,
    real React elements throughout, never `dangerouslySetInnerHTML`); headers/paragraphs/lists
    map onto this app's existing `__s9cmpx-*` typography classes (no page in this app uses
    design-system's `Typography` component yet, so adopting it only here would be an unexplained
    inconsistency, not a real improvement), and GFM tables specifically render through
    design-system's real `Table` component — reshaping react-markdown's already-rendered
    `<thead>`/`<tbody>` tree into `Table`'s `columns`/`rows` props (preserving inline formatting
    like a bolded cell) rather than a plain `<table>`, matching this project's "real components,
    never generated markup" principle. Live-verified end to end (backend + frontend together,
    same India-after-China repro sequence): the answer renders as a normal card with a real,
    sortable table — not an alert box, not raw syntax.
23. **`PromptBar`'s auto-refocus-after-loading effect (design-system, added alongside the §4
    expandable-content work) stole focus back into the bar the instant a response landed,**
    which — because focus entering the bar is also the `expandedContent` show trigger — popped
    the starter-prompt grid back open right as the answer rendered underneath it. The refocus was
    originally meant to support a "keep asking" loop (land back in the textarea, ready to type a
    follow-up, without reclicking), but the side effect of re-surfacing the starter grid after
    every single turn was worse than the convenience it bought. Removed entirely rather than
    patched to suppress just the expand — `loading` returning to `false` no longer calls
    `textareaRef.current?.focus()` at all, so focus (and expandedContent's visibility) now stays
    exactly wherever the user actually left it.
24. **On iOS Safari, submitting a query left a large blank scrollable gap below the page's real
    content** — reported directly, with screenshots from a real device. Root cause was in
    `App.tsx`'s shell, not this page: the root div's `min-height: 100vh` is sized against the
    *largest* possible viewport (URL bar collapsed), not whatever's actually visible, and
    submitting disables (therefore blurs) `PromptBar`'s focused textarea, which dismisses the
    on-screen keyboard abruptly rather than through iOS's normal tap-away animation. WebKit's
    internal layout snapshot taken while the keyboard was still up didn't get recomputed on
    this abrupt a close, leaving blank space the height of the vacated keyboard until something
    else forced a reflow. Fixed by giving the shell's root div a `.app-shell` class with a
    `min-height: 100dvh` stylesheet override (100vh kept as the inline-style fallback for
    browsers without `dvh` support) — `dvh` tracks the actual visible viewport continuously, so
    it can't get stuck stale the way a `vh` snapshot can. App-shell-level fix, not `/ask`-page-
    specific, even though this page's submit-disables-the-textarea interaction is what surfaces
    it — any other page with a focused, disable-on-submit input would hit the same bug.
    **A real, correct improvement, but user follow-up (with a real device, "not resolved") showed
    it wasn't the actual cause of the reported symptom** — see correction #25, which found and
    fixed the genuine root cause. Kept anyway: `dvh` is still objectively more correct than `vh`
    for a PWA with an on-screen keyboard, independent of whether it explains this particular
    report.
25. **The real root cause of correction #24's report: iOS Safari auto-zooms the whole page in
    when a focused text input renders below 16px font-size** — user's exact words once asked to
    clarify what "overflow" meant: "the screen automatically zoomed in and expanded beyond the
    viewport... the top and menu icons are no longer visible... one has to manually zoom it back
    into view." Not a height-calculation bug at all — a genuine pinch-zoom the browser applied
    and didn't cleanly undo. `PromptBar`'s textarea uses the underlying `Textarea` 'm' size,
    which is `body-3-short` (14px, below iOS's 16px no-zoom threshold). The same submit-disables-
    the-textarea abrupt blur from #24 is what triggers it: iOS's zoom-restore-on-blur doesn't
    reliably run when focus is lost via `disabled` rather than a natural tap-away, so the
    zoomed-in state sticks. Fixed in design-system (PR #49): `fontSize: 16` on the textarea's
    inline style, overriding the 14px class token, scoped to just this one field rather than the
    shared `Textarea`/`Input` 'm' token (other consumers of that token share the same latent
    risk but weren't reported and are out of scope here). Live-verified two ways beyond reading
    the source: `getComputedStyle` on the deployed page confirmed `fontSize: 16px` reached the
    real `<textarea>` element (not just a wrapper — Copilot's PR review specifically asked this
    to be double-checked), and the user confirmed on their actual iPhone that the bug is gone.
    Correction #24's own diagnosis (100vh vs 100dvh) turned out to be plausible-sounding but
    wrong for this specific report — a lesson in verifying against the user's exact words
    ("zoomed in," not "gap" or "overflow" in the generic sense) rather than pattern-matching to
    the first plausible-looking bug class and shipping before confirming.
26. **The §4 starter-prompt grid's forecast row auto-submitting while the historical-trends row
    only prefilled was itself the bug — reported live as an inconsistency between the grid's two
    rows.** This was a deliberate, documented design choice at ship time (SPEC.md previously read
    "the two forecast prompts have no placeholder and submit immediately on click"), not a
    regression — but it read as a surprise once both rows sat in the same grid: clicking one row
    edits, clicking the other fires immediately with no chance to change the country/scope first.
    Changed so all four tiles prefill + focus, none auto-submit (`AgentPage.tsx`'s
    `STARTER_PROMPTS` dropped its `prefill: boolean` field entirely — no longer a per-item choice
    — and `handleStarterClick` lost its now-dead auto-submit branch). The design-system
    `PromptBar` collapse-on-external-submit behavior this used to exercise
    (`AgentPage.test.tsx`) is still covered — via a §6 suggested-prompt "Try instead" reframe tile
    instead, which still calls `submit()` directly rather than going through `PromptBar`'s own
    `trySubmit`, since that mechanism wasn't removed, only the starter grid's own use of it.

---

## 1. Purpose

A conversational agent, surfaced in the React dashboard (`climate-dashboard-react/`), restricted
to the climate-emissions domain, that answers by calling `services/mcp-server`'s tools and renders
results using the existing design-system's chart/grid/card components — not a generic chatbot.
Originally a `NAV_ITEMS` entry like every other page; now a `SidebarNav.persistentAction` instead
(direct instruction: "persistent, always-visible action," design-system PR #46) — an icon+label
button next to the menu toggle, present in every sidebar state (expanded, collapsed-to-rail,
mobile drawer closed) rather than one entry among the page list. The `/ask` route itself (§2
below) is unchanged.

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
| `chart` | `ChartCard` + `SyChart` | `line` (trends), `band` (forecast CI), `bar` (ranked lists, colorValues for "heatmap" bars), `choropleth` (geography) |
| `grid` | `DataTable` in a `Card`/`CardHeader` | — |
| `card` | `KpiStat` (one or a small row) | — |
| `text` | Plain text in a `Card` | — |

Tool → intent mapping (fixed lookup, no LLM judgment except the one case noted):

| Tool | Intent |
|---|---|
| `get_historical_emissions`, `get_scenario_projection`, `compare_scenarios_across_countries` | `chart` (`line`) |
| `get_forecast` | `chart` (`line` + `band`) |
| `get_forecast_comparison` | `chart` (`line`) — the multi-country equivalent of `get_forecast` |
| `get_top_emitters` | `chart` (`bar`, or `choropleth` per §3.1 below) |
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
- A query naming both a current-state concept and a forecast concept together (e.g. the 4th
  starter prompt) still resolves to `bar` — see "Corrections applied" #17. The original design
  called for `treemap` here (tile size = one metric, tile color = the other), but
  `get_top_emitters`'s real result carries exactly one metric (`co2`); there's no second metric to
  color by. A genuine dual-metric treemap needs a merged result from two tool calls and isn't
  built — see §12 open item 5.

Both are existing `SyChart` kinds, already proven on the dashboard's Overview page — no new chart
component work, only the kind-selection logic in `ui_selection`.

### 3.2 Widget grid layout (`climate-dashboard-react`)

A turn's widgets render in an explicit `N`-column CSS grid (`AgentPage.tsx`'s
`widgetColumnCount`), driven directly by widget count, not by an auto-fit/available-width
calculation: 1, 2, or 3 widgets get that many columns each; 4 widgets deliberately drops to 2
(a 4-up row reads as cramped at this card size) rather than the naive next step of 4; 5+ caps at
3 so cards stay legible regardless of how many widgets a turn produces. A single `@media
(max-width: 768px)` override (the `.agent-widget-grid` class, same `<style>`-tag pattern
`OverviewPage.tsx`'s hero grid already uses) collapses any column count to 1 on narrow viewports
— a fixed `repeat(N, 1fr)` grid doesn't shrink its own column count the way `repeat(auto-fit,
minmax(...))` does (the pattern the starter-prompt grid and mobile-overflow fix use elsewhere in
this file), so an explicit breakpoint is needed here instead. Live-verified at both a wide
viewport (a real 4-widget China turn laying out 2×2, not 4-across) and a 500px mobile viewport
(the same turn collapsing cleanly to one column, no horizontal overflow).

## 4. Starter prompts

Four prompts, rendered as an interactive `Tile` grid (kicker category label, prompt text, arrow
icon — via the `StarterPromptTile` composition, see "Corrections applied" #3), in a fixed 2x2
layout (`starterPromptColumnCount`, same "explicit count, not auto-fit" reasoning as the response
widget grid, §3.2), font sizes reduced a step (`__s9cmpx-body4` for the prompt text) since the
grid now sits inside a compact panel rather than a full-page section (direct instruction).

**Lives inside `PromptBar` itself, not as a separate element below it** (direct instruction,
superseding an earlier "idle and empty between turns" approximation): passed as `PromptBar`'s
`expandedContent` prop (design-system PR #44), a panel that grows from inside the bar's own
rounded border on focus and collapses on blur-away or submit — see design-system's own
`PromptBar.stories.tsx` for the interaction contract (`relatedTarget`-based blur handling so a
tile click doesn't collapse the panel out from under itself; dual collapse paths for
Enter/Send-triggered vs. externally-triggered submissions). Landing's `autoFocus` means the grid
is visible immediately on first load, same as before; for the docked bar (no autofocus), the user
clicks in to reveal it — a real focus-driven interaction now, not an approximated state machine.
`AgentPage.tsx` no longer tracks "dismissed"/"idle and empty" itself at all; visibility is fully
owned by `PromptBar`.

| Category | Prompt |
|---|---|
| Historical trends | *What are China's historical emissions trends, and how do they compare to the top 10 sovereign emitters?* |
| Historical trends | *How has India's emissions grown compared to other countries?* |
| Forecasts | *What are the top 10 forecasted emitters in 2040?* |
| Forecasts | *Considering the top 10 emitters now and the forecasted ones in 2040, show the comparative trend for the countries.* |

All four prompts prefill `PromptBar`'s value with the concrete prompt text (no longer a
`<Country>` placeholder to type over — swapped to real countries, China/India, on direct
instruction) and focus it, so the user can submit as-is or edit it, e.g. to a different country.
No separate country picker. Focus now genuinely works, resolving "Corrections applied" #18's
previously-flagged gap: `PromptBar` exposes its textarea via `forwardRef`
(`React.forwardRef<HTMLTextAreaElement, ...>`, same pattern `Textarea` itself already used,
design-system PR #44), so `handleStarterClick` calls `promptBarRef.current?.focus()` directly
after prefilling. The two forecast prompts previously had no placeholder and submitted
immediately on click; that was changed (direct instruction) after it read as an inconsistent
surprise next to the two country-specific rows behaving differently on the same grid — clicking
any of the four tiles now behaves identically.

`PromptBar`'s `landing`/`docked` variants also no longer differ in width (design-system PR #45)
— `landing` previously capped at 540px, centered, while `docked` spanned its full container,
so the bar visibly resized between "before the first submit" and "after" (direct instruction to
make them match; no documented rationale existed for 540 specifically).

The same `StarterPromptTile` composition is reused for the opinion-guardrail's suggested reframes
(§6) — one clickable-prompt-card pattern used in two places, not two. Those reframe tiles are
unaffected by this section -- they render inline with their own result section, not inside
`PromptBar`.

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
5. `get_top_emitters`'s bar/choropleth pick (§3.1) is a keyword heuristic on `current_query`
   (`ui_selection.py`'s `select_top_emitters_chart_kind`), not an LLM call — matches §8's claim
   that only `get_country_profile` needs one. A genuine dual-metric treemap (current volume vs.
   forecasted growth, the original design for a query naming both concepts — see "Corrections
   applied" #17) needs a merged result from `get_top_emitters` + `get_forecast_comparison`, which
   `ui_selection` doesn't build; revisit if real usage shows this comparison is common enough to
   justify a two-tool-call widget.
6. **`ANTHROPIC_API_KEY` storage on the Mac Mini deploy** — ships in Release 1 (`ENHANCEMENTS.md`)
   as a plain `EnvironmentVariables` entry in `com.ghgemissions.agent.plist` (`chmod 600`,
   single-user machine — accepted deliberately, on direct instruction, 2026-08-14). The narrow
   exposure this accepts: any process already running as the same local user can read the key
   out of the live agent's environment via `launchctl print`/`ps eww`, even though the plist file
   itself is unreadable to anyone else. Deferred, better option if this machine's threat model
   ever changes (a second local account, shared access, etc.): store the key in macOS Keychain
   (`security add-generic-password`) and swap the plist's `ProgramArguments` for a small wrapper
   script that does `security find-generic-password -w` before exec'ing `uvicorn`, so the plist
   file never holds the raw value at all. Not designed further than this — revisit only if the
   deploy's threat model actually changes, not preemptively.

## 13. LLM prompt caching (Anthropic `cache_control`)

Not §9's `tool_cache` (an app-level dict deduping repeated MCP tool calls within a turn) —
this is Anthropic's own server-side prompt cache, keyed on the raw request bytes sent to the
Messages API, unrelated to that mechanism.

Only `agent_node` marks a `cache_control` breakpoint (`graph.py`), on its own `SystemMessage`'s
content block, not the top-level `ChatAnthropic` kwarg — confirmed by reading
`langchain_anthropic`'s source directly (not assumed): the top-level kwarg only auto-hoists a
breakpoint for non-direct transports (Bedrock etc.), and this service calls the direct Anthropic
API. Since Anthropic renders `tools → system → messages`, one breakpoint on the system block
caches the bound MCP tool schemas *and* the system prompt together.

**Why only this one call site.** Measured against the real deployed `services/mcp-server`: 13
tools, ~12.5K characters (~3K+ tokens) of descriptions and JSON schemas — comfortably over
Sonnet's 1024-token cache-eligibility floor. This exact payload repeats on every `agent`↔`tools`
loop iteration within a turn (up to `MAX_TOOL_CALLS_PER_TURN`, §10) and is identical across every
user's query, since the tool list never varies. The other five LLM nodes
(`guardrail_router`/`opinion`/`general_climate`/`ui_selection`/`compose_response`) each carry a
single-shot prompt — all six prompts in `prompts.py` total under 4KB combined, so individually
they sit below the caching floor; marking them would add the ~1.25x cache-write premium with no
read-side payoff.

Verification: the unit test above pins the `cache_control` marker's presence on the request
`agent_node` builds. Live-verified against the real Anthropic API using the actual deployed
`services/mcp-server` tool schemas: two identical-prefix calls back to back produced
`cache_creation_input_tokens=5329, cache_read_input_tokens=0` on the first call and
`cache_creation_input_tokens=0, cache_read_input_tokens=5329` on the second — the full
tools+system prefix was written once and read from cache on the repeat.
