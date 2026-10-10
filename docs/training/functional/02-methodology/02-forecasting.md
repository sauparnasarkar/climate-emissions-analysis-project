# Forecasting: Models, Evaluation and What the Results Mean

> Part of the [Functional Series](../README.md). The platform fits four kinds of model to each
> country's CO₂ series, tests them on years they have not seen, and uses one of them (a
> damped-trend exponential smoothing model) for its long-range forecasts. This document explains
> in plain language what each model does, how it is judged, and why the winner on one test is
> not the model used for the long view.

## 1. The question being asked

Given each country's CO₂ emissions up to some year, what will they be afterwards? There are two
different versions of that question, and the platform treats them separately:

| Version | Horizon | Example |
|---|---|---|
| **Next-year prediction** | One year ahead, given the recent past | Predict 2021 from 2018–2020 |
| **Long-range forecast** | Many years ahead, with nothing new observed along the way | Project 2019 to 2043 from data to 2018 (and, for scenarios, 2025 to 2040 from data to 2024) |

Models that are good at one are not necessarily good at the other. This is the single most
important point in this document.

## 2. The four models

| Model | Plain-language idea | Trained on |
|---|---|---|
| **Naive baseline** | Next year equals this year | Nothing to train; the benchmark every model must beat |
| **Linear regression (LR)** | A straight-line relationship between next year's CO₂ and recent levels, a 5-year average, the year and the year-on-year change | Each country separately, 1990–2018 |
| **Random forest (RF)** | Many decision trees voting on the same features; captures non-linear patterns | One model pooled across all 40 countries, 1979–2018, with a country identifier |
| **ETS(A,Ad,N), "Holt's damped trend"** | A smoothed level plus a trend that fades over time; uses only the series itself | Each country separately, 1990–2018 |

A per-country random forest (about 25 rows per country) is also trained, deliberately, as a
demonstration: with so little data it memorises noise, which is the reason the production
random forest is pooled across countries.

**Why damped?** An ordinary trend model extends a constant slope indefinitely, and over 20 years
that produces implausible numbers (growth forever, or emissions going negative). Damping lets the
trend fade towards zero, so a rising series flattens and a falling series levels out. Three fitted
numbers describe each country:

| Parameter | Meaning | Across the 40 countries |
|---|---|---|
| **α** (level smoothing) | How strongly the latest observation moves the estimate. Near 1: the model trusts the newest year; near 0: it averages over a long history | Median 0.84; at least a quarter of countries sit at the upper bound of 1.0 |
| **β\*** (trend smoothing) | How quickly the trend itself is updated | Median 0 (the trend is effectively fixed for at least half the countries); maximum 0.70 |
| **φ** (damping) | How fast the trend fades each year; 1 means no damping | Median 0.97 (range 0.80–0.995). With φ = 0.97 a trend keeps about half its strength after 25 years |

## 3. How the models are judged

**A fair test uses unseen years in time order.** Models are fitted on 1990–2018 and tested on
2019–2023. Years are never shuffled, because shuffling would let a model see the future it is
supposed to predict. The test window includes the 2020 pandemic drop and the rebound after it,
which makes it a deliberately hard test.

**Two error measures**, both in millions of tonnes of CO₂ per year:

| Measure | What it is | Behaviour |
|---|---|---|
| **MAE** (mean absolute error) | The average size of the miss | Easy to read |
| **RMSE** (root mean squared error) | Like MAE but squares misses first | Penalises large misses more |

Because these are absolute, large emitters have large errors by construction. The table below
therefore reports the **median across the 40 countries**, so one country (China) does not set the
number:

| Model | Median MAE, 2019–2023 (MtCO₂ per year) |
|---|---|
| Linear regression | 4.6 |
| Random forest (pooled) | 7.0 |
| Naive baseline | 16.8 |
| Random forest (per country) | 27.4 |
| ETS(A,Ad,N) | 28.0 |

**Best model by country (MAE):** linear regression for 28 of 40 countries and the pooled random
forest for 12. ETS is never the single best on this test. It beats the naive baseline for 9 of 40
countries and the pooled random forest for 2 (China and the United States).

## 4. Why ETS is still the long-range model

The ranking above is not a like-for-like contest, for three reasons:

1. **Different tasks.** The regression models predict *next year* using the *actual* lagged
   values for each test year, so they are corrected by reality every year. ETS forecasts all of
   2019–2023 from data ending in 2018 and sees none of it.
2. **A shock the model cannot see.** A trend-smoothing model cannot anticipate a pandemic. The
   linear model does well here because it has no strong memory of pre-pandemic momentum to defend.
3. **Stability over long horizons.** Linear regression can predict negative CO₂ for countries on a
   declining path (the United Kingdom, Germany and Japan are examples). A recursive forecast feeds
   each prediction back in as the next input, so a negative value corrupts every later step and
   the forecast diverges. The pooled random forest stays within its training range but cannot
   extrapolate a trend outside it. ETS with damping extrapolates a *fading* trend and produces
   bounded, interpretable paths, with confidence intervals.

For a 20-plus-year projection the platform therefore uses ETS, and shows the regression results
as the evidence of short-horizon skill, not as the forecast.

## 5. Uncertainty

- **95% confidence intervals** accompany every ETS forecast. They widen with the horizon, and in
  absolute terms are widest for large emitters.
- The intervals describe the statistical noise in the fitted model. They do **not** include the
  risk that something structural changes (a new policy, a technology shift, a war), which is why
  a forecast here is a continuation of past behaviour, not a prediction of what will happen.
- **Holdout results are a short-horizon check.** Success over five test years is not evidence of
  skill over twenty.

## 6. The second ETS fit used for scenarios

The forecasts above stop learning at 2018 so that 2019–2023 can be held back for testing. That is
right for evaluation and wrong for a scenario baseline: a forecast that has never seen 2019–2024
starts the scenarios at a level that does not continue from the observed 2024 data. The scenario
module therefore refits the same model on **every observed year (1990–2024)**. Details, and the
evidence for the choice, are in [Scenarios](04-scenarios-and-temperature-mapping.md).

## 7. Where this appears in the dashboard

| Dashboard element | What it shows |
|---|---|
| Forecasts page, per-country chart | Training history (1990–2018), holdout actuals (2019–2023) and the ETS forecast with its 95% interval to 2043 |
| Forecasts page, five-model comparison | MAE and RMSE for the models above, per country |
| Forecasts page, ETS parameters | The fitted α, β\* and φ for every country |
| About page | A one-line summary of the pipeline, models and forecast horizon |

## See also

- [Trend Analysis](01-trend-analysis.md)
- [Scenarios and Temperature Mapping](04-scenarios-and-temperature-mapping.md)
- [Limitations and Uncertainty](05-limitations-and-uncertainty.md)
- [Technical: Regression Models](../../technical/01-data-science-ml/03-regression-models.md)
- [Technical: Time-Series Forecasting](../../technical/01-data-science-ml/04-time-series-forecasting.md)
