# The Reference Landscape: Who Publishes the Benchmarks

> Part of the [Functional Series](../README.md). A benchmark is only useful if you know what it
> measures. This document lists the reference publications the platform is compared against,
> what each covers, and the scope conventions that decide whether two numbers can be compared at
> all. The comparisons themselves follow in the next three documents.

## 1. The references used

Every figure quoted in this section was read from the publication itself, in the edition named
here. Where a secondary source disagreed with the publication, the publication was used.

| Reference | Edition used | What it provides | Role in this series |
|---|---|---|---|
| **IPCC Sixth Assessment Report (AR6)**: Working Group I (physical science), Working Group III (mitigation), Synthesis Report | WGI 2021, WGIII 2022, Synthesis 2023 | Assessed warming to 2020, emissions in 2019, the TCRE range, remaining carbon budget from 2020, and emission-reduction pathways | The scientific baseline and the source of the pathway benchmarks |
| **Global Carbon Budget 2025** (Global Carbon Project) | *Earth System Science Data* 18, 3211, 2026; first released November 2025 | Fossil and land-use CO₂, atmospheric growth, sinks, a 2025 projection, remaining carbon budget | The reference for CO₂ emissions and concentration; the original source of the platform's OWID data |
| **UNEP Emissions Gap Report 2025** ("Off target") | UNEP, 2025 | Total greenhouse gases in 2024 by gas, the gap between pledges and pathways, and warming projections | The reference for total GHG emissions and for the "gap" to Paris-aligned pathways |
| **Indicators of Global Climate Change 2025** (Forster et al.) | *Earth System Science Data* 18, 3889, published 11 June 2026 | Human-induced warming, observed warming, remaining carbon budget, annual update of AR6 indicators | The most current assessment of human-induced warming and of the carbon budget |
| **WMO consolidated global temperature** | WMO news release on 2025, eight datasets | A consolidated annual global temperature from eight independent datasets | The agency-level temperature reference |
| **Copernicus (ERA5)**, **Berkeley Earth** | *Global Climate Highlights 2025* (January 2026); *Global Temperature Report for 2025* (data as of early January 2026) | Individual temperature datasets | Single-dataset comparisons; Berkeley Earth is also the platform's own source |
| **NOAA Global Monitoring Laboratory** | Annual mean files, retrieved October 2026 | Global-mean and Mauna Loa CO₂ concentration | The like-for-like concentration comparison |
| **Climate Action Tracker** | Global update, 13 November 2025 | Warming projections for current policies and national pledges | An independent warming-outlook comparison |

## 2. Six scope questions to ask of any number

Most apparent disagreements between sources are differences of definition. Before comparing two
figures, check each of these:

| Question | Why it matters | Example from this series |
|---|---|---|
| **Which gases?** | CO₂ only, or all greenhouse gases | OWID/GCB report CO₂; PRIMAP-hist and UNEP report CO₂e |
| **Which warming-potential set?** | AR5 and AR6 GWP-100 values differ slightly for CH₄ and N₂O | PRIMAP-hist uses AR5; UNEP and IPCC AR6 use AR6 |
| **Land use in or out?** | Land-use CO₂ is large (about 4–5 GtCO₂ a year) and very uncertain | PRIMAP-hist excludes it; UNEP and IPCC include it |
| **International aviation and shipping in or out?** | About 1.2 GtCO₂ a year | PRIMAP-hist and the sum of countries exclude it; OWID's World row and UNEP include it |
| **Netted or gross?** | The Global Carbon Budget subtracts a cement carbonation sink of about 0.2 GtC (0.7 GtCO₂) from fossil emissions | See [Emissions](02-emissions-vs-benchmarks.md) |
| **Station or global?** | Mauna Loa runs about 1.6–1.8 ppm above the global mean | See [Temperature and Concentration](03-temperature-and-concentration-vs-benchmarks.md) |

For temperature the equivalent questions are **which baseline** (1850–1900 or a recent period),
**which dataset or combination of datasets**, **a single year or a multi-year average**, and
**observed or human-induced** warming.

## 3. A note on uncertainty language

The IPCC uses calibrated terms. *Likely* means at least a 66% probability; *very likely* means
at least 90%. A confidence interval from a regression, such as the platform's 95% interval on the
emissions–temperature slope, is a different object. Sources also quote uncertainty at different
confidence levels: UNEP and the IPCC use 90% ranges for emissions, WMO a 90% range for
temperature, Berkeley Earth 95%. When two numbers are compared here, the interval each one
carries is stated.

## See also

- [Emissions Compared with Benchmarks](02-emissions-vs-benchmarks.md)
- [Temperature and Concentration Compared with Benchmarks](03-temperature-and-concentration-vs-benchmarks.md)
- [Pathways, Carbon Budgets and Warming Outlooks](04-pathway-comparison.md)
- [Data Sources](../01-data-sources/01-emissions-inventories.md): how each platform series is built
