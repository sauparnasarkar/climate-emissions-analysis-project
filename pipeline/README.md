# `pipeline/` — Area 2 ingestion (Release 21, Phase 1.1)

Versioned ingestion scripts for the climate-context sources, one module per source, writing
normalized series to `data/climate/` (gitignored) plus provenance. Not intern curriculum and not
`api/` runtime code — see `SPEC.md` §5.26 and `ENHANCEMENTS.md` Release 21.

```
python -m pipeline.run                      # all sources
python -m pipeline.run --source noaa_gml    # or berkeley_earth
.venv/bin/python -m pytest pipeline/tests   # offline; no network
```

| Module | Output (`data/climate/`) | Source |
|---|---|---|
| `noaa_gml.py` | `co2_concentration_annual.csv` (1750–latest, spliced), `co2_concentration_monthly_mlo.csv` | NOAA GML Mauna Loa (1959+ annual; monthly from Mar 1958) + Law Dome ice-core/firn spline (< 1959) |
| `berkeley_earth.py` | `temperature_anomaly_annual.csv` (native 1951–1980 and computed 1850–1900 baselines) | Berkeley Earth Land/Ocean summary |

Also written: `provenance.json` (one entry per series: source URLs, retrieval time, release stamps,
raw-file sha256, coverage, units, gas scope, methodology, caveats, license) and `last_run.json`
(records processed + deviations from norm). Exit code 1 only if a source fails outright; a stale
or odd source is a *deviation* (warning) the refresh job turns into an alert.

Not yet here (later Phase 1.1 PRs): EDGAR (+ ISO3 crosswalk), the OWID step, and the monthly
refresh-job wiring/alerting.
