# Concentrations and Temperature: NOAA Mauna Loa, Law Dome and Berkeley Earth

> Part of the [Functional Series](../README.md). Emissions are only the first link of the chain.
> This document describes the two series that sit downstream of them: how much CO₂ has
> accumulated in the air, and how much the surface has warmed. Emissions are in the
> [previous document](01-emissions-inventories.md).

## 1. Atmospheric CO₂: NOAA Mauna Loa and Law Dome

**What it measures.** The concentration of CO₂ in the global atmosphere, in parts per million
(ppm). Unlike emissions, which are a *flow* (tonnes per year), concentration is a *stock*: what
is left in the air after the oceans and land have taken up their share.

**Two sources, spliced at 1959.**

| Period | Source | How obtained |
|---|---|---|
| 1959 onward | NOAA Global Monitoring Laboratory, Mauna Loa Observatory (Hawaii) | Direct, continuous, in-situ measurement; 1958–1974 is the Scripps (Keeling) record that NOAA took over |
| Before 1959 | Law Dome ice cores and firn (Antarctica) | Air trapped in ice, dated and smoothed into an annual spline (Etheridge et al.; MacFarling Meure et al.) |

The two are joined in 1959 without adjustment. The platform stores how well they agree where they
overlap (1959–2004): on average the ice-core series is 2.3 ppm below the instrument record, and
the largest gap is 3.9 ppm. At the splice year itself the gap is 0.28 ppm.

**Latest values.** The 2025 annual mean is **427.35 ppm**, with 0.12 ppm measurement uncertainty.
A monthly series (from March 1958) feeds the "latest reading" indicator on the dashboard; it
shows the familiar seasonal cycle, and the platform also carries NOAA's deseasonalized value.

**What to remember.**

- **One station.** Mauna Loa is a single Northern Hemisphere site, and Law Dome reflects
  Southern Hemisphere air. Atmospheric CO₂ is well mixed, so the difference is small, but
  pre-1959 values are not directly comparable year to year with later ones.
- **Smoothed ice-core data.** The Law Dome spline attenuates variations shorter than about 20
  years by half. It is a good record of the long rise, and a poor guide to individual years.
  No per-year uncertainty is published for it, so the platform's uncertainty column is empty
  before 1959.
- **A data gap.** The 2022 Mauna Loa eruption interrupted the record; NOAA fills December 2022
  to July 2023 with measurements from Maunakea.
- **Licence.** NOAA data are public domain with a citation requested.

## 2. Global temperature: Berkeley Earth

**What it measures.** The annual change in global average surface temperature (land air
temperature and sea surface temperature) as an **anomaly**: the difference from a reference
period, not an absolute temperature.

**The product.** Berkeley Earth's High-Resolution Land/Ocean analysis, a 0.25° gridded field that
combines a land-surface field with HadSST4 ocean data and extrapolates over sea ice from nearby
land air temperature. Uncertainty is a 95% interval covering statistical and spatial
undersampling and ocean biases. The platform holds 1850–2025.

**Two reference periods.**

| Reference | Why it matters |
|---|---|
| **1951–1980** (the file's native baseline) | Berkeley Earth's own convention |
| **1850–1900** ("pre-industrial") | The reference used by the Paris Agreement and the IPCC. The platform *computes* the offset from the same dataset: the 1850–1900 mean is **−0.265 °C** relative to 1951–1980 (standard deviation 0.117 °C over 51 years), and subtracting it converts any anomaly to the Paris-relevant scale |

Subtracting that offset gives the headline numbers: **2025 is 1.45 °C and 2024 is 1.55 °C above
1850–1900**, with a 95% statistical uncertainty of about ±0.04 °C. As a cross-check, the 2025
value agrees with Berkeley Earth's own published 1.44 ± 0.09 °C.

**What to remember.**

- **Preliminary.** Berkeley Earth labels this dataset "preliminary data — subject to change
  without notice — not yet peer reviewed". Values can be revised and no final citation exists
  yet. The platform replaced an older summary file in October 2026 after Berkeley Earth confirmed
  that the high-resolution product is its operational dataset.
- **"Pre-industrial" is a convention.** 1850–1900 is a stand-in for conditions before large-scale
  fossil fuel use. The offset comes from the dataset's earliest years, where uncertainty is
  largest. Other groups choose different baselines or reconstruct them differently, and that
  alone shifts the headline "°C above pre-industrial" by a few hundredths of a degree.
- **One year is not a trend.** Annual values are influenced by El Niño and La Niña; the
  Paris Agreement's temperature goals are about long-term averages, not single years. The
  [Benchmarks](../03-benchmarks/03-temperature-and-concentration-vs-benchmarks.md) return to this.
- **Licence.** CC BY-NC: non-commercial use and attribution to Berkeley Earth. The platform's
  use is non-commercial; any commercial use would need a licence from them.

## 3. How the three series connect

| Link | Series | Unit | Nature |
|---|---|---|---|
| Emissions | OWID / GCP, PRIMAP-hist | Mt per year | Flow, inventory-based |
| Concentration | NOAA Mauna Loa + Law Dome | ppm | Stock, measured |
| Temperature | Berkeley Earth | °C above 1850–1900 | Response, observed |

The platform pairs them by calendar year and relates *cumulative* emissions to temperature,
because warming tracks the total CO₂ added to the atmosphere over time, not a single year's
emissions. [Methodology](../02-methodology/03-emissions-temperature-relationship.md) covers how, and how much
weight that relationship can bear.

## See also

- [Emissions Inventories](01-emissions-inventories.md)
- [Data Quality and Harmonization](03-data-quality-and-harmonization.md)
- [Technical: Multi-Source Data Pipelines](../../technical/01-data-science-ml/05-multi-source-pipelines.md)
  — ingestion of these two series and the pairing of series by year
