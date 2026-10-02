# `pipeline/` — Area 2 ingestion (Release 21, Phase 1.1)

Versioned ingestion scripts for the climate-context sources, one module per source, writing
normalized series to `data/climate/` (gitignored) plus provenance. Not intern curriculum and not
`api/` runtime code — see `SPEC.md` §5.26 and `ENHANCEMENTS.md` Release 21.

```
python -m pipeline.run                      # all sources
python -m pipeline.run --source noaa_gml    # or berkeley_earth, edgar
.venv/bin/python -m pytest pipeline/tests   # offline; no network
```

| Module | Output (`data/climate/`) | Source |
|---|---|---|
| `noaa_gml.py` | `co2_concentration_annual.csv` (1750–latest, spliced), `co2_concentration_monthly_mlo.csv` | NOAA GML Mauna Loa (1959+ annual; monthly from Mar 1958) + Law Dome ice-core/firn spline (< 1959) |
| `edgar.py` | `edgar_country_annual.csv` (entity × year, MtCO₂e by gas + combined total + residual), `edgar_global_composition_annual.csv` (global composition, bunkers, national total, per-year reconciliation), `country_crosswalk.csv` | EDGAR latest `EDGAR_<year>_GHG` release (auto-discovered): per-gas files + combined AR5 totals |
| `crosswalk.py` | (used by `edgar.py`) | ISO3 EDGAR↔OWID crosswalk built from both datasets' own entity lists |
| `berkeley_earth.py` | `temperature_anomaly_annual.csv` (native 1951–1980 and computed 1850–1900 baselines) | Berkeley Earth Land/Ocean summary |

Also written: `provenance.json` (one entry per series: source URLs, retrieval time, release stamps,
raw-file sha256, coverage, units, gas scope, methodology, caveats, license) and `last_run.json`
(records processed + deviations from norm). Exit code 1 only if a source fails outright; a stale
or odd source is a *deviation* (warning) the refresh job turns into an alert.

### EDGAR notes

- The gas split is built from the per-gas files (fossil CO₂; CH₄ and N₂O × AR5 GWP-100 of 28 / 265; F-gases from the AR5g CO₂e file), summed, and **reconciled against the combined AR5 workbook** every run. The per-year residual is in the output and provenance; a global residual beyond 1% in a year where all four gases exist raises a deviation.
- Known gaps in the 2026 release (explicit nulls, never interpolated; logged as `notes`, not alerts): the F-gas per-gas file has no data for 1970–1989 or 2025, and a small stable per-gas-vs-total residual exists in 1990–2024.
- International aviation/shipping (`AIR`, `SEA`) are tagged `entity_type='bunker'` and excluded from `national_total_mtco2e`, the country-share denominator; the global total includes them.
- **Licence caution:** the IEA-EDGAR CO₂ component is CC BY-NC-ND 4.0 (IEA); the workbook asks users to contact the IEA for permission. Carried in provenance; review before public/derivative use.
- Needs `openpyxl` (pinned in `requirements.txt`). Reads `data/owid-co2-data.csv` and `data/selected_countries.json` for the crosswalk if present.

Not yet here (later Phase 1.1 PR): the OWID step and the monthly refresh-job wiring/alerting.
