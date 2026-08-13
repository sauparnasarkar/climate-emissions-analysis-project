# Enhancements — Climate Emissions MCP Server

Tracks planned and shipped enhancements to `services/mcp-server`, beyond `SPEC.md`'s baseline
design. Kept separate from the root `ENHANCEMENTS.md` since this is a distinct, independently
versioned sub-project — see the root `CLAUDE.md`'s "What This Repo Is" entry for
`services/mcp-server/` and `SPEC.md` §2 for why it isn't folded into the dashboard's history.

---

## Release 1 — Stage 1 Kickoff: Spec Lands In-Repo, Implementation Complete

**Status: Shipped.** All four steps merged to `main` (PRs #135–#138).

**Goal:** Bring the previously-external MCP server design doc into the repo as
`services/mcp-server/SPEC.md`, correcting stale references discovered in the process, then
implement the server in sequential feature-branch steps (scaffold + cross-cutting pieces →
direct-wrap tools → trimming + composed tools → transport wiring and local verification) per
`SPEC.md` §7's staged verification plan.

**Step 4 — transport wiring and local verification.** Wired `MCPServer.run()` for both
transports (Streamable HTTP default per `SPEC.md` §2, host hardcoded to `127.0.0.1` — never
configurable, since `api/` has no auth yet and this server is an unauthenticated pass-through
to it; stdio as the local-dev fallback), selectable via `MCP_TRANSPORT`.

Found and fixed a real bug only reproducible by actually running the server as a subprocess,
the way an MCP client does — no in-process import test surfaced it: running
`python -m mcp_server.server` directly loads that file a second time under the name
`mcp_server.server`, separate from its own `__main__` instance, the moment `tools/*.py`'s
`from ..server import mcp` resolves. Two different `MCPServer` objects exist as a result, and
the one `main()` runs (`__main__`'s) is not the one the tools registered onto — silently down
to a single working tool (`list_countries`, the only one defined above the `tools/*` import
line). Fixed with a proper `mcp_server/__main__.py` entry point (`python -m mcp_server`,
never `.server`) and a permanent regression test (`tests/test_entry_point.py`) that launches
the real subprocess and asserts full tool registration.

Verified end-to-end against a real running `api/` and real `data/` CSVs (not just the
fixture-based suite) over both transports: all 12 tools list and execute correctly; the
resolution guard produces a real, useful fuzzy suggestion (`"Atlantis"` → `"did you mean:
Albania?"`); and trimming/`scope_note` produce correct real counts —
`get_historical_emissions(scope="sovereign")` reports "10 of 215," not 218, because 215 is
the count of sovereign countries with actual CO₂ data once the wrapped API's own `dropna`
runs, which is the number an agent doing "top 10 of X" reasoning actually needs, not the raw
sovereign-list length. Confirmed this is correct behavior, not a bug, before writing it down.

**Corrections made while bringing the spec in-repo** (the original external draft predates the
root API work it depends on, and undersold what had already shipped by the time it landed here):
- The spec's own dependency section cited root `SPEC.md` §5.21 and described the required
  scope-parameter/three-gas-sovereign work on `/historical/*` as "planned, not yet shipped."
  Both were wrong by the time of this release: the work is documented at root `SPEC.md` §5.22
  (v48), not §5.21, and it was already merged to `main` (PR #133, 112/112 `api/tests` passing)
  before this sub-project's implementation started. Not a blocker — the citation was just stale.
- §6.3 described the sovereign country field as a count to be added; it already ships today as
  a full `sovereign: list[str]` (~218 entries) on `GET /countries`, which is what the
  resolution guard (§3.1) and `scope_note` denominator (§3.2) actually consume.
- A structural asymmetry between the two historical endpoints, not mentioned in the original
  draft: `GET /historical/timeseries`'s omit-`countries` default is a hardcoded
  `FEATURED_COUNTRIES[:5]` that ignores `scope` entirely (deliberate, tested API behavior), while
  `GET /historical/decade-composition`'s omit-`countries` default correctly aggregates the whole
  scoped pool. `get_historical_emissions` (this server's wrapper for the first endpoint) has to
  resolve and rank the scope pool itself and always pass an explicit `countries` list — see
  `SPEC.md` §4. Considered and rejected: fixing the API's default instead — the frontend already
  moved its own default from 5 to the full 10 featured countries and never hits this code path,
  so a fix there is an independent `api/` cleanup, out of scope for this sub-project.
- `/scenarios/timeseries`'s `scope` param only takes effect when `view="global"` and supports
  `featured|expanded` only (no `sovereign`) — the original draft's tool table listed `scope` for
  `get_scenario_projection` without either caveat.
- `get_country_profile` and `get_forecast` both 404 on any country outside the expanded ~40 even
  though neither takes a `scope` argument — folded into §3.1's resolution guard as an explicit
  case-4 variant rather than left as an unstated edge case.

**Deliberate V1 deviations from the spec's "settled" architecture table** (§2.1 of `SPEC.md`,
confirmed with the mentor before implementation started):
- **Auth:** `api/` has no auth mechanism today (no middleware, no `Depends()` checks). V1 calls
  it unauthenticated over localhost rather than building token-presenting code that nothing on
  the API side would validate. Real service-account auth is a hard prerequisite before any
  non-local deploy.
- **Deployability:** only `pyproject.toml` ships in V1, to isolate this sub-project's
  dependencies (an MCP SDK, `rapidfuzz`) from the shared root `requirements.txt`. Dockerfile and
  a CI job are deferred, not omitted — `SPEC.md` §7 scopes Stage 1 to local Claude Desktop/Code
  verification, which needs neither, and no Docker/CI pattern exists anywhere else in this repo
  yet to extend.
- **Location:** `services/mcp-server/`, without relocating `api/` to `services/api/` — that
  relocation is a separate, higher-blast-radius refactor (touches
  `climate-dashboard-react/vite.config.ts` and the Mac Mini deploy paths) not undertaken here.

---

## Release 2 — SPEC.md §7 Iteration: Multi-Country Comparison Consistency

**Status: Shipped**, straight to `main` (no PR — small, low-risk, iteration-driven changes,
by direct instruction rather than the usual feature-branch-per-section flow).

**Goal:** `SPEC.md` §7's open-ended manual-verification phase — connect to Claude Desktop,
exercise the tools for real, and fix whatever tool-calling reliability problems that surfaces.
This release is the first real finding from that phase, start to finish: symptom → two failed
narrow fixes → correct root cause → an `api/`-side dependency → a real fix → confirmed via a
second live Desktop conversation.

**The symptom.** Manually testing two similarly-shaped questions ("China's top emissions
trends vs. the sovereign top 10" and "how has India's emissions grown compared to other
countries") produced inconsistent country-set sizes: 10 countries via `get_top_emitters` for
the first, an ad hoc 6-country list via an *explicit* `get_historical_emissions(countries=...)`
call for the second. Not an `get_historical_emissions` bug — `SPEC.md` §3.2 says an explicit
list is always honored in full — but the model was inventing that list from its own general
knowledge rather than using the tool's scope-based path, so the same question could produce a
different comparison set each time it's asked.

**Attempt 1 (didn't work): docstring nudge on `get_historical_emissions`.** Added explicit
guidance to omit `countries` and pick `scope` instead for open-ended requests. Re-tested: the
model stopped calling `get_historical_emissions` with an explicit list, but routed around the
tool entirely — called `get_country_profile` once for India, once for the US, reusing China's
profile from earlier in the conversation, confirmed directly via Claude Desktop's tool-call
trace (not just inferred from the `api/` access log).

**Attempt 2 (also didn't work): cross-reference docstring on `get_country_profile` + a
server-level `instructions` string.** Told the model explicitly not to call the single-country
tool repeatedly, and to prefer `get_historical_emissions` for comparisons — confirmed via a
direct client check that `instructions` is genuinely transmitted in the MCP `initialize`
handshake, not just stored inertly. Re-tested with the same exact question: identical
behavior, `get_country_profile` × 2 again.

**Root cause, found by reading the model's actual answers, not just its tool calls.** Both
attempts' answers included per-capita CO₂, YoY % growth, and GHG intensity for every
country — fields that only exist on `get_country_profile`'s response.
`get_historical_emissions` only returned raw yearly gas values. The model wasn't ignoring
either nudge; it was correctly recognizing that the tool I was steering it toward couldn't
supply the data it needed, and using the one that could. No docstring wording fixes a
structural data gap.

**Verified what's actually available before proposing a fix.** `co2_per_capita`,
`methane_per_capita`, `nitrous_oxide_per_capita`, `co2_growth_prct`, and `co2_per_gdp` are all
precomputed columns already in `owid-co2-data.csv` — no new derivation needed, and available
at every scope since it's the same raw file regardless of `scope`. Growth-% and per-GDP have
no OWID equivalent for methane/nitrous_oxide — confirmed by checking the actual column list,
not assumed. `co2_per_gdp` is explicitly **not** the same metric as `get_country_profile`'s
`ghg_intensity` (`total_ghg / gdp`, all three gases as CO₂-equivalent, computed only for the
expanded ~40 via Week 2's own pipeline) — confirmed by comparing both for China/2020
(`ghg_intensity=0.5186` vs `co2_per_gdp=0.451`, close but genuinely different numbers) rather
than assuming OWID's field was a drop-in substitute.

**The `api/` change** (PR #139, shipped independently by the session working on `api/`, per
this sub-project's own no-`api/`-changes convention): `GET /historical/timeseries` gained
`per_capita` (gas-aware), and CO2-only `yoy_pct_change`/`per_gdp` (`None` for
methane/nitrous_oxide) on every `TimeseriesSeries`. Root `SPEC.md` §5.23 / Release 18.

**The `services/mcp-server` change.** `get_historical_emissions` already passed the full API
response through unmodified, so the new fields required zero data-plumbing changes — only
docstring updates, since the fix was telling the model the gap it had correctly identified was
now closed: `get_historical_emissions` documents the new fields and the CO2-only-vs-`None`
split; `get_country_profile`'s docstring narrows to its one remaining unique value
(multi-gas `ghg_intensity`); the server-level `instructions` mentions the multi-country tools
now carry comparative context, not just raw totals. Also documented that `per_gdp` (and, in
the latest year or two, `yoy_pct_change`) can legitimately be `None` even for CO2, because
OWID's GDP figures lag its emissions figures by a year or two — confirmed directly against the
raw CSV (China's `co2_per_gdp` is populated through 2022, `NaN` for 2023–2024) rather than
assumed to be a bug.

**Confirmed fixed, not just shipped**, via a second live Desktop conversation on the same two
questions: the China query made a single `get_historical_emissions(scope="sovereign")` call
(no explicit `countries` — the full 218-country sovereign pool resolved and passed internally,
trimmed to the top 10 client-side, per the existing `SPEC.md` §3.2/§4 design) and produced a
table with CO₂, per-capita, and YoY% for all 10. The India follow-up made **no new tool
call** — it correctly reused the same response already in context (which already contained
India's full 1990–2024 series, being #3 in that sovereign top 10) rather than either
re-fetching or falling back to `get_country_profile`. A follow-up indexed-growth chart
(1990=100, India and China highlighted against the other 8) confirmed the same reused dataset
backed the visualization too. One well-formed tool call, reused correctly across a multi-turn
conversation, comparative fields actually present in the narrative — the combination the two
failed attempts above were aiming for.

**Noted but not acted on:** the sovereign-scope path sends all 218 countries' full 35-year
series over the wire to display 10 — correct (it's what avoids the API's own scope-blindness
bug, `SPEC.md` §4) but not free. A cheaper ranking pass before fetching full series only for
the winners (mirroring how `get_top_emitters` already uses the lighter
`/overview/world-map-series` for ranking) would be a legitimate future optimization, not
undertaken here since nothing observed made it a real cost yet.

**Also fixed in this window, unrelated:** Ctrl+C on a running server printed a raw
`KeyboardInterrupt` traceback even after a clean shutdown — cosmetic, but alarming for anyone
else testing this locally. Caught at the `__main__.py` entry point for a quiet exit.
