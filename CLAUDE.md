# CLAUDE.md — GHG Emissions Trend Analysis & Forecasting

## Project Context

**IDEAS TIH Summer Internship 2026** — Mentor: Sauparna Sarkar  
7-week project. Interns completed a 3-week online theory course before project work begins. Completion confirmed by mentor is required for intern certificates.

---

## What This Repo Is

The mentor's working repository for the GHG trend analysis and forecasting project.

> **Scope note:** Only the notebooks (Weeks 1–5) and the Streamlit app (`app.py`, Week 6
> stretch goal) are part of the internship curriculum — see `SPEC.md` §§1–2 for what interns
> are actually asked to build. `api/` and `climate-dashboard-react/` are a **separate, later
> expansion built by the mentor**, turning this project into a reference example of a
> production-shaped data engineering + front-end dashboard stack — **not** an internship
> deliverable, not graded, not part of intern certification. See `SPEC.md` §5 for that
> addendum, documented separately from the internship spec for exactly this reason.

Contains:
- `notebook/week1_eda.ipynb` … `notebook/week5_scenarios.ipynb` — one notebook per week (split from the original single combined notebook, v8); each runs independently, loading CSVs saved by the previous week
- `notebook/constants.py` — shared constants (`FEATURED_COUNTRIES`, `NON_SOVEREIGN`, `FEATURES`, `TARGET`, `TRAIN_CUTOFF`, `FORECAST_END`, etc.) imported by every week's notebook via `from constants import *` — single source of truth, do not redefine these inline in a notebook
- `notebook/archive/ghg_analysis_combined.ipynb` — the original all-in-one notebook, kept only as an inert backup; not maintained, not referenced by docs
- `app.py` — Streamlit dashboard (Week 6 stretch goal — the internship's only stretch goal)
- `api/` — FastAPI backend (mentor's post-internship reference-architecture expansion, not internship scope — see the scope note above), exposing the same page computations as JSON for `climate-dashboard-react/`; mirrors `app.py`'s pandas logic 1:1 endpoint-by-endpoint, `@lru_cache` in place of `@st.cache_data`. Has a pytest suite (`api/tests/`, run via `pytest api/tests`) covering every endpoint's happy path, 4xx/503 error paths, and pandas edge cases, against fixture CSVs written to a temp dir rather than the real (gitignored) data
- `climate-dashboard-react/` — React + TypeScript dashboard (mentor's post-internship reference-architecture expansion, not internship scope) consuming `api/`, themed via the Analytics Theme of the `design-system` project (a separate, sibling checkout at `../design-system` relative to this repo — not part of this monorepo since it's shared across other projects too; `climate-dashboard-react/vite.config.ts` aliases straight to its `src/`). Has a Vitest + React Testing Library suite (`npm test`) — API client tests plus a loading/data/error smoke test per page; `SyChart` is stubbed in page tests since Plotly's DOM lifecycle is `design-system`'s own test suite's concern, not this app's
- `data/` — gitignored CSVs; interns download OWID dataset manually, all other CSVs (`ghg_filtered.csv`, `ghg_features.csv`, `model_comparison_regression.csv`, `ets_forecasts.csv`, `model_comparison.csv`, `scenario_projections.csv`) are regenerated locally by running the week notebooks in order
- `requirements.txt` — pinned Python deps (pandas, scikit-learn, statsmodels, streamlit, fastapi, uvicorn, etc.) — shared across the internship code and the post-internship `api/` expansion alike

---

## Key Design Decisions

- **Forecasting model: ETS(A,Ad,N) — Holt's Damped Trend (statsmodels `ExponentialSmoothing`), NOT Prophet and NOT ARIMA.** Prophet is inappropriate for annual data. ARIMA was the original choice but was replaced: the damped trend in ETS(A,Ad,N) prevents unbounded long-range extrapolation and better captures emissions slowdowns in developed countries (UK, Germany). Implemented via `ExponentialSmoothing(train, trend='add', damped_trend=True, seasonal=None)`.
- **Random Forest: two variants in Week 3 (v5) plus recursive forecast in §3.8 (v6).** §3.5 trains RF per country (~25 rows each, bare `FEATURES`) — intentionally included to demonstrate overfitting on small data; do NOT add `country_encoded` here. §3.6 trains a single pooled RF on all expanded countries combined with `country_encoded` (via `LabelEncoder`) as an additional feature — this is the production approach. The encoder must be **fitted on the full `get_expanded_countries()` list** (not `FEATURED_COUNTRIES`, since Release 2.1 — see the two-tier country pattern below) and the same fitted object reused to transform test rows — never refit on test data. `country_encoded` is **§3.6 RF-only**: do NOT add it to the shared `FEATURES` constant (used by LR and §3.5 RF-PC); use `RF_FEATURES = FEATURES + ['country_encoded']` exclusively for §3.6 and §3.8. Both RF variants are evaluated per country; all four models (Baseline, LR, RF-PC, RF Pooled) appear in the §3.7 comparison table. The mandatory limitations cell explaining why pooling is necessary sits immediately before the §3.6 code cell.
- **§3.6 RF Pooled extended training data (v7).** `rf_model` is now trained on `_train_ext` — built inline in §3.6 by loading raw `owid-co2-data.csv` back to `year >= 1975` and computing features on the fly. This gives ~1,600 training rows (1979–2018, ~40/country at Release 2.1's expanded scale) vs the original ~250 rows (1994–2018, ~24/country, 10 countries). LR uses `train` (from `ghg_features.csv`, year ≥ 1990) and ETS uses `df_filtered` — both unchanged. Do NOT change their data sources. Originally validated via `experiment/1980-start` branch at the 10-country scale: RF Pooled MAE improved for all 10 countries; LR and ETS worsened for most.
- **§3.8 RF Pooled Recursive Forecasts to 2043 (v6).** Uses the already-fitted `rf_model` and `le` from §3.6 to recursively forecast from 2019 to 2043 for all expanded countries. LR is excluded from §3.8: per-country LR models predict negative CO₂ for declining-trend countries (UK, Germany, Japan), which feed back as lag values and cause rapid numerical divergence. RF's bounded predictions (capped by training range) remain stable over the 25-step horizon. The plot itself stays a 5×2 grid over `FEATURED_COUNTRIES` only (matching §4.3) — see the two-tier country pattern below for why the grid doesn't scale with the underlying data.
- **Train/test split:** 1990–2018 train, 2019–2023 test. This captures the COVID-19 emissions dip in 2020 in the test set.
- **Two-tier country pattern (Release 2.1, `ENHANCEMENTS.md`):** `FEATURED_COUNTRIES` (10, hardcoded — China, USA, India, Russia, Japan, Germany, Brazil, UK, South Africa, Australia) is the original curated set, still used as the default/narrative selection everywhere (Overview KPIs, fixed-size 5×2 subplot grids, seeded dropdown defaults). A `get_expanded_countries()` function — defined independently in `notebook/constants.py` and `app.py`, and as `load_expanded_countries()` in `api/data_loaders.py` — loads a data-driven set of ~40 major emitters (coverage + materiality thresholds, computed in Week 1 §1.2, persisted to `data/selected_countries.json`), used everywhere else: per-country training/evaluation loops, aggregate sums, tables, and any interactive picker's searchable pool. The notebook version raises `FileNotFoundError` uncaught (Weeks 2–5 can't proceed without it); the `app.py`/`api` versions degrade gracefully, falling back to `FEATURED_COUNTRIES` with a warning instead of crashing. Multi-country pickers that feed a chart (React `MultiSelect`, Streamlit `st.multiselect`) cap simultaneous selections at 10 even though their searchable pool is the full expanded list — past 10 countries on one chart stops being readable.
- **Scope:** Classical ML only (Linear Regression, Random Forest, ETS). No deep learning or LLMs — intentional to keep scope manageable for interns.
- **Week 5 (Scenario Analysis) is optional** — only attempt if Weeks 3–4 are complete.
- **Streamlit dashboard is a stretch goal**, not required for certificate.
- **`api/` and `climate-dashboard-react/` are not internship scope at all** — unlike the Streamlit stretch goal, they're a separate expansion the mentor built afterward as a production-architecture reference. Don't treat them as intern deliverables, and don't imply interns are expected to build or extend them. See `SPEC.md` §5.
- **Week 7 is final presentation only** — report template provided separately by course admin.

---

## Mentor Commitment

2 hrs/week review session with interns. Mentor confirms completion for certificates.

---

## Reference Documents

- **Project specification (v11, current):** [`SPEC.md`](SPEC.md) — full weekly breakdown, deliverables, and requirements (§§1–2); §5 separately documents the mentor's post-internship `api/`/`climate-dashboard-react/` reference architecture, explicitly out of internship scope
- Project brief v1: Google Doc ID `1fcVx1dBr3mNZkNVgX42iCfsmiYrVtdFw`
- Project brief v2: Google Doc ID `1cBMazlkGQ2WvYnp4KGB_skEobZbZClOimW6-ACW3tlQ`
- Project brief v3: Google Doc ID `17wcMXnhYk_SKfPtiINOLD-Og-e5kUovoHQH25VA9_QE`
- Project brief v4 (source of SPEC.md): Google Doc ID `1qj3fZzH3QTDb_7w8NWdq9ofjnOG4NwUxWb5Na3TW1No`

---

## Weekly Schedule Summary

| Week | Topic | Required? |
|------|-------|-----------|
| 1 | Data loading, profiling, EDA | Yes |
| 2 | Feature engineering → `ghg_features.csv` | Yes |
| 3 | Regression models (LR, RF per-country, RF pooled) + 4-model comparison table + RF recursive forecast to 2043 | Yes |
| 4 | ETS(A,Ad,N) Holt Damped forecasting | Yes |
| 5 | Scenario analysis | Optional |
| 6 | Notebook finalised + Streamlit app | Stretch |
| 7 | Final presentation | Yes |

---

## When Helping With This Project

- Reference design decisions above before suggesting model or methodology changes.
- For detailed weekly requirements and deliverables, refer to [`SPEC.md`](SPEC.md).
- Analysis code lives in the per-week notebooks (`notebook/week1_eda.ipynb` … `notebook/week5_scenarios.ipynb`), with shared constants in `notebook/constants.py`; `app.py` is the Streamlit dashboard.
- The `data/` CSVs are not committed — interns download the OWID dataset per README instructions and regenerate the rest by running the week notebooks in order.
- Weekly commits follow the convention in README.md (this is the interns' own end-of-week submission convention).
- When Claude is the one implementing notebook work broken into sections (e.g. Week 1's §1.1/§1.2/§1.3), use a feature branch **per section**, not one branch for the whole week: branch → implement → commit → push → open PR → mentor reviews and approves → merge → move to the next section. This is separate from the interns' own weekly-commit convention above — it's specifically how the mentor wants to review Claude-authored notebook changes incrementally rather than as one large diff.
- Avoid suggesting Prophet, deep learning, or LLM-based approaches — out of scope by design.
