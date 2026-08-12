# GHG Emissions Trend Analysis and Forecasting — Project Specification

**IDEAS TIH Summer Internship 2026 · Mentor Reference Document · Aug 2026 · v48**

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
- Filter dataset to retain only rows where `year ≥ 1990` and `iso_code` is non-null (the
  operative sovereignty filter as of §6.1 — cross-checked at runtime against `NON_SOVEREIGN`,
  a hand-maintained list kept as an audit record, not the primary filter)
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
- Identify the target variable — `target_co2_next` (`co2` shifted forward one year per country, per §6.1) — and input features from the Week 2 feature set. The target is deliberately *not* same-year `co2`: one of the Week 2 features (`co2_yoy_pct_change`) is a same-row function of `co2` itself, so pairing it with a same-year target would leak the answer into a feature
- Note on training strategy: three models are trained this week using two approaches — Linear Regression is trained per country (~25 rows each, adequate for a 6-feature linear model); two Random Forest variants are trained: one per country (~25 rows, §3.5, intentionally included to demonstrate overfitting on small data) and one pooled across all 10 countries (~250 rows, §3.6, the production approach); all models are evaluated per country on the 2019–2023 test set for direct comparison
- Explain the choice of a supervised regression approach in a markdown cell

**3.2 Train-Test Split**
- For each of the 10 countries, use years **1990–2018** for training and **2019 onward** for testing
- The 2019–2023 test window is deliberately chosen to include the COVID-19 pandemic emissions dip (2020) and subsequent recovery
- Do NOT use random splitting — explain in a markdown cell why temporal splitting is essential for time-series data
- Report the number of training and test samples per country

**3.3 Naive Baseline Model**
- Implement a naive baseline: predict next year CO₂ = current year CO₂ (no-change model,
  i.e. predict `target_co2_next` using the row's own `co2`)
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
| v12 | Jul 2026 | Added §5.7 (Release 2.2, `ENHANCEMENTS.md`), restructuring the Overview page into three simultaneous tiers (All Countries / Expanded / Selected) in place of §5.6's `scope=featured\|expanded` toggle. Mirrors `NON_SOVEREIGN` from `notebook/constants.py` into `api/constants.py`/`app.py` for the new unfiltered "All Countries" tier. Not an internship requirement change. |
| v13 | Jul 2026 | Added §5.8 (Release 3, `ENHANCEMENTS.md`), consolidating a full UX review into bug fixes (Forecast Summary scope, GHG Composition following selection, Data Explorer "Invalid Number", CI band opacity), a standardized green/crimson decrease/increase color convention, a Scenario Comparison redesign (treemap + three-panel comparison), a world map choropleth on Overview, and a sidebar Exploration/Projection regrouping. React-only (`climate-dashboard-react` + `api/`) — Streamlit untouched. Required four `design-system` prerequisite PRs (`KpiStat`, `MultiSelect`, `SidebarNav`, `SyChart`), all merged. Shipped; world map needs a production CSP update (`connect-src` allowing `cdn.plot.ly`) outside either repo. Not an internship requirement change. |
| v14 | Jul 2026 | Added §5.9 (Release 3.1, `ENHANCEMENTS.md`), a follow-up review found after Release 3 shipped and was checked live: Overview's map+tier-table layout redone as a 2/3 map + 1/3 KPI summary row (map-as-hero); two real world-map bugs fixed (hover showed the log10-transformed value, not real MtCO₂; colorbar was taller than the map, worse on mobile); Scenario Comparison's treemap redesigned from a fixed BAU-vs-Aggressive-only, green-only color scale to a BAU/Moderate/Aggressive-selectable green/red indicator; the "projection" chart palette's contrast fixed; the original grouped bar chart (superseded by the treemap/3-panel views) dropped, its `DataTable` kept standalone. React-only. Required one `design-system` PR (`SyChart` choropleth hover/colorbar fix). Not an internship requirement change. |
| v15 | Jul 2026 | Documented Release 3.1's post-ship follow-up (`ENHANCEMENTS.md` §3.1.8): two more rounds of KPI-panel/typography polish (icon repositioned + recolored, several font-size bumps); two real chart bugs found and fixed in `SyChart.tsx` — a mobile-only legend rendering as a bare scrollbar over the plot (fixed height allocation didn't grow with wrapped rows), and a diverging colorscale silently auto-ranging away from a true zero midpoint on skewed data (the actual root cause of the treemap showing backwards red/green, confirmed against real API data before fixing); and a treemap hover enhancement showing both the tile-size and tile-color metrics instead of just size. Required three more `design-system` PRs. Not an internship requirement change. |
| v16 | Jul 2026 | Added §6 (`ENHANCEMENTS.md` Release 4), a **curriculum correction**, not a post-internship addition: Week 3's regression `TARGET` was same-year `co2` while `FEATURES` included a same-row function of it (`co2_yoy_pct_change`) — genuine target leakage, found by comparing against a separate intern's independent implementation and confirmed algebraically. Fixed by reframing to a next-year target (`target_co2_next`), which also required restructuring §3.8's recursive forecaster (it was already forced to approximate around the same leak) and fixing an incidental rolling-mean off-by-one uncovered along the way. Separately, Week 1's `NON_SOVEREIGN` sovereignty filter was missing two null-`iso_code` entities (`Kosovo`, bare `Ryukyu Islands`) — switched to `iso_code.notna()` as the operative filter (220→218 sovereign countries), with the same fix applied to `api/data_loaders.py` and `app.py`'s independently-hand-mirrored copies of the same filter. §3.1's curriculum text already said "year Y+1" before this fix — the implementation is what changed to match it, not the spec. |
| v17 | Jul 2026 | Added §5.10 (`ENHANCEMENTS.md` Release 5): two genuine interaction "traps" (treemap tap-to-drill with no way back; world map pinch/scroll-zoom with no reset), iPad layout (tiny map, dead space, from a stretched grid row + width-only resize logic + a breakpoint that trips at neither reported iPad orientation), three PWA gaps (iOS install not launching standalone, no safe-area handling, stale "10 major countries" copy), and eight accessibility findings (reduced-motion ignored, animated numbers exposed to screen readers, silent route changes, undersized touch targets, color-only good/bad delta, low card-border contrast, sidebar nav items missing real hrefs, no skip link, skipped/back-jumping heading order). Every finding independently re-verified against current source before planning; four corrections made along the way (`SidebarNav`'s href fix needs no `design-system` change; one treemap caller not two; 1400px breakpoint not the originally-suggested 1200px, which wouldn't have fixed iPad landscape; `height={420}` dead code confirmed real in production). Not an internship requirement change. |
| v18 | Jul 2026 | Added §5.11 (`ENHANCEMENTS.md` Release 6): generalizes Release 5's hand-rolled scenario-treemap expand/restore control into a reusable `expandable` prop on `design-system`'s `ChartCard` itself, then applies it to every other non-full-width chart across the app (Scenario Comparison's 3 comparison panels, Country Profile's 2 grid charts, Overview's world map) instead of leaving the pattern duplicated per page. Live verification surfaced and fixed a real z-index bug (expanded overlay rendering behind the sidebar nav); Copilot's review of the `design-system` PR added modal accessibility semantics (dialog role, focus trap, Escape-to-close), reviewed and verified before shipping. Not an internship requirement change. |
| v19 | Jul 2026 | §5.11 follow-up (`ENHANCEMENTS.md` Release 6 §6.5, `design-system` #22): two real bugs found on the user's own iPhone shortly after Release 6 shipped — in landscape, an expanded chart didn't reliably cover the full viewport and couldn't be scrolled to reveal the rest, and the treemap's own tapped-tile detail box bled through a different chart's expanded overlay. Root cause was the overlay's viewport-offset-based sizing and unlocked background scroll on iOS Safari; fixed with `inset: 0` sizing plus a proper `position: fixed`-based scroll lock (bare `overflow: hidden` doesn't hold against iOS Safari's touch scrolling). Confirmed fixed on the reporting device after deploy. Not an internship requirement change. |
| v20 | Jul 2026 | Added §5.12 (`ENHANCEMENTS.md` Release 7, **Planned**): chart palette lacks luminance contrast (mean 3.83:1 vs. an FT reference chart's independently-measured 7.40:1) plus stroke/marker/gridline defaults tuned for a light-background origin, found by comparing against a Financial Times reference chart. Every claim independently re-verified against current `design-system` source before planning. Two of the nine replacement palette tokens were reshaped after review found they collided in hue with this dashboard's own sentiment-positive/negative tokens — the exact "reads as good/bad news" risk the original proposal's own constraint was meant to prevent, but hadn't actually been checked against real token values. Not an internship requirement change. |
| v21 | Jul 2026 | §5.12 (Release 7) shipped: `design-system` #23 (palette + `SyChart`/`ChartCard` defaults) and `climate-emissions-analysis-project` #107 (retiring the now-redundant projection-palette override). Copilot caught a real bug in #23 — `xaxis.showgrid: false` hardcoded regardless of orientation, which would have broken Forecasts' `orientation="h"` feature-importance chart's value-axis gridlines — fixed and re-reviewed clean. Deploy itself surfaced a real process bug, unrelated to the code: the Mac Mini rebuild needs `DEPLOY_BASE_PATH` set at build time, not just serve time, or the built assets 404 under the wrong path. Verified live across all seven pages by reading actual Plotly/DOM state, not just visually; the override's redundancy was confirmed with a live A/B rather than assumed. Not an internship requirement change. |
| v22 | Jul 2026 | Added §5.13 (`ENHANCEMENTS.md` Release 8, **Parked**): a climate-specific `data-theme="climate-analytics"` variant (Zeff-derived earth-green surfaces, seafoam accent, muted ramp), built and previewed locally on feature branches in both repos per explicit instruction — no PR, no merge, no deploy. Three surface-lightness variants tried live (dark forest-green, light pastel, medium sage); a reproducible AG Grid blank-render issue surfaced on the medium variant, not root-caused before the whole direction was abandoned in favor of keeping the existing navy `analytics` theme. Both branches left parked at the original dark-green variant's contents. Not an internship requirement change. |
| v23 | Jul 2026 | Added §5.14 (Release 9, **Shipped**) and §5.15 (Release 10, **Shipped**), documentation catch-up for two already-deployed fixes: the BAU-only static legend on Scenario Comparison's three panels (`showLegend={i === 0}`, misaligning all three axes), and the unified-hover tooltip's position/security/transparency work — Plotly's own label box repositioned unpredictably near a chart's edges, replaced with a React tooltip pinned to the chart's middle; Copilot caught a real `innerHTML` injection risk, a `pointer-events`/scroll contradiction, and a stale file-path comment, all fixed; the tooltip's opacity was tuned twice (0.85, then 0.65) after live verification showed 0.85 still read as opaque. Added §5.16 (Release 11, **Planned**): embeds the internship review deck in the About page via Microsoft's web viewer, preserving its native PowerPoint animations — blocked on a production CSP change (`frame-src` for `view.officeapps.live.com`) that lives outside either repo. Not an internship requirement change. |
| v24 | Jul 2026 | §5.16 (Release 11) revised and shipped: PR #110 (initial iframe embed) merged and deployed, then Copilot caught three real issues before merge (missing `rel="noopener"` on two `target="_blank"` links, a test hardcoding a URL the component built dynamically, an inaccurate code comment) — fixed. Post-merge, revised the design from an inline iframe to two `target="_blank"` links ("Open the presentation" via Microsoft's viewer, "Download the .pptx" direct) in PR #111 — a new-tab link needs no `frame-src` CSP allowance at all, since it's a top-level navigation rather than a same-page embed, making the CSP dependency moot (the CSP change was applied in the interim but had a syntax bug — a quoted hostname, `frame-src 'view.officeapps.live.com'`, which CSP treats as invalid since quotes are reserved for keywords — flagged and fixed). Verified live: both links resolve correctly and "Open the presentation" renders the actual deck in Microsoft's viewer. Not an internship requirement change. |
| v25 | Aug 2026 | Added §5.17 (Release 12, **Shipped**): the Overview world map animates through 1990–2024, synced with the KPI/tier numbers. Three PRs — `design-system` #28 (`SyChart` `colorRange`/`animationFrame`/no-data trace, `Slider` keyboard nav, `useReducedMotion`), `climate-emissions-analysis-project` #117 (`/overview/world-map-series`, `co2_by_year`), #118 (Overview page wiring) — each reviewed via the `copilot-review-loop` skill; #28's review caught two real issues (a `colorRange` zmin/null footgun, a no-data trace only provisioned when the *initial* frame had nulls), both fixed and re-verified live before a clean re-review; #117/#118 came back clean. Two corrections to the original draft found by checking the real data before implementing: 9 no-data countries, not 6 (three microstates report zero data for the *entire* range, not an early-1990s gap); Antarctica's literal `0.0` CO₂ required excluding exact zero from `value_range`'s floor (log10(0) is undefined). Verified live pre- and post-deploy: zoom held across a full animation run, `world-map-series` fetched exactly once regardless of selection changes, no-data countries render correctly. Not an internship requirement change. |
| v26 | Aug 2026 | §5.17 follow-up (`climate-emissions-analysis-project` #119, **Shipped**): autoplay now steps by decade (1990, 2000, 2010, 2020, 2024) instead of year by year, prompted by feedback that year-over-year change was too gradual to notice live — manual scrubbing is unaffected, still any year in range. Fixed a genuine one-tick lag surfaced while implementing this (Play/Pause only updated one dwell period after the animation actually finished, invisible at 35 fast ticks but obvious at 5 slower ones). Copilot review clean. Verified live pre- and post-deploy. Not an internship requirement change. |
| v27 | Aug 2026 | §5.17 second follow-up (`climate-emissions-analysis-project` #120, **Shipped**, same day as v26): split the KPI count-up duration (1200ms) from the autoplay dwell interval (4200ms) — previously the same 1800ms constant, so the count-up was still easing when the next decade jump fired. The ~3s gap between them is now genuine settled, readable time per stop. No Copilot review requested for this one, per explicit instruction. Verified live across multiple real decade stops. Not an internship requirement change. |
| v28 | Aug 2026 | §5.17 third follow-up (same day): `ANIMATION_STOP_MS` tuned down from 4200ms to 2400ms after live feedback that the resulting ~3s settled hold read as too long a pause — `KPI_COUNT_UP_MS` unchanged at 1200ms, leaving a ~1.2s settled window per stop. Committed and pushed directly to `main` per explicit instruction (no feature branch/PR/review for this one). Verified live. Not an internship requirement change. |
| v29 | Aug 2026 | §5.17 fourth follow-up (same day): autoplay now steps every 5 years (`STEP_YEARS = 5` in `useYearAnimation`, renamed `computeDecadeStops` → `computeAutoplayStops`) instead of every 10; the KPI tier numbers (Countries/CO₂/% Change) no longer count up at all — they snap directly to the new value each tick, since a 1200ms-interval animation was either lagging behind the map or still easing when the next tick fired. `KPI_COUNT_UP_MS` removed; `ANIMATION_STOP_MS` set to 1200ms. `CountUpText` itself is untouched and still used for the two KpiStat cards (Fastest Growth/Largest Reduction), which count up once on load and aren't tied to the year animation. Committed and pushed directly to `main` per explicit instruction. Verified live. Not an internship requirement change. |
| v30 | Aug 2026 | §5.17 fifth follow-up: `MAGNITUDE_SCALE` widened from a 3-stop cream/orange/deep-red interpolation to ColorBrewer's YlOrRd 9-stop sequential palette (pale yellow → orange → deep maroon), after live feedback that the 1990-vs-2024 difference wasn't visually clear enough — `colorRange` itself stays the true global min/max (SPEC.md §5.17.2, unchanged, must not be narrowed/widened or the per-frame color re-normalization problem it exists to prevent would return); only the color resolution across that fixed range increased. Verified live pre- and post-deploy comparing 1991 directly against 2020/2024. Not an internship requirement change. |
| v31 | Aug 2026 | §5.17 sixth follow-up: `design-system` Slider gained `showRangeLabels` (min/max at the track's ends) and `showThumbValue` (a floating label tracking the thumb live) — `design-system` PR #29, `climate-emissions-analysis-project` PR #121 wiring them into the Overview year slider, both reviewed via `copilot-review-loop` (both clean, no findings) and merged. A same-turn follow-up removed the slider's old static "Year ... 2024" value label (`showValue={false}`), now redundant once the moving label shows the same number in context. Verified live pre- and post-deploy: no clipping at either range extreme, no layout clash with the Play button, console clean. Not an internship requirement change. |
| v32 | Aug 2026 | Added §5.18 (Release 13, **Shipped**): a deterministic, data-derived headline sentence above a compressed tier table on Overview (`climate-emissions-analysis-project` PR #122), plus two independent `design-system` fixes (PR #30) — the Slider thumb raised from 16×16/20×20 to 24×24 to meet WCAG 2.2 §2.5.8, and `SyChart`'s no-data choropleth trace given an explicit "No data reported" hover in place of a silent `hoverinfo: 'skip'`. Both PRs reviewed via `copilot-review-loop`; #122 came back clean (one cosmetic wording observation confirmed as spec-intentional, not a bug); #30's first review attempt failed at the infrastructure level (runner never acquired) and was re-requested, second attempt clean. Verified live pre- and post-deploy: headline matches the hand-verified default-selection example, disappears at 0 selected countries, compressed table doesn't stretch the hero row past the map's height, slider thumb measures exactly 24×24, no-data hovertemplate confirmed via the live Plotly trace. Not an internship requirement change. |
| v33 | Aug 2026 | §5.18 follow-up (`climate-emissions-analysis-project` PR #123, **Shipped**): fixed two issues found in live review of Release 13 — the "Since 1990" eyebrow and the headline sentence itself both stated the timeframe (fixed by dropping the redundant inline "since 1990" from the sentence), and "Expanded (Coverage + ≥100 Mt)" truncated to "Expanded (Cover..." in the compressed table's Tier column (measured 204px needed vs. 133px available), losing the coverage/materiality qualifier that tier's definition rests on — fixed by replacing the shared 4-column table with a full-width tier-name heading per row above a compact 3-column metric strip. Copilot review clean. Verified live via direct DOM measurement (`scrollWidth`/`clientWidth` equality), not just visual inspection. Not an internship requirement change. |
| v34 | Aug 2026 | Added §5.18.5 (**Shipped**, `climate-emissions-analysis-project` PR #124): decoupled the headline sentence from `selected`/`top_movers` — it silently changed (and could look inconsistent) the moment a user changed the picker, since it sits above the fold, easy to miss re-reading. New `headline_movers` API field: a fixed top 10 sovereign countries by latest-year CO₂, computed from `df_all`/`df_map` (the same selection-invariant universe `world_map` already uses), never `df_selected`; `top_movers` untouched, still backing the below-the-fold Top Movers cards/chart. `buildHeadlineSentence` gained a required `scope` parameter ("Among {scope}, ...") kept out of the pure function for the same reason the "Since 1990" eyebrow already is. The `selected.length > 0` gate on the headline is removed entirely — it now stays visible even at 0 selected countries. Verified against real 2024 data before writing: the true top 10 emitters is not `FEATURED_COUNTRIES` — the United Kingdom drops out of the headline entirely, Germany becomes the steepest decliner, Russia enters in the UK's place. Copilot review clean. Verified live pre- and post-deploy: headline text confirmed byte-identical before/after deselecting every country (the core fix), stays visible at 0 selected, below-the-fold Top Movers section confirmed still reacting to the picker (United Kingdom still shown there), console clean. Not an internship requirement change. |
| v35 | Aug 2026 | Added §5.18.6 (**Shipped**, `climate-emissions-analysis-project` PR #125): highlighted the headline sentence — country names bolded, increase/decrease values colored via the app's existing `NEGATIVE_COLOR` (increase, bad)/`POSITIVE_COLOR` (decrease, good) convention, the same rule `TierSummaryPanel`'s % Change column already applies. `buildHeadlineSentence` now returns tagged `HeadlineSegment[]` (text/country/value, with a derived `sentiment` on values) instead of a plain string, so the renderer styles each part directly rather than parsing prose back apart — `sentiment` is a derived fact, kept separate from the actual color choice, the same wording/derivation split the "Since 1990" eyebrow and `scope` parameter already follow. A new `headlineSegmentsToText` helper flattens segments back to plain text, confirmed byte-identical to the prior string output in tests. Copilot review came back with a clean `success` check-run conclusion and no comments — confirmed genuine (not silence masking an infra failure, per the §5.18.5 PR #30 precedent) by checking the conclusion field directly, not just the absence of a comment. Verified live pre- and post-deploy: bold country names, red increase values, green decrease values, console clean. Not an internship requirement change. |
| v36 | Aug 2026 | Added §5.19 (Release 14, **Shipped**): per-page "Jump To" navigation on all six main pages, built on `design-system`'s existing but completely unused `JumpLinks` component rather than a new `Chip`-based nav — `design-system` PR #31 (`ChartCard.id` passthrough, `JumpLinks` smooth-scroll/focus/click-interception, `Accordion` controlled `openIds` for Forecasts' onBeforeJump-driven panel-opening), `climate-emissions-analysis-project` PR #126 (wiring all six pages, plus hash-on-load handling for bookmarked `#anchor` URLs). Not an internship requirement change. |
| v37 | Aug 2026 | Added §5.20 (Release 15, **Shipped**): a floating "Back to Top" button, page-agnostic unlike `JumpLinks` — `design-system` PR #32 (new `BackToTop` component, reusing `scrollToJumpTarget` rather than `window.scrollTo` directly after live testing found `window.scrollTo({behavior:'smooth'})` doesn't reliably animate in this app's browser contexts; two more real issues from Copilot's review, a keyboard-focus-drop bug and a test-only `matchMedia` leak, both fixed), `climate-emissions-analysis-project` PR #127 (one-line wiring into the shared app shell, reusing the existing `#main-content` focus landmark). Not an internship requirement change. |
| v38 | Aug 2026 | §5.20 first post-ship fix (`design-system` PR #33, **Shipped**): reported directly, clicking a `JumpLinks` link scrolled the page but the button never appeared. Root-caused precisely: `Element.scrollIntoView()` moved `scrollY` genuinely past the threshold but fired zero native `scroll` events on `window` in this app's browser contexts (confirmed via a counting listener), so `BackToTop`'s passive scroll listener never re-checked. Fixed in `scrollToJumpTarget` itself (shared by every `JumpLinks` click, not `BackToTop`-specific): dispatches a synthetic `scroll` event immediately and again on `scrollend`. Storybook's own test harness doesn't reproduce the missing-event behavior, confirmed and noted directly in the added test rather than presented as self-sufficient proof. Not an internship requirement change. |
| v39 | Aug 2026 | §5.20 second post-ship fix (`design-system` PR #34, **Shipped**): reported with a screen recording, jump targets near the bottom of a page undershot the top by up to `226px` — the browser silently clamping the scroll short wherever there wasn't enough page left below the target. Fixed with a temporary `aria-hidden` spacer giving just enough extra scrollable room. Copilot's review caught a real correctness gap (shortfall measured via `el.offsetTop`, wrong for any target inside a positioned ancestor) and a real regression in its own suggested fix (removing the spacer synchronously for the reduced-motion path raced the browser's layout update, caught by the same regression test the fix added). Not an internship requirement change. |
| v40 | Aug 2026 | §5.20 third post-ship fix (`design-system` PR #35, **Shipped**): the user's clarification of the first bug report turned out to describe a third, distinct bug — clicking "Emissions"/"Per Capita" on Country Profile scrolled the page slightly even though both were already fully visible, hiding the `JumpLinks` nav for no benefit. Fixed by skipping the scroll entirely when the target is already fully within the viewport (focus still moves either way). Took three attempts to get a genuinely discriminating regression test right, surfacing a previously-unknown limitation of this project's own Storybook test harness along the way: it doesn't unmount previous stories' DOM between `play`-function runs in the same file, silently corrupting absolute-position measurements in earlier tests too. Not an internship requirement change. |
| v41 | Aug 2026 | §5.20 fourth post-ship fix and an anchor-placement fix, found together (**Shipped**): the third fix's "skip if visible" logic was too broad, also suppressing the scroll for genuinely later sections (Country Profile's "YoY Change", Historical Trends' "GHG Share by Decade") whenever they merely happened to already be on screen. A first attempt (`design-system` PR #36) redefined "top section" geometrically and was itself confirmed wrong by this session's own live verification immediately after deploying it (a 1920x963 viewport still misclassified a genuinely later section); corrected in PR #37 to a structural definition (only `items[0]`, never inferred from viewport geometry). Separately, `climate-emissions-analysis-project` PR #128 fixed "By Country"/"Country Comparison" landing on a heading with the country picker they need scrolled out of view above it — moved the anchor `id` onto the picker itself. Not an internship requirement change. |
| v42 | Aug 2026 | §5.20 fifth post-ship fix (`design-system` PR #38, **Shipped**), found by accident while live-verifying the fourth: the shortfall spacer's own timed cleanup (`scrollend`/rAF removal, from PR #34) silently re-clamped `scrollY` back down the instant it fired, reproducing the exact undershoot bug it was supposed to prevent — a structural consequence of removing a spacer that's the only thing making a position reachable, not a timing race fixable with a different delay. Fixed by never auto-removing the spacer, reclaiming it lazily at the start of the next jump instead. Two Copilot follow-up commits during review, one reverted (a persistent `scroll`-listener cleanup approach that introduced a real regression in `BackToTop`, caught by running its own story suite in isolation) and one kept (an unrelated test-flakiness fix, independently verified). Not an internship requirement change. |
| v43 | Aug 2026 | §5.20 sixth post-ship refinement (`design-system` PR #39 + `climate-emissions-analysis-project` PR #129, **Shipped**): the fourth fix's `items[0]`-only rule was too strict once Country Profile needed a second top-section neighbor — "Per Capita", stacked directly under "Emissions" — but this couldn't be solved with better geometry again (already demonstrated wrong once this release). Added an explicit `JumpLinkItem.topSection` opt-in instead, which only widens eligibility for the existing visibility check rather than replacing it, so it still scrolls normally on a short/mobile viewport where the marked item is genuinely below the fold. Not an internship requirement change. |
| v44 | Aug 2026 | §5.20 seventh post-ship fix (`design-system` PR #40 + `climate-emissions-analysis-project` PR #130, **Shipped**): reported with screenshots, jumping to a page's last section could leave `BackToTop` stranded deep inside the large scrollable gap the fifth fix's permanent shortfall spacer can leave below the footer. Fixed with a new `BackToTop.avoidSelector` prop (wired to `footer`): once the matched element's top edge rises above the viewport's bottom edge, the button's `bottom` offset grows to stay docked just above it, scrolling out of view entirely once even that element has scrolled past. Copilot's review caught a real math error before merge (the initial `dockOffset` calculation double-counted the button's base margin, docking it 24px higher than intended), independently verified before merging. Not an internship requirement change. |
| v45 | Aug 2026 | §5.20 eighth post-ship fix (`design-system` PR #41, **Shipped**): the seventh fix treated a symptom without touching the gap itself — reported directly, with screenshots, jumping to a short page's last section still left a large blank area below the real content with the footer scrolled far out of view above it; the user asked directly whether scrolling could instead be controlled so the footer always stays at the bottom. Root-caused to the second post-ship fix's shortfall spacer, which exists specifically to defeat the browser's own scroll clamp. Fixed by removing the spacer mechanism entirely rather than resizing it — the browser's native clamp already produces the requested behavior once nothing artificially extends `scrollHeight` — accepting that a short page's last section may no longer land perfectly flush at the top. Also deleted a meaningful amount of complexity that existed only to manage the spacer's lifecycle. `BackToTop.avoidSelector` (v44) was kept — independently useful, not specific to the removed mechanism. Copilot's review was clean; independently re-verified before merging. Not an internship requirement change. |
| v46 | Aug 2026 | §5.20 ninth post-ship fix (`design-system` PR #42, **Shipped**): a direct consequence of the eighth fix, reported the moment it could be observed — on Historical Trends, "GHG Share by Decade" now correctly scrolled down, but `BackToTop` still never appeared. Root-caused: that page's entire natural scroll range (`~294px`) sits under `BackToTop`'s `400px` default threshold — the now-removed shortfall spacer used to inflate `scrollY` well past it as a side effect on every short page, masking that the pixel-only check could never fire there at all. Fixed by adding a second, independent trigger: the button now also shows once `scrollY` reaches the document's own natural maximum, regardless of pixel count. Writing the regression test surfaced a smaller lesson about the same test file: its first draft silently produced zero real overflow in this exact test environment and passed vacuously either way — fixed with more content plus a deliberately unreachable `threshold` to reliably isolate the new trigger. Copilot's review was clean; independently re-verified before merging. Not an internship requirement change. |
| v47 | Aug 2026 | §5.21 (`climate-emissions-analysis-project` PR #131, **Shipped**): cleared the 2 Medium dependency findings from a `/security-infra-audit` run the same day — backend transitive-dependency CVEs (`mistune`, `pillow`, `gitpython`, `jupyter-server`, `setuptools`) pinned past their fixed versions, `jupyterlab` floor raised to 4.5.10 (staying under `notebook`'s `<4.6` cap), `pytest` bumped 8.3.4 → 9.0.3; frontend `react-router-dom` and 5 transitive build-tool packages resolved via lockfile-only `npm audit fix`. Verified: `pip-audit`/`npm audit` clean, full `api/tests` (104/104) and `npm test` (90/90) pass, Week 1 notebook executes end-to-end. Not an internship requirement change. |
| v48 | Aug 2026 | §5.22 (`climate-emissions-analysis-project` PR #133, **Shipped**): prerequisite `api/` work for a planned MCP server sub-project — `load_raw_sovereign()` extended to carry methane/nitrous_oxide (was `co2`-only), a new `scope` (`featured`\|`expanded`\|`sovereign`) parameter added to **both** `/historical/timeseries` and `/historical/decade-composition` (widened from the original proposal, which only covered `timeseries`, after verification found `decade-composition` shared the identical gap), and a new `sovereign` field on `/countries`. Fully backward-compatible — the dashboard never sends `scope`, confirmed by inspection. Verified: 112/112 tests pass (8 new/changed, each confirmed to fail against pre-change code), live-smoke-tested against real data. Not an internship requirement change. |

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

### 5.7 Three-Tier Overview (Release 2.2)

**Status: shipped** — tracked in `ENHANCEMENTS.md`, not a curriculum change. Restructures the
Overview page (`app.py`, `api/`, `climate-dashboard-react/`) from a single 10-country KPI row
into three simultaneous tiers of increasing specificity, replacing the
`scope=featured|expanded` query param §5.6 introduced (no UI ever exposed it as a toggle).

| Aspect | Detail |
|---|---|
| Three tiers | **All Countries** — every sovereign country (`NON_SOVEREIGN` excluded), unfiltered by coverage/Mt, the true global total. **Expanded** — §5.6's coverage+materiality set (~40). **Selected** — a user-chosen subset capped at 10, defaulted to `FEATURED_COUNTRIES`; drives the bar chart, % change chart, and Top Movers section exclusively |
| `NON_SOVEREIGN` mirror | Existed only in `notebook/constants.py` before this release; mirrored to `api/constants.py` (and `app.py`) since a genuine unfiltered "all countries" view is new — no prior API code needed it |
| Data sources | Expanded/Selected tiers keep reading `ghg_features.csv` (`load_features()`, unchanged since §5.6); only the new All Countries tier reads raw OWID data directly via a new `load_raw_sovereign()` |
| `/overview` breaking change | `scope=featured\|expanded` removed; replaced by a repeated `countries` query param capped server-side at 10 (422 over cap, 404 on an unknown country) — the frontend's `maxSelected` is UX convenience, not the enforcement boundary |
| Empty selection | The Selected tier + charts + Top Movers gate behind at least one selected country (mirroring §5.6's Historical Trends picker), with a "Reset to default" action restoring `FEATURED_COUNTRIES` in one click; the All Countries/Expanded tiers render regardless, since they don't depend on the selection |
| Display | All three tiers render together in a single bordered table (Tier / Countries / CO₂ / % Change since 1990), not three separate KPI-card rows — condensed post-launch after the original nine-card layout proved too tall; `% Change` keeps color-coded up/down styling via a custom column renderer |

### 5.8 UX Review Fixes, World Map, Scenario Redesign, Visual Polish (Release 3)

**Status: shipped** — tracked in `ENHANCEMENTS.md`, React-only for this release (Streamlit/`app.py`
untouched), not a curriculum change. Consolidates a full UX review (code-level + live-screenshot
pass) into bug fixes, two new visualizations, and a polish pass. Note: the world map's CO₂ colors
require the production CSP's `connect-src` to allow `https://cdn.plot.ly` (Plotly's own topojson
host) — a deployment-config item outside either repo, not a code defect; see `ENHANCEMENTS.md`.

| Aspect | Detail |
|---|---|
| Bug fixes | Forecast Summary now always shows all 40 countries (was silently stuck at 10 — the frontend never passed the `scope` param the backend already supported); GHG Composition chart now follows Historical Trends' own country selection instead of always aggregating all 40; Data Explorer's Summary Statistics table no longer shows "Invalid Number" for numeric rows (AG Grid column-type inference fix); Overview's redundant duplicate country-list caption removed; the forecast chart's 95% CI band's fill opacity reduced so it no longer visually dominates by 2043 |
| Color semantics | Green = decrease/good, crimson = increase/bad, standardized everywhere — required a `design-system` fix (`KpiStat` gained a `good`/`bad` `deltaDirection`, since the existing `up`/`down` colored by numeric sign rather than outcome, which had Overview's Fastest Growth/Largest Reduction cards wired backwards) |
| Scenario Comparison redesign | The old ungated 40-country grouped bar chart replaced with a treemap (tile size = cumulative BAU 2025–2040, color = % reduction under Aggressive) plus a `MultiSelect`-driven three-panel comparison (one panel per scenario, all selected countries per panel, jointly-computed shared y-axis range) |
| World map | New choropleth at the top of Overview — the All Countries tier's first chart of its own — log-scaled sequential color axis, CO₂-only |
| `design-system` prerequisites | `KpiStat` (`good`/`bad`), `MultiSelect` (clear-all button visual separation from the last tag), `SidebarNav` (labeled group support), `SyChart` (choropleth + treemap trace kinds, explicit axis-range props, multi-point annotations) — each its own PR in that repo, merged before the app-side phase consuming it; no publish/version-bump step, since `climate-dashboard-react` aliases straight to `design-system/src` |
| Navigation | Sidebar regrouped into labeled "Exploration" (Overview, Historical Trends, Country Profile, Data Explorer) and "Projection" (Forecasts, Scenario Comparison) sections; About stays in the existing pinned-footer slot |
| Deferred | Total GHG (CO₂e) alongside CO₂ — `total_ghg` doesn't exist in `ghg_features.csv` (Week 2's output), only in raw OWID data and Week 1's filtered output; picking this up later needs either a Week 2 notebook change or an API-side re-derivation from raw data, not the naive same-dataframe approach the original draft assumed |

### 5.9 Post-Release-3 Layout, Map, and Contrast Fixes (Release 3.1)

**Status: shipped** — tracked in `ENHANCEMENTS.md`, React-only, not a curriculum change. A
follow-up review (code-level + a live pass against `labs.syena.io/ghg-emissions-analysis` at
desktop and mobile) found three problems left over from Release 3; verified fixed live in
production post-deploy. §3.1.8 documents a further round of post-ship follow-up (two more real
`SyChart` bugs plus continued KPI/typography polish) found from user feedback after this table's
own scope shipped.

| Aspect | Detail |
|---|---|
| Overview layout | The map and tier table, today two stacked full-width blocks, become one grid row — map ~66% width, a new `TierSummaryPanel` (three stacked mini cards, one per tier) ~33% width — so the selector/bar chart sit closer to the fold; collapses to one column on mobile |
| World map hover | Fixed a real bug, not just a units gap: the choropleth's hover showed the log10-transformed color value (from `zLog`), not the real MtCO₂ figure, since no `hovertemplate`/`customdata` was ever set — required a `design-system` fix |
| World map colorbar | Fixed the colorbar being visibly taller than the map itself (worse on mobile) — the aspect-fit `natural earth` projection can be letterboxed within its domain box while the colorbar, unconstrained, still spans it fully; moved the colorbar to a horizontal orientation below the map — same `design-system` PR as the hover fix |
| Scenario Comparison treemap | Redesigned from a fixed BAU-vs-Aggressive-only comparison rendered on a green-only scale (structurally unable to show red) to a BAU/Moderate/Aggressive-selectable radio coloring each tile green/red by whether the selected scenario's 2040 level is above or below the country's current level — required extending `GET /scenarios/cumulative` with a per-scenario 2040 value and a current-level baseline |
| Chart palette contrast | The "projection" category's chart palette (Release 3's 3.12.3) widened for better perceptual separation at up to 10 selected countries — CSS-only |
| Dropped | The original 40-country grouped bar chart on Scenario Comparison — superseded by the treemap/3-panel views, its only remaining unique value being the `DataTable` underneath, which stays standalone |
| `design-system` prerequisite | `SyChart`'s choropleth branch (hover + colorbar fix) — one PR, merged before the app-side phases |
| §3.1.8 follow-up: mobile legend bug | A chart legend that can't fit its entries in one row on a narrow viewport silently became an internally-scrollable, unstyled gray bar over the plot — Plotly reserves a fixed height share for the legend regardless of wrapped row count. Fixed by growing chart `height` to fit the estimated rows, reusing the choropleth's own resize pattern |
| §3.1.8 follow-up: treemap colors backwards | The real root cause behind the treemap's colors: Plotly auto-scales a diverging colorscale to the data's actual min/max, not to a fixed zero-centered range, so one outlier country skewed the whole scale and inverted the visible red/green split. Fixed by pinning the colorscale's midpoint to true zero (`marker.cmid: 0`) |
| §3.1.8 follow-up: treemap hover | Now shows both the tile-size metric (cumulative BAU) and the tile-color metric (the scenario delta) on hover, not just size |

### 5.10 Tablet/Mobile Interaction, PWA, and Accessibility Fixes (Release 5)

**Status: Shipped** — tracked in `ENHANCEMENTS.md` Release 5. React-only, not a curriculum
change. Sources: four interaction issues reported from real iPad/iPhone use, plus a full
accessibility/PWA/mobile audit performed against shipped source and then verified live against
`labs.syena.io/ghg-emissions-analysis` via DOM/Plotly-state inspection (an `axe-core` scan wasn't
possible — the production CSP blocks external scripts — so checks were written directly against
the DOM: target size, accessible names, heading order, landmarks, SPA-navigation behavior; not a
substitute for a full automated ruleset). Every finding was independently re-verified against
current source before this table was written — that pass confirmed the great majority exactly,
and corrected four things: `SidebarNav`'s missing real `href`s need no `design-system` change (the
component already supports `href` per item — the bug is the app's own item-mapping code); only one
treemap caller exists, not two; the suggested ~1200px breakpoint wouldn't actually fix iPad
landscape (1366px wide) — 1400px is what closes the gap for both reported orientations; and the
`height={420}` dead-code claim is confirmed real in production (`OverviewPage.tsx`), not just a
Storybook artifact.

Nine PRs shipped across four phases: `design-system` #17 (treemap-drill + map-zoom-reset), #18
(MultiSelect touch target + KpiStat non-color cue), #19 (SidebarNav click-handler fix, two rounds
of Copilot-caught regressions resolved before merge), #20 (Icon expand/collapse glyphs); app-side
#101 (onTileClick wiring), #102 (PWA meta tags + safe-area insets), #103 (Overview breakpoint),
#104 (App.tsx href/title/focus/skip-link + useCountUp reduced-motion + CountUpText ARIA + explicit
`headingLevel` on every `ChartCard` site), #105 (scenario expand/restore control). Each merge
deployed to the Mac Mini (`vitepreview` rebuild + restart only — no Release 5 change touches
`api`/`app.py`) and verified live against `labs.syena.io/ghg-emissions-analysis`: treemap tap shows
tapped-tile detail with no drill-zoom, world map "Reset view" returns to the default projection,
the Overview hero grid is single-column through 1366px, the scenario treemap's expand/restore
toggle renders correctly inside the safe-area-aware fixed overlay with the tapped-tile detail
still functional at both sizes.

| Aspect | Detail |
|---|---|
| Treemap drill with no way back | Tapping a tile triggers Plotly's default click-to-zoom; since `pathbar` isn't configured and every tile's `parents` is `''` (a flat, non-hierarchical treemap), there is no breadcrumb and no way back to the root view short of a re-render — confirmed live by dispatching a click and reading Plotly's own state. Fixed by cancelling the drill via a new `plotly_treemapclick` handler and exposing an `onTileClick` prop so the app can show tapped-tile detail instead |
| Map zoom with no reset | Pinch/scroll zoom on the choropleth is Plotly's enabled-by-default behavior (`scrollZoom` is never set), while `displayModeBar: false` removes the only built-in "Reset axes" affordance, for every chart kind. Fixed by adding a self-contained "Reset view" control to the choropleth branch only |
| iPad: tiny map, dead space below it | Three compounding causes, confirmed live: `OverviewPage`'s hero grid uses `alignItems: 'stretch'` (map card forced to match the taller tier panel — both measured at exactly 540px); the choropleth's resize logic sizes purely from container width, never height (measured: 231px of dead space inside the 540px card); and the only breakpoint (900px) doesn't trip at either reported iPad width (portrait 1024, landscape 1366). Fixed by raising the breakpoint to 1400px (not the originally-suggested 1200px, which would leave landscape iPad unfixed) and removing the now-fully-dead `height={420}` prop |
| iOS "Add to Home Screen" won't launch standalone | `index.html` has no `apple-mobile-web-app-capable`/`-status-bar-style`/`-title` meta tags — iOS Safari ignores the manifest's `display: standalone` and keys off these tags instead, so installing on the exact devices this release targets still opens a normal browser tab |
| No safe-area handling | No `viewport-fit=cover`, no `env(safe-area-inset-*)` padding anywhere — sequenced after the iOS standalone fix, since it only matters once the app actually launches standalone (a browser tab's own chrome already absorbs the notch/home-indicator area) |
| Stale "10 major countries" copy | Both `index.html`'s meta description and `vite.config.ts`'s PWA manifest description still cite the pre-Release-2.1 count; the real expanded set is ~40. Reworded to not hardcode a count at all — this is the second review to catch the same drift |
| Reduced-motion ignored | `useCountUp` always animates over 1500ms regardless of `prefers-reduced-motion`; the codebase already uses this exact media query elsewhere (`SidebarNav`, for a different purpose) |
| Animated numbers exposed to screen readers mid-flight | `CountUpText` renders the in-progress value as plain text with no ARIA handling |
| Silent, untitled route changes | Navigating between pages leaves `document.title` unchanged, moves no focus, and announces nothing — the only `aria-live` region on any page belongs to AG Grid's own internal container, not the app |
| Undersized touch targets | `MultiSelect`'s per-country tag remove button renders at 20×20 CSS px, under WCAG 2.2's 24×24 minimum — a `design-system` fix |
| good/bad delta is color-only | `KpiStat` renders no chevron for `'good'`/`'bad'` (a deliberate §5.8 tradeoff) — partially mitigated by the existing +/− sign, but borderline against WCAG 1.4.1 |
| Card border contrast | `--__s9cmpx-static-divider-weak` against the page background computes to 1.40:1 (confirmed independently), under WCAG 1.4.11's 3:1 — low priority, since tier cards also carry a background fill |
| Sidebar nav items lack real hrefs | All seven items render `href="#"` with JS-driven navigation — breaks open-in-new-tab, middle-click, and link-preview affordances. `SidebarNav` itself already supports a real `href` per item; the app's own item-mapping code just never passes one through — an app-only fix |
| No skip link | Confirmed absent (an earlier automated check's "skip link" was a false positive, matching the seven `href="#"` nav items instead) |
| Heading order skips and back-jumps | Confirmed live on Overview: `H1 → H5 → H5 → H2 → H5` — every `ChartCard` defaults to `h5` with no caller passing an explicit `headingLevel`, systemic across all 5 pages that use it |
| No expand/restore control on scenario charts | `ChartCard`'s existing `actions` slot needs no change; `design-system`'s `Icon` set has no expand/collapse glyph to build the control with |

**Sequencing:** four phases by severity — the two interaction "traps" (treemap drill, map zoom)
first, since both leave a user stuck with no way out; then the iOS/iPad fixes, since both
directly affect the reported devices; then the accessibility findings; then polish (the Icon
glyphs + expand/restore control, and the low-priority divider contrast). `design-system` PRs
land before the app-side PRs that consume them within each phase.

### 5.11 Generalized Chart Expand/Restore Control (Release 6)

**Status: Shipped** — tracked in `ENHANCEMENTS.md` Release 6. React-only, no `api`/`app.py`
change. Prompted directly by user feedback after using Release 5's scenario-treemap
expand/restore control live: the same need exists on every other chart that doesn't already fill
the page's full width, and Release 5 built that control by hand, once, inline in
`ScenarioComparisonPage.tsx` — not reusable as written.

| Aspect | Detail |
|---|---|
| Problem | Release 5 (§5.10) added an expand/restore toggle to exactly one chart (the scenario treemap), implemented as page-local `useState` plus a hand-written `position: fixed` safe-area-aware overlay. Extending the same affordance to another chart meant copy-pasting that ~40-line block again — the wrong direction once a second, real need for it exists |
| Fix: `expandable` on `ChartCard` | `design-system`'s `ChartCard` (`SyChart/ChartCard.tsx`) gains an `expandable?: boolean` prop. When set, `ChartCard` owns the toggle state itself, renders the expand/collapse button (reusing Release 5's `Icon` glyphs) in its existing header `actions` slot, and wraps its content in the same safe-area-aware fixed overlay Release 5 already validated live — all internal, no per-page duplication |
| `children` as a function of `isExpanded` | An expandable chart usually wants a taller `SyChart` while expanded, not just a bigger empty card. `ChartCard`'s `children` prop is widened to accept `React.ReactNode \| ((isExpanded: boolean) => React.ReactNode)`; callers that want a size-reactive chart pass a function, e.g. `{(isExpanded) => <SyChart height={isExpanded ? 640 : 300} .../>}`. Callers that don't pass `expandable` are unaffected — existing plain-node usage keeps working unchanged |
| Scenario Comparison: treemap refactor | `ScenarioComparisonPage.tsx`'s treemap `ChartCard` drops its own `treemapExpanded` state and inline overlay markup, switching to `expandable` + the children-function form — behavior is identical to what Release 5 shipped and already verified live, just no longer duplicated in app code |
| Scenario Comparison: 3 comparison panels | The BAU/Moderate/Aggressive line-chart panels (`ScenarioComparisonPage.tsx`, 3-column grid) gain `expandable`, sized 300px collapsed / 600px expanded — the actual feature the user asked for |
| Country Profile: 2 grid charts | The CO₂ Emissions and CO₂ per Capita charts (`CountryProfilePage.tsx`, 2-column grid) gain `expandable`, sized 280px collapsed / 560px expanded. The Year-on-Year chart below them is already full-width and is left unchanged |
| Overview: world map | The choropleth `ChartCard` (`OverviewPage.tsx`, 2fr/1fr hero grid) gains `expandable`. No explicit height prop is needed — the choropleth's existing `ResizeObserver` already recomputes height from container width alone (§5.10's `height={420}` dead-code fix), so widening the container on expand is sufficient. Coexists with the map's own internal "Reset view" control (Release 5, §5.1/5.2) — different button, different location, no conflict |
| Not touched | Historical Trends' two charts and the Forecasts page's ETS/feature-importance charts are already full-width (no multi-column grid wraps them) — nothing to change there |

**Sequencing:** one `design-system` PR (the `ChartCard` change) lands first; one app-side PR
bundles the treemap refactor and the five new `expandable` sites, since they're all the same
mechanical change applied at different call sites, not independent features.

**Shipped:** two PRs merged — `design-system` #21 (the `ChartCard` change) and
`climate-emissions-analysis-project` #106 (the treemap refactor + five new `expandable` sites).
Verifying the change live surfaced a real bug not caught in code review: the expanded overlay's
prior ad-hoc `z-index: 50` sat below the sidebar nav's own vendor-CSS z-index
(`--__s9cmpx-c-sidebar-z-index`, 310), so an expanded chart's left edge rendered *behind* the
always-visible desktop sidebar instead of over it — reproduced by clicking Expand and confirmed
via `document.elementFromPoint`, which returned a sidebar link at that pixel instead of the chart.
Fixed in the same PR with `var(--__s9cmpx-z-index-modal)`, the design system's own token tier for
a full-content-covering overlay. Copilot's review of PR #21 (a clean pass, no comments) also
pushed a direct commit adding proper modal semantics (`role="dialog"`, `aria-modal`,
`aria-labelledby`, focus trap via the existing shared `useFocusTrap` hook, Escape-to-close) —
reviewed and verified (typecheck, full test suite, and live Escape-key behavior) before being
treated as part of the shipped change. Copilot's review of PR #106 caught two real issues (a
brittle DOM-traversal test selector reaching into `design-system`'s internal class names;
missing test coverage for `CountryProfilePage`'s new expand/restore control) — both fixed,
verified, and re-reviewed clean before merge. Deployed to the Mac Mini and verified live against
`labs.syena.io/ghg-emissions-analysis`: the treemap, the 3 Country Comparison panels, both
Country Profile grid charts, and the Overview world map all expand/restore correctly, the sidebar
no longer bleeds through the expanded overlay, Escape closes it, and the map's own "Reset view"
control coexists with the new expand button without conflict.

**Follow-up fix (`design-system` #22):** found on a real iPhone shortly after shipping — in
landscape, an expanded chart didn't reliably cover the full visual viewport and couldn't be
scrolled to reveal the rest, and the treemap's own tapped-tile detail box (§5.1's intentional
touch-equivalent-of-hover feature) bled through the top edge of a different chart's expanded
overlay. Root cause: the overlay's `top/right/bottom/left: calc(16px + env(safe-area-inset-*))`
sizing depends on iOS Safari correctly recomputing four viewport-relative distances as its
toolbar shows/hides, and background scroll was never locked. Fixed with `inset: 0` (immune to
that recalculation) plus a `position: fixed`-based body scroll lock (bare `overflow: hidden` is a
known no-op against touch scrolling on iOS Safari). Confirmed fixed on the reporting user's own
iPhone in landscape after deploy.

### 5.12 Chart Legibility & Visual Impact (Release 7)

**Status: Shipped.** Mostly a `design-system` change (palette tokens + `SyChart` stroke/marker/grid
defaults); the app inherited it with one follow-up code change (§5.12.4). Prompted by the
dashboard's charts reading as dull next to a Financial Times line chart used as a reference.
Rather than treat that as a matter of taste, the reference was measured pixel-by-pixel (legend
swatch colors sampled at peak luminance, stroke width sampled across the plot area) and compared
against this project's actual token values — independently re-verified against current source
(not taken on faith) before this section was written.

Two PRs merged: `design-system` #23 (palette + `SyChart`/`ChartCard` rendering defaults) and
`climate-emissions-analysis-project` #107 (retiring the now-redundant projection-palette
override, §5.12.4). Copilot's review of #23 caught one real bug: `xaxis.showgrid: false` was
hardcoded regardless of chart orientation, which — confirmed against the actual call site,
`ForecastsPage.tsx`'s `orientation="h"` feature-importance chart — would have silently removed
the *value*-axis gridlines there while leaving the useless category-axis ones on. Fixed so
gridlines always follow the value axis regardless of orientation; re-reviewed clean before merge.
Copilot's review of #107 was a clean pass with no comments.

Deploying #23 surfaced a real deploy-process bug, unrelated to the code change itself: the Mac
Mini rebuild step needs `DEPLOY_BASE_PATH=/ghg-emissions-analysis/` set at *build* time (baked
into the bundle), not just at serve time (already set in the `vitepreview` LaunchAgent's own
environment) — a plain `npm run build` without it produced an index.html referencing assets at
the wrong path, 404ing every JS/CSS request and leaving a blank page. Caught via network-request
inspection, fixed by rebuilding with the env var set.

Verified live against `labs.syena.io/ghg-emissions-analysis` across all seven pages, reading
actual Plotly/DOM state rather than eyeballing: Historical Trends' multi-country chart confirmed
the reshaped orchid/magenta tokens, 2.75px strokes, no per-point markers on the 35-point series,
no vertical gridlines; Forecasts' feature-importance chart confirmed the gridline-orientation fix
(`yaxis.showgrid: false`, `xaxis.showgrid` unset so Plotly's default applies); `ChartCard`
confirmed rendering at the page background color via computed style. The projection-palette
override's redundancy (§5.12.4) was confirmed by a live A/B — disabling it in the running app and
comparing the Scenario Comparison panels side by side — rather than assumed from the token math
alone.

#### 5.12.1 Root cause: the palette is saturated but not *light*

| | mean relative luminance | luminance range | mean contrast vs. its background |
|---|---|---|---|
| FT reference | 0.491 | 0.167 → 0.848 | **7.40:1** |
| This dashboard | 0.253 | 0.193 → **0.291** | 3.83:1 |

The nine `--__s9cmpx-chart-categorical-default-0N` tokens are *highly* saturated (mean ~0.74,
higher than the reference's) but occupy a luminance band only **0.098 wide**; the reference spans
0.681. On a dark ground, perceived prominence tracks **luminance contrast**, not saturation — so a
saturated mid-tone palette authored for light backgrounds collapses to a uniform perceptual
mid-grey when reused on dark navy.

Two consequences, one already a filed complaint: charts look muted, **and** series are hard to
tell apart. That is the same root cause as §5.9's "projection palette lacks contrast between
countries" item, fixed there by widening *hues* in an app-level override
(`[data-chart-category='projection']`, `climate-dashboard-react/src/styles.css`). Widening
*luminance* in the base theme addresses both symptoms at once and likely supersedes that override
— confirmed as a follow-up after this ships, not assumed (see §5.12.4).

#### 5.12.2 Revised palette

Validated against the card background (`#1e2f52`), ordered brightest-first so the first-assigned
series are automatically most prominent. Two tokens were reshaped from the original proposal after
review caught a real problem: the first draft's `-03` ("mint," `#4ee0a8`) and `-09` ("rose,"
`#ff5c8a`) sat in the same hue family as this dashboard's own sentiment-positive (`#3ecf95`, ~1°
apart) and sentiment-negative (`#f36b84`, ~6° apart) tokens — exactly the "reads as good/bad news"
risk the draft's own constraint was meant to rule out, but never actually checked against the real
token values. Reshaped to an orchid/magenta pair (~308° hue, ~41° from both sentiment tokens and
every other categorical hue) at matching luminance targets, so the hierarchy is unaffected:

| token | hex | luminance | vs. card | vs. page |
|---|---|---|---|---|
| `-01` cream | `#ecf0f6` | 0.868 | 11.59:1 | 14.54:1 |
| `-02` lime | `#c3e86b` | 0.704 | 9.52:1 | 11.94:1 |
| `-03` orchid | `#eab8e4` | 0.574 | 7.87:1 | 9.87:1 |
| `-04` amber | `#ffb454` | 0.545 | 7.52:1 | 9.43:1 |
| `-05` cyan | `#5ecbf5` | 0.517 | 7.16:1 | 8.98:1 |
| `-06` violet | `#c89cff` | 0.433 | 6.10:1 | 7.65:1 |
| `-07` coral | `#ff8f6b` | 0.420 | 5.93:1 | 7.44:1 |
| `-08` sky | `#7aa5ff` | 0.383 | 5.46:1 | 6.85:1 |
| `-09` magenta | `#ff4ae7` | 0.319 | 4.66:1 | 5.85:1 |

Mean luminance 0.529, mean contrast **7.31:1** (FT reference: 7.40:1) — independently recomputed
from the raw hex values, not just carried forward from the proposal.

**Constraint:** Release 3 standardized green = decrease / crimson = increase for change metrics.
The categorical ramp must stay clearly non-semantic so a bright series color never reads as a
sentiment cue; the `-03`/`-09` reshape above exists specifically to satisfy this, having caught the
original proposal not actually satisfying its own stated version of this rule.

#### 5.12.3 `SyChart` rendering defaults

| Aspect | Detail |
|---|---|
| Stroke width | `line: { width: 1.5 }` → **2.75px**. Reference measures ~3.3 CSS px; highest-impact single-line change after the palette |
| Markers on line charts | `mode: 'lines+markers'` with `marker: { size: 5 }` on every point competes with the strokes at 35 annual points × up to 10 countries. New `showMarkers?: boolean` per-series prop, defaulting to on only below a 10-point series (dense multi-country charts switch to pure strokes; sparse charts keep their markers unchanged) |
| Vertical gridlines | Neither axis set `showgrid`, so Plotly's `true` default applied to both. Gridlines now follow the **value** axis, not just `xaxis` unconditionally — Copilot caught that a hardcoded `xaxis.showgrid: false` breaks `orientation="h"` charts (categories on y, values on x, e.g. Forecasts' feature-importance chart), where it would have dropped the useful value gridlines and kept the useless category ones. Fixed with `showgrid: orientation === 'h' ? undefined : false` on `xaxis` (mirrored on `yaxis`) |
| Chart-card background | `paper_bgcolor`/`plot_bgcolor` are transparent, so the fix belongs to the card, not `SyChart`. `ChartCard` overrides its own `<Card>`'s background component-token to the page background (`#121e35`) rather than the general card surface (`#1e2f52`), gaining ~1.8:1 extra contrast for every series at no cost to non-chart cards |
| Legend placement, title hierarchy | Both deferred — larger/independent changes than the rest of this release (see §5.12.4) |

#### 5.12.4 Sequencing

One `design-system` PR carried the palette (5.12.2) and the `SyChart`/`ChartCard` rendering
defaults (5.12.3) together (#23). The app inherited the change with no code edits, but a full
visual pass across **all seven pages** confirmed no regressions, since every chart in the app
picked up new colors/strokes/markers/gridlines at once. One follow-up app-side decision after that
pass: `styles.css`'s `[data-chart-category='projection']` override (Release 3.1's fix for the same
contrast problem, scoped to Forecasts/Scenario Comparison) was retired in
`climate-emissions-analysis-project` #107 — confirmed redundant by a live A/B (disabling the
override in the running app and comparing the Scenario Comparison panels side by side), not
assumed from the token math alone. Legend-inside-plot and title-hierarchy items remain deferred,
optional, and out of scope for this release.

### 5.13 Climate Theme Variant (Release 8)

**Status: Parked — feature branch only, not merged.** A follow-on to Release 7: repositioning the
GHG dashboard's dark-theme identity from generic corporate navy to a climate-specific one, derived
from Pentagram's Zeff brand system (earth-green surfaces, seafoam/cooled-cyan accent, muted
categorical ramp). Tracked in `ENHANCEMENTS.md` Release 8. React-only, no `api`/`app.py` change.

Implemented as a genuinely separate `data-theme="climate-analytics"` theme (not a redefinition of
`analytics`, which keeps its navy surfaces and neon ramp for other consumers) on
`design-system` branch `feature/8.1-climate-analytics-theme` and
`climate-emissions-analysis-project` branch `feature/8.1-climate-analytics-theme` — both pushed,
neither opened as a PR nor merged. Per explicit instruction, the whole thing was built and
previewed locally (feature branches only, `npm run dev` against a local API instance, no deploy)
so the result could be seen running before any decision to merge — the opposite of the
merge-then-verify-live sequencing every other release in this document used.

Three surface-lightness variants were tried live, in order: the original dark forest-green/Zeff
derivation (surfaces luminance-matched to navy's own tokens, categorical ramp reshaped to avoid
the sentiment-green/red hue zones); a full light pastel/sage theme (read as too light once actually
seen running); a medium-toned sage between the two (surfaced a reproducible AG Grid rendering issue
— large paginated tables painted blank white despite correct computed styles, root cause not
isolated before the direction was abandoned). After comparing all three live, the decision was to
keep none of them and stay on the existing navy `analytics` theme — both feature branches were left
at the original dark-green variant's file contents (not the medium-sage state) as the parked
record, rather than deleted.

Not an internship requirement change.

### 5.14 Scenario Panel Legend Consistency (Release 9)

**Status: Shipped** — tracked in `ENHANCEMENTS.md` Release 9. `climate-emissions-analysis-project`
PR #109. React-only.

`ScenarioComparisonPage.tsx`'s three Country Comparison panels (BAU/Moderate/Aggressive) set
`showLegend={i === 0}` on their `SyChart` calls — only the first (BAU) panel got a static legend,
pushing its y-axis down relative to the other two and breaking horizontal alignment across the
row, worse on mobile. All three panels already show the same series info via `hovermode: 'x
unified'` on hover, so the static legend was redundant as well as inconsistent. Set to `false`
uniformly. Merged, deployed, and verified live: all three panels' axes now align.

### 5.15 Fixed-Position, Translucent Hover Tooltip (Release 10)

**Status: Shipped** — tracked in `ENHANCEMENTS.md` Release 10. `design-system` PRs #24, #25, #26.
React-only, affects every cartesian (line/bar/band) `SyChart` instance app-wide.

Plotly's own `hovermode: 'x unified'` label box is positioned near the topmost active trace's own
y-pixel at the hovered x — it moves as that value moves across the series and flips sides near
the plot's edges, confirmed live on Scenario Comparison's 10-series charts to make some rows hard
to reach without re-hovering. Fixed (#24) by keeping Plotly's own hover hit-testing and spike
guideline intact, but suppressing only its label box's rendering (a CSS rule scoped to
`.hoverlayer > .legend`, confirmed against the live DOM as the correct, distinct class) and
substituting a React-rendered tooltip pinned to the chart's vertical middle — never moves,
follows the cursor horizontally with edge clamping, and scrolls internally if a series list is
taller than the chart. Copilot's review of #24 caught three real issues, all fixed before merge:
tooltip content was built via `innerHTML` string interpolation (a real HTML-injection risk for a
general-purpose component that doesn't control what callers pass as series names) — rewritten via
`createElement`/`textContent`; `pointerEvents: 'none'` made the intended scroll affordance
unreachable — fixed with pointer events enabled plus a grace-period delay before hiding on
`plotly_unhover` (an immediate hide loses the race the moment the cursor reaches the tooltip,
confirmed live); and a stale comment referencing the wrong file path.

Follow-up, found on manual verification of the live deploy: the tooltip's flat
`--static-layer-standard` background fully hid chart lines underneath it. Made translucent via the
existing `withAlpha` helper (#25, 0.85 opacity — still read as effectively opaque once actually
seen live; #26, dropped to 0.65, confirmed against the live site to clearly show chart lines
through the tooltip while text stays legible).

### 5.16 Final Presentation Link (Release 11)

**Status: Shipped.** `climate-emissions-analysis-project` only, no `design-system` change.
`climate-emissions-analysis-project` branches `feature/9.1-about-presentation-embed` (initial
iframe version, merged as PR #110) superseded by `fix/9.2-presentation-open-new-tab` (two-link
design, merged as PR #111), `fix/9.3-pwa-navigate-fallback-denylist` (PWA bug fix below),
`fix/9.4-pptx-content-disposition` (Content-Type/Content-Disposition bug fix below),
`fix/9.5-navigate-denylist-query-string` (denylist robustness fix below), and
`fix/9.6-remove-pptx-download-link` (product decision, below) which is the current design.
Deployed to the Mac Mini and verified live: "Open the presentation" resolves to the correct URL
with `target="_blank" rel="noopener noreferrer"` and opens Microsoft's viewer in a new tab
rendering the deck correctly (confirmed slide 1 of 17).

**Product decision: no direct download link, viewer-only access.** The two-link design
(`fix/9.2`) offered both "Open the presentation" and a direct "Download the .pptx" link. Decided
the deck should only be viewable through Microsoft's online viewer, not offered as a direct
download — removed the "Download the .pptx" link from `AboutPage.tsx` and the
`pptxDownloadHeadersPlugin` middleware in `vite.config.ts` that existed solely to make that link's
`Content-Type`/`Content-Disposition` behave correctly (see the second and fourth bugs below — both
were specific to that link and are moot once it's gone). The `.pptx` itself is still served as a
static asset (Microsoft's viewer still fetches it server-side via the embed URL), and its literal
URL is still technically reachable by anyone who knows it or inspects the page — this only removes
the UI affordance for downloading it, not access to the underlying file, which isn't meaningfully
restrictable without a token-gated endpoint that would be disproportionate for an internship
deck. The `navigateFallbackDenylist` fix (`fix/9.3`/`fix/9.5`, below) was kept — it's a general
robustness fix for any static asset under `public/`, unrelated to whether a download link exists.

**Real bug found live after PR #111 shipped:** clicking "Download the .pptx" opened a new tab
that redirected to the Overview page instead of downloading the file. Root cause: `vite-plugin-
pwa`'s generated `sw.js` registers Workbox's default `NavigationRoute` with no
`navigateFallbackDenylist`, so it intercepts *every* top-level navigation (`mode: 'navigate'`) —
including a `target="_blank"` click on a plain `<a href>` to a static file — and serves the SPA
shell instead, since the route can't distinguish an app route (`/historical`, `/about`, etc.) from
a real static asset. Fixed in `vite.config.ts` by adding
`workbox.navigateFallbackDenylist: [/\.[a-zA-Z0-9]{2,5}$/]`, excluding any path ending in a file
extension from the fallback (safe here since every app route is extensionless) — confirmed fixed
locally via `vite preview` with a real service-worker-controlled page (clicking the link now
downloads the file; the About page no longer redirects).

**Second real bug found live after the above fix shipped:** with the redirect fixed, the download
link opened a new tab showing the `.pptx`'s raw binary content instead of downloading it. Root
cause: neither `vite dev` nor `vite preview` set a `Content-Type` for a `public/` file with an
unrecognized extension (confirmed via `curl -sI`: empty `Content-Type` for `.pptx` in both modes,
a known gap flagged — incorrectly, as it turned out — as non-blocking when this feature first
shipped), so a browser with nothing registered for that MIME type sniffs the response and renders
it as text. `vite preview` is the literal process the Mac Mini's Cloudflare Tunnel deploy forwards
to (no separate reverse proxy or static host sets headers), so the fix had to live in
`vite.config.ts` itself: a small Connect middleware (mirroring the existing
`redirectBareBasePlugin` pattern, applied to both `configureServer` and `configurePreviewServer`)
that sets `Content-Type: application/vnd.openxmlformats-officedocument.presentationml
.presentation` and `Content-Disposition: attachment; filename="GHG_Internship_Review_QA_Deck
.pptx"` for any request ending in `.pptx`. `Content-Disposition: attachment` also directly matches
the link's own label ("Download the .pptx") — forces a download regardless of how any given
browser would otherwise have sniffed the content. Doesn't affect the "Open the presentation" link,
since Microsoft's viewer fetches the same URL server-side (like `curl`), not as a browser
navigation that interprets `Content-Disposition`. Verified fixed locally: `curl -sI` shows both
headers, and clicking the link in a real browser now triggers a genuine download instead of
rendering garbled binary. (Copilot review on PR #113 caught one real issue: the `Content-
Disposition` filename was hardcoded to the one file that exists today even though the middleware
matches any `.pptx` path — fixed to derive it via `path.basename()` on the request path instead.)

**Third real bug, found live while investigating a user report that looked like a caching
issue:** after PR #113 shipped, a screenshot showed "Download the .pptx" rendering raw binary
again. Investigation (a page-context `fetch()` with `cache: 'reload'` to bypass the browser's own
HTTP cache) confirmed the server was sending the correct headers — the screenshot was very likely
this browser's own stale disk-cache entry for that exact URL from earlier testing sessions before
the header fix shipped, not a live regression. But testing this surfaced a second, genuinely real
gap: appending any query string to the `.pptx` URL (e.g. a cache-busting param) resurrected the
original redirect-to-Overview bug from `fix/9.3`. Root cause: Workbox's `NavigationRoute` tests its
denylist against the full `pathname + search`, not just `pathname` — confirmed empirically (the
bare `\.[a-zA-Z0-9]{2,5}$` pattern stopped matching, and the SPA fallback fired again, the moment a
query string was appended). Fixed by widening the regex to
`/\.[a-zA-Z0-9]{2,5}(\?.*)?$/`, tolerating an optional trailing query string. Verified with a real
service-worker-controlled page: navigating a fresh tab directly to a query-stringed `.pptx` URL now
triggers a download (the tab reverts to blank/new-tab state) instead of rendering the Overview
page.

Adds a "Final Presentation" section to the About page linking to the internship review Q&A deck
with its original PowerPoint animations/transitions intact — a PDF or plain download link
wouldn't preserve those, so the deck is served as a static asset
(`climate-dashboard-react/public/GHG_Internship_Review_QA_Deck.pptx`, renamed from the source
`docs/GHG_Internship_Review_Q&A_Deck.pptx` to drop the `&` for URL-safety) and opened via
Microsoft's own web viewer (`view.officeapps.live.com`), which renders it with materially better
animation fidelity than a Google Slides conversion would, and needs no manual upload/publish step
— the viewer just fetches the file from its own public URL, computed at runtime via
`window.location.origin` + `import.meta.env.BASE_URL` rather than hardcoded, so it resolves
correctly under the deploy prefix. A second link opens the raw `.pptx` directly as a download
fallback. Both links open in a new tab (`target="_blank" rel="noopener noreferrer"`).

**Revised from an inline `<iframe>` embed to two `target="_blank"` links** (the Office viewer, and
a direct download) after initial merge — a new-tab link is a full top-level navigation to
`view.officeapps.live.com`, not a same-page embed, so it needs no `frame-src` CSP allowance at all;
only `frame-ancestors`/`frame-src` govern iframes. This removes the deployment-config dependency
entirely — no Cloudflare change is needed for this feature to work, unlike the world map's
`connect-src` requirement for `cdn.plot.ly` (§5.8), which does still apply since that's a real
same-page fetch.

**Known gap, deliberately not fixed:** `.gitignore`'s repo-wide `*.pptx` rule (meant for the
mentor's own working drafts under `docs/`, confirmed never part of the intern template) needed a
narrow negation (`!climate-dashboard-react/public/*.pptx`) for this one file specifically, since
it's now a real served asset, not a draft sitting in a working directory.

### 5.17 Animated Choropleth Time-Series (Release 12)

**Status: Shipped.** Tracked in `ENHANCEMENTS.md` Release 12. Turns the Overview world map from a
static latest-year snapshot into an autoplaying, scrubbable 1990–2024 sequence, synchronized with
the KPI/tier numbers so they read the actual totals for whichever year the map is currently
showing rather than a decorative 0→final count-up. Three PRs: `design-system` #28 (`colorRange`/
`animationFrame`/no-data trace on `SyChart`, `Slider` keyboard nav, new `useReducedMotion` hook),
`climate-emissions-analysis-project` #117 (`GET /overview/world-map-series`, `co2_by_year`), #118
(the Overview page wiring itself). Not an internship requirement change.

**Architecture.** The color axis is pinned across every frame (`colorRange` → `zmin`/`zmax` +
`zauto: false`) — without this, an animated chart re-normalizes its color scale to each frame's
own min/max, hiding real magnitude growth behind constant-looking colors. Per-frame updates go
through a new `animationFrame` prop, applied via a direct `Plotly.restyle` in an effect isolated
from `SyChart`'s main render effect — confirmed live (Storybook and, after deploy, production
itself) that this preserves a user's map zoom/pan exactly across a full ~23s animation run, while
the ordinary `Plotly.react` path a `series` prop change takes does not. The choropleth `series`
passed to `SyChart` is memoized to the initial year only and must never change reference for the
component's lifetime, or the animation would both lose the user's zoom and pay for a full
re-render (hover handlers rebound, the resize `ResizeObserver` torn down/recreated) every tick.
`useYearAnimation` (new hook, `climate-dashboard-react`) owns `currentYear`/`isPlaying`,
autoplays on mount, and — gated on design-system's new live-subscribed `useReducedMotion` hook —
pins at the final year with Play disabled (manual scrubbing still works) when
`prefers-reduced-motion` is set. All Countries/Expanded's per-year KPI totals come from the API's
new `co2_by_year` field; Selected is summed client-side from the same `world-map-series` payload
restricted to the current selection, since re-fetching it per selection change would defeat the
point of a selection-invariant, fetch-once endpoint.

**Two corrections found by verifying against the real data before implementing, not assumed from
the original draft spec:**
- **9 no-data countries, not 6.** The original draft claimed only 6 countries (`CXR, ERI, FSM,
  MHL, NAM, TLS`) have any missing year, all resolved by 1995. Verified against the actual OWID
  data: three more — Monaco, San Marino, Vatican City — report **zero** CO₂ data across the
  *entire* 1990–2024 range, not just an early-1990s gap. No code change was needed (the no-data
  trace design handles any number of always/sometimes-null countries generically), but the
  world-map-series loader's docstring documents the real figure.
- **A literal-zero value breaks a log-scaled floor.** Antarctica reports genuine `0.0` CO₂ for
  2008–2024 (real, not missing — it has a real ISO-3 code and passes the `iso_code.notna()`
  filter same as every other entity). `log10(0)` is undefined, so `WorldMapTimeSeries.value_range`
  excludes exact zero from its floor, using the smallest genuinely positive value instead
  (confirmed: `0.004` Mt, not `0.0`) — otherwise a zLog-scaled `colorRange` would compute a null
  `zmin`.

**Copilot review (design-system #28) caught two real issues, both fixed before merge:** (1) the
same zLog-guarded log10 transform applied to `colorRange`'s bounds could itself produce a `null`
`zmin` if a caller passed a non-positive lower bound (e.g. a naive `colorRange: [0, max]`) —
Plotly's behavior with `zmin: null` alongside `zauto: false` is undefined and could silently
re-enable auto-scaling, defeating the point of pinning the range at all; fixed with a defensive
floor (`Number.MIN_VALUE`) distinct from the per-data-point transform (where `null` legitimately
means "no color for this point"). (2) The no-data trace's existence was decided once, at the
initial `Plotly.react` call, based on whether *that* render's `colorValues` happened to contain a
null — an animated choropleth whose first frame was fully populated would permanently lose
no-data highlighting for every later frame that did introduce a gap, since `animationFrame`'s own
effect never re-runs the trace-construction code. Fixed by always constructing the trace (with
empty `locations` when there's nothing to highlight yet — costs nothing, renders nothing). Both
re-verified live (Storybook `ChoroplethAnimated` story + `Plotly` state inspection) before the
re-review came back clean.

**Verified live after deploy** against `labs.syena.io/ghg-emissions-analysis` (service worker and
Cache Storage cleared first, per the standing deploy-verification practice): the map animates
1990→2024, zoom held exactly across the full run, `world-map-series` fetched exactly once per
page load regardless of country-selection changes (confirmed via network inspection, both
pre-deploy against the real API and post-deploy against production), Namibia (a real early-1990s
no-data country) renders in the muted no-data gray at 1990 and resolves to real data by the
mid-90s, and the KPI/tier numbers settle to the exact figures the API returns (218 countries /
37,398 MtCO₂ / +68.6% for All Countries at 2024, matching the API response byte-for-byte). Console
clean throughout.

**Follow-up: decade-stepped autoplay, not year-by-year (`climate-emissions-analysis-project`
#119).** Shipped the same day, prompted by direct feedback after using the year-by-year version
live: annual change is gradual enough to be hard to notice while autoplay steps through it one
year at a time, whereas jumping decade to decade (1990, 2000, 2010, 2020, then 2024) makes the
trend obvious at a glance. `useYearAnimation` now autoplays through a fixed stop list — `minYear`,
every decade boundary after it, then `maxYear` — instead of incrementing by 1 each tick; manual
scrubbing (the `Slider`/`seek()`) is completely unaffected, since it was already independent of
whatever stepping scheme autoplay uses and still allows any year in range. Resuming Play after a
manual seek advances to the next stop *after* wherever the user left off (e.g. seek to 2015, hit
Play → next stop is 2020), not the next index in the stop list. Dwell time per stop raised to
1800ms (from 600ms/year) — 5 stops instead of 35 means total autoplay time actually *drops* to
~9s (from ~21s) despite each stop lasting 3× longer, while giving both the map's color jump and
the KPI count-up time to register before the next stop. (Further tuned in a same-day follow-up,
PR #120 — see below.)

Implementing this surfaced a genuine one-tick lag in the original (year-by-year) design, invisible
at 35 roughly-one-second ticks but obvious at 5 stops of 1.8s each: `isPlaying` only flipped to
`false` the tick *after* reaching the final stop, not on arrival, so the Play/Pause control read as
stale for a full extra dwell period after the animation had visibly finished. Fixed by stopping the
instant the final stop is reached (a separate effect keyed on `currentYear` reaching the last
stop), verified live: the button now flips back to "Play" immediately when the map lands on 2024,
both on `localhost` against the real API and post-deploy on `labs.syena.io`. Copilot's review of
#119 was a clean pass, no comments.

**Second follow-up: separate the KPI count-up duration from the autoplay interval (PR #120,
same day).** Reported live immediately after #119 shipped: the KPI numbers didn't have time to sit
still before the slider advanced, since the count-up's own duration and the autoplay tick interval
were the same constant (both 1800ms) — the numbers were still easing right up until the next jump
fired. Split into two constants: `KPI_COUNT_UP_MS` (1200ms, how long the count-up itself takes) and
`ANIMATION_STOP_MS` (4200ms, total dwell per stop, passed to `useYearAnimation`'s `intervalMs`). The
~3s gap between them is genuine settled, fully-readable time before the next stop. No Copilot
review requested for this small a change, per explicit instruction. Verified live pre- and
post-deploy across multiple real decade stops (1990/2000/2010/2024), each showing correct settled
figures matching the API exactly.

**Third follow-up: shorten the dwell time (same day).** The ~3s settled hold the second follow-up
introduced turned out to read as too long a pause once seen live. `ANIMATION_STOP_MS` tuned down
from 4200ms to 2400ms (`KPI_COUNT_UP_MS` unchanged at 1200ms), leaving a ~1.2s settled window per
stop. Committed and pushed directly to `main` per explicit instruction — no feature branch, PR, or
review for this one. Verified live post-deploy: multiple real decade stops still settle to the
correct figures, Play/Pause still flips back immediately on reaching 2024, console clean.

**Fourth follow-up: 5-year steps, no KPI count-up (same day).** Two changes requested directly
together: step every 5 years instead of every 10 (`STEP_YEARS = 5` in `useYearAnimation`,
`computeDecadeStops` renamed `computeAutoplayStops` since "decade" no longer describes it — for
the real range this produces `[1990, 1995, 2000, ..., 2020, 2024]`, 8 stops instead of 5), and
drop the KPI count-up animation entirely — the tier numbers (Countries/CO₂/% Change) now snap
directly to their new value in step with the map rather than easing toward it, since at a 1200ms
tick interval the count-up was either lagging visibly behind the map or still mid-ease when the
next tick fired. `KPI_COUNT_UP_MS` removed; `ANIMATION_STOP_MS` set to 1200ms. `CountUpText`
itself and its accessibility handling (aria-hidden animated span + visually-hidden true-value
span) are untouched and still used for the two KpiStat cards elsewhere on the page (Fastest
Growth/Largest Reduction), which count up once from the initial page load and were never tied to
`currentYear`. `useYearAnimation.test.ts` rewritten for 5-year steps; `OverviewPage.test.tsx`'s
tier-number assertions changed from asserting 2 occurrences (the old aria-hidden/visually-hidden
pair) to 1, since these three metrics no longer render through `CountUpText` at all. Committed and
pushed directly to `main` per explicit instruction. Verified live pre- and post-deploy: confirmed a
genuine 5-year stop mid-run (e.g. landing on 2005/2000), correct settled figures with no animation
lag, clean finish at 2024, console clean.

**Fifth follow-up: richer color palette.** Reported live: the visual difference between 1990 and
2024 wasn't clear enough. `colorRange` itself is deliberately pinned to the true global min/max
across the whole animation (§5.17.2) and had to stay that way — widening or narrowing it would
reintroduce the per-frame color re-normalization problem that prop exists to prevent, and most
countries, most years, sit in the same middle band of that fixed range regardless. The actual
issue was that `MAGNITUDE_SCALE`'s old 3-stop interpolation (pale cream → orange → deep red) gave
that middle band almost no color resolution, so a country's value doubling over the animation
often produced only a subtle shift within a near-uniform orange. Replaced with ColorBrewer's
YlOrRd 9-stop sequential palette (pale yellow through orange to deep maroon) — same `colorRange`,
same `zLog` transform, far more graduated color across the values that actually vary year to year.
Verified live pre- and post-deploy comparing 1991 directly against 2020/2024: countries that were
pale yellow/light orange early in the range now read as visibly, distinctly deeper red/maroon
later on.

**Sixth follow-up: slider range labels and a moving current-value label.** Requested directly:
indicate the year slider's start/end years, and show a label that moves with the thumb as it plays
or is scrubbed. `design-system`'s `Slider` gained two new opt-in props (PR #29): `showRangeLabels`
(renders `min`/`max` below the track's two ends) and `showThumbValue` (a small floating label
above the thumb, positioned via the same `pct` calculation the thumb itself already uses, so it
tracks live regardless of whether the value changes via drag, keyboard, or — as here — autoplay).
Both additive to the existing `showValue` (a static line above the track), not a replacement.
`climate-emissions-analysis-project` PR #121 wired both into the Overview page's year `Slider`. A
same-turn follow-up then removed the old static "Year ... 2024" value next to the label
(`showValue={false}`), reported as redundant once the moving label shows the same number in
context. Both PRs reviewed via the `copilot-review-loop` skill — both came back clean, no findings
(design-system's review noted one harmless redundancy, an unneeded explicit `position: relative`
already set by the vendor CSS, no action needed). Verified live pre- and post-deploy: the moving
label tracks the thumb correctly through a full autoplay run with no clipping at either range
extreme (1990/2024), no layout clash with the Play button or `ChartCard` title, and the static
value label confirmed removed.

### 5.18 Overview Headline Sentence, Compressed Tier Panel, Slider Touch Target & No-Data Hover (Release 13)

**Status: Shipped.** Bundles two unrelated efforts from the same review pass under one release,
following the precedent set by §5.9 (Release 3.1) — no dependency between them and no shared code,
but no reason that requires separate release numbers either.

**5.18.1–5.18.2 (`climate-emissions-analysis-project` PR #122, React-only).** Added a one-sentence,
data-derived headline to the Overview page's hero row, placed above a compressed tier table inside
the existing right-hand column rather than as a new full-width section — keeping page height flat
after prior releases (the 2/3-map/1/3-KPI restructure) fought it down. Deterministic string
templating from `top_movers`, explicitly not an LLM call: this project verifies every number before
stating it, and free-form generation can't be unit-tested for factual correctness the way a
template can. New `src/lib/overviewHeadline.ts` derives `absGrower`/`pctGrower`/`mostStable`/
`decliners` itself via hand-rolled `maxBy`/`minBy` (no `lodash` in this project) rather than
trusting `top_movers`' given sort order, which is a server-side contract not encoded in the TS
type. Handles the edge cases the draft flagged — `absGrower === pctGrower` collapses to one clause,
zero decliners drops the final clause, fewer than 4 usable rows suppresses only the "most stable"
clause, ties resolve deterministically — plus one the draft didn't call out: exactly one decliner
needs its own singular-wording branch, not the plural template with an empty second slot. Labeled
with a "Since 1990" eyebrow so it doesn't appear to describe whatever year the adjacent, user-
scrubbable animated map happens to be paused on.

Gated on `selected.length > 0`, a correctness fix over the original draft: `top_movers` reflects
the server's default selection even when the local `selected` array is empty, which would
otherwise narrate a phantom selection right next to the "Select at least one country" warning —
the same gate the Selected tier row already used.

`TierSummaryPanel` recompressed from three per-tier cards (with a per-tier icon column) to a single
`Table`, freeing the vertical space the headline needs — direct precedent for exactly this shape
already existed in this file's own history (`47c6e3d`, later reverted to cards in `a4d3967` for
unrelated reasons). `TierRow` needed its `[key: string]: unknown` index signature back (`Table`'s
own generic constraint), the same fix made once before (`bf84e76`) and dropped when cards replaced
the table (`940ccb9`).

Copilot's review of #122 came back clean — one cosmetic observation (a positive-but-near-zero
`mostStable` value reads as "stayed comparatively flat," which is mildly odd wording for a country
that still grew) was confirmed to be exactly this section's own specified algorithm and template
wording, not a deviation, so left as-is. 9 new `overviewHeadline.test.ts` cases plus 3 new/updated
`OverviewPage.test.tsx` assertions. Verified live pre- and post-deploy: the headline matches this
section's own hand-verified example (China +9,806 MtCO₂/+452.5%, United States −4.4%, United
Kingdom/Germany steepest declines at −48.0%/−45.7%), disappears at 0 selected countries and
reappears on reset, and the compressed table doesn't stretch the hero row past the map's own height
(`alignItems: 'stretch'` would otherwise reintroduce the dead-space problem §5.10 fixed).

**5.18.3–5.18.4 (`design-system` PR #30).** Two independent, small fixes, bundled in one PR since
neither shares code or has an ordering dependency:

- **Slider touch target.** `.__s9cmpx-slider__thumb` was 16×16 at rest, 20×20 on `:hover` — both
  below WCAG 2.2 §2.5.8's 24×24 CSS px minimum, and `:hover` doesn't help keyboard or touch users
  reach even that still-failing size. Fixed in `overrides.css` (not the vendored CSS directly, per
  this repo's own convention) by raising the resting size to 24×24 and matching `:hover` to the
  same value so hover is a no-op rather than a shrink — following the exact template of this same
  file's existing `.__s9cmpx-tags__remove-button` WCAG fix, but landing at 24×24 rather than that
  fix's own reasoning for staying small: the slider thumb sits alone on open track space, not
  crowded against sibling controls the way a tag's remove button is. New Storybook `play` assertion
  (`getBoundingClientRect() >= 24×24`) — no existing story asserted thumb pixel size before this.
- **No-data hover text.** `SyChart`'s no-data choropleth trace used `hoverinfo: 'skip'`, giving
  no-data countries a silent, uninformative hover. Replaced with an explicit `hovertemplate`
  ("No data reported" by default), extracted to a new `noDataHovertemplate()` helper in
  `chartMath.ts` (this file's own established home for `SyChart`'s Plotly-free pure logic, so it's
  unit-testable without pulling in `plotly.js-dist-min`) and a new optional `SyChartSeries` field,
  `noDataHoverText`, for callers that want a more specific label than the generic default.

Copilot's first review attempt on #30 failed at the infrastructure level ("the job was not acquired
by Runner of type hosted even after multiple attempts") rather than completing — re-requested;
the second attempt reviewed all 6 changed files cleanly, no comments. Consuming apps need no code
change for either fix: `climate-dashboard-react`'s `vite.config.ts` aliases `design-system` straight
to its source (no `main`/`exports`/version to bump), so both land the moment `design-system`'s
`main` is merged.

Verified live pre- and post-deploy (`labs.syena.io/ghg-emissions-analysis`, service worker/Cache
Storage cleared first): the Overview year slider's thumb measures exactly 24×24 via
`getBoundingClientRect()`, and the no-data (gray) countries' Plotly trace carries the new
`"%{location}<br>No data reported<extra></extra>"` hovertemplate in place of the old silent
`hoverinfo: 'skip'`.

**Follow-up (`climate-emissions-analysis-project` PR #123):** two issues found in live review of
the just-shipped panel. First, the "Since 1990" eyebrow and the headline sentence itself both
stated the timeframe — fixed by dropping the inline "since 1990" from the sentence now that the
eyebrow carries it alone. Second, the compressed table's Tier column gave "Expanded (Coverage +
≥100 Mt)" 133px against a measured 204px needed, clipping to "Expanded (Cover..." and losing the
coverage/materiality qualifier that tier's whole definition rests on — fixed by replacing the
single 4-column table with a full-width tier-name heading per row above a compact 3-column metric
strip, giving the name the panel's entire width to wrap into. Copilot's review of #123 came back
clean. Verified live pre- and post-deploy via direct DOM measurement (`scrollWidth`/`clientWidth`
equality, not just visual inspection): zero truncated elements, zero redundant "since 1990"
occurrences in the rendered sentence.

#### 5.18.5 Decouple the headline sentence from the country picker (Shipped, PR #124)

The headline read `top_movers`, computed from whichever countries are `selected` in the picker —
so it silently changed (and could read as inconsistent) the moment a user changed the selection,
since it sits above the fold, easy to miss re-reading. Prompted by a direct question about what
the headline was actually describing: "whatever's currently selected," correct today only because
the picker's default happens to coincide with a sensible story.

New API field, independent of `selected`: `headline_movers`, a fixed top 10 sovereign countries by
absolute latest-year CO₂, computed from `df_all`/`df_map` (the same selection-invariant universe
`world_map` already uses), never `df_selected`. `top_movers` is completely untouched — still
computed from `selected`, still backing the separate Top Movers cards/chart below the fold, which
correctly keep reacting to the picker.

`buildHeadlineSentence` gained a required `scope` parameter — the caller supplies the framing
clause ("the top 10 emitters by 2024 output"), fused via a comma splice onto the sentence's first
clause ("Among {scope}, {country} has grown the most..."). Kept out of the pure function for the
same reason the "Since 1990" eyebrow already is: a wording concern, not a derived fact, so the
function's output stays independently testable. The `selected.length > 0` gate on the headline —
previously needed because `top_movers` reflected the server's default selection even when
`selected` was empty — is removed entirely, since `headline_movers` no longer depends on the
picker at all; the headline now stays visible even at 0 selected countries.

Verified against real 2024 OWID data before implementing: the true top 10 emitters (China, United
States, India, Russia, Japan, Indonesia, Iran, Saudi Arabia, South Korea, Germany) is not
`FEATURED_COUNTRIES` — the United Kingdom drops out of the headline entirely (its 48% decline was
only ever there because it's in the curated `FEATURED_COUNTRIES` list, not its raw tonnage);
Germany becomes the steepest decliner; Russia (−29.8%) enters in the UK's place.

Copilot's review of #124 came back clean, no findings. Two new backend tests:
`test_overview_headline_movers_unaffected_by_countries_param` (the load-bearing regression proof —
mirrors the existing `world_map` invariance test) and
`test_overview_headline_movers_ordering_and_top_n_cap` (a dedicated 12-country fixture proving the
`TOP_N_HEADLINE` cap actually excludes the 11th/12th-largest emitters). Verified live pre- and
post-deploy (`labs.syena.io/ghg-emissions-analysis`, service worker/Cache Storage cleared first):
headline text confirmed **byte-identical** before and after deselecting every country in the
picker (the core fix); stays visible at 0 selected; the below-the-fold Top Movers section confirmed
still reacting to the picker (United Kingdom still shown there, unaffected); console clean.

#### 5.18.6 Highlight country names and color values in the headline (Shipped, PR #125)

Requested directly: highlight the countries named in the headline sentence, and color the numeric
values using this app's existing color-coding convention. That convention already exists —
`TierSummaryPanel`'s % Change column colors an increase `NEGATIVE_COLOR` (more emissions is bad)
and a decrease `POSITIVE_COLOR` (less is good) — so the fix is to apply the same rule to the
headline rather than invent a new one.

`buildHeadlineSentence` changed from returning a plain string to a `HeadlineSegment[]` — tagged
`text`/`country`/`value` pieces, with a derived `sentiment: 'positive' | 'negative'` on each value
segment (whether the underlying number is an increase or decrease). The actual color choice stays
a rendering concern, applied by `OverviewHeadline` from `sentiment` — the same wording/derivation
split this file already used for the "Since 1990" eyebrow and the `scope` parameter (SPEC.md
§5.18.5): the pure function states facts, the component decides how to present them. A new
`headlineSegmentsToText` helper flattens segments back to plain text for tests; confirmed
byte-for-byte identical to the prior string output for every existing test case, so this was a
pure structural refactor, not a wording change.

`OverviewHeadline` renders `country` segments as `<strong>` and `value` segments with an inline
`color` based on `sentiment`. Existing exact-string test assertions on the rendered sentence broke
(the text is now split across multiple DOM nodes, not one text node) — replaced with a custom
matcher checking the `<p>`'s full `textContent`, plus new assertions confirming specific country
names render as `<strong>` and specific values carry the correct color via `toHaveStyle`.

Copilot's review of #125 posted no comment at all — confirmed this was a genuine clean pass, not
silence masking an infrastructure failure (the exact failure mode seen on §5.18.3–5.18.4's PR #30),
by checking the `copilot` check-run's `conclusion` field directly: `success`, not `cancelled`.

Verified live pre- and post-deploy (`labs.syena.io/ghg-emissions-analysis`, service worker/Cache
Storage cleared first): country names render bold, increase values (China's absolute change,
India's growth rate) render red, decrease values (United States, Germany, Russia) render green,
visually consistent with the tier table's own coloring; console clean.

### 5.19 Per-Page "Jump To" Navigation (Shipped, Release 14)

**Status: Shipped.** `design-system` PR #31 + `climate-emissions-analysis-project` PR #126. A
small in-page anchor-link row under each of the six main pages' `<h1>`, letting a user jump
straight to a below-the-fold section instead of scrolling — Overview and Forecasts each have 3–5
sections; the rest have 2–4.

**Reuse over new-build.** The draft spec called for a new `Chip`-based `JumpNav` component. Before
implementing, research found `design-system` already shipped an unused `JumpLinks` component
(`src/components/JumpLinks/JumpLinks.tsx`, exported from `src/index.ts`, real vendored CSS,
confirmed zero usages in either repo) built for exactly this purpose, styled as underline tabs
rather than pill chips. Presented as an explicit choice; reusing `JumpLinks` was selected —
eliminating the need for the `Chip` `href` variant the draft also called for.

**`design-system` changes (PR #31).** `ChartCard` gained a passthrough `id?: string` (the
underlying `Card` already forwarded `id` via `{...rest}`, so this was a one-line addition).
`JumpLinks`' `JumpLinkItem` gained an optional `onBeforeJump?: () => void | Promise<void>`, awaited
before scrolling — used by Forecasts to force-open a collapsed `Accordion` panel before jumping
into it. The click handler mirrors `SidebarNav`'s existing interception guard (a modified click —
ctrl/cmd/shift/alt — or a non-primary mouse button is never intercepted, so "open in new
tab"/"copy link address" keep working natively). A new exported `scrollToJumpTarget(id, opts)`
helper factors the scroll/focus logic out for reuse by the consuming apps' own hash-on-load effect.
`Accordion` gained an optional controlled `openIds`/`onOpenChange` pair (additive; the sole
existing consumer, `ForecastsPage`, was fully uncontrolled and unaffected).

Copilot's review of #31 found one real bug: the click handler's `e.preventDefault()` (needed to run
the scroll/focus sequence instead of a native jump) meant the URL hash never actually updated,
breaking "copy link address" and back-button behavior. Fixed by adding a `window.history.pushState`
call after the scroll. A Storybook `play`-function test asserting a modified click is *not*
intercepted reproducibly crashed the Storybook/vitest browser-mode test runner (root-caused via
bisection to a real native hash-navigation completing inside that specific test harness, not a bug
in the interception-guard code itself, which is a direct port of `SidebarNav`'s already-shipped
logic) — dropped that one story, documented why in a code comment, and covered that behavior via
live browser verification instead.

**`climate-emissions-analysis-project` changes (PR #126).** All six pages (Overview, Historical
Trends, Country Profile, Forecasts, Scenario Comparison, Data Explorer) render a `<JumpLinks>` row
under their `<h1>`, plus a new shared `useJumpToHashOnLoad` hook so a bookmarked/shared `#anchor`
URL lands on the right section once data resolves, not just at the page top. For three pages
(Historical Trends, Scenario Comparison, Data Explorer) the target `<h2>` headings were already
unconditionally rendered, so no refactor was needed. Overview was the exception: its "By Country"
and "% Change" sections previously had their entire heading-and-content block inside the
`selected.length === 0` ternary — refactored to match the pattern the other pages already used
(heading outside the gate, only the chart/content beneath it conditional), the same pattern
Historical Trends already established. A side effect: the "Select at least one country." warning
now renders once per gated section (2×) instead of once — a deliberate, accepted behavior change.

Forecasts is the special case: 3 of its 5 jump targets live inside a collapsed-by-default
`Accordion`. Each of those `JumpLinkItem`s' `onBeforeJump` opens its panel via `Accordion`'s new
controlled `openIds`; `JumpLinks` awaits that, then a double-`requestAnimationFrame` settle (to let
the panel's DOM mutation actually lay out) before measuring scroll position.

Copilot's review of #126 found one real bug: `useJumpToHashOnLoad(true, ...)` on Forecasts fired
immediately on first render — before the 3 accordion-backed targets' data (and therefore the panel
elements themselves) existed in the DOM — so a bookmarked `#model-comparison-accordion-panel` URL
silently no-opped. Fixed by resolving the hash against a `PANEL_TO_ACCORDION_ID` map at mount,
opening the matching panel once its data loads, and only then letting the hash-jump hook fire;
`#forecast-chart`/`#forecast-summary` (always in the DOM from first render) keep firing
immediately. Added a regression test and verified the fix live pre-deploy.

A genuine test-infrastructure bug was found and fixed along the way, unrelated to the feature
itself: `vi.unstubAllGlobals()`, copied into five page test files' `afterEach` from
`useCountUp.test.ts`'s established pattern, also wiped the global `ResizeObserver` stub
`src/test/setup.ts` establishes once per file for `design-system`'s `DataTable` — breaking every
`DataTable`-rendering test after the first in each file. Confirmed via `git stash` bisection that
this was a real regression, not pre-existing flakiness; fixed by dropping the blanket unstub (each
file's `beforeEach` already re-stubs `matchMedia` fresh, so nothing else needed cleaning up).

Verified live pre- and post-deploy (`labs.syena.io/ghg-emissions-analysis`, service worker/Cache
Storage cleared first, both `design-system` and `climate-dashboard-react` checkouts fast-forwarded
on the Mac Mini, `vitepreview` rebuilt/restarted — no `api/` change, `uvicorn` untouched): all six
pages' jump rows render the correct labels/hrefs; clicking scrolls to and focuses the right target;
keyboard Tab+Enter activation works; a fresh page load with a `#anchor` already in the URL lands on
the right section once data resolves; Forecasts' 3 accordion items visibly open their panel before
the scroll lands, confirmed directly on the exact bookmarked-URL case the review caught
(`/forecasts#model-comparison-accordion-panel`); jump-link `href`s resolve to real, copyable anchor
URLs.

### 5.20 Floating "Back to Top" Button (Shipped, Release 15)

**Status: Shipped.** `design-system` PR #32 + `climate-emissions-analysis-project` PR #127.
Requested directly, as a companion to §5.19's jump nav: a floating button that appears once the
user has scrolled below the fold and, on click, returns to the top of the page. Unlike §5.19, this
is page-agnostic — the same behavior on every page — so it needed exactly one new `design-system`
component plus one wiring point in `climate-dashboard-react`'s shared `App.tsx` shell, not six
per-page integrations. Confirmed no existing vendored CSS or unused component covers this (unlike
§5.19's `JumpLinks` find) — this one was a genuine new build.

**`design-system`: new `BackToTop` component.** Composed from the existing `Button` (`iconOnly`,
`fullRadius`, `iconLeft="chevron-up"`, `variant="primary"`) rather than custom-styled from scratch
— `iconOnly` + `fullRadius` together already render a circular icon button. Wrapped in a `position:
fixed` container, bottom-right, respecting the same `env(safe-area-inset-*)` handling `App.tsx`
already applies at the shell level; `z-index: var(--__s9cmpx-z-index-modal)` to clear the sidebar
nav's own z-index, the same fix `ChartCard`'s expand overlay already needed for the same reason.
Visibility toggles on a plain `window` `scroll` listener once `window.scrollY` exceeds a `threshold`
prop (default 400px) — no `requestAnimationFrame` throttling, unlike an earlier draft of this
component: live Storybook testing showed rAF callbacks can go unfired in a backgrounded/non-visible
test-runner tab, so the simpler direct `setState` call is both correct and more testable.

**A real cross-browser scroll bug, found and fixed before merge.** The original implementation
called `window.scrollTo({ top: 0, behavior })` directly, mirroring the plan's draft. Live testing
turned up that `window.scrollTo({ behavior: 'smooth' })` does not reliably animate in some browser
contexts this app runs in — confirmed via direct `scrollY` polling, the call was a complete no-op
under `'smooth'` while `behavior: 'auto'` worked instantly and correctly every time. `Element.
scrollIntoView({ behavior: 'smooth' })` — the mechanism `scrollToJumpTarget` (§5.19) already
uses — did not share this problem. Fixed by having `BackToTop` require callers to pass a real
element id via `targetId` and call `scrollToJumpTarget(targetId, { reduceMotion })` directly rather
than scrolling the window itself; `targetId` is optional in the type but effectively required in
practice (the one real caller always has a landmark to point at), with an instant, non-animated
`window.scrollTo(0, 0)` retained only as a fallback if it's omitted.

**Two more issues found by Copilot's review, both real.** First: activating the button via
keyboard (Enter/Space while focused) and landing back below the visibility threshold would unmount
the button — `if (!visible) return null` — while it still held keyboard focus, silently dropping a
keyboard user's focus into the void. Fixed with a `focusWithin` state (`onFocusCapture`/
`onBlurCapture`) that keeps the button mounted as long as it still contains focus, independent of
`visible`. Second, smaller: a Storybook story's `window.matchMedia` override (forcing reduced
motion for deterministic testing) was applied at render time with no teardown, leaking into
subsequent stories in the same test run — fixed with proper `beforeEach`/`afterEach` story hooks.
Both fixes were pushed by Copilot directly to the PR branch; verified correct and merged in
alongside this session's own `scrollToJumpTarget` change (the two touched adjacent but
non-overlapping code, reconciled by hand where the same story file needed both).

**`climate-emissions-analysis-project`: one line in `App.tsx`.** `<BackToTop targetId="main-content" />`
added once to the shared app shell (outside `<Routes>`), reusing the same `<main id="main-content"
tabIndex={-1}>` element `App.tsx`'s existing route-change focus-management effect already targets
— a "back to top" click lands focus in the same place an in-app navigation already does. No
`App.test.tsx` was added: `BackToTop`'s own behavior is already covered by its Storybook stories in
isolation, and the one-line wiring itself was verified via live browser testing rather than a new
test file that would need to mock the app's full page/routing/API surface just to check one
declarative line.

Sequencing followed the plan: `design-system` PR #32 landed first, `climate-emissions-analysis-project`
PR #127 second. Live verification (dev server first, then production with service worker/Cache
Storage cleared) confirmed: the button is absent at the top of the page and appears once scrolled
past the threshold; clicking it moves focus to `#main-content`, confirmed via direct
`document.activeElement` inspection since real smooth-scroll-animation completion isn't reliably
observable through this session's own browser-automation tooling (a limitation of that tool in this
session, not of the shipped code — the underlying instant/`'auto'` scroll path, which the automation
tool *can* observe reliably, was separately confirmed correct). Deploy pulled `design-system` before
`climate-dashboard-react` on the Mac Mini, since the app's build failed against a stale
`design-system` checkout missing the new export — the same dependency-ordering lesson §5.19's deploy
already established.

**Post-ship bug report and fix (`design-system` PR, `fix/5.20.1-back-to-top-scroll-event`).**
Reported directly: on Country Profile, clicking a `JumpLinks` link ("Emissions"/"Per Capita")
scrolled the page but the button never appeared; same on Data Explorer's "Summary Statistics".
Reproduced live and root-caused precisely: `Element.scrollIntoView()` — the mechanism
`scrollToJumpTarget` uses — moved `window.scrollY` genuinely past the button's threshold, but fired
**zero** native `scroll` events on `window`, confirmed via a counting listener attached before the
call. `BackToTop`'s visibility toggle is a passive `scroll` listener with no other trigger, so it
never re-checked `scrollY` and never became visible — a bug in `scrollToJumpTarget` itself (shared
by every `JumpLinks` click across all six pages, not something specific to Country Profile or Data
Explorer), not in `BackToTop`'s own logic, which is why it hadn't surfaced during this release's own
verification: that testing exercised `BackToTop`'s click handler and visibility threshold in
isolation, never a *different* component's navigation making it visible.

Fixed in `scrollToJumpTarget` itself: dispatches a synthetic `scroll` event on `window` immediately
after calling `scrollIntoView` (covers the reduced-motion/instant case, where the position is
already final), and once more on the native `scrollend` event (covers the default smooth case, once
the animation has genuinely settled) — `scroll` listeners re-read `window.scrollY` fresh each time
they fire, so a synthetic event carrying no real position data is sufficient to make them re-check.
Fixed at the shared utility rather than inside `BackToTop`, since any other future passive
scroll-position observer would have hit the identical bug.

Verified the root cause and the fix directly in a real browser (not the Storybook test harness,
which — confirmed separately — does not reproduce the missing-event behavior at all, so a
Storybook-only regression test could not discriminate fixed from unfixed): a counting `scroll`
listener recorded 0 events across a genuine `scrollY` change from a raw `scrollIntoView` call;
manually dispatching a synthetic `scroll` event immediately after made a real `BackToTop` instance
become visible. A Storybook regression test was still added (`BecomesVisibleAfterAJumpLinksNavigationElsewhere`,
simulating a `JumpLinks`-style external `scrollToJumpTarget` call and asserting `BackToTop` reacts)
for documentation and as a partial guard, with this environment-specific limitation noted directly
in the test file rather than presented as a self-sufficient regression proof.

Deployed and verified live post-deploy (`labs.syena.io/ghg-emissions-analysis`, service
worker/Cache Storage cleared first): confirmed the deployed JS bundle actually contains the fix
(fetched and grepped for the `scrollend` token); attached a fresh counting `scroll` listener and
clicked a real Country Profile `JumpLinks` link, confirming the fix's synthetic dispatch genuinely
fires on a real click against production, not just in isolated testing. Full end-to-end
confirmation that the button visually appears after a real smooth-scroll animation completes
wasn't independently re-observable through this session's own browser-automation tooling — the
same pre-existing environment limitation already noted above for this release's initial
verification — but every other link in the causal chain (event fires → listener re-checks →
`BackToTop` becomes visible once `scrollY` crosses the threshold) was directly confirmed correct.

**Second post-ship bug report, with a screen recording: jump targets near the bottom of a page
undershoot the top.** Reported directly: clicking a `JumpLinks` link on Country Profile still left
part of the previous section visible above the target. Root-caused with exact scroll-geometry
math against production, independent of any animation-timing ambiguity: Country Profile's
`#key-stats` needs `958px` of scroll to reach the top, but the page's total scrollable range is
only `732px` — a `226px` undershoot the browser silently clamps to, no matter how the scroll is
triggered. The same shortfall (also `~226px`) reproduced identically on Data Explorer's
`#summary-stats` and (`116px`) on Overview's `#pct-change` — every page's *last* jump target,
confirming this isn't page-specific but a structural consequence of "not enough page left below
the target to scroll it flush to the top."

Fixed in `scrollToJumpTarget`: before scrolling, compute the shortfall (target's document-relative
position minus the page's current max scroll position) and, if positive, temporarily append an
`aria-hidden` spacer giving just enough extra scrollable room, removed once the scroll settles (on
the smooth path, `scrollend` with a 1s fallback timeout; on the reduced-motion/instant path, a
double `requestAnimationFrame`, not immediate synchronous removal — confirmed live that removing
the spacer in the same tick races the browser's own layout update and reintroduces the exact
undershoot the fix exists to prevent). Never adds visible empty space during a normal scroll-down;
only for the brief duration of an anchor jump that actually needs it.

Copilot's review caught one real correctness gap — the shortfall was measured via `el.offsetTop`,
relative to the element's `offsetParent` rather than the document origin, wrong for any target
inside a positioned ancestor (not currently true of any target in this app, but a latent bug
waiting for one) — fixed by switching to `getBoundingClientRect().top + window.scrollY`. Its
second suggestion (remove the spacer synchronously for the reduced-motion path rather than waiting)
was tried and found to be a real regression, caught by the same regression test the fix itself
added: reverting to synchronous removal made the test fail at the *original* unfixed shortfall
value. Landed the double-rAF approach instead.

Added a regression test (`ClickScrollsFullyToTopEvenNearPageBottom`) confirmed to genuinely
discriminate, unlike the earlier scroll-event fix's test — reverting the fix and re-running was the
same check used both times, but this time it actually failed without the fix (at the exact
shortfall amount) and passed with it, in Storybook's own browser-mode harness, not just live.

Deployed and verified: both repos fast-forwarded on the Mac Mini and `climate-dashboard-react`
rebuilt; confirmed via the deployed script's Vite content-hash filename that the exact just-tested
build (not a stale bundle) is what's live. Real-browser click-through verification of the visual
scroll landing was, once again, not reliably observable through this session's own
browser-automation tooling for the same pre-existing reason noted earlier in this section — by this
point in the session that tool's smooth-scroll and even basic click-registration reliability had
degraded further, unrelated to the shipped code.

**Third post-ship bug report: clicking a near-top target still scrolled, hiding the nav itself for
no benefit.** The user clarified precisely what they meant by the first bug report — not that the
scroll undershot (that was the second report, above), but that on Country Profile, clicking
"Emissions" or "Per Capita" scrolled the page a little even though both charts were already fully
visible without scrolling, just enough to push the `JumpLinks` nav row itself (and the page's own
`<h1>`) out of view, with nothing new brought on screen to show for it. Since the distance was
under `BackToTop`'s threshold, the button never appeared either — leaving no easy way back up
except a manual scroll.

**The fix.** `scrollToJumpTarget` now checks whether the target is already fully within the
viewport (`getBoundingClientRect().top >= 0 && bottom <= window.innerHeight`) before doing
anything else, and skips scrolling entirely when it is — focus still moves to the target either
way, for accessibility consistency. All of the shortfall-spacer and scroll-event-dispatch logic
from the two earlier fixes above now lives inside the "actually needs to scroll" branch, otherwise
unchanged.

**A regression test that took three iterations to get right, and a genuinely useful discovery about
this test harness along the way.** The first attempt asserted position immediately after a raw
`scrollIntoView` precondition-setup call — passed regardless of whether the fix was present,
because setting the precondition via `block: 'start'` positioned the target at *exactly* the
position a buggy click handler would also produce, so there was nothing left to distinguish. The
second attempt discovered, via a diagnostic dump, that this Storybook browser-mode test harness
does not unmount previous stories' rendered DOM between `play`-function runs within the same file —
every preceding story's own content (and scroll position) accumulates in `document.body`, so
nothing genuinely starts "at the top of the page" by default, which had been silently corrupting
several `rect.top`/`offsetTop` measurements across this whole release's testing without being
caught until now. Landed on establishing the precondition explicitly via `block: 'center'` (leaving
real room both above and below the target) combined with forcing reduced motion for deterministic
timing — confirmed by reverting the fix and re-running: fails at exactly the undesired scroll
position (`866` → `1298`) without it, passes with it.

Deployed and verified live against the exact reported scenario: on production, clicking "Per
Capita" on Country Profile now leaves `window.scrollY` at `0` (unchanged) while correctly moving
focus to the target — directly confirmed via `document.activeElement`, not just inferred. The
`Key Statistics` case (needs a real scroll) still correctly updates the hash and moves focus on
production; the visual scroll animation itself remained unobservable through this session's own
degraded browser-automation tooling, the same pre-existing limitation as the prior two fixes, not a
gap in the shipped logic itself.

**Fourth post-ship bug report: the third fix's "skip scroll when visible" was too broad, also
suppressing genuinely later sections.** The user confirmed the third fix was correct as far as it
went, but wanted an allowance for sections that *aren't* the page's top section: on Country
Profile, clicking "YoY Change" (the 3rd of 4 jump items) should always bring that section to the
top, since it visibly demonstrates the link actually did something; same for Historical Trends'
"GHG Share by Decade" (its 2nd and last item). Both had inherited the third fix's "already visible
→ skip" logic even though neither is the page's actual top section — they just happened to already
be on screen, which isn't the same thing.

**First attempt (`design-system` PR #36) was itself wrong, caught immediately by this session's own
live verification before the user ever saw it.** It redefined "top section" geometrically — a
target counts as top-section if its document-relative position is less than `window.innerHeight`
(i.e., "would this be visible with zero scrolling"). This looked reasonable and passed every
Storybook test, but live-testing it immediately after deploying turned up a direct counterexample:
on a common 1920x963 desktop viewport, Country Profile's "YoY Change" sits only 604px down the
page, comfortably under the 963px viewport height, so it still got wrongly classified as
top-section and its link still did nothing — reproducing the exact bug the user had just described,
on the very fix meant to resolve it.

**Corrected fix (`design-system` PR #37): "top section" is a structural fact, not a geometric one.**
Only `items[0]` — literally the first entry in a page's `JumpLinks` list, the one rendered right
after the `<h1>` — is ever eligible to skip its scroll when already visible; every other item
always scrolls flush to the top when clicked, regardless of whether it happens to already be
visible in whatever viewport is open. `scrollToJumpTarget` now takes an explicit `isTopSection`
option instead of inferring it, set by `JumpLinks`' own click handler as `item.id ===
items[0]?.id`. Callers that don't pass it — `BackToTop`'s own click, and a page's hash-on-load
handling — always scroll, correct in both cases. Both regression stories were rewritten around
this structural definition (clicking `items[0]` while visible must not scroll; clicking a later
item while visible must still scroll to top) and confirmed genuinely discriminating against PR
#36's geometric code, not just against the original unfixed behavior.

Deployed and verified live against both of the user's named examples: Country Profile's "YoY
Change" now reaches `scrollY = 556` with `BackToTop` appearing; Historical Trends' "GHG Share by
Decade" now scrolls (previously a no-op).

**Anchor-placement bug report, found alongside the above: "By Country" and "Country Comparison"
should land on the country picker, not just near it.** Reported directly: the Overview page's
"By Country" jump target sat on the section's `<h2>`, but the country picker it needs (shared with
the "% Change" section below) sits *above* that heading — confirmed live, heading at document
y=728 vs. picker at y=656, 72px above and scrolled out of view after the jump, leaving the exact
control a user needs to change their selection unreachable without an extra manual scroll up.
Scenario Comparison's "Country Comparison" target got the identical treatment for consistency, even
though its own picker already sat close to (just below) its heading rather than above it.

Fixed in `climate-dashboard-react` (PR #128, `OverviewPage.tsx`/`ScenarioComparisonPage.tsx`): the
`id` moved from each page's `<h2>` onto the `country-picker-row` div itself, so the picker — not
just a heading near it — is what lands flush at the top of the viewport. Both ids remain
unconditionally rendered (the picker rows were never gated on a selection, same as the headings
they replaced), so existing tests asserting target existence needed no changes. Deployed and
verified live: Overview's "By Country" now lands with "Select countries" flush at the top of the
viewport, heading and chart visible right below it.

**Fifth post-ship bug, found incidentally while live-verifying the fourth: the shortfall spacer's
own cleanup silently undid the fix it was cleaning up after.** While confirming "GHG Share by
Decade" now scrolls, direct `scrollY` polling caught it reaching the intended flush-to-top position
(`671`, with the second fix's shortfall spacer in place) and then snapping back down to `255` the
instant that spacer was removed on `scrollend` — reproducing, on the very page that motivated the
second fix, the exact "previous section stays visible" bug that fix exists to prevent.

Root-caused as **structural, not a timing race**: removing a spacer that is the *only* thing making
a target's position reachable will always make the browser re-clamp `scrollY` back down, because
`scrollTop` is continuously clamped to `[0, scrollHeight - clientHeight]` as the document resizes —
true however long the code waits first. The original regression test only looked correct because
its assertion happened to run before the scheduled removal fired.

Fixed (`design-system` PR #38): the spacer is never auto-removed on a timer or `scrollend` at all.
It's reclaimed lazily instead, at the very start of the *next* jump (tracked via a module-level
`activeSpacer`), once the user has already moved on from wherever it put them — a scroll adjustment
as a side effect of a new click isn't surprising the way one out of nowhere would be. A new
regression test (`ClickStaysFlushToTopAfterScrollSettles`) dispatches a real `scrollend` and waits
past the old 1s fallback window before asserting the position holds — confirmed genuinely
discriminating by reverting to the old removal logic and re-running (fails at `827.9`, reclamped).

**Two follow-up commits from Copilot's review, one reverted, one kept.** Its first suggestion
proactively reclaimed the spacer via a persistent `scroll` listener once the user scrolled back to
a position valid without it, rather than waiting for the next jump — a reasonable idea, but
verified (by pulling the commit and running `BackToTop.stories.tsx` alone) to introduce a real
regression: a listener armed by one story's spacer stays registered past that story's lifetime,
and firing on a later, unrelated test's own `scroll` event resized the document and re-clamped
`scrollY` synchronously, before `BackToTop`'s own visibility listener read it — the button never
appeared. Reverted with a comment explaining why, re-requesting review on the reverted state rather
than accepting the added complexity. Its second suggestion — switching one story's `userEvent.click`
to a raw DOM `.click()`, since Playwright's `userEvent.click` can auto-scroll a target into
interactable position before clicking, contaminating a scroll-position assertion for reasons
unrelated to the app's own logic — didn't touch the reverted source code, was verified independently
(typecheck, full story suite, full `npm run test`), and was merged.

Deployed and verified: the spacer/instant-scroll mechanics were confirmed directly on production
(shortfall computed, spacer appended, target lands exactly flush at `scrollY = 672`, and holds
after 1.2s) — the `smooth` animation itself remained unobservable through this session's own
degraded browser-automation tooling (confirmed separately that `behavior: 'auto'` scrolls
correctly in the same tab, isolating the gap to that tool's known inability to progress `smooth`
scroll animation frames, not a defect in the shipped code), the same pre-existing limitation noted
throughout this section.

**Sixth post-ship refinement: `items[0]`-only was too strict for a genuine second top-section
neighbor.** Reported directly: Country Profile's "Per Capita" chart sits stacked directly under
"Emissions" — close enough a neighbor that scrolling it away while both are already visible just
hides the nav for no benefit, the exact reasoning the fourth fix's `items[0]`-only rule was already
built on. A purely geometric definition couldn't distinguish this case from "YoY Change" (a
genuinely later section that must always scroll) — both are just a document position compared
against a viewport height, and the fourth fix had already demonstrated live that geometry alone
gets this wrong. The user flagged the follow-on concern directly: on a mobile viewport, "Per
Capita" is genuinely below the fold (with "Emissions" alone filling the screen), so any fix here
still has to scroll normally in that case.

Fixed (`design-system` PR #39) with an explicit per-item opt-in rather than another inference
attempt: `JumpLinkItem.topSection`, set by the page author on whichever later items they know are
close neighbors of the actual top section. It only widens *eligibility* for the existing
`alreadyFullyVisible` check — doesn't bypass it — so the mobile case the user raised is already
handled by the same check that handles every other viewport size, no separate mobile-specific
logic needed. Country Profile's `JUMP_ITEMS[1]` ("Per Capita") is the one place this flag is set
(`climate-emissions-analysis-project` PR #129); every other page's jump items are unaffected,
still defaulting to `items[0]`-only.

Two new regression stories prove both halves of the behavior: one confirms a marked item skips
its scroll when already visible (confirmed genuinely discriminating against the pre-flag code —
fails at `470` vs. expected `38`, passes with the fix), the other confirms the same marked item
still scrolls normally when it genuinely isn't visible. Deployed and verified live: "Per Capita",
fully visible on a 1920x963 viewport, no longer scrolls when clicked (`scrollY` stays `0`); with
the page pre-scrolled so "Per Capita" is off-screen, clicking it correctly targets the right
position (confirmed via the same instant-scroll mechanics check used earlier in this section,
isolating the same pre-existing `smooth`-animation observability gap rather than a code defect).

**Seventh post-ship bug report, with screenshots: the fifth fix's permanent shortfall spacer
strands `BackToTop` deep inside a large empty gap below the footer.** Reported directly: jumping
to Overview's last section ("% Change") opened a large blank area beneath the page's real content,
with the floating "Back to top" button rendering well below the footer, visibly detached from it.
Root-caused directly against the fifth fix's own design: the shortfall spacer `scrollToJumpTarget`
uses to bring a short page's last target flush to the top is deliberately never auto-removed (that
fix's whole point — removing it re-clamps scroll back down) — confirmed live, Overview's
`#pct-change` spacer measured `348px`, leaving the footer's `bottom` edge at `-1082px` (deep
off-screen above) once scrolled fully into the gap it leaves. `BackToTop`'s `position: fixed`
naturally kept rendering at its normal viewport-anchored spot inside that gap regardless — the
gap itself was an accepted, known tradeoff of the fifth fix, but this consequence for the button
specifically wasn't previously addressed.

Fixed (`design-system` PR #40) with a new optional `BackToTop.avoidSelector` prop: once the
matched element's (the app's real `<footer>`) top edge rises above the viewport's bottom edge, the
button's `bottom` offset grows to keep it docked just above that edge instead of the viewport's —
and keeps growing as the user scrolls further into the gap, so the button scrolls out of view
entirely (rather than staying pinned in empty space) once even the footer itself has scrolled
past. Wired in `climate-dashboard-react` (PR #130) as `<BackToTop targetId="main-content"
avoidSelector="footer" />`, matching `Footer`'s own real `<footer>` element.

**Copilot's review caught a real math error before merge.** The initial implementation's
`dockOffset` calculation double-counted the button's own base 24px bottom margin, docking it 24px
higher above the footer than intended — still functionally correct (never overlapping the footer),
but with a 40px gap instead of the intended 16px. Pulled the fix (`ad1291c`) and verified
independently (typecheck, full `BackToTop`/`JumpLinks` story suite — 17/17, full `npm run test` —
197/197) before merging, per this session's established practice of not trusting a bot-authored fix
on its own say-so.

Deployed and verified live against the exact reported scenario: on production, jumping to
Overview's `#pct-change` and forcing the scroll to its settled position (the same instant-scroll
technique used to isolate this session's known `smooth`-animation observability gap) shows the
button's bottom edge at `y=542` and the footer's top edge at `y=558` — a clean `16px` gap, matching
`DOCK_GAP_PX` exactly, with the button visibly docked just above the footer rather than stranded
in empty space below it.

**Eighth post-ship fix, addressing the seventh fix's own root cause directly: never scroll a jump
target past the document's natural end.** The seventh fix (`avoidSelector`) treated the symptom —
`BackToTop` rendering inside the blank gap a short page's shortfall spacer leaves below the
footer — without touching the gap itself. Reported directly, with screenshots, once that symptom
was fixed: the gap was still there, and still looked wrong — jumping to a short page's last
section (e.g. Historical Trends' "GHG Share by Decade") pulled it flush to the very top, leaving a
large blank area below the real content with the footer scrolled far out of view above it. The
user asked directly whether the footer could instead always stay at the bottom of the page.

Fixed (`design-system` PR #41) by removing the shortfall-spacer mechanism entirely, rather than
adjusting its size. The spacer (introduced by the second post-ship fix, above) existed specifically
to defeat the browser's own scroll clamp — `scrollTop` is naturally bounded to
`[0, scrollHeight - clientHeight]` — so a target could always reach exactly flush-to-top even on a
page too short to naturally support that. Once nothing artificially extends `scrollHeight`, that
native clamp already produces the requested behavior on its own: the page scrolls exactly as far
as its real content allows, landing the footer at the bottom with no blank space past it. Accepted
tradeoff, stated directly: a short page's last section may no longer land perfectly flush at the
very top (part of the previous section can remain visible above it) — preferred over ever showing
blank space past the page's real content. This also deleted a meaningful amount of complexity that
existed only to manage the spacer's own lifecycle (the module-level `activeSpacer` tracking and its
lazy-reclaim-on-next-jump logic from the fifth fix).

The two spacer-specific regression tests (`ClickScrollsFullyToTopEvenNearPageBottom`,
`ClickStaysFlushToTopAfterScrollSettles`) were replaced with one verifying the new behavior
(`ClickNeverScrollsPastTheDocumentsNaturalEnd`) — confirmed genuinely discriminating against the
removed spacer mechanism by reverting and re-running (a spacer is created when none is expected).
Copilot's review was clean, independently re-verified (typecheck, full `JumpLinks`/`BackToTop`
story suite, full `npm run test` — 196/196) before merging. `BackToTop.avoidSelector` (seventh fix)
remains independently useful — general "dock above the footer" behavior for any deep scroll, not
specific to the now-removed spacer — so it was kept rather than reverted alongside the mechanism
that originally motivated it.

Deployed and verified live against the exact reported scenario: on Historical Trends, forcing the
scroll to "GHG Share by Decade"'s settled position shows `scrollY` (`294`) exactly equal to the
document's natural max scroll, the footer's `bottom` edge (`905px`) landing right at the viewport's
own bottom edge (`913px`, an 8px difference consistent with layout rounding) — no spacer in the
DOM, no blank space past the footer — confirmed visually via screenshot.

**Ninth post-ship bug report, a direct consequence of the eighth fix: `BackToTop` never appears on
a page short enough that its whole natural scroll range sits under the visibility threshold.**
Reported directly: on Historical Trends, clicking "GHG Share by Decade" now correctly scrolled
down (the eighth fix), but the button still never appeared. Root-caused directly: Historical
Trends' entire natural scroll range is only `~294px`, under `BackToTop`'s `400px` default
`threshold` — confirmed live, `scrollY` reached exactly `294` at the page's genuine bottom, still
short of `400`. The eighth fix's removal of the shortfall spacer was the direct cause of this
becoming visible: that spacer used to inflate `scrollY` well past the threshold as a side effect
on every short page, masking that the raw-pixel-only visibility check could never fire on a page
this short at all, regardless of scroll position.

Fixed (`design-system` PR #42) by adding a second, independent trigger alongside the existing
threshold check: once `scrollY` reaches the document's own natural maximum
(`scrollHeight - clientHeight`), the button becomes visible regardless of how few pixels that
represents — a user who has genuinely reached the end of a page's real content should have a way
back to the top, however short that page happens to be. A new regression story
(`VisibleAtNaturalBottomEvenUnderThreshold`) sets `threshold` to a deliberately unreachable value
(`100000`) to isolate the new trigger from the existing pixel check, confirmed genuinely
discriminating by reverting and re-running (the button never appears against the old code, even
scrolled to the real bottom, with real overflow confirmed present via a diagnostic dump rather
than assumed — the test's first draft used too little content and silently produced zero natural
overflow in this exact test environment, which would have made it pass vacuously either way).
Copilot's review was clean; independently re-verified (typecheck, full `JumpLinks`/`BackToTop`
story suite — 17/17, full `npm run test` — 197/197) before merging.

Deployed and verified live against the exact reported scenario: on production, forcing the scroll
to "GHG Share by Decade"'s settled position on Historical Trends now shows the button present at
`scrollY: 184` — well under the `400px` threshold, confirming the new "at natural bottom" trigger
is what's firing, not the old pixel check — confirmed visually via screenshot alongside the eighth
fix's own footer-flush-at-bottom result in the same view.

### 5.21 Dependency Maintenance from the 2026-08-11 Infra Audit (Shipped, `climate-emissions-analysis-project` PR #131)

A `/security-infra-audit` run against the Mac Mini deployment (published as an
[Artifact](https://claude.ai/code/artifact/da0a1846-4422-4c32-910f-05613ba5137d), later updated
in place as findings were resolved) flagged two Medium-severity dependency findings — real CVEs,
both confirmed to have no exploitable path in this app as actually built and used:

- **Backend** (`pip-audit`): ~60 advisories, all landing in `jupyterlab`, `jupyter-server`,
  `mistune`, `pillow`, `GitPython`, `pytest`, and `setuptools` — none imported by `api/` or
  `app.py`, and no Jupyter server running on the host. `fastapi`/`uvicorn`, the actual production
  dependencies, were clean.
- **Frontend** (`npm audit`, `climate-dashboard-react/`): `react-router-dom` 7.18.1
  (GHSA-qwww-vcr4-c8h2, an RSC-Mode CSRF bypass — this app uses plain `<BrowserRouter>`, not
  React Router's framework/RSC mode, so the vulnerable path was unreachable), plus 5 transitive
  build-tool packages not in `package.json` at all.

Both were marked routine maintenance rather than urgent, and fixed the same day. Five of the
flagged backend packages are transitive (not in `requirements.txt`); each of their real requirers
(`nbconvert`, `matplotlib`, `streamlit`, `jupyterlab`/`notebook`, `jupyterlab` respectively)
already permits the fixed version via an open-ended constraint, so each just needed a new explicit
pin. `jupyterlab` itself needed care: `notebook==7.5.6` caps `jupyterlab<4.6`, so the fix bumps the
floor to `jupyterlab>=4.5.10` (the 4.5.x fix) rather than `4.6.2`, which would have forced bumping
`notebook` too. `pytest==8.3.4 -> 9.0.3` is a major-version bump — checked against pytest's own
changelog and this repo's actual usage first (no removed APIs touched, no `pytest.ini`/
`pyproject.toml` config to migrate), then verified directly: full `api/tests` suite (104/104) and
a Week 1 notebook end-to-end execution both pass clean against the upgraded toolchain.

On the frontend, `npm audit fix` (no `--force`) resolved all 6 flagged packages via lockfile-only
changes — `react-router-dom`'s fix (7.18.2) lands inside the existing `^7.18.1` range, so
`package.json` itself didn't need touching. `npm test` (90/90), `npm run build`, and `npm run
lint` all verified clean afterward.

`pip-audit` and `npm audit` both re-ran clean after the fixes. The audit Artifact itself (linked
above) was updated in place to mark both findings Resolved, with before/after evidence — the same
treatment already used earlier the same day for an unrelated host-level finding (AirPlay Receiver)
from the same audit run. That host-level finding and the rest of the audit's non-dependency areas
are intentionally not narrated here — this project's docs track the app/curriculum itself, not
host-specific infrastructure checks.

### 5.22 Sovereign-Scope Gas Coverage & Historical `scope` Parameter (Shipped, `climate-emissions-analysis-project` PR #133)

**Status: Shipped.** Another mentor addition tracked outside the internship curriculum, in the
same category as §5.6/§5.7/§5.21 — not a curriculum scope change. Triggered by design work on a
separate conversational-agent sub-project (an MCP server wrapping this API; design doc kept
outside this repo, not yet started), which surfaced two gaps in the API's historical-data coverage
while defining its tool set. Recorded here because both changes touch `api/`, independent of
whether the agent project ships.

| Aspect | Detail |
|---|---|
| Gap found | `load_raw_sovereign()` (backing `/overview` and, indirectly, the "All Countries" tier) carried only `co2` — `methane` and `nitrous_oxide` were unavailable at sovereign scope (~218 countries), unlike `load_raw()` (~40 expanded countries), which already carried all three. Neither `/historical/timeseries` nor `/historical/decade-composition` had a scope concept at all — both silently resolved against the expanded ~40 only, via `load_raw()`, regardless of what a caller might want. |
| Fix 1: three-gas sovereign loader | `load_raw_sovereign()`'s `usecols` extended to `["country", "year", "co2", "methane", "nitrous_oxide", "iso_code"]`. Same `iso_code.notna()` filter, same year range — additive columns only. Traced every consumer before shipping: `/overview` is the sole caller, and every touchpoint there explicitly selects `co2` only — the two new columns are inert for it. `/overview/world-map-series` uses a fully separate loader (`load_world_map_series()`, reads `owid-co2-data.csv` directly), unaffected regardless. |
| Fix 2: `scope` param on **both** historical endpoints | New `scope: Literal["featured", "expanded", "sovereign"] = "expanded"` parameter on `/historical/timeseries` **and** `/historical/decade-composition`, via a shared `_scoped_pool()` helper in `historical.py`. `featured`/`expanded` continue to use `load_raw()` as before (filtered further to `FEATURED_COUNTRIES` for `featured`); `sovereign` uses the now-three-gas `load_raw_sovereign()`. |
| Widened from the original proposal | The original design only covered `/historical/timeseries`. Verified directly against the code before implementing: `/historical/decade-composition` shared the identical expanded-only limitation and already aggregated all three gases, so it would have been a near-identical follow-up gap left for later — extended to both endpoints in the same change instead. |
| Default diverges from `forecasts.py`/`scenarios.py` on purpose | Those routers default their own (separately-defined, not shared) `Scope` to `"featured"`. Both historical endpoints default to `"expanded"` instead, because that's the pool they already implicitly served before this change via `load_raw()` — matching it is what keeps this change backward-compatible. | 
| Backward compatibility | The dashboard client (`climate-dashboard-react/src/api/client.ts`) sends only `countries`/`gas` to these endpoints, never `scope` — confirmed by direct inspection before shipping. With `scope` defaulting to `"expanded"`, every existing dashboard call resolves identically to before. `get_timeseries`'s no-`countries` fallback (`FEATURED_COUNTRIES[:5]`) stays scope-independent; `get_decade_composition`'s no-`countries` fallback (the whole pool) now generalizes to "the whole *selected-scope* pool," a direct extension of its prior "whole expanded pool" behavior. |
| `/countries` gains a `sovereign` field | Alongside the existing `featured`/`expanded` lists, `/countries` now returns the full ~218-country sovereign name list — the canonical list a future MCP-layer country-resolution guard needs to validate a sovereign-scope query at all (previously only ~40 names were exposed anywhere). Also gives an accurate denominator for an eventual "10 of 218"-style annotation, an open item both this change and the separate MCP design doc had flagged. Behavior change: `/countries` can now 503 on a missing raw CSV, which it never could before this field existed. |
| Response schema | `HistoricalTimeseriesResponse`/`HistoricalDecadeCompositionResponse` unchanged — no new fields. Any scope/trimming annotation for agent consumption is an MCP-layer concern, not part of this API's response shape. |
| Testing | New: `load_raw_sovereign()` unit test (methane/N₂O spot-checked against the fixture); `scope` tests for all three values on both historical endpoints, each with an explicit "no `scope` sent → byte-identical to before" case; `/countries` test confirming the new `sovereign` field and its 503 path. 112/112 total pass, including 8 new/changed — each independently confirmed to fail against the pre-change code (`git stash` + re-run) before being trusted. |
| Verification | Smoke-tested live against real local data post-implementation: `scope=sovereign` reaches Bhutan (outside the ~40 expanded countries, present in the real dataset) with real methane figures; no-`scope` calls confirmed byte-identical to pre-change responses. |
| Not a curriculum scope change | Internship Weeks 1–5 and §§1–4 are unaffected; this is `api/`-only, same category as the rest of §5. |

---

## 6. Post-Ship Corrections to Internship Curriculum Notebooks

> **This section is different from §5.** §5 documents the mentor's *separate, post-internship*
> reference architecture — additional scope, not a correction. This section instead documents
> corrections to the internship curriculum itself (Weeks 1 and 3), found after the fact via
> external comparison, not a scope change. Interns who already completed these weeks are not
> required to redo them for certification; the corrections apply going forward.

### 6.1 Regression Target Leakage & Sovereignty Filter Fixes (Release 4)

**Status: Shipped** — tracked in `ENHANCEMENTS.md` Release 4. Found by comparing this repo's
Week 1/3 notebooks against a separate intern's independent implementation of the same
curriculum (`Maulik-17/climate-ghg-trend-analysis`); every claim below was verified directly
against this repo's own current code and data before being adopted, not taken on the other
project's word. Three PRs merged (#98 Week 1, #99 Week 3, #100 `api`/`app.py`); deployed to
the Mac Mini and verified live — the Overview "All Countries" tier shows 218 countries in
production, and an on-demand `ghg-data-refresh` run confirmed the notebook fixes re-execute
cleanly in the exact environment the weekly job uses (no hard-fail or soft-flag on the
220→218 count shift, well under the 5% validation threshold).

| Aspect | Detail |
|---|---|
| Regression target leakage | Week 3's `FEATURES` includes `co2_yoy_pct_change` (a same-row function of `co2`), while `TARGET` was same-year `co2`, unshifted — `co2_yoy_pct_change` and `co2_lag1` together algebraically determine `co2` exactly, so the feature leaks the answer. Present in every version of `week3_regression.ipynb`'s git history |
| Fix: next-year target | Introduced `REGRESSION_TARGET = 'target_co2_next'` (`co2` shifted forward one year per country) in `notebook/constants.py`, alongside — not replacing — the existing `TARGET = 'co2'`, which `week4_ets_forecasting.ipynb` still needs for same-year ETS evaluation. `FEATURES` itself is unchanged; under the new framing, `co2_yoy_pct_change` becomes a legitimate "known-as-of-year-Y" input to a Y+1 target |
| Downstream effects | Each country's most recent year loses its training/test row (no next-year actual to shift into); §3.8's recursive forecast loop and its `build_forecast_features` helper needed restructuring — the old loop and its rolling-mean/YoY lookback windows were built around same-year prediction and had already been forced into a one-year-stale approximation by the same leak; MAE/RMSE now measure a genuinely harder "predict next year" task, not directly comparable to pre-fix numbers |
| Sovereignty filter gap | `notebook/constants.py`'s `NON_SOVEREIGN` list never wrongly excludes a real country, but is missing two null-`iso_code` entities — `Kosovo` and bare `Ryukyu Islands` (only `"Ryukyu Islands (GCP)"` is listed). Both immaterial (Kosovo's max annual `co2` is 8.8 Mt; Ryukyu Islands has no `co2` data at all) and absent from the current `data/selected_countries.json` expanded set — verified empirically, not assumed |
| Fix: `iso_code.notna()` | Switched Week 1's operative filter to `df_raw['iso_code'].notna()` (220 → 218 sovereign countries), keeping `NON_SOVEREIGN` as a reviewable audit record with a runtime drift-check logging any divergence between the two, rather than deleting the list outright |
| Three-way mirror fix | The identical `NON_SOVEREIGN`-based gap existed independently in `api/data_loaders.py`'s and `app.py`'s own hand-mirrored `load_raw_sovereign()` (used for the Overview "All Countries" tier and the world map) — both switched to the same `iso_code.notna()` filter for consistency across all three copies |
| Not a curriculum scope change | §3.1's problem-framing text already described a "year Y+1" target before this fix existed — the notebook implementation is what's catching up to the spec, not the other way around |
