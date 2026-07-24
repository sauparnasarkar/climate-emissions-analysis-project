# GHG Emissions Trend Analysis and Forecasting — Project Specification

**IDEAS TIH Summer Internship 2026 · Mentor Reference Document · July 2026 · v10**

---

## 1. Project Overview

### Goal

Build an end-to-end analytical project that ingests open Greenhouse Gas (GHG) emissions datasets, performs exploratory data analysis, trains forecasting models to project future emissions, and assembles findings into a well-documented Jupyter Notebook and an optional interactive Streamlit dashboard.

> **Scope note:** This project deliberately focuses on classical machine learning and time-series methods — specifically regression models and Holt's Damped Trend (ETS) forecasting. These approaches are well-suited to structured tabular data and annual time-series with a limited number of data points.

### Core Deliverables

| Deliverable | Required? |
|-------------|-----------|
| Jupyter Notebook (fully documented with markdown cells) | Yes |
| Final Presentation to mentor (1 hour) | Yes |
| Streamlit interactive dashboard | Stretch goal only |

> This table is the complete list of internship deliverables. A separate FastAPI + React
> stack also exists in this repo, built by the mentor after the internship's own scope — see
> §5 for that addendum. It is not a deliverable for interns.

### Datasets

| Dataset | Source | Format |
|---------|--------|--------|
| OWID CO₂ and GHG Emissions | github.com/owid/co2-data | CSV |
| Climate Watch Historical Emissions | climatewatchdata.org | CSV |

### Countries of Focus

**China · USA · India · Russia · Japan · Germany · Brazil · United Kingdom · South Africa · Australia**

These represent a mix of major emitters, economies at different stages of development, and countries with documented emissions reduction trajectories (e.g. UK, Germany).

> These 10 remain the required internship curriculum baseline — nothing in §§1–2 changes.
> Separately, the mentor's own reference implementation (notebooks + `app.py` + the §5
> addendum) has since expanded per-country training/evaluation to a data-driven ~40-country
> set alongside these 10, computed in Week 1 §1.2 and persisted to
> `data/selected_countries.json`. See §5.6.

### Tools and Libraries

| Tool / Library | Purpose |
|----------------|---------|
| Python 3.x, Jupyter Notebook | Primary development environment |
| Pandas, NumPy | Data loading, cleaning, feature engineering |
| Matplotlib, Plotly Express | Visualisation (static and interactive) |
| Scikit-learn | Linear Regression, Random Forest (Week 3) |
| Statsmodels — ExponentialSmoothing | ETS(A,Ad,N) Holt Damped Trend forecasting (Week 4) |
| Streamlit | Interactive dashboard (Week 6 stretch goal only) |
| GitHub | Version control — commit at end of every week |

---

## 2. Weekly Breakdown

### Week 1: Data Acquisition, Exploration and Understanding

*Learning Objective: Understand the structure and content of GHG datasets and produce a clean, profiled dataset ready for analysis.*

**1.1 Data Loading**
- Download the OWID CO₂ dataset from GitHub (owid/co2-data) as a CSV file
- Load into a Pandas DataFrame and display the first 10 rows, column names, data types, and shape
- Write a markdown cell explaining what each key column represents: `co2`, `co2_per_capita`, `methane`, `nitrous_oxide`, `total_ghg`, `year`, `country`

**1.2 Data Profiling**
- Report the number of null values per column as a percentage of total rows
- Identify which countries and years have the most complete data coverage
- Filter dataset to retain only rows where `year ≥ 1990` and `country` is a sovereign nation (exclude aggregates like World, Asia, Europe)
- Document filtering decisions in a markdown cell with justification

**1.3 Exploratory Data Analysis (EDA)**
- Plot a line chart of global CO₂ emissions from 1990 to the latest year available
- Plot a multi-line chart comparing CO₂ emission trends for the top 5 emitting countries: China, USA, India, Russia, Japan
- Plot a stacked bar or area chart showing share of total global GHG by gas type (CO₂, CH₄, N₂O) per decade: 1990s, 2000s, 2010s, 2020s
- Write a 3–5 sentence summary of key patterns observed in each chart

**1.4 Notebook Standards (apply from Week 1 onward)**
- Every code cell must be preceded by a markdown cell explaining what the code does and why
- All charts must have titles, axis labels, and legends
- All variable names must be descriptive (no single-letter names except loop counters)
- Commit notebook to GitHub at end of every week

**Week 1 Checkpoint:** Loaded and profiled dataset demonstrated in notebook · Three completed EDA charts with written observations · GitHub repository set up with first commit

---

### Week 2: Feature Engineering

*Learning Objective: Transform raw emissions data into a structured, model-ready feature set that captures temporal patterns and relationships between variables.*

**2.1 Time-Based Features**
- Add a `decade` column derived from the `year` column (e.g. 1990 → 1990s)
- Add a `years_since_1990` column as a simple numeric time index for regression modelling
- For each country, compute a `co2_5yr_rolling_mean` column using a 5-year rolling average on annual CO₂ values

**2.2 Lag Features**
- For each country, create `co2_lag1` (previous year CO₂), `co2_lag2`, and `co2_lag3` columns
- Write a markdown cell explaining what lag features are and why they are useful for time-series prediction

**2.3 Per-Capita and Intensity Features**
- Verify `co2_per_capita` is correctly computed by cross-checking against `co2` and `population` for at least 3 countries and 3 years
- Create a `ghg_intensity` column defined as `total_ghg / gdp * 1e9` where both columns are available — `total_ghg` is in MtCO₂e (1 Mt = 1e9 kg), so this expresses intensity in **kg CO₂e per $ of GDP**, a standard, comparable unit (the unscaled ratio is ~1e-9 and rounds to 0.00 at any sane display precision)
- Note countries and years where `ghg_intensity` cannot be computed due to missing GDP data

**2.4 Growth Rate Features**
- Compute annual `co2_yoy_change` (year-on-year absolute change) and `co2_yoy_pct_change` for each country
- Identify and list the top 5 countries with the highest average annual CO₂ growth rate since 1990
- Identify and list the top 5 countries with the largest CO₂ reductions since 1990

**2.5 Final Feature Dataset**

Produce a clean modelling DataFrame for the 10 project countries. Required columns:

`country · year · co2 · co2_per_capita · co2_5yr_rolling_mean · co2_lag1 · co2_lag2 · co2_lag3 · co2_yoy_pct_change · ghg_intensity (kg CO₂e/$ GDP, where available)`

- Save as `ghg_features.csv` and commit to GitHub

**Week 2 Checkpoint:** Demonstrate the feature DataFrame with all engineered columns · Walk through the rolling mean and lag feature logic · Show the top 5 growth and top 5 reduction countries

---

### Week 3: Baseline ML Models — Regression

*Learning Objective: Train, evaluate, and compare supervised regression models to predict future CO₂ emissions; understand model evaluation metrics.*

**3.1 Problem Framing**
- Write a markdown cell clearly stating the prediction task: *Given features X for country C in year Y, predict CO₂ emissions for year Y+1*
- Identify the target variable (`co2`) and input features from the Week 2 feature set
- Note on training strategy: three models are trained this week using two approaches — Linear Regression is trained per country (~25 rows each, adequate for a 6-feature linear model); two Random Forest variants are trained: one per country (~25 rows, §3.5, intentionally included to demonstrate overfitting on small data) and one pooled across all 10 countries (~250 rows, §3.6, the production approach); all models are evaluated per country on the 2019–2023 test set for direct comparison
- Explain the choice of a supervised regression approach in a markdown cell

**3.2 Train-Test Split**
- For each of the 10 countries, use years **1990–2018** for training and **2019 onward** for testing
- The 2019–2023 test window is deliberately chosen to include the COVID-19 pandemic emissions dip (2020) and subsequent recovery
- Do NOT use random splitting — explain in a markdown cell why temporal splitting is essential for time-series data
- Report the number of training and test samples per country

**3.3 Naive Baseline Model**
- Implement a naive baseline: predict next year CO₂ = current year CO₂ (no-change model)
- Compute MAE and RMSE for the baseline on the test set for each country
- Plot actual vs predicted values for the baseline for 3 countries

**3.4 Linear Regression**
- Train a Linear Regression model using scikit-learn on the training set for each of the 10 countries
- Compute MAE and RMSE on the test set
- Plot regression line alongside actual test values for 3 countries
- Print model coefficients and write a markdown cell interpreting which features most influence predictions

**3.5 Random Forest Regressor — Per Country**

Train a separate `RandomForestRegressor(n_estimators=100, random_state=42)` for each of the 10 countries using only that country's ~25 training rows and `FEATURES` (no `country_encoded`). Evaluate per country on the 2019–2023 test set. Store results in `rf_pc_results` and `rf_pc_preds` dictionaries. Display the results table.

> **Pedagogical intent:** This section is intentionally included to demonstrate the consequences of training a 100-tree ensemble on insufficient data. Compare these results against §3.6 (pooled RF) in the §3.7 comparison table to make the case for pooling.

**3.6 Random Forest Regressor — Pooled**

> **v4 change:** RF production training strategy is pooled (all 10 countries, ~250 rows), not per-country. Rationale: ~25 rows per country is insufficient for reliable RF; pooling provides adequate training data. `country_encoded` added as RF feature. Mandatory limitations cell added before this section.

- **Pooled Training Approach:** With only ~25 rows per country (years 1990–2018 after dropna), training Random Forest per country risks severe overfitting and produces unreliable feature importance scores. Instead, train a **single** Random Forest Regressor (`n_estimators=100`, `random_state=42`) on a pooled dataset covering all 10 countries. Implementation notes:
  - Fit a `LabelEncoder` on the full `COUNTRIES` constant to create `country_encoded`; add this column to `train` and `test` using `.loc[:, 'country_encoded']` (CoW-safe). Do **not** refit the encoder on test data — refitting on a single-country slice always returns 0 and silently corrupts evaluation.
  - Do **not** extend the shared `FEATURES` constant — it is also used by the per-country Linear Regression, which has no `country_encoded` column. Instead define `RF_FEATURES = FEATURES + ['country_encoded']` and use it exclusively for the pooled RF.
  - **Extended training data (v7):** Load raw `owid-co2-data.csv` back to `year >= 1975` inline in §3.6 and compute features on the fly to build `_train_ext` (years 1979–2018, ~40 rows/country, ~400 rows total). Train on `_train_ext[RF_FEATURES]`. LR and ETS are unaffected — they continue to use `train` (from `ghg_features.csv`, year ≥ 1990) and `df_filtered` respectively. *Rationale: full-notebook experiment (`experiment/1980-start` branch) showed RF Pooled MAE improves for all 10 countries with extended data; LR and ETS worsen for most due to pre-1990 structural breaks (German reunification, Soviet collapse).*
- Evaluate the pooled RF model per country: for each country filter `test` to that country's rows (`test_c`), pass `test_c[RF_FEATURES]` to the fitted model (using the pre-computed `country_encoded` values from the same encoder), then compute MAE and RMSE against `test_c[TARGET]`; results are directly comparable to the per-country Linear Regression evaluation
- Plot feature importance from the pooled RF model as a horizontal bar chart (one chart for the single pooled model, not per country); write a markdown cell interpreting which features drive cross-country emissions predictions
- **Mandatory limitations cell:** Include a notebook cell immediately before the RF training code that explains (1) why ~25 rows per country is insufficient for per-country RF (overfitting, unstable bootstrap samples, unreliable feature importance), (2) what pooling achieves and its trade-offs (learns cross-country patterns but cannot capture purely country-specific dynamics), and (3) the key teaching point that model complexity must match data availability — simple models trained on small data often outperform complex models that lack sufficient training examples

**3.7 Model Comparison Table**

Produce a results table with columns:

`Country · Baseline MAE · LR MAE · RF-PC MAE · RF MAE · Baseline RMSE · LR RMSE · RF-PC RMSE · RF RMSE · Best Model`

*Note: LR = per-country Linear Regression; RF-PC = Random Forest trained per country (~25 rows); RF = single pooled Random Forest (~250 rows). Best Model is selected by lowest MAE across all four models (Baseline, LR, RF-PC, RF).*

- Write a 3–5 sentence conclusion interpreting the results; compare all four models; note that RF-PC vs RF directly illustrates the impact of training data size on ensemble methods

**3.8 Regression Model Forecasts to 2043**

Extend the trained **RF Pooled** model beyond the 2019–2023 test set using **recursive (iterative) forecasting**: predict one year at a time, feed each prediction back as the next step's lag feature, and repeat to 2043.

Implementation notes:
- Use the same `build_forecast_features(history, yr)` helper that assembles one `FEATURES` row from a running `history` dict `{year: co2}`
- At each step append the prediction to `history` before computing the next row
- Use `RF_FEATURES = FEATURES + ['country_encoded']` with the pre-fitted `LabelEncoder`
- Plot results in a 5×2 subplot grid (matching §4.3 layout): train actuals (blue), holdout actuals (orange), RF forecast (purple)

> **Why RF, not LR?** LR can predict negative CO₂ values for countries with declining trends (UK, Germany, Japan). Negative lag values feed back into subsequent predictions and cause rapid divergence. RF cannot extrapolate below its training range, so its recursive predictions stay bounded — making it far more stable at long horizons despite LR's superior 5-year holdout performance.

**Week 3 Checkpoint:** Demonstrate train-test split logic and explain why temporal splitting was used · Walk through the model comparison table and interpret at least one country result · Show the feature importance chart · Show the §3.8 recursive RF forecast plot and explain why LR is unsuitable for long-horizon recursive prediction

---

### Week 4: Time-Series Forecasting with ETS(A,Ad,N) — Holt's Damped Trend

*Learning Objective: Apply ETS(A,Ad,N) to generate multi-year emissions forecasts with confidence intervals; understand why a damped trend model is well-suited to long-range annual emissions data.*

> **v3 change:** ARIMA replaced by ETS(A,Ad,N). Rationale: the damping parameter prevents unbounded trend extrapolation over a 20-year horizon, which is more realistic for emissions data — particularly for countries with documented slowdowns (UK, Germany). The implementation is also simpler, requiring no stationarity testing or order selection.

**4.1 Concept Introduction**

Write a markdown cell explaining the ETS (Error, Trend, Seasonality) state space framework:

- **E (Error):** additive — the model's residuals are added to the state
- **T (Trend):** additive damped — the trend decays toward zero over the forecast horizon via a damping parameter φ (0 < φ < 1)
- **S (Seasonality):** none — annual data has no within-year seasonal cycle

Explain why ETS(A,Ad,N) is appropriate for annual emissions data:
- No within-year seasonality to model
- Damped trend prevents unbounded long-range projections
- Works reliably with ~30 data points — fewer free parameters than alternatives
- Physically sensible: emissions trajectories tend to slow, plateau, or gradually reverse

**4.2 Model Fitting**

For each of the 10 countries, fit on the 1990–2018 training series:

```python
from statsmodels.tsa.holtwinters import ExponentialSmoothing

model = ExponentialSmoothing(
    train_co2,
    trend='add',
    damped_trend=True,
    seasonal=None
)
fit = model.fit(optimized=True)
```

Print the fitted smoothing level (α), smoothing trend (β\*), and damping (φ) parameters for at least 3 countries. Write a markdown cell interpreting what a high vs low φ value implies for that country's emissions trajectory.

**4.3 Forecasting to 2043**
- Generate out-of-sample forecasts from **2024 to 2043** (20 years beyond the test period) for each of the 10 countries
- Include 95% confidence intervals using `fit.forecast()` or `fit.get_forecast()`
- Produce a forecast plot per country showing: historical actuals (1990–2018), fitted values, 2019–2023 holdout actuals overlaid, out-of-sample forecast to 2043 with CI shading
- Use distinct colours for actuals, fitted, holdout, and forecast

**4.4 Trend Interpretation**
- For at least 3 countries, write a markdown cell interpreting the forecast trend
- Discuss whether the damped projection aligns with known real-world context (e.g. UK carbon legislation, India's growth trajectory, China's peak-emissions target)
- Comment on whether the CI widens significantly over the 20-year horizon and what that implies

**4.5 Forecast Summary Table**

Produce a summary table with columns:

`Country · 2030 Forecast (MtCO₂) · 2035 Forecast · 2040 Forecast · 2020 Actual · % Change 2020 → 2040`

**4.6 Model Validation**
- Compute MAE and RMSE of ETS forecasts against the 2019–2023 holdout values for each country
- Add ETS MAE and ETS RMSE to the model comparison table from Week 3, creating a consolidated five-model table:

**Naive Baseline · Linear Regression · RF Per-Country · RF Pooled · ETS(A,Ad,N)**

- Write a 3–5 sentence conclusion comparing model performance across the five approaches

**Week 4 Checkpoint:** Show fitted α, β\*, φ parameters for 3 countries and interpret the damping values · Show forecast plots for at least 3 countries with holdout overlay · Walk through the forecast summary table · Present the consolidated five-model comparison table

---

### Week 5: Scenario Analysis *(Optional — Complete Only if Time Permits)*

*Proceed to Week 5 only if Weeks 3 and 4 are fully complete, documented, and committed to GitHub. If time is limited, skip directly to Week 6.*

*Learning Objective: Build a what-if scenario module to simulate the emissions impact of policy interventions; develop skills in parameterised analysis and result interpretation.*

**5.1 Scenario Design**

- **Scenario A – Business as Usual (BAU):** No policy change; use the ETS(A,Ad,N) baseline forecast from Week 4
- **Scenario B – Moderate Mitigation:** Apply a linear annual reduction rate of 2% per year to the BAU forecast starting from 2025
- **Scenario C – Aggressive Mitigation:** Apply a linear annual reduction rate of 5% per year to the BAU forecast starting from 2025

Write a markdown cell explaining the basis and limitations of each scenario; note these are illustrative, not scientifically calibrated.

**5.2 Scenario Calculation**
- For each of the 10 countries and each scenario, compute projected annual CO₂ values from 2025 to 2040
- Store results in a tidy DataFrame with columns: `country · year · scenario · co2_projected`
- Save as `scenario_projections.csv` and commit to GitHub

**5.3 Scenario Visualisations**
- For each of the 10 countries, produce a single line chart overlaying all 3 scenarios from 2020 to 2040 with historical actuals from 1990 to 2024 as a grey reference line
- Colours: blue for BAU, orange for Moderate, green for Aggressive
- Add a horizontal reference line indicating the country's 1990 emissions level as a policy benchmark
- Produce one global aggregate chart showing the sum of all 10 countries' projections under each scenario

**5.4 Impact Summary**
- For each country and scenario, compute total cumulative CO₂ emissions from 2025 to 2040
- Produce a grouped bar chart comparing cumulative emissions per country across the 3 scenarios
- Write a 3–5 sentence interpretation: which countries benefit most from aggressive mitigation?

**Week 5 Checkpoint:** Walk through the scenario DataFrame and explain the calculation logic · Show the per-country overlay charts and global aggregate chart · Present the cumulative emissions grouped bar chart with written interpretation

---

### Week 6: Notebook Finalisation and Optional Streamlit Dashboard

*Learning Objective: Finalise the notebook to professional documentation standards; optionally assemble analytical outputs into an interactive Streamlit dashboard.*

**6.1 Notebook Finalisation**
- Ensure every section from Weeks 1–4 (and Week 5 if completed) has a clear markdown introduction and written summary conclusion
- Add a Table of Contents cell at the top of the notebook with links to each section
- Ensure all charts have consistent colour schemes, font sizes, and labelling style throughout
- Remove all debugging print statements and dead code cells

**6.2 Streamlit App *(Stretch Goal)***

*Attempt only if Weeks 3–4 are complete and time remains. Notebook quality takes priority.*

Sections to include:
- **Overview:** title, project description, headline KPIs (total global CO₂ latest year, % change since 1990, number of countries analysed)
- **Historical Trends:** multi-line chart for user-selected countries; stacked area chart of GHG by gas type
- **Country Profile:** select a country to show emissions trend, per-capita trend, YoY change chart, key stats table
- **Forecasts:** select a country to show ETS(A,Ad,N) forecast chart to 2040 with CI and forecast summary table
- **Scenario Comparison** (if Week 5 complete): overlay chart of 3 scenarios and cumulative emissions bar chart
- **About:** data sources, methodology summary, internship attribution

> **Note:** `app.py` also has a further "Data Explorer" page beyond this list — a mentor
> addition, not a required §6.2 section (see §5.5).

**6.3 Interactivity Requirements (if building Streamlit app)**
- At minimum: one `st.selectbox` for country selection, one `st.multiselect` for gas type, one `st.radio` for scenario selection
- All charts must use Plotly Express (not static Matplotlib)
- App must run without errors with `streamlit run app.py` on a fresh environment

**6.4 GitHub Repository Requirements (by end of Week 6)**

| File / Folder | Contents |
|---------------|----------|
| `notebook/week1_eda.ipynb` … `notebook/week5_scenarios.ipynb` | Complete Jupyter Notebooks, one per week (v8: split from the original single combined notebook) |
| `notebook/constants.py` | Shared constants imported by every week notebook |
| `app.py` | Streamlit application (if built) |
| `data/` | Downloaded CSV datasets |
| `requirements.txt` | All Python dependencies with version numbers |
| `README.md` | Project description, setup instructions, data sources |

**Week 6 Checkpoint:** Walk through the finalised notebook — all sections, charts, and written summaries · Live demo of Streamlit app if completed · Review GitHub repository structure and README

---

### Week 7: Final Presentation

*Learning Objective: Deliver a structured presentation to the mentor demonstrating the full analytical workflow and consolidated findings.*

**Format**
- Duration: 1 hour
- Format: Slides with live notebook walkthrough

**Content to Cover**
- Project objective and dataset overview
- EDA key findings (Week 1)
- Feature engineering decisions (Week 2)
- Model comparison results — Naive Baseline · Linear Regression · RF Per-Country · RF Pooled · ETS(A,Ad,N) (Weeks 3–4)
- ETS forecast plots and summary table (Week 4)
- Scenario analysis findings (Week 5, if completed)
- Key takeaways and limitations

**Final Submission Checklist**
- [ ] Jupyter Notebook: fully documented, all cells run cleanly from top to bottom
- [ ] Streamlit app (if built): runs without errors, `requirements.txt` complete
- [ ] GitHub repository: all files committed, README complete, link shared with mentor before session
- [ ] Presentation slides: shared with mentor before the session
- [ ] Project report: submitted in IDEAS TIH template format (template provided by course administration)

---

## 3. Pre-Read Resource List

### Tier 1 — Must Read Before Starting

| Resource | Est. Time |
|----------|-----------|
| Kaggle: Intro to Machine Learning — kaggle.com/learn/intro-to-machine-learning | ~3 hrs |
| Dataquest: Pandas Time Series Tutorial — dataquest.io/blog/tutorial-time-series-analysis-with-pandas | ~1.5 hrs |
| Scikit-learn Beginner Tutorial — scikit-learn.org/stable/tutorial/basic/tutorial.html | ~1 hr |
| Statsmodels Exponential Smoothing docs — statsmodels.org/stable/tsa.html#exponential-smoothing | Reference (Week 4) |

### Tier 2 — Pick Up During Project as Needed

- Hyndman & Athanasopoulos, *Forecasting: Principles and Practice* Ch 7–8 (ETS models) — otexts.com/fpp3/ets.html
- Plotly Express documentation — plotly.com/python/plotly-express (Week 6)
- Streamlit Get Started tutorial — docs.streamlit.io/get-started (Week 6, if attempting Streamlit)
- W3Schools Python Machine Learning — w3schools.com/python/python_ml_getting_started.asp

### Domain Reference

- Our World in Data: CO₂ and GHG Emissions — ourworldindata.org/co2-and-greenhouse-gas-emissions
- Machine Learning for Climate Change — Rolnick et al. (2022), arXiv:1906.05433
- IPCC AR6 Summary for Policymakers — ipcc.ch/report/ar6/wg1

---

## 4. Version History

| Version | Date | Change |
|---------|------|--------|
| v1 | Jun 2026 | Initial scope document |
| v2 | Jun 2026 | Train/test split rationale added; Week 5 marked optional; Streamlit marked stretch goal |
| v3 | Jun 2026 | Week 4 forecasting model changed from ARIMA(1,1,1) to ETS(A,Ad,N) Holt Damped Trend. Rationale: damped trend prevents unbounded long-range extrapolation and better captures emissions slowdowns. Pre-read updated to FPP3 Ch 7–8 (ETS) in place of ARIMA tutorial. |
| v4 | Jun 2026 | Week 3 Random Forest training strategy changed from per-country to pooled (all 10 countries, ~250 rows). Rationale: ~25 rows per country is insufficient for reliable RF; pooling provides adequate training data. `country_encoded` added as RF feature. Mandatory limitations markdown cell added to §3.6. Model comparison table updated to note LR is per-country and RF is pooled. |
| v5 | Jun 2026 | Added §3.5 RF Per-Country as an intentional pedagogical comparison step. Renumbered previous §3.5 (RF Pooled) → §3.6, §3.6 (Comparison) → §3.7. Comparison table expanded to 4 models (Baseline, LR, RF-PC, RF Pooled); §4.6 extended to 5-model table when ETS is added. |
| v6 | Jul 2026 | Added §3.8 RF Pooled Recursive Forecasts to 2043. LR excluded from recursive forecasting due to numerical instability (negative lag feedback causes divergence on declining-trend countries). RF is naturally bounded by training range and stable at long horizons. |
| v7 | Jul 2026 | RF Pooled (§3.6) now trains on extended 1975+ dataset (~400 rows, 1979–2018) built inline from raw OWID data, up from ~250 rows (1994–2018). LR and ETS training windows unchanged. Validated via `experiment/1980-start` branch. |
| v8 | Jul 2026 | Notebook split from a single `notebook/ghg_analysis.ipynb` into one notebook per week (`week1_eda.ipynb` … `week5_scenarios.ipynb`), each runnable independently. Shared constants (`COUNTRIES`, `NON_SOVEREIGN`, `FEATURES`, `TARGET`, `TRAIN_CUTOFF`, `FORECAST_END`) extracted into `notebook/constants.py`. New intermediate artifacts `data/ghg_filtered.csv` (Week 1 output) and `data/model_comparison_regression.csv` (Week 3's 4-model table, extended with ETS in Week 4) persist hand-offs that were previously in-memory only. Original combined notebook kept as an inert backup at `notebook/archive/ghg_analysis_combined.ipynb`. |
| v9 | Jul 2026 | Added §5, documenting the mentor's `api/` (FastAPI) + `climate-dashboard-react/` (React) reference architecture. This is a **post-internship addendum, not a scope change** — §5 is explicitly *not* part of the internship curriculum (§§1–2 are unchanged); it exists here only so the mentor's own further work on this repo is specified somewhere, clearly separated from what interns are asked to build. |
| v10 | Jul 2026 | Added §5.5, documenting a new "Data Explorer" page (`app.py`, `api/`, `climate-dashboard-react/`) browsing the full ~220-country Week 1 output (`data/ghg_filtered.csv`) instead of the 10-focus-country dataset every other page uses — another mentor addition, not an internship requirement (§6.2 cross-references it). Required two `design-system` additions: a new `RangeSlider` component (dual-thumb year-range filter) and type-to-search added to the existing `MultiSelect` (on by default for all consumers, not just this page). |
| v11 | Jul 2026 | Added §5.6 (Release 2.1, `ENHANCEMENTS.md`), documenting the mentor's expansion of per-country training/evaluation to a data-driven ~40-country set (`get_expanded_countries()` / `load_expanded_countries()`, computed in Week 1 §1.2, persisted to `data/selected_countries.json`) alongside the original 10 (`FEATURED_COUNTRIES`, still the default/narrative selection) — not an internship requirement change (§1's "Countries of Focus" cross-references it). `design-system`'s `Select` gained the same type-to-search pattern §5.5 gave `MultiSelect`; `MultiSelect` gained a `maxSelected` cap. |

---

## 5. Post-Internship Addendum: FastAPI + React Reference Architecture *(Not Part of Internship Scope)*

> **This section is not an internship requirement.** Everything in §§1–4 above is the
> complete internship specification — the notebooks (Weeks 1–5) and, as the internship's
> *only* stretch goal, the Streamlit app (§2, Week 6 §6.2). Nothing in this section is
> assigned to interns, graded, or required for certification. It documents a separate body of
> work the mentor has since built on top of the internship's own output (the same `data/*.csv`
> files produced by Weeks 1–5), turning this project into a reference example of a
> production-shaped data engineering + front-end dashboard stack. It's specified here, in its
> own section, precisely so it doesn't get conflated with §§1–2's actual internship scope.

### 5.1 Rationale

The Streamlit app (§6.2) is the fastest path from a finished notebook to an interactive
dashboard — one file, no separate server. The FastAPI + React stack instead demonstrates a
real client/server split: an API layer with its own typed contract, and a UI built from a
proper shared component library rather than a fixed widget set. Both read the exact same
`data/*.csv` outputs of Weeks 1–5 and implement the same page-by-page computations; neither
depends on the other.

### 5.2 Python API Backend (`api/`)

| Aspect | Detail |
|---|---|
| Framework | FastAPI + Pydantic (response models = the API's actual contract), served via `uvicorn` |
| Structure | One router per dashboard page concept (`overview`, `historical`, `country_profile`, `forecasts`, `scenarios`), plus `main.py` (app instance, CORS, deploy-path middleware), `data_loaders.py` (`@lru_cache` CSV loaders), `schemas.py` (Pydantic models), `constants.py` (hand-mirrors `notebook/constants.py`) |
| Data source | Reads the same `data/*.csv` files Weeks 1–5 produce — no new data pipeline of its own |
| Missing-data behavior | A required CSV not yet generated → `HTTPException(503)` with a message naming which week produces it (mirrors `app.py`'s in-page warning) |
| Endpoints | `GET /api/health`; `/api/overview`; `/api/historical/timeseries`, `/decade-composition`; `/api/countries/{country}/profile`; `/api/forecasts/summary`, `/model-comparison`, `/ets-parameters`, `/feature-importance`, `/{country}`; `/api/scenarios/timeseries`, `/cumulative`; `/api/explorer/meta`, `/data`, `/summary`, `/download` (see §5.5) |
| Deployment | Served behind a Cloudflare Tunnel at `labs.syena.io/ghg-emissions-analysis/api/...`; `main.py`'s `StripDeployPrefixMiddleware` strips that deploy prefix so the same app also works unprefixed for local/Tailscale access |

### 5.3 React Front-End (`climate-dashboard-react/`)

| Aspect | Detail |
|---|---|
| Framework | Vite + React 19 + `react-router-dom` |
| UI components | The sibling `design-system` project (a separate checkout at `../design-system`, shared across other products, not built for this project) — `Header`, `SidebarNav`, `Footer`, `KpiStat`, `ChartCard`, `SyChart` (Plotly), `DataTable` (AG Grid), `MultiSelect` (type-to-search built in), `RangeSlider` (dual-thumb, added for §5.5), themed via its Analytics theme |
| Structure | One page per nav item (`OverviewPage`, `HistoricalTrendsPage`, `CountryProfilePage`, `ForecastsPage`, `ScenarioComparisonPage`, `DataExplorerPage` — see §5.5, `AboutPage`), each following the same `useAsync(() => api.xxx())` → loading/error/data pattern |
| Data source | `src/api/client.ts` — a typed `fetch` wrapper calling `api/` exclusively; never reads a CSV directly, never talks to `app.py` |
| Deployment | Same Cloudflare Tunnel deployment as `api/` (`labs.syena.io/ghg-emissions-analysis`); `vite.config.ts` handles the same deploy-prefix concern on the client side (build-time `base`, dev/preview proxy to `api/`), plus PWA/service-worker configuration |

### 5.4 Test Requirements (this addendum, not the internship)

Unlike the internship notebooks (verified by "Restart & Run All" + written markdown
observations, not automated tests) and unlike `app.py` (which currently has **no** automated
test suite at all — verified manually via `streamlit run app.py`), this addendum's two
components each carry their own automated suite:

| Component | Suite | Run with |
|---|---|---|
| `api/` | pytest — every endpoint's happy path, 4xx/503 error paths, pandas edge cases, against fixture CSVs (never the real gitignored data) | `pytest api/tests` |
| `climate-dashboard-react/` | Vitest + React Testing Library — API client contract tests, one loading/data/error smoke test per page (`api.client` always mocked, never a live backend) | `npm test` (from `climate-dashboard-react/`) |

See `docs/training/02-python-api-backend/` and `docs/training/04-react-frontend/` for the
full training curricula covering both.

### 5.5 Data Explorer Page

A further mentor addition (`app.py`, `api/`, and `climate-dashboard-react/` alike) beyond
§6.2's required Streamlit sections and beyond every other page in this addendum: it browses
the **full Week 1 output** (`data/ghg_filtered.csv` — all ~220 sovereign countries, year
≥ 1990, `NON_SOVEREIGN` aggregates already excluded), not the 10-focus-country dataset every
other page uses.

| Aspect | Detail |
|---|---|
| Filters | Country (multiselect, empty = all), year range (continuous slider/range, or a single year with both ends equal), columns (multiselect, defaults to a representative 7-column subset of the ~79 available) |
| `app.py` | Sidebar page after "Scenario Comparison": preview table, `.describe(include="all")` summary stats, CSV download — both the preview and summary respect the column selection |
| `api/` | `GET /api/explorer/meta` (available countries/columns/year range); `/data` (paginated, `page`/`page_size`); `/summary` (full-filtered-set `describe()`, reuses `ModelComparisonResponse`'s `{columns, rows}` shape); `/download` (CSV file, `StreamingResponse`) — all four `503` the same way as every other endpoint if `ghg_filtered.csv` is missing |
| `climate-dashboard-react/` | `DataExplorerPage`, paginated `DataTable`, CSV download link; the year-range filter uses `design-system`'s new `RangeSlider` (dual-thumb, APG multi-thumb slider pattern) — built for this page specifically, since no range-selecting control previously existed in `design-system` |
| Country/column pickers | Both use `design-system`'s `MultiSelect`, which now opens with a type-to-search box filtering the option list by label — added directly because of this page's ~220-entry country list, but on by default for every `MultiSelect` consumer |

### 5.6 Expanded Country Set (Release 2.1)

Another mentor addition, tracked in `ENHANCEMENTS.md` — not a curriculum change. §1's
"Countries of Focus" (the original 10) remains the internship's required baseline; this
section documents the mentor's own reference implementation additionally analyzing a
data-driven ~40-country set alongside it, across the notebooks, `app.py`, `api/`, and
`climate-dashboard-react/` alike.

| Aspect | Detail |
|---|---|
| Selection method | Week 1 §1.2: countries with a data-quality coverage score (min, not mean, across key columns) above a natural gap in the distribution, further floored to ≥100 Mt latest-year CO₂ (materiality) — ~40 countries, persisted to `data/selected_countries.json` |
| Two-tier naming | `FEATURED_COUNTRIES` (the original 10, hardcoded) stays the default/narrative selection everywhere (Overview KPIs, the fixed-size 5×2 subplot grids in §3.8/§4.3, seeded dropdown defaults). A `get_expanded_countries()` function — in `notebook/constants.py`, `app.py`, and as `load_expanded_countries()` in `api/data_loaders.py` — loads the ~40-country set for per-country training/evaluation loops, aggregate sums, tables, and every interactive picker's searchable pool |
| Missing-file behavior | The notebook version raises `FileNotFoundError` uncaught (Weeks 2–5 genuinely can't proceed without it); the `app.py`/`api/` versions degrade gracefully, falling back to `FEATURED_COUNTRIES` with a warning rather than crashing a live app |
| Multi-country pickers | React `MultiSelect` and Streamlit's `st.multiselect` both cap simultaneous selections at 10 (`maxSelected` / `max_selections`) even though their searchable pool is the full ~40 — past 10 countries on one chart stops being readable. Single-country pickers (`Select` / `st.selectbox`) have no such cap and search the full ~40 |
| `design-system` | `Select` gained the same type-to-search pattern §5.5 added to `MultiSelect`; `MultiSelect` gained the new `maxSelected` prop described above |
