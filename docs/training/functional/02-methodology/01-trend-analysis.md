# Trend Analysis: Reading the Historical Charts

> Part of the [Functional Series](../README.md). Before any forecast, the platform describes what
> has already happened. This document explains the measures behind the historical charts, what
> each one is good for, and the mistakes each invites. The data behind them is described in
> [Data Sources](../01-data-sources/01-emissions-inventories.md).

## 1. The measures

| Measure | What it answers | Where it appears | Watch out for |
|---|---|---|---|
| **Level** (MtCO₂) | How much is emitted? | Overview, Country Profile, Data Explorer | Large countries dominate any comparison of levels |
| **Year-on-year change** (%) | Is the country emitting more or less than last year? | Country Profile (YoY chart) | Noisy; one recession, pandemic or data revision swings a single year |
| **Change since a base year** (%, or index with base = 100) | How far has it moved from the starting point? | Overview "% Change", Historical Trends, Scenario Comparison | The answer depends on the base year chosen (§2) |
| **Per capita** (tCO₂ per person) | How much per resident? | Country Profile | Hides total scale: a small, rich country can be high per person and tiny in total |
| **Share** (% of a total) | Who accounts for how much? | Overview share section, gas-composition charts | A share can fall while the level rises, if others grow faster |
| **Composition by decade** (% by gas) | Which gases make up the total? | Historical Trends | Needs a source that covers all gases (PRIMAP-hist), so it starts later than the CO₂ series |
| **Cumulative** (GtCO₂) | How much has been emitted in total since a start year? | Overview map (cumulative view), correlation module | Warming follows the cumulative total, not any single year |

**Colour convention.** Decreases in emissions are shown in green and increases in crimson, on
every chart where a direction is judged. A *forecast* is shown in a neutral colour, because a
forecast is a series, not a verdict.

## 2. The base-year problem

"Change since 1990" is a ratio, so its value depends on where 1990 sat in a country's own history.
A country that had a bad year in 1990 looks better against it, and a country that had a good year
looks worse. The platform therefore says which baseline each view uses:

| View | Baseline | Why |
|---|---|---|
| Overview, Historical Trends, Scenario Comparison | 1990 = 100 | Matches the model training window (1990 onward) used across the platform |
| Country Profile trend | Full OWID history | 1990 is shown as a marker, not as the start |
| All-gas relationship, gas composition | 1970 onward | Earlier PRIMAP-hist values are reconstructions, not measurements |
| Long-run CO₂ relationship | 1850–1900 reference | Pre-industrial context keeps early accumulation visible |
| Global, non-ML totals | Full available range | No model-consistency constraint applies |

1990 has a second meaning the reader should know. It is the reference year of the Kyoto-era
climate agreements, and for many countries it is a meaningful starting point. In some it is also
distorted: German reunification and the collapse of the Soviet economy both occurred around it,
which cut emissions in the affected countries for reasons unrelated to climate policy. A
country's decline since 1990 is therefore not the same as the effect of its climate policy.

## 3. Which countries, and the aggregation choices

- **Featured (10) and Selected (up to 10)** drive the readable comparison charts. Past ten lines,
  a chart stops being readable.
- **Expanded (40)** is used for totals, the scenario treemap and model evaluation. These countries
  hold 92.2% of the 2024 global total, so an expanded-set total approximates the world, but it is
  not the world.
- **Non-sovereign entries** (regions, income groups, the European Union aggregates, international
  transport) are excluded from every country ranking. They would double count the countries they
  contain.

A global total from the World row and a total from summing countries differ by design: the World
row includes international aviation and shipping, and the sum of countries does not.

## 4. A short reading guide

1. **Say what is plotted**: level, rate, index or share, and in which unit.
2. **Check the base year** before comparing two "% change" figures.
3. **Separate total from per capita**: they answer different questions and can point in opposite
   directions.
4. **Look at several years, not one.** The pandemic year 2020 sits inside most series and is a
   drop that reversed; a single point there is not a trend.
5. **Remember the scope**: territorial emissions, excluding emissions embodied in trade.

## See also

- [Forecasting](02-forecasting.md): extending these series forward
- [Limitations and Uncertainty](05-limitations-and-uncertainty.md)
- [Technical: EDA and Data Engineering](../../technical/01-data-science-ml/01-eda-data-engineering.md)
- [Technical: Feature Engineering](../../technical/01-data-science-ml/02-feature-engineering.md):
  the lag, rolling and percentage-change features computed from these series
