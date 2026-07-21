# GHG Emissions Trend Analysis and Forecasting

**IDEAS TIH Summer Internship 2026 | Mentor: Sauparna Sarkar**

---

## Project Overview

This project builds an end-to-end analytical pipeline on open Greenhouse Gas (GHG) emissions data. The team ingests the OWID CO₂ dataset, performs exploratory data analysis, engineers time-series features, trains regression and forecasting models, and (optionally) assembles an interactive Streamlit dashboard. The focus is on classical ML and time-series methods applied to structured annual emissions data for 10 countries across 1990–2023.

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

### 6. Run the Streamlit app (Week 6 stretch goal)
> **Prerequisite:** Complete Week 2 first so that `data/ghg_features.csv` exists.

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

---

## Data Sources

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
│   ├── schemas.py                 ← Pydantic response models
│   └── routers/                   ← One router per dashboard page
├── climate-dashboard-react/    ← React + TS dashboard (stretch) — consumes api/, Analytics Theme
│   └── src/
│       ├── api/                   ← Typed fetch client + response types (mirrors api/schemas.py)
│       └── pages/                 ← One page per route, 1:1 with app.py's pages
├── app.py                     ← Streamlit dashboard (Week 6 stretch goal)
├── requirements.txt           ← Python dependencies
├── SPEC.md                    ← Full project specification (weekly requirements)
├── .gitignore
└── README.md
```

---

## Project Specification

Full weekly requirements, deliverables, checkpoints, and pre-read resources are in [`SPEC.md`](SPEC.md).

---

## Weekly Commit Schedule

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
