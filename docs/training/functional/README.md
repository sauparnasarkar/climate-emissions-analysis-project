# Climate Analytics Platform Functional Series

A domain-level series on what the platform measures, how it analyses it, how the results compare
with authoritative climate references, and what its trends imply for the Paris Agreement
targets. It complements the [Technical Series](../technical/README.md), which covers how the
platform is built. No programming is needed to follow it.

> **Status: complete as of October 2026.** All five sections are written. Facts about pledges and the COP process are
> dated; see the "as of" note at the top of each document.

## 1. The domain in one page

**The greenhouse effect.** Gases such as carbon dioxide absorb heat that the Earth would
otherwise radiate to space. Burning fossil fuels, producing cement, farming and changing how land
is used add these gases to the atmosphere faster than natural processes remove them, so their
concentrations rise and the surface warms.

**The chain this platform follows.** Each link has its own measurements, and the platform holds
data for each:

```
emissions  ──▶  atmospheric concentration  ──▶  global temperature
(what we release)   (what stays in the air)        (the physical response)
```

| Link | Question | Platform data |
|---|---|---|
| Emissions | How much is released, by whom, of which gas? | OWID / Global Carbon Project (CO₂), PRIMAP-hist (all main gases) |
| Concentration | How much has accumulated in the air? | NOAA Mauna Loa (measured) spliced to Law Dome ice cores |
| Temperature | How much has the surface warmed? | Berkeley Earth, relative to 1850–1900 |

The platform's forecasts and scenarios apply to the first link; its relationship analysis
([Methodology](02-methodology/03-emissions-temperature-relationship.md)) connects the three.

**The gases.** Carbon dioxide (CO₂) dominates by volume. Methane (CH₄), nitrous oxide (N₂O) and
the fluorinated gases ("F-gases") are much less abundant but trap far more heat per tonne. To
add them up, each is converted to **CO₂-equivalent (CO₂e)** with a *global warming potential*
(GWP) over a fixed horizon. This platform uses the IPCC Fifth Assessment Report's 100-year
values (CH₄ = 28, N₂O = 265) wherever it reports a combined total. The choice of GWP set
changes the totals, so any comparison with another source has to check which one it used.

**Who is counted.** Emissions inventories are *territorial*: they count emissions released
within a country's borders, not those embodied in the goods it imports. They usually exclude
international aviation and shipping, and treat land use, land-use change and forestry (LULUCF)
separately because it is far more uncertain than fossil emissions. Each document says which
convention a number follows.

## 2. What this platform is, and is not

| It is | It is not |
|---|---|
| A transparent, reproducible analysis of published historical data | A climate model; it does not simulate physics |
| Short-horizon statistical forecasts of CO₂ with held-out testing | A prediction of what governments or technology will do |
| Illustrative what-if scenarios (constant percentage reductions) | Calibrated policy pathways |
| A way to see trends and compare them with reference benchmarks | An authority; the IPCC and the sources in [Benchmarks](03-benchmarks/01-reference-landscape.md) are |

Keep this table in mind when reading the Findings section.

## 3. Key numbers

These are the platform's own latest values, as of the data refresh behind this document. Later
sections refer back to them. Sources, scope and caveats are in
the Data Sources documents ([emissions](01-data-sources/01-emissions-inventories.md), [concentrations and temperature](01-data-sources/02-concentrations-and-temperature.md), [quality](01-data-sources/03-data-quality-and-harmonization.md)).

| Quantity | Latest value | Source and scope |
|---|---|---|
| World CO₂ from fossil fuels and cement, 2024 | 38,599 MtCO₂ | OWID / Global Carbon Project; includes international aviation and shipping |
| World land-use-change CO₂, 2024 | 4,586 MtCO₂ | Same source; a modelled estimate with large uncertainty |
| World total GHG, 2024 | 50,550 MtCO₂e | PRIMAP-hist; CO₂, CH₄, N₂O, F-gases (AR5 GWP-100); excludes LULUCF and international transport |
| Share of that total, 2024 | CO₂ 75.1%, CH₄ 16.7%, N₂O 5.4%, F-gases 2.9% | PRIMAP-hist |
| Atmospheric CO₂, 2025 annual mean | 427.35 ppm | NOAA Mauna Loa |
| Global temperature, 2025 | 1.45 °C above 1850–1900 (preliminary) | Berkeley Earth; 95% uncertainty ±0.04 °C is statistical only |
| Global temperature, 2024 | 1.55 °C above 1850–1900 (preliminary) | Berkeley Earth |

Fossil CO₂ is not the same thing as total greenhouse gases, and the two sources above disagree
by a few percent on shared quantities because of scope and method; the platform discloses that
and does not reconcile it.

## 4. The series

| # | Section | What it covers |
|---|---|---|
| 1 | Data Sources: [emissions inventories](01-data-sources/01-emissions-inventories.md), [concentrations and temperature](01-data-sources/02-concentrations-and-temperature.md), [quality and harmonization](01-data-sources/03-data-quality-and-harmonization.md) | The five sources, their coverage, quality and harmonization |
| 2 | Methodology: [trend analysis](02-methodology/01-trend-analysis.md), [forecasting](02-methodology/02-forecasting.md), [emissions–temperature relationship](02-methodology/03-emissions-temperature-relationship.md), [scenarios and temperature mapping](02-methodology/04-scenarios-and-temperature-mapping.md), [limitations and uncertainty](02-methodology/05-limitations-and-uncertainty.md) | How the numbers are produced, and how far they can be trusted |
| 3 | Benchmarks: [reference landscape](03-benchmarks/01-reference-landscape.md), [emissions](03-benchmarks/02-emissions-vs-benchmarks.md), [temperature and concentration](03-benchmarks/03-temperature-and-concentration-vs-benchmarks.md), [pathways, carbon budgets and warming outlooks](03-benchmarks/04-pathway-comparison.md) | The platform's outputs against IPCC, UNEP, the Global Carbon Budget and other references |
| 4 | Paris Agreement: [the agreement and COP process](04-paris-agreement/01-the-agreement.md), [targets as numbers](04-paris-agreement/02-targets-as-numbers.md), [country NDCs](04-paris-agreement/03-country-ndcs.md) | The agreement, its targets expressed as numbers, and country NDCs |
| 5 | Findings: [where things stand](05-findings/01-where-we-are.md), [trajectory against Paris](05-findings/02-trajectory-vs-paris.md), [country differences](05-findings/03-country-differences.md), [caveats and reading guide](05-findings/04-caveats-and-reading-guide.md) | Where emissions stand, how the scenarios compare with Paris-aligned pathways, and caveats |

## Glossary

| Term | Meaning |
|---|---|
| **Anomaly** | A deviation from a reference period's average, not an absolute temperature |
| **CO₂e** | CO₂-equivalent: other gases converted to CO₂ using a global warming potential |
| **GWP** | Global warming potential: heat trapped per tonne relative to CO₂, over a fixed horizon (here 100 years) |
| **LULUCF** | Land use, land-use change and forestry |
| **Mt, Gt** | Million tonnes, billion tonnes (1 Gt = 1,000 Mt) |
| **ppm** | Parts per million: a concentration, as in CO₂ molecules per million air molecules |
| **Pre-industrial** | Conventionally 1850–1900 in this platform's temperature data |
| **Territorial emissions** | Emissions released within a country's borders |
