# Enhancements — Climate Emissions MCP Server

Tracks planned and shipped enhancements to `services/mcp-server`, beyond `SPEC.md`'s baseline
design. Kept separate from the root `ENHANCEMENTS.md` since this is a distinct, independently
versioned sub-project — see the root `CLAUDE.md`'s "What This Repo Is" entry for
`services/mcp-server/` and `SPEC.md` §2 for why it isn't folded into the dashboard's history.

---

## Release 1 — Stage 1 Kickoff: Spec Lands In-Repo, Implementation Begins

**Status: In progress.**

**Goal:** Bring the previously-external MCP server design doc into the repo as
`services/mcp-server/SPEC.md`, correcting stale references discovered in the process, then
implement the server in sequential feature-branch steps (scaffold + cross-cutting pieces →
direct-wrap tools → trimming + composed tools → transport wiring and local verification) per
`SPEC.md` §7's staged verification plan.

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
