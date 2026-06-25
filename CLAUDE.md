# CLAUDE.md — GHG Trend Analysis & Forecasting

## Project Context

**IDEAS TIH Summer Internship 2026** — Mentor: Sauparna Sarkar  
7-week project. Interns completed a 3-week online theory course before project work begins. Completion confirmed by mentor is required for intern certificates.

---

## What This Repo Is

The mentor's working repository for the GHG trend analysis and forecasting project. Contains:
- `notebook/ghg_analysis.ipynb` — main analysis notebook
- `app.py` — Streamlit dashboard (Week 6 stretch goal)
- `data/` — gitignored CSVs; interns download OWID dataset manually
- `requirements.txt` — pinned Python deps (pandas, scikit-learn, statsmodels, streamlit, etc.)

---

## Key Design Decisions

- **Forecasting model: ETS(A,Ad,N) — Holt's Damped Trend (statsmodels `ExponentialSmoothing`), NOT Prophet and NOT ARIMA.** Prophet is inappropriate for annual data. ARIMA was the original choice but was replaced: the damped trend in ETS(A,Ad,N) prevents unbounded long-range extrapolation and better captures emissions slowdowns in developed countries (UK, Germany). Implemented via `ExponentialSmoothing(train, trend='add', damped_trend=True, seasonal=None)`.
- **Random Forest training: pooled (v4), NOT per-country.** ~26 rows per country (1990–2018) is too small for reliable RF — results in overfitting and unstable feature importances. A single RF is trained on all 10 countries pooled (~260 rows) with `country_encoded` (via `LabelEncoder`) as an additional feature. Evaluation is still per country. Linear Regression remains per-country (26 rows is adequate). This distinction must be documented in a mandatory limitations cell in §3.5.
- **Train/test split:** 1990–2018 train, 2019–2023 test. This captures the COVID-19 emissions dip in 2020 in the test set.
- **10 focus countries (pre-specified):** China, USA, India, Russia, Japan, Germany, Brazil, UK, South Africa, Australia.
- **Scope:** Classical ML only (Linear Regression, Random Forest, ETS). No deep learning or LLMs — intentional to keep scope manageable for interns.
- **Week 5 (Scenario Analysis) is optional** — only attempt if Weeks 3–4 are complete.
- **Streamlit dashboard is a stretch goal**, not required for certificate.
- **Week 7 is final presentation only** — report template provided separately by course admin.

---

## Mentor Commitment

2 hrs/week review session with interns. Mentor confirms completion for certificates.

---

## Reference Documents

- **Project specification (v4, current):** [`SPEC.md`](SPEC.md) — full weekly breakdown, deliverables, and requirements
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
| 3 | Regression models (LR, RF) + comparison table | Yes |
| 4 | ETS(A,Ad,N) Holt Damped forecasting | Yes |
| 5 | Scenario analysis | Optional |
| 6 | Notebook finalised + Streamlit app | Stretch |
| 7 | Final presentation | Yes |

---

## When Helping With This Project

- Reference design decisions above before suggesting model or methodology changes.
- For detailed weekly requirements and deliverables, refer to [`SPEC.md`](SPEC.md).
- Analysis code lives in `notebook/ghg_analysis.ipynb`; `app.py` is the Streamlit dashboard.
- The `data/` CSVs are not committed — interns download OWID dataset per README instructions.
- Weekly commits follow the convention in README.md.
- Avoid suggesting Prophet, deep learning, or LLM-based approaches — out of scope by design.
