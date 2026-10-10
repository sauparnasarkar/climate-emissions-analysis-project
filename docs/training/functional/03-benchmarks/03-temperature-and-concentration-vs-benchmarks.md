# Temperature and Concentration Compared with Benchmarks

> Part of the [Functional Series](../README.md). The platform's temperature series is a single
> dataset (Berkeley Earth, preliminary) and its concentration series is a single station. This
> document compares both with the IPCC, WMO, Copernicus, Berkeley Earth's own reports, the
> Forster et al. annual indicators and NOAA's global mean.

## 1. Temperature over multi-year periods

The IPCC assesses warming as multi-year averages, which is the right way to compare it with a
single dataset. All values are relative to 1850–1900.

| Period | Platform (Berkeley Earth HR) | Reference | Reference value (°C) |
|---|---|---|---|
| 2001–2020 | 1.01 | IPCC AR6 WGI SPM A.1.2 | 0.99 [0.84–1.10] |
| 2010–2019 | 1.08 | IPCC AR6 WGI SPM | 1.06 [0.88–1.21] |
| 2011–2020 | 1.11 | IPCC AR6 WGI SPM A.1.2 | 1.09 [0.95–1.20] |
| 2016–2025 | 1.29 | Forster et al. 2026 (observed) | 1.26 [1.13–1.36] |
| 2023–2025 | 1.49 | WMO consolidated, eight datasets | 1.48 ± 0.13 |

The platform is within 0.02–0.03 °C of the IPCC and WMO values and well inside every reference
range. Berkeley Earth is one of the eight datasets WMO consolidates, so the WMO row is agreement
with a synthesis that includes it, not an independent confirmation.

## 2. Temperature in single years

| Year | Platform | Berkeley Earth's own report | WMO consolidated (8 datasets) | Copernicus ERA5 | Forster et al. (observed) |
|---|---|---|---|---|---|
| 2023 | 1.48 | about 1.47 (derived) | | | |
| 2024 | 1.55 | about 1.52 (derived) | | 1.60 | 1.51 ± 0.13 |
| 2025 | 1.45 | 1.44 ± 0.09 | 1.44 ± 0.13 | 1.47 | 1.39 ± 0.13 |

Notes:

- **The spread across datasets in a single year is about 0.1 °C** (2025 runs from 1.39 to 1.47),
  comparable to the stated uncertainties. The IPCC puts the internal variability of a single
  year at about ±0.25 °C (5–95% range), which is why it reports warming as running 20-year
  averages. A difference of a few hundredths of a degree between
  the platform and any one reference is not meaningful.
- **Berkeley Earth's own report** gives 2024 and 2023 only implicitly (2025 is "about 0.08 °C
  cooler" than 2024 and "0.03 °C cooler" than 2023), so those two entries are derived. The
  platform's 2024 value is about 0.03 °C above the derived figure; Berkeley Earth notes that its
  analyses are revised as new observations arrive, typically by small amounts.
- **2025 ranks third warmest** in six of the eight WMO datasets and second in two; the platform
  agrees on the ranking (2024 > 2023 > 2025 in its series).
- **The single warm years are not the long-term level.** 2023–2025 averaged above 1.5 °C in
  Copernicus's analysis, which presents it as the first three-year period to do so. The Paris
  temperature goal is about the long-term level, which is lower (§3).

## 3. Long-term warming, and when it reaches 1.5 °C

Several groups estimate the *underlying* warming level, free of year-to-year variability:

| Source | Estimate | Method |
|---|---|---|
| Forster et al. 2026 | Human-induced warming 1.37 °C in 2025 [1.1–1.7]; rising 0.27 °C a decade; reaches 1.5 °C around 2030 | Attribution of observed warming to human causes |
| Copernicus | about 1.4 °C | "Several methods" (not named on the page read) |
| Berkeley Earth | Long-term trend "has already crossed 1.4 °C"; "less than 5 years" to reach 1.5 °C | 30-year LOESS smooth |
| Global Carbon Budget 2025 | Human-caused warming 1.36 °C in 2024 | Attribution of observed warming to human activities |
| **Platform** | Starting level 1.32 °C (mean of 2020–2024); implied 2025 level 1.34 °C | Five-year mean of observations plus implied warming |

The platform's starting level is lower than the others because a *five-year mean of
observations* lags a trend that is still rising, and because it is an observed value, not an
attributed one. The platform's implied 2025 level (1.34) is about 0.03 °C below Forster et al.'s
human-induced 1.37, consistent with that.

## 4. Atmospheric CO₂

The platform uses the Mauna Loa station for its recent record. The IPCC, the Global Carbon Budget
and NOAA's global series use a **global mean**, so the like-for-like comparison is with NOAA's
global annual mean.

| Year | IPCC / Global Carbon Budget | NOAA global mean | Platform (Mauna Loa) | Platform minus global |
|---|---|---|---|---|
| 2019 | 410 ppm (IPCC SYR A.1.3) | 410.07 | 411.65 | +1.58 |
| 2024 | 422.8 ± 0.1 (GCB 2025) | 422.79 | 424.61 | +1.82 |
| 2025 | 425.6 (GCB 2025 projection) | 425.62 | 427.35 | +1.73 |

The platform series is about 1.6–1.8 ppm above the global mean every year, the expected offset
of a Northern Hemisphere station. The global means agree with each other to within 0.05 ppm,
and the platform's trend (about 2–3 ppm a year) matches. One further reference, quoted in the
UNEP report from WMO, gives 423.9 ppm for 2024; WMO's global-mean product differs slightly from
NOAA's.

## 5. What this comparison shows

- **Temperature: agreement within the datasets' own spread**, both over decades and in recent
  years. The platform's latest values are preliminary and could move by a few hundredths.
- **Concentration: agreement once station and global means are matched.** The offset is
  systematic, not an error.
- **Long-term warming is the figure that matters for Paris, and it is below the recent single
  years.** The platform's scenario translation starts at 1.32 °C for that reason.

## See also

- [The Reference Landscape](01-reference-landscape.md)
- [Emissions Compared with Benchmarks](02-emissions-vs-benchmarks.md)
- [Pathways, Carbon Budgets and Warming Outlooks](04-pathway-comparison.md)
- [Concentrations and Temperature](../01-data-sources/02-concentrations-and-temperature.md): how
  the platform's two series are built
