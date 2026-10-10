# Limitations and Uncertainty

> Part of the [Functional Series](../README.md). Every claim the platform makes has a limit. This
> document gathers them in one place, ranks where the uncertainty is largest, and maps which
> dashboard element carries which caveat. Read it before quoting any figure from the
> Findings section (in development).

## 1. Four kinds of uncertainty

| Kind | What it is | Example here |
|---|---|---|
| **Measurement and data** | The inputs are estimates or reconstructions | PRIMAP-hist before about 1970; land-use CO₂ (about ±2.6 GtCO₂ per year); the preliminary temperature dataset |
| **Statistical** | Noise in a fitted model | The 95% intervals on ETS forecasts and on the 0.486 slope |
| **Structural** | The model form may be wrong | A straight line through cumulative emissions; one fixed damping pattern per country |
| **Scenario** | The future depends on choices nobody has made | The 2% and 5% reductions; the held-flat land use; the rest-of-world share |

The intervals the platform shows cover only the **statistical** kind. The other three do not
appear as bands, which is why a narrow interval is not the same as a confident prediction.

## 2. Where the uncertainty is largest

| Result | Main sources of uncertainty | Confidence |
|---|---|---|
| Historical emissions by country, since 1990 | Inventory methods; the source choice (a few percent between sources) | High for trend and rank order |
| Global temperature anomaly | Preliminary dataset; baseline convention (a few hundredths of a degree) | High for the multi-decade trend; lower for the latest single year |
| Atmospheric CO₂ since 1959 | Direct measurement | Very high |
| Emissions–temperature slope | Autocorrelation, non-CO₂ forcing, land-use estimates, non-constant relationship | Moderate: inside the IPCC range, but an analogue |
| ETS forecasts to 2043 | Everything outside the past trend; five-year holdout is the only test | Low for levels beyond about a decade; better as a statement of "if trends continue" |
| Scenario pathways to 2040 | The scenarios are assumptions, not forecasts | Comparative only |
| Implied temperature, 2040 | All of the above, compounded, with only slope uncertainty shown | Comparative only |

## 3. Limits specific to each stage

**Data**
- Territorial emissions only: emissions embodied in traded goods are not allocated to the
  consuming country.
- International aviation and shipping are included in the OWID World total but not in
  PRIMAP-hist or in country sums.
- The 40-country expanded set holds 92.2% of 2024 emissions; the other ~175 countries are in the
  rankings but not in the models.
- The latest year is the most likely to be revised.

**Forecasting**
- Univariate: each ETS forecast uses only that country's own CO₂ history. It does not know about
  policies, prices, energy transitions, wars or recessions.
- The test is five years long and contains the pandemic. Success there is not evidence of skill
  over twenty years.
- One model family (damped trend) is used for the long view; no model selection among others.
- Single-year data anomalies are flagged but not altered (Kuwait's 1991 oil fires distort its fit).

**Relationship and scenarios**
- The slope is estimated from a single observed history in which emissions, other gases and
  aerosols all rose together.
- Scenarios apply one percentage reduction to every country alike.
- Land use is held flat; rest-of-world follows the covered countries.
- Level figures in 2040 start from a five-year average anchor (1.32 °C), so they are only as good
  as that choice.

## 4. What the platform does to keep itself honest

- **Labels where the number is read.** Scenario results are marked "Illustrative · implied
  outcomes, not projections"; the relationship is marked "context, not proof"; the 1970-onward
  all-gas view is explicitly "not TCRE".
- **Figures come from the data, not from prose.** Numbers on the relationship and scenario pages
  are read from pipeline output, so a figure and its explanation cannot drift apart.
- **No attribution to countries.** Warming is never assigned to a country.
- **Failing safe.** If a source is stale or incomplete, the platform shows an explicit gap and a
  reason rather than a stale or partial number.
- **Disclosed, not reconciled.** Known differences between sources are stated and left visible.

## 5. Where the methodology appears in the dashboard

| Where | What it carries |
|---|---|
| **About** page, "Methodology Summary" | A seven-row summary: dataset, countries, features, train/test split, models, forecasting, scenarios |
| **Climate Correlation**, "Methodology & sources" | Sources, coverage, vintage and licence for every dataset; the baseline used by each view; the temperature offset; why the emissions series differ; the two-totals note; the 1959 splice |
| **Climate Correlation**, "How this number was derived" | The seven-step derivation of the slope, including a "what this is not" step |
| **Forecasts** | The five-model comparison, the fitted ETS parameters, and the holdout overlay on each forecast |
| **Scenario Comparison** and **Overview** | The scenario definitions and the "illustrative" label on implied temperature |

The About page is a short summary; the other pages hold the detail.

## 6. A checklist before quoting a number

1. Which **source** and which **scope** (gases, land use, international transport)?
2. Which **baseline year** or reference period?
3. Is it an **observation**, a **model fit**, a **forecast** or a **scenario**?
4. Does the uncertainty shown include **everything**, or only the statistical part?
5. Is it the **latest year** and so liable to revision?
6. Is it being used **comparatively** (fine) or as a **prediction** (usually not)?

## See also

- [Trend Analysis](01-trend-analysis.md)
- [Forecasting](02-forecasting.md)
- [The Emissions–Temperature Relationship](03-emissions-temperature-relationship.md)
- [Scenarios and Temperature Mapping](04-scenarios-and-temperature-mapping.md)
- [Data Quality and Harmonization](../01-data-sources/03-data-quality-and-harmonization.md)
