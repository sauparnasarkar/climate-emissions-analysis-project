# Data Quality and Harmonization

> Part of the [Functional Series](../README.md). The platform combines sources that were built
> for different purposes. This document describes, in non-technical terms, what the platform
> does to keep them trustworthy, what it will not do, and a one-page reference for all five
> sources.

## 1. The reference table

| Source | Measures | Scope | Years | Updated | Licence | Main limitation |
|---|---|---|---|---|---|---|
| **OWID / Global Carbon Project** | CO₂ from fossil fuels and cement, by country; land-use CO₂ separately | CO₂ only | 1750–2024 | Annually (with the Global Carbon Budget); platform re-downloads monthly | CC BY 4.0 (OWID); cite the Global Carbon Project | Land-use CO₂ is modelled and uncertain; file mixes countries with regions |
| **PRIMAP-hist v2.8** | CO₂, CH₄, N₂O, F-gases by country, excluding land use | AR5 GWP-100, MtCO₂e | 1750–2024 | Annually (Sep/Oct) | CC BY-NC-SA 4.0 | Composite reconstruction; no international transport; pre-1970 rebuilt |
| **NOAA GML Mauna Loa** | Atmospheric CO₂ concentration | Global, one station | 1959–2025 annual; monthly to 2026 | Monthly | Public domain | Single station |
| **Law Dome ice core** | Atmospheric CO₂ concentration, pre-1959 | Antarctic air | 1750–1958 | Static | Cite the original papers | Smoothed; no per-year uncertainty |
| **Berkeley Earth High-Res** | Global surface temperature anomaly | Land + ocean | 1850–2025 | Monthly | CC BY-NC | Preliminary; baseline-dependent |

A sixth source, EDGAR (the European Commission's emissions database), was evaluated and then
**shelved**. It is retained only for internal cross-checks, not published, because part of its
fuel-combustion CO₂ comes from the International Energy Agency under a no-derivatives licence
that does not allow the platform to publish derived results.

## 2. The principles

**One key, one unit, one scope.** Every indicator in the harmonized layer is keyed by calendar
year (and country, where relevant), has a single unit, and declares whether it is global or
national. A figure never silently changes unit or scope between pages.

**Gaps are gaps.** Missing values stay missing. The platform does not interpolate across a gap
or replace a missing gas with zero, because either would invent data.

**Validate before publishing.** Each source is checked before its output reaches the dashboard:

| Check | Example from this platform |
|---|---|
| Completeness | A PRIMAP-hist year is published only if every gas covers at least 98% of the previous year's emissions |
| Plausibility | The total may not move more than ±15% from the previous year |
| Internal consistency | The gases must add up to the source's own total within 0.5% |
| Integrity | Downloads are verified against the publisher's checksums; a truncated file fails instead of publishing |
| Freshness | A stale or unusual source raises an alert but does not stop the run |

When a check fails, the platform holds back the affected year or series. It does not repair it.
That is why the latest PRIMAP-hist year shown is 2024 even though the file contains 2025.

**Provenance is data.** Every published series carries a record of where it came from: source
URLs, retrieval time, the release version, a fingerprint of the raw file, coverage, units, scope,
method, caveats and licence. The dashboard and API read this record; they do not recompute it.

**Licences are enforced.** Non-commercial terms, share-alike terms and citation requirements are
recorded with each series, and derived data carries the notices it must. Using data under a
licence that forbids a use is treated as a defect, which is how EDGAR came to be shelved.

## 3. Known discrepancies that are disclosed, not reconciled

| Discrepancy | Why it exists |
|---|---|
| OWID/GCP and PRIMAP-hist CO₂ totals differ by a few percent | Different scope (international transport) and different energy statistics and emission factors |
| PRIMAP-hist is about 3% below EDGAR national totals by 2023, with large country differences (for example India about −14%, United States about +6%) | Different inventory construction and gap-filling |
| PRIMAP-hist country-reported and third-party scenarios differ by about 4.7% in 2023 | Genuine uncertainty in the underlying data |
| The sum of countries differs from the World row in OWID | The World row includes international aviation and shipping; some summed entities are non-sovereign territories |
| Temperature "above pre-industrial" varies by a few hundredths of a degree between groups | Different baselines and different construction of the 1850–1900 reference |

None of these is an error. They are the normal spread between competent datasets, and they set
the realistic limit on how precisely any claim in this series can be made.

## 4. What this means for a reader

1. **Check the scope before comparing numbers.** Gases, land use, international transport, GWP
   set and baseline are the five things that explain most disagreements.
2. **Treat the latest year with care.** It is the one most likely to be revised, and for
   temperature it is flagged preliminary.
3. **Trust trends over single values.** The sources agree far better on direction and rate of
   change than on any one year's level.

## See also

- [Emissions Inventories](01-emissions-inventories.md)
- [Concentrations and Temperature](02-concentrations-and-temperature.md)
- [Technical: Multi-Source Data Pipelines §3–5](../../technical/01-data-science-ml/05-multi-source-pipelines.md) —
  the validation, provenance and harmonization mechanics
