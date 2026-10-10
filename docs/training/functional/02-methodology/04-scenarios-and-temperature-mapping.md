# Scenarios and Temperature Mapping

> Part of the [Functional Series](../README.md). The platform builds three emissions pathways to
> 2040 and translates them into the *implied* warming they would add, using the relationship
> measured in the [previous document](03-emissions-temperature-relationship.md). This document
> explains each step and, as importantly, how little the result should be read as a prediction.

## 1. The three pathways

| Scenario | Definition | Basis |
|---|---|---|
| **Business as Usual (BAU)** | The damped-trend ETS forecast for each country, refitted on all observed years (1990–2024), continuing from 2025 | Each country's own history |
| **Moderate Mitigation** | BAU reduced by 2% per year from 2025, compounding | An illustrative bounding case |
| **Aggressive Mitigation** | BAU reduced by 5% per year from 2025, compounding | An illustrative bounding case |

**What "BAU" means.** It is not "emissions stay flat". It is the model's continuation of each
country's recent trajectory, including declines already under way (the United Kingdom's, for
example) and slowdowns (China's). "No policy change" really means "nothing beyond what is already
in the historical trend".

**What the reductions mean.** The reductions *compound*: in year *n* after 2025, the pathway is
BAU × (1 − rate)ⁿ. By 2040 (15 steps on) that is **26% below BAU for Moderate and 54% below BAU
for Aggressive**. Both are applied identically to every country, so they ignore real differences
in how fast a country can change. Nothing links them to GDP, energy mix, carbon prices or
technology costs.

## 2. Why BAU is a second fit

A forecast fitted only to 2018 has not seen 2019–2024. Used as the baseline, it would start 2025
about 3.7% above the observed 2024 total, with country-level jumps from −51% to +62%, so every
scenario would carry a discontinuity unrelated to mitigation. The scenarios therefore use the
same model refitted on 1990–2024. A continuity check confirms the result: the aggregate 2025
step is **+0.9%** against 2024, within a ±2% tolerance, and any country outside ±5% is listed
for explanation (Kuwait, for instance, is distorted by the 1991 oil fires).

The evidence for the refit is a short-horizon test: forecasts made from data through 2021 or 2022
(pandemic years included) had median country errors of roughly 3.5–7% over the following years,
against roughly 7–11% for the fit stuck at 2018. It supports using the full-data fit; it does
**not** show skill over a 16-year horizon.

## 3. The 2040 emissions picture

| | 40 covered countries, 2040 | World-equivalent, 2040 |
|---|---|---|
| BAU | 40,086 MtCO₂ | 44,877 MtCO₂ |
| Moderate | 29,606 MtCO₂ | |
| Aggressive | 18,571 MtCO₂ | 20,791 MtCO₂ |

The 40 covered countries hold 89.3% of the 2024 world CO₂ total. To translate to a global figure,
the **rest of the world is held at its last observed share** (10.7%), so it moves in proportion
with the covered countries. International aviation and shipping fall inside that remainder.
The Aggressive world-equivalent is 2.2 times lower than BAU by 2040.

## 4. From emissions to implied warming

For each scenario and year:

1. **Cumulative emissions since 2024** are accumulated: the scenario's global fossil and cement
   CO₂, plus land-use CO₂.
2. **Land use is held flat** at its trailing five-year mean (about 4,660 MtCO₂ per year),
   because the scenarios do not model it. This is an explicit assumption, not a finding.
3. **Implied added warming** = the slope (0.486 °C per 1,000 GtCO₂) × the cumulative emissions
   since 2024. The band shown is the slope's 95% interval only.
4. **The level** = an *anchor* + the implied added warming. The anchor is the **mean of the
   observed anomaly over the last five years (2020–2024), 1.32 °C**. It is not the single 2024
   value (1.55 °C), which would bake in one year's natural variability, and not the regression
   line, which sits below the observed anomaly and would make the curve jump at the start.

A second line applies the fossil-only slope (0.749) to fossil and cement emissions only, so the
effect of the definition is visible.

## 5. The result

| Scenario | Added warming by 2040 | Implied level in 2040 (°C above 1850–1900) |
|---|---|---|
| BAU | +0.36 °C | 1.68 (slope-uncertainty band 1.65–1.72) |
| Moderate | +0.32 °C | 1.64 (1.61–1.67) |
| Aggressive | +0.26 °C | 1.58 (1.56–1.61) |

**The scenarios differ by only about 0.10 °C in 2040**, although their annual emissions differ by
a factor of about 2.2. The reasons are what makes the figure instructive:

- 2025–2040 is a short window against the 175 years of emissions already accumulated.
- Most of the 2040 level (78–83%) is warming **already observed** by 2024, before any scenario
  begins.
- What a scenario changes is only the emissions still to come. Relative to BAU's +0.36 °C of
  further warming, the Aggressive pathway adds about 28% less.
- The gap keeps widening each year the pathways stay apart (about 0.025 °C by 2032, 0.10 °C
  by 2040).

## 6. How to read these numbers

| Do | Do not |
|---|---|
| Treat them as *comparative*: how much does a bounded change in the pathway matter? | Quote 1.68 °C as a forecast of the 2040 temperature |
| Note that the band covers only the slope's statistical uncertainty | Read the band as the range of possible outcomes; it excludes scenario, policy and climate-system uncertainty |
| Compare the three pathways with each other | Compare a 2040 level here directly with an IPCC "warming level", which is a 20-year average under defined conditions (see [Benchmarks](../03-benchmarks/04-pathway-comparison.md)) |

The dashboard labels these results "Illustrative · implied outcomes, not projections", and the
output file names them "illustrative, partial-coverage translation", dependent on "the selected
regression period, emissions source and model assumptions".

## 7. Where this appears in the dashboard

| Dashboard element | What it shows |
|---|---|
| Scenario Comparison page | The three pathways per country, a treemap of cumulative BAU emissions coloured by each scenario's 2040 level against today's, a cumulative table |
| Overview and Climate Correlation | The implied-temperature translation, labelled illustrative |
| About page | A one-line description of the three scenarios |

## See also

- [Forecasting](02-forecasting.md)
- [The Emissions–Temperature Relationship](03-emissions-temperature-relationship.md)
- [Limitations and Uncertainty](05-limitations-and-uncertainty.md)
- [Technical: Time-Series Forecasting](../../technical/01-data-science-ml/04-time-series-forecasting.md)
- [Technical: Multi-Source Data Pipelines §8](../../technical/01-data-science-ml/05-multi-source-pipelines.md):
  how the translation is computed
