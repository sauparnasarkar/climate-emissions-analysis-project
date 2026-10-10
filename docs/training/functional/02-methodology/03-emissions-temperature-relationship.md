# The Emissions–Temperature Relationship

> Part of the [Functional Series](../README.md). Warming tracks the CO₂ humans have put into the
> air over time. This document explains how the platform measures that relationship from
> observed data, how it compares with the IPCC's own figure, and how much weight the number can
> carry. The input series are described in
> [Concentrations and Temperature](../01-data-sources/02-concentrations-and-temperature.md).

## 1. Cumulative, not annual

A single year's emissions say little about that year's temperature: CO₂ stays in the atmosphere
for a very long time, so today's warming reflects everything emitted so far. The climate-science
term for the resulting relationship is the **transient climate response to cumulative CO₂
emissions (TCRE)**: roughly, how many degrees of warming follow from each additional trillion
tonnes of CO₂.

The platform measures a simplified, data-driven analogue of it: a straight-line fit of the
observed temperature anomaly against the observed cumulative CO₂ emitted since 1850.

| | |
|---|---|
| **Temperature** (y) | Berkeley Earth global anomaly relative to 1850–1900, annual, 1850–2024 |
| **Emissions** (x) | World cumulative CO₂ since 1850: fossil fuels and cement, **plus land-use change**, from OWID/Global Carbon Project, including international aviation and shipping |
| **Fit** | Ordinary least squares with an intercept; 175 annual points |
| **Unit of the answer** | °C per 1,000 GtCO₂ (a thousand billion tonnes) |

## 2. The result

| Quantity | Value |
|---|---|
| Slope, total anthropogenic CO₂ | **0.486 °C per 1,000 GtCO₂** |
| 95% interval (robust to autocorrelation) | 0.442 – 0.530 |
| R² | 0.89 |
| Cumulative CO₂ since 1850, to 2024 | about 2,750 GtCO₂ total; 1,849 GtCO₂ fossil and cement only |
| Same fit, fossil and cement only | 0.749 (0.705 – 0.793) |

**Reading R² = 0.89.** Cumulative emissions account for most of the long-run variation in the
temperature record. That is a statement of association over 175 years in which both series
trend upward; it is not, by itself, proof of cause. The cause is established by physics and
other evidence, and the platform states plainly that this is "context, not proof".

## 3. Comparison with the IPCC range

The IPCC's Sixth Assessment Report gives a TCRE best estimate of 0.45 °C per 1,000 GtCO₂, with a
**likely** range of 0.27–0.63 (Working Group I Summary for Policymakers, D.1.1; "likely" means at
least a 66% probability). A *95% statistical interval* around a fitted slope and a *66% assessed
range* from many lines of evidence are different kinds of interval, so "overlaps" below means the
two are consistent, not that one validates the other.

| Measure | Platform | Versus IPCC AR6 |
|---|---|---|
| Total-CO₂ slope | 0.486 | Inside the range; 1.08 × the best estimate; the 95% interval overlaps the range |
| Fossil-and-cement-only slope | 0.749 | Above the range |

The fossil-only figure sits higher because it leaves out land-use emissions: the same warming is
being attributed to a smaller amount of CO₂, so each tonne appears to do more. The comparison is
only meaningful for the total-CO₂ version, which matches the IPCC definition more closely, and
even that is an analogue, not a restatement, because:

- the regression also absorbs warming from **non-CO₂ gases and aerosols** that rose and fell
  alongside CO₂;
- it uses **one observed climate history**, not an ensemble of Earth-system models;
- it depends on **land-use emission estimates** that are themselves uncertain
  (about ±2.6 GtCO₂ per year, one standard deviation, in recent decades).

## 4. How the uncertainty is handled

The 175 annual points are not independent: a warm year tends to follow a warm year. Ignoring that
makes the fit look more certain than it is.

| Check | What it shows |
|---|---|
| Residuals are autocorrelated | Lag-1 autocorrelation 0.59; Durbin–Watson 0.80 (a value near 2 would mean none) |
| Robust standard error | Newey–West (HAC) standard error 0.022, against 0.013 from the naive formula: about 1.7 × larger, so the naive interval would be too narrow |
| Lag-length sensitivity | The interval is 0.447–0.524, 0.442–0.530 and 0.436–0.536 for 4, 8 and 16 lags |
| Block bootstrap | Resampling the residuals in 10-year blocks, 2,000 times, gives 0.435–0.536, close to the robust interval; other block lengths from 5 to 30 years give intervals of similar width |
| Holdouts | The fit is also tested by fitting on early decades and predicting later ones, against a simple baseline |

## 5. The relationship is not constant

Fitting only more recent periods gives larger slopes:

| Fit period | Slope (°C per 1,000 GtCO₂) |
|---|---|
| 1850–2024 | 0.486 |
| 1900–2024 | 0.527 |
| 1950–2024 | 0.581 |
| 1970–2024 | 0.630 |

If CO₂ alone set the temperature through a fixed proportionality, the slope would not drift this
way. The drift is consistent with other influences changing over time (non-CO₂ gases, aerosols,
the pace of ocean heat uptake), and it means the headline number is the best single summary of
the full record, not a law. The platform uses the full-range value for its scenario translation
and shows the shorter windows so a reader can see the sensitivity.

## 6. What this is not

- Not a climate model: no physics, no ocean, no feedbacks.
- Not an attribution of warming to any country. Country shares describe each country's part of
  *cumulative emissions*; no country series is regressed against temperature.
- Not a forecast on its own. Its use in the scenario translation is described in
  [Scenarios](04-scenarios-and-temperature-mapping.md).

## 7. Where this appears in the dashboard

| Dashboard element | What it shows |
|---|---|
| Climate Correlation page | The relationship chart, the headline slope, and an IPCC AR6 comparison strip |
| "How this number was derived" | A seven-step explanation: what is regressed on what, the uncertainty, sensitivity, stability, the IPCC comparison, data and licences, and what the number is *not* |
| "Methodology & sources" | The sources table (coverage, vintage, licence), the baseline used by each view, the temperature offset and the two-totals note |

## See also

- [Scenarios and Temperature Mapping](04-scenarios-and-temperature-mapping.md)
- [Limitations and Uncertainty](05-limitations-and-uncertainty.md)
- [Technical: Multi-Source Data Pipelines](../../technical/01-data-science-ml/05-multi-source-pipelines.md):
  how the fit and its uncertainty are computed
