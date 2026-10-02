# `pipeline/` — Area 2 ingestion (Release 21, Phase 1.1)

Versioned ingestion scripts for the climate-context sources, one module per source, writing
normalized series to `data/climate/` (gitignored) plus provenance. Not intern curriculum and not
`api/` runtime code — see `SPEC.md` §5.26 and `ENHANCEMENTS.md` Release 21.

```
python -m pipeline.run                      # all ACTIVE (publishable) sources
python -m pipeline.run --source noaa_gml    # or berkeley_earth, primap_hist
python -m pipeline.run --source edgar       # shelved source: explicit opt-in, writes to data/internal/edgar/ only
.venv/bin/python -m pytest pipeline/tests   # offline; no network
```

| Module | Output (`data/climate/`) | Source |
|---|---|---|
| `noaa_gml.py` | `co2_concentration_annual.csv` (1750–latest, spliced), `co2_concentration_monthly_mlo.csv` | NOAA GML Mauna Loa (1959+ annual; monthly from Mar 1958) + Law Dome ice-core/firn spline (< 1959) |
| `primap_hist.py` | `primap_country_annual.csv` (area × year, MtCO₂e by gas + Kyoto-basket total + residual; explicit nulls), `primap_global_composition_annual.csv` (1750–latest complete year: gases, areas reporting, per-gas-sum residual), `country_crosswalk.csv` | PRIMAP-hist, latest Zenodo release (via the concept record): no-extrapolation CSV, HISTCR, category M.0.EL, AR5 baskets; **CC BY-NC-SA 4.0** |
| `edgar.py` **(shelved — internal validation only)** | `data/internal/edgar/`: `edgar_country_annual.csv` (entity × year, MtCO₂e by gas + combined total + residual), `edgar_global_composition_annual.csv` (global composition, bunkers, national total, per-year reconciliation), `country_crosswalk.csv` | EDGAR latest `EDGAR_<year>_GHG` release (auto-discovered): per-gas files + combined AR5 totals |
| `crosswalk.py` | (used by `edgar.py`) | ISO3 EDGAR↔OWID crosswalk built from both datasets' own entity lists |
| `berkeley_earth.py` | `temperature_anomaly_annual.csv` (native 1951–1980 and computed 1850–1900 baselines) | Berkeley Earth Land/Ocean summary |

Also written: `provenance.json` (one entry per series: source URLs, retrieval time, release stamps,
raw-file sha256, coverage, units, gas scope, methodology, caveats, license) and `last_run.json`
(records processed + deviations from norm). Exit code 1 only if a source fails outright; a stale
or odd source is a *deviation* (warning) the refresh job turns into an alert.

### PRIMAP-hist notes

- **Why PRIMAP-hist:** it replaces EDGAR as the total-GHG / composition / country-share source because EDGAR's IEA-sourced fuel-combustion CO₂ is CC BY-NC-ND 4.0 (`ENHANCEMENTS.md` Release 21, decisions 20–21). PRIMAP-hist is **CC BY-NC-SA 4.0** (since v2.8; the dataset's YAML says Attribution-NonCommercial — the authors have been asked which is authoritative): non-commercial use only, published derived data must carry the notice and attribution, and the authors ask to be notified of use. Its provenance entry carries the licence, both citations and `attribution_required`.
- **Integrity:** the release is found through Zenodo's concept record; the CSV and YAML MD5 are verified against Zenodo's own checksums, so a truncated download fails instead of publishing.
- **Completeness (decision 22):** a year is published only if each of CO₂, CH₄, N₂O and the F-gas basket has **emission-weighted coverage ≥ 98%** (the share of the previous year's emissions still reported) and the national total is within **±15%** of the prior year. Emission-weighted rather than area-count because F-gas reporting drifts from 169 to 151 areas over 2017–2024 while the missing areas hold ~0.04% of emissions. Calibrated over 1751–2024: every gas ≥ 99.96%, total year-on-year −9.2% (1945) to +9.9% (1920). v2.8's 2025 fails (CH₄ 2.0%, N₂O 0.1%, F-gases 0.0%, total −28.3%) and is excluded. A failing year followed by a passing one raises; more than one trailing year trimmed raises a deviation.
- **Consistency check:** the per-gas sum (CO₂ + CH₄×28 + N₂O×265 + F-gas basket) must reproduce PRIMAP-hist's own Kyoto basket within 0.5% (v2.8: −0.18% … +0.21%).
- **Scope:** national emissions excluding LULUCF **and excluding international aviation/shipping** (not in the dataset); no world aggregate in the file, so the world total is the sum of areas.

### EDGAR notes — SHELVED for publication

EDGAR is **not** an active source: it is excluded from `--source all`, writes only to `data/internal/edgar/` (which the API never reads), and must not feed any public surface. Reason: the fuel-combustion CO₂ in EDGAR (88.5% of its CO₂ and 65.5% of its total GHG in 2023) is IEA data licensed CC BY-NC-ND 4.0; ND bars sharing the transformed series this pipeline produces, and IEA permission has not been obtained. It is kept to cross-check the active total-GHG source locally, and for re-activation if permission is obtained and its sector detail proves worth it (`ENHANCEMENTS.md` Release 21, decision 20).

- The gas split is built from the per-gas files (fossil CO₂; CH₄ and N₂O × AR5 GWP-100 of 28 / 265; F-gases from the AR5g CO₂e file), summed, and **reconciled against the combined AR5 workbook** every run. The per-year residual is in the output and provenance; a global residual beyond 1% in a year where all four gases exist raises a deviation.
- Known gaps in the 2026 release (explicit nulls, never interpolated; logged as `notes`, not alerts): the F-gas per-gas file has no data for 1970–1989 or 2025, and a small stable per-gas-vs-total residual exists in 1990–2024.
- International aviation/shipping (`AIR`, `SEA`) are tagged `entity_type='bunker'` and excluded from `national_total_mtco2e`, the country-share denominator; the global total includes them.
- Needs `openpyxl` (pinned in `requirements.txt`). Reads `data/owid-co2-data.csv` and `data/selected_countries.json` for the crosswalk if present.

Not yet here (later Phase 1.1 PR): the OWID step and the monthly refresh-job wiring/alerting.
