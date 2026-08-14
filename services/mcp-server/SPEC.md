# Climate Emissions MCP Server — Specification

**Status: Design / pre-implementation (Stage 1 of the conversational-agent project)**

Companion document to the root `SPEC.md`. Lives in this repo as a separate sub-project
(`services/mcp-server`), independently versioned and deployable (own `pyproject.toml`,
Dockerfile, CI job), but scoped and documented here rather than folded into the root `SPEC.md`
itself since it's a distinct sub-project, not an addendum to the dashboard.

---

## 1. Purpose

Wraps the existing `climate-emissions-analysis-project` REST API (`api/`) as a set of
hand-curated MCP tools, so that:

- A future LangGraph-based conversational agent can answer emissions/forecasting questions
  by calling these tools, restricted to the climate-change/emissions domain.
- The same tool set can be exercised directly via Claude Desktop or Claude Code during Stage
  1, before any agent or UI work begins — this is the verification step for tool-calling
  quality, ahead of building anything else.

## 2. Architecture decisions (settled)

| Decision | Choice | Rationale |
|---|---|---|
| Repo structure | Same monorepo, `services/mcp-server` alongside `api/` | API is specific to this project; coordination benefits of one repo outweigh split-repo overhead at this scale. `api/` stays at the repo top level rather than moving to `services/api` — that relocation is a separate, higher-blast-radius refactor (touches `climate-dashboard-react/vite.config.ts` and the Mac Mini deploy paths) not undertaken here. The resulting lopsided `services/` directory (containing only `mcp-server/`) is accepted as directional, not fixed as part of this work. |
| Deployability | Independently versioned/deployable — own `pyproject.toml`, Dockerfile, CI job, even though co-located | Keeps a clean boundary between the public/dashboard-facing REST API and the agent tool surface; avoids coupling MCP tool-schema releases to unrelated dashboard API deploys; doesn't foreclose extraction later. **V1 implements only the `pyproject.toml` piece of this** — see §2.1. |
| Data access path | **Option A** — HTTP client of the existing REST API, same interface any consumer uses | No privileged access path for the agent; clean process boundary; negligible latency cost for this use case. Rejected: importing API business logic as a shared library (Option B) — faster, but couples the two services' dependency graphs and undercuts "independently deployable." |
| Tool curation | Hand-curated wrappers, not auto-converted from OpenAPI | This API is unusually well-suited to near-1:1 wrapping (each endpoint already answers one analytical question, not generic CRUD), but forecast/scenario endpoints still benefit from composed, task-shaped tools (e.g. `get_top_emitters`) that a raw conversion wouldn't produce. |
| Transport | Streamable HTTP (MCP's current recommended remote transport) | Works identically whether Claude Desktop/Code is testing locally or the LangGraph agent calls it in production; stdio available as a local-dev fallback only. |
| Auth | Service-account token presented to the API | The API-mount approaches (`fastapi-mcp`, `FastMCP.from_fastapi`) would give free `Depends()` reuse, but were rejected in favor of a standalone service — auth has to be handled explicitly here rather than inherited. **`api/` has zero auth today (no middleware, no `Depends()` checks) — see §2.1: V1 deliberately does not implement this row.** **Superseded by §8's settled design: the actual new surface (external MCP clients reaching this server) is gated by Cloudflare Access at the edge, not an app-layer service-account token — see §8.2 for why this row's original shape turned out to be the wrong mechanism for that boundary specifically.** |

### 2.1 V1 scope deviations from this table

Two rows above describe the eventual target shape, not what V1 actually builds. Both are
deliberate, not oversights:

- **Auth:** `api/` currently has no auth mechanism of any kind. V1 of this server calls `api/`
  unauthenticated over localhost — it does not add token-presenting code on the MCP side, since
  nothing on the API side would validate such a token (that would be dead code). Real
  service-account auth, on both sides, is a **hard prerequisite before any non-local deploy** of
  this server. **Settled by §8 (2026-08-13):** this call (this server → `api/`, boundary B3 in
  §8.1) stays exactly as described above — still unauthenticated, still localhost-only, and
  correctly so, since it's already network-isolated and adding a token here now would be dead
  code until `api/` itself has something to check it against. What actually needed resolving
  before a non-local deploy was the *other* direction — external clients reaching *this*
  server — which §8 gates via Cloudflare Access instead of an app-layer token. See §8 in full.
- **Deployability:** V1 adds `services/mcp-server/pyproject.toml` only, to isolate this
  sub-project's dependencies (an MCP SDK, `rapidfuzz`) from the shared root `requirements.txt`
  that the notebooks/jupyter also depend on. A Dockerfile and CI job are deferred — §7 scopes
  Stage 1 to local Claude Desktop/Code verification, which needs neither, and no Dockerfile or
  CI workflow exists anywhere else in this repo yet to extend.

## 3. Cross-cutting conventions

These apply across every tool below, rather than being redefined per tool.

### 3.1 Country identifier & resolution guard
The underlying API takes plain country-name strings (OWID's canonical names), not ISO codes
— confirmed directly in `api/data_loaders.py` (`country.isin(...)` matching). No name→code
translation is needed, but a resolution layer sits in front of every tool that accepts a
`country`/`countries` argument, because the raw API's own behavior on a mismatch is a silent
drop, which is worse for an LLM than for a chart:

1. Exact match against the canonical list (from `list_countries`) first.
2. Above a high similarity threshold, fuzzy-match and auto-resolve (e.g. `rapidfuzz`).
3. Below that threshold, return an explicit tool error (`"No match for 'Congo' — did you
   mean: Congo, Democratic Republic of Congo?"`) rather than guessing or silently dropping.
4. A second, distinct case once `scope` exists (root `SPEC.md` §5.22): a *known* country name
   that's outside the requested/default scope — e.g. `"Bhutan exists but is outside
   'expanded' scope — retry with scope='sovereign'"` — rather than a silent empty result.
   This case-4 error applies not only to tools that take an explicit `scope` argument, but
   also to `get_country_profile` and `get_forecast`, which have no `scope` argument at all
   but still 404 on any country outside `load_expanded_countries()` — the same "known but
   out of the tool's fixed scope" situation, just without a `scope` param to retry with.

### 3.2 Response trimming & `scope_note`
When a tool's default (unscoped) query would return more than a handful of rows, cap and
annotate rather than silently returning a partial view:

- **Trigger is "no explicit countries given," not "multi-country."** If the agent passes a
  specific list of countries, return exactly those, uncapped — trimming there would silently
  drop something the user asked for.
- When trimming does apply (broad/default scope), cap at 10 and sort by a sensible default
  per tool (generally latest-year emissions level, descending, unless the tool has an
  obvious alternative like `pct_change`).
- Every trimmed response carries a `scope_note` field stating both the count and the sort
  key, e.g. `"Showing 10 of 40 countries (Expanded scope — coverage ≥ natural gap
  threshold, ≥100 Mt latest-year CO2), sorted by latest-year CO2 descending"`. Wording is
  sourced from the same canonical language as root `SPEC.md` §5.6, not reinvented here — see
  §3.3. The "N of 218" sovereign-scope denominator is `len(sovereign)` from `list_countries`'s
  `sovereign` field (a full `list[str]` of ~218 names returned by `GET /countries`, not a
  count — see §5's `list_countries` row).
- Absence of `scope_note` on a response is itself informative ("this is everything") — the
  agent's system prompt instructs it to mention scope only when the field is present.

### 3.3 Methodology grounding
`get_methodology_notes` (§5, below) and every `scope_note` string draw from one shared
source of canonical text (e.g. a small `methodology.py` alongside the tool definitions),
rather than each duplicating its own description of the expanded-scope criteria, ETS(A,Ad,N),
or the model comparison set. A future documentation change should only need to happen once.

### 3.4 Error/empty-data behavior
Inherits the underlying API's existing leniency for this initial implementation (e.g. an
unrecognized column silently dropped by `/explorer/*`-style endpoints, where those are used)
rather than adding new validation logic. Revisit only if this is observed to degrade agent
answers in practice. The country-resolution guard in §3.1 is a deliberate exception — it
exists specifically to give the *agent* a chance to self-correct before a silent drop would
otherwise happen, not a general tightening of API behavior.

### 3.5 Tool output shape
Every tool returns structured data (+ optional `scope_note` per §3.2) and never a UI
directive. UI selection is a separate, later concern (Stage 3 of the broader project) —
this separation is what keeps this stage decoupled from the generative-UI stage.

## 4. Dependency on API changes

`get_historical_emissions` and `get_gas_composition_by_decade` (§5) both require the `scope`
parameter and three-gas sovereign coverage specified in root `SPEC.md` §5.22. **This has
shipped and is merged to `main`** (PR #133, documented at root `SPEC.md` §5.22 / v48;
112/112 `api/tests` passing at the time this doc was brought into the repo) — it is not a
blocker for this sub-project. §5.22 covers both `timeseries` and `decade-composition` (the
same `load_raw()`-only limitation existed on both endpoints, undocumented as an intentional
exclusion, and `decade-composition` needed no logic change beyond the same `scope` param —
it already aggregates all three gases at once).

Root `SPEC.md` §5.22 also includes a sovereign country count/list on `/countries`
(`sovereign: list[str]`, ~218 entries) — this is the canonical source for the resolution
guard (§3.1) and the `scope_note` denominator at sovereign scope (§3.2).

**A structural asymmetry to account for, not a shipped/unshipped question:**
`get_historical_emissions` wraps `GET /historical/timeseries`, whose omit-`countries`
default is a hardcoded `FEATURED_COUNTRIES[:5]` **regardless of the `scope` param** — this is
deliberate, tested API behavior (`api/tests/test_historical.py`), not a bug. By contrast,
`get_gas_composition_by_decade` wraps `GET /historical/decade-composition`, whose
omit-`countries` default aggregates the *entire* scoped pool, correctly respecting `scope`.
Applying §3.2's trimming rule naively to `get_historical_emissions` would silently return 5
featured countries while emitting a `scope_note` claiming "10 of 218 sovereign countries,
sorted by latest-year CO2 descending" — wrong data with a confident, wrong caption.
**`get_historical_emissions` must resolve the scope pool itself (via `list_countries`), rank
it, and always pass an explicit `countries` list to the API — it must never rely on the
endpoint's own omit-default.** `get_gas_composition_by_decade` can rely on the omit-default,
since it already does what §3.2 wants.

## 5. Tool catalog

### Direct wraps

| Tool | Wraps | Args | Notes |
|---|---|---|---|
| `list_countries` | `GET /countries` | — | Returns `featured` (10), `expanded` (~40), and `sovereign` (~218, `list[str]`) lists. Canonical source for the resolution guard (§3.1) and for the `scope_note` denominator at sovereign scope (`len(sovereign)`). |
| `get_country_profile` | `GET /countries/{country}/profile` | `country` | Full yearly table: CO₂, per-capita, YoY %, GHG intensity. Single-country — no trimming applies. 404s (via the §3.1 case-4 error) on any country outside the expanded ~40, even though this tool has no `scope` arg. |
| `get_historical_emissions` | `GET /historical/timeseries` | `countries?`, `gas` (co2\|methane\|nitrous_oxide), `scope` (featured\|expanded\|sovereign) | Tool always passes `scope` explicitly, never omits it — tool-level default `"expanded"` regardless of the API's own default, chosen independently for a chat context (not inherited from the API for consistency's sake; see §6.1). **When the agent omits `countries`, the tool resolves+ranks the scope pool itself and passes an explicit list — see §4's asymmetry note. It never relies on the API's own omit-`countries` default.** |
| `get_gas_composition_by_decade` | `GET /historical/decade-composition` | `countries?`, `scope` (featured\|expanded\|sovereign) | Same explicit-scope, tool-level-default convention as above. Unlike `get_historical_emissions`, this tool *can* omit `countries` and let the API aggregate the full scoped pool — see §4. |
| `get_forecast` | `GET /forecasts/{country}` | `country` | Always the ETS-based production forecast — **not** model-selectable (corrected from an earlier draft of this tool set, which incorrectly assumed a `model` argument). Includes confidence interval. 404s (via the §3.1 case-4 error) on any country outside the expanded ~40, same as `get_country_profile`. |
| `get_forecast_summary` | `GET /forecasts/summary` | `scope` (featured\|expanded) | 2030/2035/2040 snapshot table. Trimming applies at `expanded` scope. |
| `get_model_comparison` | `GET /forecasts/model-comparison` | — | Precomputed backtest comparison across Naive/Linear Regression/RF-per-country/RF-pooled/ETS — **not computed live**; this is a direct wrap of a static artifact, not a composed tool. |
| `get_scenario_projection` | `GET /scenarios/timeseries` | `view` (single\|global), `country?`, `scope` | BAU/Moderate/Aggressive trajectories. **`scope` only has an effect when `view="global"`, and only supports `featured\|expanded` — there is no `sovereign` option on this endpoint**, unlike the two historical tools above. |
| `get_scenario_cumulative_impact` | `GET /scenarios/cumulative` | `sort_by` (BAU\|Moderate\|Aggressive) | 2025–2040 cumulative by scenario, ranked. Trimming applies. |
| `compare_scenarios_across_countries` | `GET /scenarios/compare` | `countries` | Per-scenario series, multiple countries at once — not summed across countries (unlike the cumulative endpoint above). |

### Composed

| Tool | Behavior |
|---|---|
| `get_top_emitters` | `(year, n)` — fetches `/overview/world-map-series` fresh on every call (no server-side cache for V1; see §6.2) and ranks in memory for the requested year. No ranked-by-year endpoint exists today, so this is genuine composition, not pass-through. Countries with a `null` value at the requested year are excluded from the ranking, not treated as zero. |
| `get_forecast_comparison` | `(countries?, scope)` — the multi-country equivalent of `get_forecast`. No multi-country endpoint with full historical/holdout/forecast/CI detail exists (`get_forecast_summary` is 2030/2035/2040 snapshots only), so this fans out to `GET /forecasts/{country}` once per resolved country **concurrently** inside a single tool call, rather than requiring the caller to invoke `get_forecast` once per country (added Release 2 — see `ENHANCEMENTS.md`, after real testing showed a "top 10 forecasts to 2040" question triggering 10 sequential tool calls). `scope` is `featured`\|`expanded` only — no `sovereign`, since forecasts only exist for the expanded ~40 (same restriction as `get_forecast_summary`). Trimming (§3.2) applies on the omitted-`countries` path, ranked by latest historical actual value. |
| `get_methodology_notes` | Not endpoint-backed. Static text (ETS(A,Ad,N) explanation, the five-model comparison set, OWID dataset provenance/caveats, expanded-scope selection criteria per root `SPEC.md` §5.6) sourced from the shared canonical text in §3.3, so the agent quotes documented methodology instead of improvising it. |

### Explicitly out of scope for V1

| Endpoint(s) | Why excluded |
|---|---|
| `/overview`, `/overview/world-map-series` (raw) | Built for the animated choropleth specifically — large, chart-shaped payload. `get_top_emitters` extracts the one thing from this that's actually useful conversationally. |
| `/explorer/*` (meta/data/summary/download) | Generic tabular browse/download for the human-facing Data Explorer page — arbitrary column selection and pagination aren't a good LLM tool interface. `/explorer/download` also returns a CSV stream, not JSON, which the tool-output shape (§3.5) doesn't accommodate anyway. Revisit only if users start asking for arbitrary raw-column pulls. |
| `/forecasts/ets-parameters`, `/forecasts/feature-importance` | Real endpoints, cheap to add later. Methodology drill-down detail rather than something asked for standalone — folded into `get_methodology_notes` for V1 rather than exposed as their own tools. |

## 6. Open items

1. **§6.1 — Tool-level `scope` default independent of the API's default.** The API's own
   default for `/historical/timeseries` is `"expanded"` for backward compatibility (root
   `SPEC.md` §5.22). The MCP tool's default is also `"expanded"`, but arrived at independently
   for chat-context reasons (an open-ended question shouldn't inherit constraints — fixed 5×2
   subplot grids, narrative framing — that only make sense for the dashboard). The tool always
   sends `scope` explicitly; it never depends on the API's default, so there is no drift risk
   if either default is revisited independently later.
2. **§6.2 — `get_top_emitters` caching.** V1 re-fetches `/overview/world-map-series` on every
   call rather than caching in-process, to keep the MCP server stateless (simpler, no
   cache-invalidation logic, no per-replica cache divergence under horizontal scaling). The
   payload is small (~50KB) and the underlying data only changes on notebook reruns, so
   there's no freshness reason to cache yet — revisit only if call volume makes the redundant
   fetch a measurable cost.
3. **§6.3 — Sovereign country list — resolved, no longer deferred.** Originally flagged by
   both source documents as "not required to ship," then included during implementation of
   root `SPEC.md` §5.22 once it was clear it's a one-line addition piggybacking on the loader
   change that work already required. `GET /countries` returns `sovereign` as a full sorted
   `list[str]` (~218 entries, confirmed in `api/schemas.py`/`api/routers/countries.py`) — this
   is what `list_countries` surfaces directly (§5) and what `scope_note` (§3.2) derives its
   "N of 218" denominator from via `len(sovereign)`.

## 7. Staged verification plan

Per the broader project's Stage 1: build this server, connect it to Claude Desktop/Claude
Code over Streamable HTTP, and iterate on tool descriptions/argument schemas until
tool-calling is reliable — before any LangGraph agent or generative-UI work begins.

## 8. AuthZ architecture (Design — confirmed 2026-08-13, Phase 1 implemented)

Addendum to §2's Auth row and §2.1's V1 deviation note — this section is the settled design
those two deferred, now that this server is about to leave localhost-only per §7's staged plan.
Written against the actual deploy topology (Cloudflare Tunnel `ghg-emissions-analysis`, its
published application routes on `labs.syena.io`, free-tier Zero Trust) rather than a generic
pattern — every claim below was checked against the live Cloudflare config or the installed
SDK, not assumed (§8.3).

### 8.1 Four trust boundaries, not one

"Comprehensive AuthZ" for this project isn't a single mechanism — the browser-facing and
service-to-service legs have genuinely different constraints, and conflating them was the main
risk in the original ask:

| Boundary | Parties | Can hold a secret? |
|---|---|---|
| B1 — Browser ↔ dashboard | Anonymous public visitor ↔ static SPA | No — public by design |
| B2 — Browser ↔ `api/` | Anonymous public visitor ↔ FastAPI | No — anything a browser sends is visible via DevTools/view-source; no mechanism can hide a secret from the party presenting it |
| B3 — This server ↔ `api/` | This server ↔ `api/`, same Mac Mini | Yes — both sides are ours |
| B4 — External MCP clients ↔ this server | Claude Desktop/Code, named testers ↔ this server, now internet-reachable. **Not** this project's own LangGraph agent — see the corrected §8.4 checklist item below; a co-located agent is B3, not B4. | Yes — the client list is small and known |

A single bearer-token gate on `/api/*` would authenticate B3 correctly but breaks B2 (the
dashboard has no way to hold the secret) — the two must not share one gate. This is why §8.2
leaves `/api/*` open and puts the actual new auth surface on B4.

### 8.2 Decisions

| Boundary | Decision | Rationale | Rejected / deferred |
|---|---|---|---|
| B1/B2 | Stay unauthenticated. `CORS allow_origins` gains the production origin (`https://labs.syena.io`) alongside the existing dev origin. This is an `api/main.py` change, owned by root `SPEC.md`'s own addendum, not this file — listed here only as the §4-style cross-reference this doc already uses for API-side dependencies. | Data is meant to be public; a browser-visible token protects nothing and adds maintenance for no real gain. The existing Cloudflare rate-limit rule (50 req/10s per IP on `/ghg-emissions-analysis`) and response-header rules (CSP, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`) already cover the realistic abuse surface for public read data. | A same-origin session cookie or edge-issued token — adds complexity without stopping a determined actor, since the browser must always be able to read what it renders. |
| B3 | No change. `uvicorn` stays bound to `127.0.0.1:8081`, reachable only via the Tunnel — this server's calls to `api/` are already network-isolated, not merely unauthenticated. | Network topology already does the job an app-layer token would do here. Revisit only when Phase 2 (§8.5) restricts `/api/*` itself. | A service-account bearer token on this leg now — the eventual target shape per §2, but dead code while `api/` has no auth to check it against (same reasoning §2.1 already gave for V1; still true). |
| B4 | Cloudflare Access, Service Auth policy, scoped to a new published application route — no application-layer auth code added to this server. | Matches the actual client list at launch (§8's header date): Claude Desktop/Code and a handful of named testers — a small, fully known set is exactly what Access Service Tokens are for. (This project's own LangGraph agent turned out not to be in this list — see §8.4's corrected checklist item; it's co-located and reaches this server as a B3 client instead.) Free-tier Zero Trust (confirmed: up to 50 seats, Service Tokens included) covers this with room to spare. Enforcement happens at Cloudflare's edge, before a request reaches the Mac Mini at all — less code to write and maintain than hand-rolled bearer-token middleware, and per-client revocation/rotation becomes a dashboard action instead of a deploy. | Hand-rolled bearer-token ASGI middleware — viable, more code, no material security difference for this client list. OAuth 2.1 — the correct mechanism once clients aren't ones being personally handed out; deferred to §8.5. |

### 8.3 Deploy topology — path on the existing hostname, not a new subdomain

Reuses `labs.syena.io` rather than provisioning a new hostname, extending the existing
published-application-routes table (screenshot-confirmed 2026-08-13):

| # | Hostname | Path | Service | Status |
|---|---|---|---|---|
| 1 | `labs.syena.io` | `^/ghg-emissions-analysis/api` | `http://localhost:8081` | existing |
| 2 (new) | `labs.syena.io` | `^/ghg-emissions-analysis/mcp` | `http://localhost:8765` | to add — must sit above row 3, see below |
| 3 | `labs.syena.io` | `/ghg-emissions-analysis` | `http://localhost:4173` | existing, unanchored |

Ordering is load-bearing, not cosmetic. Row 3's pattern is an unanchored prefix match on
`/ghg-emissions-analysis` — the same reason row 1 needed anchoring above it when it was added.
Placing the new `/mcp` route below row 3 would have every MCP request silently swallowed by the
dashboard's catch-all and served `index.html` (HTTP 200) instead of a Streamable HTTP response
— no error, just a confusing client-side failure.

Access application: attached to `labs.syena.io` with Application path `/ghg-emissions-analysis/mcp`,
so the Service Auth policy (§8.2) only gates this one path; rows 1 and 3 are untouched by it.

**Server-side path handling — confirmed against the installed SDK** (`mcp>=2.0.0`,
`mcp.server.mcpserver.MCPServer.run_streamable_http_async`), not assumed:

```python
async def run_streamable_http_async(
    self, *, host: str = "127.0.0.1", port: int = 8000,
    streamable_http_path: str = "/mcp", ...,
    transport_security: TransportSecuritySettings | None = None,
) -> None:
```

`streamable_http_path` is a first-class kwarg, and `MCPServer.run(transport="streamable-http",
**kwargs)` forwards straight into it — this server does not need a
`StripDeployPrefixMiddleware`-style workaround the way `api/main.py` did. `server.py` reads the
same `DEPLOY_BASE_PATH` env var `api/main.py` and `vite.config.ts` already share
(`ARCHITECTURE.md` §5/§6) and derives `streamable_http_path` from it — **through the same
`_normalize_deploy_prefix` normalization `api/main.py` already applies**, not naive string
concatenation: `DEPLOY_BASE_PATH`'s documented production value carries a trailing slash
(`/ghg-emissions-analysis/`), so `f"{prefix}/mcp"` without first stripping it would produce
`/ghg-emissions-analysis//mcp`. `server.py` carries its own hand-mirrored copy of this
normalization (not a shared import — the two services don't share a dependency graph), the same
pattern already established between `api/data_loaders.py` and `app.py`.

**DNS-rebinding protection will silently reject the deploy if left at defaults.**
`TransportSecuritySettings` (also confirmed against the installed SDK) defaults to:

```python
enable_dns_rebinding_protection: bool = True
allowed_hosts: list[str] = []
allowed_origins: list[str] = []
```

Once traffic arrives via the Tunnel it carries `Host: labs.syena.io` — with the empty
allow-lists above, every request would be rejected. Must be passed explicitly:

```python
transport_security=TransportSecuritySettings(
    allowed_hosts=["labs.syena.io"],
    allowed_origins=["https://labs.syena.io"],
)
```

Left unset, this would present as "Tunnel healthy, Access passing tokens through, every MCP
call still fails" with no obvious cause — worth catching in design rather than after deploying.

**This must not apply unconditionally**, or every local/test connection to this server breaks —
they connect via `127.0.0.1:<port>`, not `labs.syena.io`, and `TransportSecurityMiddleware`
only disables DNS-rebinding protection entirely when its settings argument is `None`; an
*empty* `TransportSecuritySettings` (rather than `None`) would still reject every local
request, since its own `allowed_hosts`/`allowed_origins` default to `[]`. `server.py` reuses
`DEPLOY_BASE_PATH`'s presence — already this codebase's existing signal for "deployed behind
the Tunnel" — as the switch: `transport_security` is built only when that env var is set, and
passed as `None` (not an empty settings object) otherwise, preserving today's permissive
local/stdio behavior exactly.

**Host binding stays as-is.** `server.py`'s comment previously tied `host="127.0.0.1"` to "not
reachable externally," written when no Access layer existed. Once the Access-gated Tunnel route
exists, those two facts are separable — the binding itself does not need to change, and now
reads as a deliberate defense-in-depth choice (Access at the edge, network isolation
underneath) rather than a stopgap for missing auth.

### 8.4 Required changes

- [x] `services/mcp-server/src/mcp_server/server.py` — reads `DEPLOY_BASE_PATH` (via a local
  `_normalize_deploy_prefix`, mirroring `api/main.py`'s exactly); derives `streamable_http_path`
  and a conditional `transport_security` (both `None` when unset, locked to `labs.syena.io`
  when set) via `_streamable_http_settings()`; passes both into the existing `mcp.run(...)` call
  in `main()`; host-binding comment updated to reflect the reasoning above, not the binding
  itself. Verified via `pytest services/mcp-server/tests` and direct local smoke tests against a
  real subprocess (unset: `/mcp` unchanged; set: `/ghg-emissions-analysis/mcp` responds, correct
  `Host: labs.syena.io` succeeds, mismatched `Host` gets a `421`, old unprefixed `/mcp` 404s).
- [x] **Cloudflare dashboard** — published application route added (correctly ordered above the
  dashboard's catch-all row); Access application `ghg-emissions-mcp-server` created, scoped to
  `labs.syena.io` path `/ghg-emissions-analysis/mcp`; policy `ghg-emissions-mcp-auth` created
  with action **Service Auth** (not a login/identity-provider policy); three named, individually
  revocable Service Tokens issued (`ghg-emissions-mcp-app-agent`, `ghg-emissions-mcp-claude-desktop`,
  `ghg-emissions-mcp-internal-tester`), each added to the policy's Include rule by name.
  **Verified live from outside the Mac Mini**: `https://labs.syena.io/ghg-emissions-analysis/mcp`
  with no credentials and with a wrong/bogus `CF-Access-Client-Id`/`CF-Access-Client-Secret` pair
  both return `403` — Access is genuinely gating the endpoint at Cloudflare's edge, before a
  request ever reaches the Mac Mini. (The accept path — a real, valid Service Token succeeding —
  wasn't verified from this session, since token secrets are shown once in the dashboard and
  weren't shared here; worth confirming once a real client is configured, §8.4's next bullet.)
- [x] **Client-side, Claude Desktop.** Correcting an assumption this checklist made before it
  was actually tried: Claude Desktop's GUI "Add custom connector" flow does **not** support
  arbitrary static headers — its "Advanced settings" fields are OAuth Client ID/Secret for a
  server that implements OAuth 2.1 itself (`/authorize`, `/token`). This server deliberately
  doesn't (§8.2's whole point is Cloudflare Access instead of app-layer auth), so that flow
  fails: Desktop opens a browser to an `/authorize` URL that doesn't exist, which downloads as
  a zero-byte file rather than completing. **Working alternative**: bypass the GUI entirely and
  add a `claude_desktop_config.json` `mcpServers` entry using
  [`mcp-remote`](https://github.com/geelen/mcp-remote) (`npx mcp-remote <url> --header
  "CF-Access-Client-Id:${CF_CLIENT_ID}" --header "CF-Access-Client-Secret:${CF_CLIENT_SECRET}"`,
  values sourced from an `env` block — not inlined with a space after the colon, which a known
  Desktop bug mangles) as a local stdio↔HTTP bridge that injects the two Access headers itself.
  Confirmed working end-to-end: connector loaded, all 13 tools listed correctly. Uses the
  `ghg-emissions-mcp-claude-desktop` Service Token specifically (not the app-agent/tester ones),
  keeping per-client attribution/revocation meaningful.
- [x] **Client-side, LangGraph agent (Stage 2) — turned out not to be a B4 client.** Corrected
  2026-08-13 when `services/agent`'s Step 1 confirmed it's deployed **co-located on the same Mac
  Mini** as this server, not reaching in from outside it. That makes it a B3 case, not B4: it
  connects over `127.0.0.1:8765`, unauthenticated, the same trust boundary this server's own
  calls to `api/` already use — no Cloudflare Access headers, no Service Token. The
  `ghg-emissions-mcp-app-agent` Service Token (provisioned above) stays unused unless an actual
  external agent deployment shows up later; it is not dead weight to remove, just currently
  idle. See `services/agent/SPEC.md` "Corrections applied" #4 and
  `services/agent/ARCHITECTURE.md` for the full boundary writeup on the agent's side.
- [x] `api/main.py` — CORS `allow_origins` gains `https://labs.syena.io` alongside the existing
  dev origin (`http://localhost:5173`). Cross-referenced here (§4-style) but this is the one
  explicit, narrow exception to `CLAUDE.md`'s "no changes to `api/`" convention for this Phase
  1 work, made on direct instruction rather than folded in unprompted. Same-origin dashboard
  traffic behind the Tunnel never triggered a CORS check either way — this makes the intended
  origin allow-list explicit in code rather than an accident of same-origin deployment, so a
  future subdomain/staging origin has to be added deliberately rather than silently inheriting
  or lacking access with no record of the decision either way. Verified via two new
  `api/tests/test_main.py` cases (production origin gets the header, an unlisted origin
  doesn't); full `pytest api/tests` green (117 passed).
- No change required to `services/mcp-server/src/mcp_server/client.py` (B3, §8.2) or to `api/`
  auth (none exists today, none added in this phase — see §8.5).

### 8.5 Phase 2 — deferred, scope confirmed but not designed

Two items intentionally bundled for a later pass, per the 2026-08-13 discussion this addendum
comes from:

- Restricting `/api/*` from fully public reads — shape not yet decided (gate behind Access too?
  split public-read vs restricted-read endpoints? give the B3 service-account token from §2's
  original target shape real work to do instead of being redundant with network isolation?).
- OAuth 2.1 for B4, if/when this server's MCP client list stops being ones handed out
  individually — Service Tokens (§8.2) are the right fit for a small known set, not for
  arbitrary or self-registering third-party clients.

Both are explicitly out of scope for the Phase 1 work in §8.4.
