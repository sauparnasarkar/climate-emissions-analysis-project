# Emissions Inventories: OWID / Global Carbon Project and PRIMAP-hist

> Part of the [Functional Series](../README.md). This document describes the two sources the
> platform uses for **emissions** — who produces each, what it counts, how far it reaches, and
> why there are two. Concentration and temperature are in the
> [next document](02-concentrations-and-temperature.md).

## 1. Two sources, two jobs

| | OWID / Global Carbon Project | PRIMAP-hist |
|---|---|---|
| **Producer** | Our World in Data republishing the Global Carbon Project's Global Carbon Budget data | The PRIMAP research group (Gütschow, Pflüger and colleagues), published on Zenodo |
| **Gases** | CO₂ only (fossil fuels + cement; land-use change as a separate column) | CO₂, CH₄, N₂O and F-gases, with the Kyoto-basket total |
| **Used for** | The country-level analysis: trends, forecasts, scenarios, the Overview, Country Profile and Scenario pages | Total greenhouse gases, gas composition and each country's share of the global total |
| **Years** | 1750–2024 | 1750–2024 (v2.8; 2025 was published but excluded as incomplete) |
| **Geography** | 254 entities in the file, of which 215 report CO₂ in 2024; the rest are regions, groupings and income classes | 207 country and territory areas |
| **Unit** | Million tonnes of CO₂ (MtCO₂) | Million tonnes of CO₂-equivalent (MtCO₂e), AR5 GWP-100 |
| **Licence** | CC BY 4.0 for OWID's compilation; Global Carbon Project data requires citing the original | CC BY-NC-SA 4.0: non-commercial use, attribution, share-alike |

The split is deliberate. OWID's file is richer per country (population, GDP and per-capita
values) but covers CO₂ only. PRIMAP-hist is the
only source in the platform that puts the other gases on the same footing as CO₂, so it answers
"what is the *total* and how is it composed?".

## 2. OWID / Global Carbon Project

**What it measures.** Annual CO₂ emissions from burning fossil fuels and making cement, by
country, from the Global Carbon Project's annual Global Carbon Budget. Land-use-change CO₂
(deforestation, afforestation and similar) is a *separate* column, not part of the headline
`co2` figure.

**How it is produced.** The Global Carbon Project combines energy statistics with emission
factors for fossil CO₂, and averages several bookkeeping models for land-use change. OWID
republishes the result as one tidy file, adds derived per-capita and cumulative columns, and
updates it when a new Global Carbon Budget is released. The platform's refresh job re-downloads
it monthly.

**What to remember when reading it.**

- **Fossil and land-use CO₂ differ in confidence.** Fossil CO₂ is comparatively well measured;
  land-use CO₂ is a modelled estimate with a large uncertainty (roughly ±2.6 GtCO₂ per year, one
  standard deviation, in recent decades, per the Global Carbon Budget). The platform keeps them
  separate and only adds them when it says so.
- **International aviation and shipping.** The World row includes them; the sum of the countries
  does not. The platform keeps both numbers (`co2_mt` and `national_sum_mt`) and uses the
  national sum as the denominator for country shares.
- **Not every row is a country.** The file mixes sovereign countries with continents, income
  groups, the European Union aggregates and special entries (for example, "Kuwaiti Oil Fires").
  The platform filters these out of any country ranking using one list in the notebooks'
  shared constants, and its API does the same.
- **The year range depends on country.** A country's series begins when data begin: coverage in
  the 1990s differs for countries that did not yet exist.

## 3. PRIMAP-hist

**What it measures.** A single, consistent, long national series of greenhouse gas emissions
since 1750 for CO₂, CH₄, N₂O and the fluorinated gases, covering the national total *excluding*
land use, land-use change and forestry (category M.0.EL).

**How it is produced.** It is a composite. Country-reported data, where a country has submitted
an inventory to the UN climate convention, take priority; gaps are filled from third-party
datasets (including CDIAC, the Energy Institute, FAOSTAT and EDGAR) and harmonized into one
series. The platform uses the *country-reported priority* scenario (HISTCR) from the file
without extrapolation. The country-reported and third-party scenarios differ by about 4.7% in
2023, which is a good indication of the underlying uncertainty.

**What to remember when reading it.**

- **It is a reconstruction, not a measurement.** Values before about 1970 are rebuilt from
  historical datasets.
- **Explicit gaps, not zeros.** Methane and nitrous oxide cover 206 areas; F-gases cover about
  150–170. An area without a gas is recorded as missing, never as zero.
- **No world aggregate and no international transport.** The world total is the sum of the
  reporting areas and so excludes international aviation and shipping.
- **A year is published only when it is complete.** The platform requires each gas to cover at
  least 98% of the previous year's emissions and the national total to be within ±15% of the
  prior year. The 2025 values in v2.8 fail this rule (methane coverage 2.0%, F-gases 0.0%,
  total −28% against 2024) and are held back rather than extrapolated.
- **Arithmetic is checked.** The platform recomputes the total from the gases (CO₂ + CH₄ × 28 +
  N₂O × 265 + the F-gas basket) and requires it to match PRIMAP-hist's own total within 0.5%.
  Across 1750–2024 the mismatch is below 0.5% in every year the platform publishes.

## 4. Why two sources disagree, and what the platform does about it

OWID/GCP and PRIMAP-hist report different 2024 CO₂ figures: 38,599 MtCO₂ (OWID, includes
international transport) against 37,974 MtCO₂ (PRIMAP-hist, excludes it). Part of the gap is
scope, since international aviation and shipping alone are about 1,192 MtCO₂ in OWID's 2024
figures. The remainder reflects different energy statistics, emission factors and treatment of
gaps. The platform's position:

1. Use each source only for what it covers best, and **never silently mix them** in one chart.
2. Label each figure with its scope (gases, whether land use and international transport are
   included).
3. **Disclose** the difference rather than hide it by reconciling the two.

When the benchmark documents compare the platform with the IPCC and others, the same rule holds:
the first question is always *which scope does this number use?*

## 5. The country sets

The platform works with three overlapping sets of countries:

| Set | Size | How chosen | Used for |
|---|---|---|---|
| **Featured** | 10 | Hand-picked: China, United States, India, Russia, Japan, Germany, Brazil, United Kingdom, South Africa, Australia | Default charts and narrative |
| **Expanded** | 40 | Data-driven: at least 90% data coverage and at least 100 MtCO₂ in the latest year (2024). Together they hold 92.2% of the global total | Model training and evaluation, aggregate sums, tables and picker pools |
| **All countries** | ~215 | Every sovereign country with data | Overview rankings and the map |

The expanded set is recomputed from live data and stored in `data/selected_countries.json`.

## See also

- [Concentrations and Temperature](02-concentrations-and-temperature.md)
- [Data Quality and Harmonization](03-data-quality-and-harmonization.md)
- [Technical: Multi-Source Data Pipelines](../../technical/01-data-science-ml/05-multi-source-pipelines.md) —
  how these sources are ingested, validated and published
- [Technical: EDA and Data Engineering](../../technical/01-data-science-ml/01-eda-data-engineering.md) —
  how the OWID file is profiled and filtered
