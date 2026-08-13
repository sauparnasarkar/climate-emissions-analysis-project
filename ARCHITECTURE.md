# Architecture

A current-state description of how this system is actually built, as of `SPEC.md` v44.
Unlike `SPEC.md` (weekly curriculum requirements + a versioned decision log) and
`ENHANCEMENTS.md` (a chronological release-by-release changelog), this document doesn't
narrate history — it describes what exists today. For *why* a given piece is shaped the
way it is, or when it changed, follow the `SPEC.md §`/`ENHANCEMENTS.md Release` cross-references
inline rather than expecting the reasoning to be repeated here.

---

## 1. Two parallel deliverables, one dataset

This repo contains two genuinely separate things sharing the same `data/` pipeline:

- **The internship curriculum** (`SPEC.md` §§1–2): five per-week Jupyter notebooks
  (`notebook/week1_eda.ipynb` … `week5_scenarios.ipynb`) producing a documented analysis,
  plus an optional Streamlit app (`app.py`, the Week 6 stretch goal). This is what interns
  are actually asked to build.
- **The mentor's post-internship reference architecture** (`SPEC.md` §5): a FastAPI
  backend (`api/`) and a React + TypeScript dashboard (`climate-dashboard-react/`)
  exposing the same computations as a production-shaped web app. Not internship scope,
  not graded — built afterward as a separate example of a full data-engineering +
  front-end stack on top of the same analysis.

Both read from the same `data/` CSVs; neither depends on the other at runtime.

A third strand, `services/mcp-server/` (§8), is joining the second group — it's a client of
`api/` (over HTTP, not the shared `data/` pipeline directly), so it doesn't fit this section's
"reads from `data/`" framing, but the same "mentor's post-internship expansion, not internship
scope" boundary applies to it.

## 2. Data pipeline

```
data/owid-co2-data.csv (manual download, ~50MB, gitignored)
        │
        ▼
notebook/week1_eda.ipynb ──▶ data/ghg_filtered.csv, data/selected_countries.json
        │
        ▼
notebook/week2_features.ipynb ──▶ data/ghg_features.csv
        │
        ▼
notebook/week3_regression.ipynb ──▶ data/model_comparison_regression.csv, data/feature_importance.csv
        │
        ▼
notebook/week4_ets_forecasting.ipynb ──▶ data/ets_forecasts.csv, data/ets_parameters.csv, data/model_comparison.csv
        │
        ▼
notebook/week5_scenarios.ipynb (optional) ──▶ data/scenario_projections.csv
```

Every notebook runs independently, loading whatever the previous week already wrote —
`notebook/constants.py` is the single source of truth for shared constants
(`FEATURED_COUNTRIES`, `NON_SOVEREIGN`, `FEATURES`, `TARGET`, `TRAIN_CUTOFF`,
`FORECAST_END`, …), imported via `from constants import *`, never redefined inline.

**Consumers read the same CSVs, not each other.** `app.py` (`@st.cache_data`) and
`api/data_loaders.py` (`@lru_cache(maxsize=1)`) each independently load and cache the
same files in-process — the two loader modules are hand-mirrored 1:1, not shared code.
Cache invalidation is "restart the process" (a deploy, or the weekly refresh below); there
is no explicit invalidation path.

**Weekly automated refresh** (`ghg-data-refresh` skill, `com.ghgemissions.datarefresh`
launchd agent, Sundays 03:30 local on the Mac Mini): re-downloads `owid-co2-data.csv` and
re-runs the full notebook pipeline non-interactively (`run_notebooks.sh`, `jupyter
nbconvert --execute --inplace`, stopping at the first failure), then restarts the
`uvicorn`/`vitepreview` services so the API/frontend pick up the new CSVs. Validates the
new country count against a drift threshold (see `SPEC.md` §6.1) rather than blindly
trusting upstream data.

## 3. The two/three-tier country pattern

`FEATURED_COUNTRIES` (10, hardcoded) is the original curated set, still the default
everywhere a fixed-size UI needs one (5×2 subplot grids, seeded picker defaults).
`get_expanded_countries()` (`notebook/constants.py`) / `load_expanded_countries()`
(`api/data_loaders.py`) load a data-driven ~40-country set (coverage + materiality
thresholds, computed in Week 1 §1.2, persisted to `data/selected_countries.json`), used
everywhere else — per-country training loops, aggregate sums, any interactive picker's
searchable pool. The Overview page extends this into three simultaneous tiers (All
Countries / Expanded / Selected) rather than picking one. Full rationale in `CLAUDE.md`'s
"Key Design Decisions" and `SPEC.md` §5.6–§5.7.

## 4. Backend (`api/`)

FastAPI (`0.139.2`) + Uvicorn (`0.51.0`), one router per dashboard page
(`api/routers/{overview,historical,country_profile,forecasts,scenarios,explorer,countries}.py`),
Pydantic response models (`api/schemas.py`). Mirrors `app.py`'s pandas logic
endpoint-by-endpoint — same computations, same cache shape, different transport.

**Deploy-prefix handling** (`api/main.py`): `DEPLOY_BASE_PATH` (same env var the frontend
build reads, see §6) is normalized and used two ways — `root_path=DEPLOY_PATH_PREFIX` on
the `FastAPI()` instance so Starlette's own URL generation (`/docs`, `/redoc`,
`openapi.json`) stays prefix-aware, and a `StripDeployPrefixMiddleware` that actually
strips the prefix from `scope["path"]`/`scope["raw_path"]` before routing — necessary
because Cloudflare Tunnel forwards the *full* prefixed path with no stripping of its own,
while every route is mounted at plain `/api/...`. `redirect_slashes=False` throughout,
since Starlette's trailing-slash redirect builds its `Location` header from the
un-prefixed path regardless of `root_path`, which would otherwise redirect to a broken URL.

**Tests**: `pytest api/tests` — every endpoint's happy path, 4xx/503 error paths, and
pandas edge cases, against small fixture CSVs written to a temp dir rather than the real
(gitignored) data.

## 5. Frontend (`climate-dashboard-react/`)

React (`19.2.7`) + TypeScript + Vite (`8.1.1`), React Router (one page per route:
Overview, Historical Trends, Country Profile, Forecasts, Scenario Comparison, Data
Explorer, About — `App.tsx`'s `NAV_ITEMS`), a typed fetch client (`src/api/`) mirroring
`api/schemas.py`, AG Grid for tabular data, Plotly (via design-system's `SyChart`) for
charts.

### Design-system integration

Built on the **Analytics theme** (`data-theme="analytics"`, set once at `App.tsx`'s root)
of the Syena design system — a separate, sibling checkout (`../../design-system`, one
level above this repo, not a submodule) shared across other projects too, which is why it
isn't vendored into this monorepo. For the design system itself — token architecture,
theming, the full component catalog, established conventions — see `DESIGN.md` in the
`design-system` repo; this section only covers how *this app* consumes it.

- **Sourced, not published.** `vite.config.ts` aliases `design-system` straight to
  `../../design-system/src` — there's no `main`/`exports`/`dist`, no version to bump, no
  publish step. A change merged to `design-system`'s `main` is live in this app the moment
  its checkout is pulled and rebuilt (see deploy sequencing, §6).
- **Single React instance.** Because design-system's components run inside this app's own
  bundle rather than as an installed package, `react`/`react-dom` are aliased to this
  app's `node_modules` copies explicitly — two copies would break hooks.
- **No per-page selection.** The theme is applied once, at the shell; individual pages
  don't opt in or out.

### PWA / service worker

`vite-plugin-pwa` (Workbox, `registerType: 'autoUpdate'`). `NetworkFirst` for `/api/*`
(data freshness matters more than offline access for a live dashboard; 5s timeout before
falling back to cache), default precache-then-serve for the built JS/CSS/icons.
`navigateFallbackDenylist` excludes any path with a file extension from the SPA-shell
fallback, so a direct link to a static asset (e.g. the About page's `.pptx`) downloads
instead of resolving to `index.html`.

### Deploy-prefix handling

`DEPLOY_BASE_PATH` (e.g. `/ghg-emissions-analysis/`) is read by both `vite.config.ts`
(`normalizeBase`, sets Vite's own `base` + rewrites the dev/preview `/api` proxy target)
and `api/main.py` (`_normalize_deploy_prefix`, §4) from the **same** env var, so the two
can't drift on what prefix is being stripped. Must be set at *build* time for the
frontend, not just serve time — the prefix is baked into the built assets.

### Tests

`npx vitest run` (`climate-dashboard-react/`) — API client URL/param construction plus a
loading/data/error smoke test per page, mocking `api/client.ts` rather than hitting a live
backend; `SyChart` is stubbed in page tests (Plotly's own DOM lifecycle is design-system's
test suite's concern, not this app's).

## 6. Deploy topology

Everything runs on a single Mac Mini, exposed publicly via Cloudflare Tunnel — no cloud
hosting. Four `launchd` agents (`~/Library/LaunchAgents/com.ghgemissions.*.plist`):

| Agent | Runs | Port | Notes |
|---|---|---|---|
| `cloudflared` | `cloudflared tunnel run` | — | Publishes `labs.syena.io` → this machine; forwards full prefixed paths with no stripping (`KeepAlive`) |
| `uvicorn` | `api.main:app` | `127.0.0.1:8081` | `DEPLOY_BASE_PATH=/ghg-emissions-analysis/` |
| `vitepreview` | `vite preview` (built `climate-dashboard-react/dist`) | `127.0.0.1:4173` | Same `DEPLOY_BASE_PATH`; must be rebuilt (not just restarted) after any change, since the prefix is baked in at build time |
| `datarefresh` | `ghg-data-refresh.sh` | — | Weekly, §2 above |

**Deploy sequencing**: `design-system` must be pulled (`git merge --ff-only`) *before*
`climate-dashboard-react` is rebuilt, since the frontend build reads design-system's
source directly (§5) — pulling frontend changes without first updating a design-system
dependency they need fails the build. Standard sequence for a frontend-affecting change:
pull `design-system` → pull this repo → `DEPLOY_BASE_PATH=/ghg-emissions-analysis/ npm run
build` in `climate-dashboard-react/` → `launchctl kickstart -k
gui/$(id -u)/com.ghgemissions.vitepreview`. A Vite content-hash filename
(`assets/index-<hash>.js`) is the reliable way to confirm a fresh build — not a stale
bundle — is actually what's live.

## 7. MCP server (`services/mcp-server/`)

Wraps `api/` as hand-curated MCP tools — Stage 1 of a separate conversational-agent project
(not the internship, not the `api/`+`climate-dashboard-react/` dashboard stack in §§4–6). Full
design lives in `services/mcp-server/SPEC.md`; this section covers only where it sits relative
to the rest of the system.

**Data flow**: HTTP client of `api/`, same interface any consumer uses (no shared-library
import, no privileged access path) — `API_BASE_URL` env var, must include the `/api` prefix.
Independently versioned/deployable from `api/` (own `pyproject.toml`), though in practice both
still ship from the same repo and the same Mac Mini would host both if this were deployed.

**Not yet in the deploy topology (§6)**: as of this writing, it hasn't reached a Mac Mini
deploy — no `launchd` agent for it exists in §6's table yet. The auth blocker that gated a
public deploy is now resolved by design (`services/mcp-server/SPEC.md` §8, settled 2026-08-13):
this server's own public endpoint is gated by Cloudflare Access at the edge, not an app-layer
token, and the code-side piece (`DEPLOY_BASE_PATH`-driven path prefixing + DNS-rebinding
protection) is implemented. What remains before this section gets a real deploy-topology entry
is operational, not architectural: the Cloudflare dashboard work (new published route, Access
application, Service Tokens per client) and the actual Mac Mini `launchd` agent —
`services/mcp-server/SPEC.md` §8.4 tracks the checklist. A Dockerfile and CI job remain
deliberately deferred (`SPEC.md` §2.1), unrelated to the auth resolution.

## 8. See also

- **`SPEC.md`** — curriculum requirements (§§1–2), the mentor's addendum with full
  narrative rationale for every architectural decision (§5), curriculum corrections (§6),
  and a versioned decision log (§4, "Version History").
- **`ENHANCEMENTS.md`** — the same history as `SPEC.md` §5, told chronologically by
  release rather than by topic — useful for "what shipped in what order," where `SPEC.md`
  is organized for "what does §5.X do and why."
- **`CLAUDE.md`** — agent-facing operating instructions, plus the ML methodology
  decisions (model choices, train/test split, scope boundaries) this document doesn't
  cover.
- **`design-system/DESIGN.md`** — the design system itself, independent of any one consumer.
- **`services/mcp-server/SPEC.md`**, **`services/mcp-server/CLAUDE.md`**,
  **`services/mcp-server/ENHANCEMENTS.md`** — the MCP server sub-project's own design,
  agent-facing instructions, and release history, kept separate from the above rather than
  folded in (§8).
