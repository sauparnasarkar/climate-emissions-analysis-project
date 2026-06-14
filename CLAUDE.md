# CLAUDE.md — GHG Trend Analysis & Forecasting (Intern Template)

## Project Context

**IDEAS TIH Summer Internship 2026** — Mentor: Sauparna Sarkar  
Internship coordinator: Bidisha Dobe (bidisha@ideas-tih.org)  
7 interns, 7-week project starting mid-June 2026. Interns completed a 3-week online theory course before project work begins. Completion confirmed by mentor is required for intern certificates.

**Interns:** Neeladrish Sahoo, Saicharan Yandrapu, Mallikarjun, Haindavi Paladugu, Maulik Pratap Singhal, Trina Khanra, Tumuluri Varshini.  
Mix of CS/AI/ML and Mathematics & Computing backgrounds.

---

## What This Repo Is

Template scaffold for interns to fork and fill in week by week. Contains:
- `notebook/ghg_analysis.ipynb` — main analysis notebook (skeleton, interns fill in)
- `app.py` — Streamlit dashboard (Week 6 stretch goal, already built)
- `data/` — gitignored CSVs; interns download OWID dataset manually
- `requirements.txt` — pinned Python deps (pandas, scikit-learn, statsmodels, streamlit, etc.)

---

## Key Design Decisions

- **Forecasting model: ETS(A,Ad,N) — Holt's Damped Trend (statsmodels `ExponentialSmoothing`), NOT Prophet and NOT ARIMA.** Prophet is inappropriate for annual data. ARIMA was the original choice but was replaced: the damped trend in ETS(A,Ad,N) prevents unbounded long-range extrapolation and better captures emissions slowdowns in developed countries (UK, Germany). Implemented via `ExponentialSmoothing(train, trend='add', damped_trend=True, seasonal=None)`.
- **Train/test split:** 1990–2018 train, 2019–2023 test. This captures the COVID-19 emissions dip in 2020 in the test set.
- **10 focus countries (pre-specified):** China, USA, India, Russia, Japan, Germany, Brazil, UK, South Africa, Australia.
- **Scope:** Classical ML only (Linear Regression, Random Forest, ETS). No deep learning or LLMs — intentional to keep scope manageable for interns.
- **Week 5 (Scenario Analysis) is optional** — only attempt if Weeks 3–4 are complete.
- **Streamlit dashboard is a stretch goal**, not required for certificate.
- **Week 7 is final presentation only** — report template provided separately by course admin.

---

## Mentor Commitment

2 hrs/week review session with interns. Sauparna confirms completion for certificates.

---

## Reference Documents

- Project brief v1: Google Doc ID `1fcVx1dBr3mNZkNVgX42iCfsmiYrVtdFw`
- Project brief v2 (current): Google Doc ID `1cBMazlkGQ2WvYnp4KGB_skEobZbZClOimW6-ACW3tlQ`

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
- Intern code goes in `notebook/ghg_analysis.ipynb`; `app.py` is the mentor-built dashboard.
- The `data/` CSVs are not committed — interns download OWID dataset per README instructions.
- Weekly commits follow the convention in README.md.
- Avoid suggesting Prophet, deep learning, or LLM-based approaches — out of scope by design.
