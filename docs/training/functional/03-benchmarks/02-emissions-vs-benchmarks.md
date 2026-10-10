# Emissions Compared with Benchmarks

> Part of the [Functional Series](../README.md). This document compares the platform's emissions
> series with the Global Carbon Budget, the UNEP Emissions Gap Report and the IPCC. The scope
> columns matter more than the numbers: the sources agree closely once their definitions are
> aligned, and disagree by several gigatonnes when they are not.

## 1. Fossil CO₂ in 2024

| Source | 2024 fossil CO₂ (GtCO₂) | Gases | Bunkers (international aviation and shipping) | Cement carbonation sink |
|---|---|---|---|---|
| **Platform, OWID World row** | 38.6 | CO₂ | Included (1.19) | Not netted out, as far as can be checked |
| **Platform, PRIMAP-hist** | 37.97 | CO₂ | Excluded | n/a |
| **Global Carbon Budget 2025** | 37.8 ± 1.8 | CO₂ | Estimated separately; whether the headline total includes them was not confirmed in the text read | **Netted out** (0.2 GtC ≈ 0.7 GtCO₂) |
| **UNEP EGR 2025** (EDGAR-based) | 39.6 ± 3.2 | CO₂ | Included | Not stated |

The gap between the platform's 38.6 and the Global Carbon Budget's 37.8 is about 0.8 GtCO₂.
Subtracting the cement carbonation sink the Global Carbon Budget nets out (0.2 GtC, about
0.73 GtCO₂) leaves 37.9, within rounding of 37.8. The platform's number therefore appears to be
the gross figure, but OWID's codebook does not state its treatment, so this is a consistent
explanation, not a verified one. Either way the two agree within the Global Carbon Budget's own
uncertainty of ±1.8.

The same alignment works for the totals including land use:

| | Fossil CO₂ | Land-use CO₂ | Total anthropogenic CO₂ |
|---|---|---|---|
| Platform (OWID / Global Carbon Project), 2024 | 38.6 | 4.6 | 43.2 |
| Platform, less the 0.73 carbonation sink | 37.9 | 4.6 | 42.4 |
| Global Carbon Budget 2025, 2024 | 37.8 ± 1.8 | about 4.8 (1.3 ± 0.7 GtC) | 42.4 ± 3.2 |

The Global Carbon Budget's 2025 projection (38.1 GtCO₂ fossil, up 1.0%, and 4.1 GtCO₂ land use)
is beyond the end of the platform's data, which stops at 2024.

**Land use is the largest relative uncertainty.** Its uncertainty is about ±2.6 GtCO₂ a year
(one standard deviation), compared with ±1.8 for all fossil CO₂.

## 2. Total greenhouse gases

The totals look very different, and almost all of the difference is scope:

| | Platform (PRIMAP-hist) 2024 | UNEP EGR 2025, 2024 | Difference |
|---|---|---|---|
| Fossil CO₂ | 37.97 | 39.6 | +1.6 |
| Land-use CO₂ (bookkeeping) | not included | 4.4 | +4.4 |
| Methane (CO₂e) | 8.42 | 9.3 | +0.9 |
| Nitrous oxide (CO₂e) | 2.73 | 2.6 | −0.1 |
| F-gases (CO₂e) | 1.45 | 1.7 | +0.25 |
| **Total (GtCO₂e)** | **50.55** | **57.7 ± 5.5** | **+7.1** |
| GWP set | AR5 GWP-100 | AR6 GWP-100 | |

An approximate decomposition of the 7.1 GtCO₂e gap, not a reconciliation:

- **Land-use CO₂ (4.4)** is the biggest single item, a scope difference the platform states.
- **Fossil CO₂ (+1.6)** is mostly the international aviation and shipping that PRIMAP-hist
  excludes (about 1.2 in OWID's 2024 figures); the remainder reflects different inventories.
- **Methane (+0.9)** is the largest gap that is not a scope difference. It was not traced here.
  A similar pattern appears against the IPCC's 2019 estimate (below).
- Nitrous oxide and F-gases nearly cancel.

**The same check for 2019 against the IPCC.** AR6 Working Group III estimates net
anthropogenic emissions in 2019 at 59 ± 6.6 GtCO₂e, made up of:

| Component, 2019 | IPCC AR6 WGIII (GtCO₂e) | Platform (PRIMAP-hist, OWID) | Note |
|---|---|---|---|
| Fossil CO₂ and industry | 38 ± 3 | 37.1 (OWID, incl. bunkers); 36.4 (PRIMAP-hist, excl.) | Consistent |
| Land-use CO₂ | 6.6 ± 4.6 | 4.9 (OWID / Global Carbon Project) | Within the IPCC's range |
| Methane | 11 ± 3.2 | 8.2 | Platform is lower |
| Nitrous oxide | 2.7 ± 1.6 | 2.6 | Consistent |
| F-gases | 1.4 ± 0.41 | 1.2 | Consistent |
| **Total** | **59 ± 6.6** | **48.3** (PRIMAP-hist, no land use) | Platform total excludes land use |

Excluding land use, the IPCC's own components sum to about 53.1, against the platform's 48.3, a
gap of about 4.8. Methane (2.8) and fossil CO₂ (about 1.6, largely the bunkers PRIMAP-hist
excludes) account for most of it.

## 3. Growth in 2024

| Source | 2024 growth | What it covers |
|---|---|---|
| Platform, OWID fossil CO₂ | +1.3% | Fossil CO₂ with bunkers |
| Global Carbon Budget 2025 | +1.1% | Fossil CO₂ |
| EDGAR, as quoted by UNEP | +1.1% | Fossil CO₂ |
| Platform, PRIMAP-hist total GHG | +1.0% | CO₂, CH₄, N₂O, F-gases; no land use |
| UNEP, total GHG | +2.3% | All gases including land use |
| UNEP, total GHG excluding land use (derived from its Table 2.1) | about +1.3% | All gases without land use |

The headline difference (+2.3% against about +1%) is almost entirely land use: UNEP's net
land-use CO₂ rose from 3.6 to 4.4 GtCO₂, a 21% jump (UNEP's own statement). Without it, the
sources agree within a few tenths of a percent. This is the main reason for keeping land use out
of trend comparisons.

## 4. Cumulative emissions

| | Platform | IPCC AR6 | Comparison |
|---|---|---|---|
| Cumulative net CO₂, 1850–2019 | 2,542 GtCO₂ (fossil 1,658; land use 884) | 2,400 ± 240 GtCO₂ (Synthesis Report A.1.3) | Within the IPCC's range |
| Share emitted 1990–2019 | 41.8% | "about 42%" | Matches |

## 5. What this comparison shows

- **Levels agree once scope is aligned.** Fossil CO₂ matches the Global Carbon Budget within
  rounding after the cement carbonation sink; land use and cumulative totals sit inside the IPCC
  and Global Carbon Budget ranges.
- **The platform's total GHG is lower by design, not by error.** It excludes land use and
  international transport, uses an older GWP set, and (not traced here) carries less methane than
  the global inventories.
- **Trends agree better than levels.** Growth in 2024 is within a few tenths of a percent across
  sources once land use is set aside.
- **The 2025 projections are not yet in the platform.** The Global Carbon Budget projects fossil
  CO₂ of 38.1 GtCO₂ for 2025, a record.

## See also

- [The Reference Landscape](01-reference-landscape.md)
- [Temperature and Concentration Compared with Benchmarks](03-temperature-and-concentration-vs-benchmarks.md)
- [Data Quality and Harmonization](../01-data-sources/03-data-quality-and-harmonization.md): the
  known discrepancies between the platform's own sources
