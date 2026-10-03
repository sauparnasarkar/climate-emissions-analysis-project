# GHG Emissions Trend Analysis and Forecasting

**Started as a Reference Implementation for IDEAS TIH Summer Internship 2026 (Mentor: Sauparna Sarkar)**

**The Focus of the Reference Implementation was limited to the GHG emissions data, ML pipeline and Streamlit dashboard**

**This was later expanded to an end-to-end Analytic Pipeline, Visualization Dashboard and an AI Analytic Engine with a cimate-context layer**

---

## Project Overview

This project builds an end-to-end analytical pipeline on open Greenhouse Gas (GHG) emissions data. The team ingests the OWID CO₂ dataset, performs exploratory data analysis, engineers time-series features, trains regression and forecasting models, and (optionally) assembles an interactive Streamlit dashboard. The focus is on classical ML and time-series methods applied to structured annual emissions data for 10 countries across 1990–2023.

**Area 2 — the climate-context layer (post-internship, not an internship deliverable).** A separate `pipeline/`
ingests atmospheric CO₂ concentration (NOAA GML + Law Dome ice cores), global temperature (Berkeley Earth) and
all-gas national emissions (PRIMAP-hist) alongside OWID, harmonizes them, and precomputes the analytics a dashboard
or an agent needs: a total-anthropogenic-CO₂ vs temperature regression (a simplified, data-driven analog to the IPCC's
TCRE, with its uncertainty and stability checks), the greenhouse-gas composition, each country's cumulative share, and an
illustrative translation of the Week 5 scenarios into implied temperature. Seven read-only `/api/correlation/*`
endpoints serve those outputs. These are descriptive analyses, not climate-model projections, and co-movement is
not presented as proof of causation. See [`pipeline/README.md`](pipeline/README.md) and `SPEC.md` §5.26.

---

## Setup

### 1. Clone the repository
```bash
git clone https://github.com/sauparnasarkar/climate-emissions-analysis-project.git
cd climate-emissions-analysis-project
```

### 2. Create a virtual environment (recommended)
```bash
python3 -m venv venv
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Download the dataset
The OWID CO₂ dataset is not committed to this repository (it is ~50 MB). Download it once and save it to the `data/` folder:

```bash
curl -o data/owid-co2-data.csv \
  https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv
```

Or download manually from: https://github.com/owid/co2-data

### 5. Run the notebooks

The analysis is split into one notebook per week. Run them **in order** — each week
loads CSVs saved by the previous one (`notebook/constants.py` holds constants shared
by every notebook, e.g. `COUNTRIES`, `FEATURES`, `TRAIN_CUTOFF`):

```bash
jupyter notebook notebook/week1_eda.ipynb              # → data/ghg_filtered.csv
jupyter notebook notebook/week2_features.ipynb          # → data/ghg_features.csv
jupyter notebook notebook/week3_regression.ipynb         # → data/model_comparison_regression.csv, data/feature_importance.csv
jupyter notebook notebook/week4_ets_forecasting.ipynb    # → data/ets_forecasts.csv, data/ets_parameters.csv, data/model_comparison.csv
jupyter notebook notebook/week5_scenarios.ipynb          # → data/scenario_projections.csv (optional)
```

Alternatively, run all 5 in order non-interactively with `./run_notebooks.sh` (executes
each via `jupyter nbconvert --execute --inplace`, stopping at the first failure). Requires
`data/owid-co2-data.csv` to already be downloaded (step 4).

### 6. Run the Streamlit app (Week 6 stretch goal)
> **Prerequisite:** Complete Week 2 first so that `data/ghg_features.csv` exists — that's
> the only file the app requires to start. Weeks 3–5's outputs are all optional: without
> them, the Forecasts and Scenario Comparison pages just show a "file not found" message
> in place of real data rather than crashing. Complete Week 5 too if you want the Scenario
> Comparison page to actually show scenario projections.

```bash
streamlit run app.py
```

### 7. Run the FastAPI backend + React dashboard (stretch)

An alternative to the Streamlit app: a FastAPI backend (`api/`) exposing the same
computations as JSON, consumed by a React + TypeScript dashboard (`climate-dashboard-react/`)
built on the Analytics Theme of the (separate, sibling) Syena design system. Two processes,
two terminals, both from the repo root:

```bash
# Terminal 1 — backend
pip install -r requirements.txt
uvicorn api.main:app --reload --port 8081

# Terminal 2 — frontend
cd climate-dashboard-react
npm install
npm run dev            # → http://localhost:5173, proxies /api to :8081
```

> **Note:** `climate-dashboard-react` resolves the design system via a Vite alias to
> `../../design-system/src` — it expects a sibling `design-system/` checkout one level
> above this repo (i.e. `design-system` and `climate-emissions-analysis-project` are both
> under the same parent directory).

**Frontend tests**: `cd climate-dashboard-react && npm test` (Vitest + React Testing
Library) — API client URL/param construction plus a loading/data/error smoke test per
page, mocking `api/client.ts` rather than hitting a live backend. `npm run test:watch`
for watch mode.

**Backend tests**: `pytest api/tests` from the repo root (pytest + FastAPI's `TestClient`)
— every endpoint's happy path, 4xx/503 error paths, and pandas edge cases (NaN handling,
sort ordering, the deploy-prefix middleware), all against small fixture CSVs written to a
temp dir rather than the real (gitignored) data.

### 8. Run the Area 2 climate-context pipeline (post-internship, optional)

Needs the same environment as above (the pinned `requirements.txt` matters: **numpy 2.3.5** —
with numpy 2.2.6 on Python 3.14, large dense pandas reshapes were found to corrupt silently, see
[`pipeline/README.md`](pipeline/README.md)), the OWID file from step 4, and network access to NOAA GML,
Berkeley Earth and Zenodo. The scenario translation also reads `data/scenario_projections.csv`, so run the
**Week 5 notebook before the scenario stage** (step 5).

```bash
python -m pipeline.run --source all        # one source: --source noaa_gml | berkeley_earth | primap_hist | owid
                                           #   | harmonize | correlate | composition | country_share
                                           #   | ets_baseline | scenario_temperature
# → data/climate/*.csv|json (gitignored), plus data/climate/last_run.json with every deviation from norm
```

Each stage always rewrites its outputs: an input that is missing or fails a check produces explicit nulls and a
reason (never a stale or partial result) and is reported as a deviation. The backend reads `data/climate/` (override
with `CLIMATE_DATA_DIR`):

```bash
uvicorn api.main:app --port 8081
curl http://127.0.0.1:8081/api/correlation/meta       # sources, licences, baselines, output freshness
# also: /concentration /temperature /emissions-temperature /ghg-composition /country-share /scenario-temperature
```

**Tests**: `pytest pipeline/tests` (each stage on small stubbed inputs, plus the refresh job's shell logic) and
`pytest api/tests` (the API tests build their data by running the real pipeline stages). On the Mac Mini the
pipeline runs monthly via the refresh job in [`pipeline/ops/`](pipeline/ops/README.md).

### 9. The monthly data refresh (Mac Mini)

On the Mac Mini a launchd job runs [`~/bin/ghg-data-refresh.sh`](pipeline/ops/ghg-data-refresh.sh) **monthly, on day 10 at
03:30** (after NOAA's monthly file and Berkeley Earth's update have landed; label `com.ghgemissions.datarefresh`,
definition in [`pipeline/ops/`](pipeline/ops/README.md)). One run, in this order:

1. **Back up and download** `data/owid-co2-data.csv` (`data/owid-co2-data.csv.bak-YYYYMMDD`); a download under ~5 MB restores the backup and stops.
2. **Week 1** notebook with its validation against the backup. A hard failure restores the backup and skips the notebooks;
   a soft flag (e.g. an unusual row-count change) continues and is reported.
3. **Weeks 2–5** notebooks (features, models, forecasts, scenarios), executed in place.
4. **Area 2 pipeline** (`python -m pipeline.run --source all`), after the notebooks so the scenario stage reads this run's
   scenarios. It also runs after a notebook failure (its own failure domain).
5. **API restart** (`com.ghgemissions.uvicorn` only, a few seconds of failed requests), so it loads the refreshed files:
   after a validated notebook refresh, or after a week-1 failure when the Area 2 stage produced new files. Never after a
   weeks 2–5 failure (partially regenerated CSVs).
6. **Notification** (ntfy) with the outcome: priority `high` if anything was flagged, `urgent` if a notebook or a pipeline
   source failed; the Area 2 deviations (e.g. the Berkeley Earth stale-source alert) are appended.

**Run it on demand** (on the Mac Mini):

```bash
~/bin/ghg-data-refresh.sh                          # the full job, as scheduled
GHG_SKIP_API_RESTART=1 ~/bin/ghg-data-refresh.sh   # same, but leave the running API alone
launchctl kickstart gui/$(id -u)/com.ghgemissions.datarefresh   # or let launchd run it
```

**Read the result**: `~/.ghg-data-refresh/logs/YYYY-MM-DD.log` (and `launchd.out.log` / `launchd.err.log` beside it);
`data/climate/last_run.json` has every note and deviation of the Area 2 stage; `/api/correlation/meta` shows each output's age and
a `stale` flag (more than 45 days old). Confirm the restart with `launchctl list | grep ghgemissions.uvicorn` (a new PID).

**Without the Mac Mini** (e.g. a laptop): `./run_notebooks.sh` then `python -m pipeline.run --source all`, as in steps 5 and 8.

**Change the schedule or roll back**: edit `Day`/`Hour`/`Minute` in the plist, then
`launchctl bootout gui/$(id -u)/com.ghgemissions.datarefresh` and
`launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.ghgemissions.datarefresh.plist` (`kickstart -k` would keep the
old definition). Timestamped backups of the script and plist (`.bak-YYYYMMDD`) sit beside the live files; the
[ops README](pipeline/ops/README.md) has the full deploy and rollback steps.

---

## Data Sources

| Dataset | Source | Format | Licence (authoritative text: `data/climate/provenance.json`, `/api/correlation/meta`) |
|---------|--------|--------|--------|
| OWID CO₂ and GHG Emissions (incl. Global Carbon Project land-use CO₂) | https://github.com/owid/co2-data | CSV | CC BY 4.0 for OWID's compilation; third-party data under its original terms (the land-use series requires citing the Global Carbon Project) |
| Atmospheric CO₂ concentration | NOAA GML Mauna Loa (1959+), spliced to the Law Dome ice-core/firn spline before 1959 | CSV / text | NOAA: public domain, citation requested; Law Dome: cite the original papers |
| Global temperature anomaly | Berkeley Earth Land/Ocean (annual) | text | CC BY-NC 4.0 (non-commercial; commercial use needs a licence from Berkeley Earth), cite Rohde & Hausfather 2020 |
| National all-gas emissions (CO₂, CH₄, N₂O, F-gases) | PRIMAP-hist v2.8 (Zenodo) | CSV | CC BY-NC-SA 4.0 (non-commercial, share-alike) |
| Climate Watch Historical Emissions | https://climatewatchdata.org | CSV | deferred, not ingested |
| EDGAR | JRC | — | shelved for publication (the IEA fuel-combustion CO₂ inside it is CC BY-NC-ND); code kept dormant for internal validation only |

| Dataset | Source | Format |
|---------|--------|--------|
| OWID CO₂ and GHG Emissions | https://github.com/owid/co2-data | CSV |
| Climate Watch Historical Emissions | https://climatewatchdata.org | CSV |

---

## Project Structure

```
ghg-trend-analysis-forecasting/
├── notebook/
│   ├── constants.py                  ← Shared constants (COUNTRIES, FEATURES, TRAIN_CUTOFF, ...)
│   ├── week1_eda.ipynb                ← Week 1: data loading, profiling, EDA
│   ├── week2_features.ipynb           ← Week 2: feature engineering
│   ├── week3_regression.ipynb         ← Week 3: regression models + comparison table
│   ├── week4_ets_forecasting.ipynb    ← Week 4: ETS(A,Ad,N) Holt Damped forecasting
│   ├── week5_scenarios.ipynb          ← Week 5: scenario analysis (optional)
│   └── archive/
│       └── ghg_analysis_combined.ipynb ← Original single-file notebook, kept as a backup only
├── data/
│   ├── .gitkeep                ← Keeps the folder in git; actual CSVs are gitignored
│   ├── owid-co2-data.csv       ← Download manually (see Setup above)
│   ├── ghg_filtered.csv        ← Generated in Week 1
│   ├── ghg_features.csv        ← Generated in Week 2
│   ├── model_comparison_regression.csv ← Generated in Week 3 (4-model table, extended in Week 4)
│   ├── feature_importance.csv  ← Generated in Week 3 §3.6 (RF pooled importances)
│   ├── ets_forecasts.csv       ← Generated in Week 4
│   ├── ets_parameters.csv      ← Generated in Week 4 (α, β*, φ per country)
│   ├── model_comparison.csv    ← Generated in Week 4 (final 5-model table)
│   └── scenario_projections.csv ← Generated in Week 5 (optional)
├── api/                        ← FastAPI backend (stretch) — same computations as app.py, as JSON
│   ├── main.py                  ← FastAPI() instance, CORS, router includes, /api/health
│   ├── constants.py              ← COUNTRIES, GAS_COLUMNS, SCENARIO_COLORS (mirrors app.py)
│   ├── data_loaders.py            ← @lru_cache CSV loaders (replaces @st.cache_data)
│   ├── climate_loaders.py         ← read-only loaders over data/climate (a missing/unavailable file is a 503 with the cause)
│   ├── schemas.py                 ← Pydantic response models
│   ├── schemas_correlation.py     ← response models for /api/correlation/*
│   └── routers/                   ← One router per dashboard page (+ correlation.py: the seven climate-context endpoints)
├── climate-dashboard-react/    ← React + TS dashboard (stretch) — consumes api/, Analytics Theme
│   └── src/
│       ├── api/                   ← Typed fetch client + response types (mirrors api/schemas.py)
│       └── pages/                 ← One page per route, 1:1 with app.py's pages
├── pipeline/                   ← Area 2 climate-context ingestion + analytics (post-internship), see pipeline/README.md
│   ├── run.py                   ← `python -m pipeline.run` entry point, stage order and dependencies
│   ├── noaa_gml.py, berkeley_earth.py, primap_hist.py, owid.py  ← one module per source
│   ├── harmonize.py, derive.py, pairing.py  ← the harmonized layer, indicator catalog, series pairing
│   ├── correlation.py, composition.py, country_share.py  ← regression, gas composition, cumulative shares
│   ├── ets_baseline.py, step_check.py, scenario_temperature.py  ← scenario baseline, first-year step check, temperature translation
│   ├── ops/                     ← the monthly refresh job (versioned copies of what runs on the Mac Mini)
│   └── tests/
├── data/climate/               ← Area 2 outputs (gitignored): harmonized tables, provenance.json, correlation_*.json|csv, last_run.json
├── services/
│   ├── mcp-server/              ← MCP server wrapping api/ as tools (post-internship; own CLAUDE.md/SPEC.md)
│   └── agent/                   ← LangGraph conversational agent over the MCP tools (post-internship; own CLAUDE.md/SPEC.md)
├── app.py                     ← Streamlit dashboard (Week 6 stretch goal)
├── requirements.txt           ← Python dependencies
├── SPEC.md                    ← Full project specification (weekly requirements)
├── ENHANCEMENTS.md            ← Release history and design decisions (incl. Release 21 / Area 2)
├── ARCHITECTURE.md            ← How the system is actually built (current state)
├── .gitignore
└── README.md
```

---

## Project Specification

Full weekly requirements, deliverables, checkpoints, and pre-read resources are in [`SPEC.md`](SPEC.md).

## Architecture

For how the system is actually built — the data pipeline, the `api`/`climate-dashboard-react`
internals, and the Mac Mini deploy topology — see [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## IDEAS TIH Summer Internship 2026 Weekly Commit Schedule

Commit that week's notebook to GitHub at the end of every week using a clear message:

```bash
git add notebook/week1_eda.ipynb
git commit -m "Week 1: data loading, profiling, and EDA complete"
git push
```

| Week | Commit | Commit message convention |
|------|--------|--------------------------|
| 1 | `notebook/week1_eda.ipynb` | `Week 1: data loading, profiling, and EDA complete` |
| 2 | `notebook/week2_features.ipynb` | `Week 2: feature engineering complete, ghg_features.csv added` |
| 3 | `notebook/week3_regression.ipynb` | `Week 3: regression models and comparison table complete` |
| 4 | `notebook/week4_ets_forecasting.ipynb` | `Week 4: ETS(A,Ad,N) Holt Damped forecasting complete` |
| 5 | `notebook/week5_scenarios.ipynb` | `Week 5: scenario analysis complete` *(if applicable)* |
| 6 | `app.py` (and any notebook cleanup) | `Week 6: notebook finalised, Streamlit app added` |

---

## Mentor

**Sauparna Sarkar** — IDEAS TIH Summer Internship 2026  
Contact your mentor via email to schedule weekly review sessions (2 hours/week).
