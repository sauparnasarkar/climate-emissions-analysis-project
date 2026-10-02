# `pipeline/` — Area 2 ingestion (Release 21, Phase 1.1)

Versioned ingestion scripts for the climate-context sources, one module per source, writing
normalized series to `data/climate/` (gitignored) plus provenance. Not intern curriculum and not
`api/` runtime code — see `SPEC.md` §5.26 and `ENHANCEMENTS.md` Release 21.

```
python -m pipeline.run                      # all ACTIVE (publishable) sources
python -m pipeline.run --source noaa_gml    # or berkeley_earth, primap_hist, owid, harmonize
python -m pipeline.run --source edgar       # shelved source: explicit opt-in, writes to data/internal/edgar/ only
.venv/bin/python -m pytest pipeline/tests   # offline; no network
```

| Module | Output (`data/climate/`) | Source |
|---|---|---|
| `noaa_gml.py` | `co2_concentration_annual.csv` (1750–latest, spliced), `co2_concentration_monthly_mlo.csv` | NOAA GML Mauna Loa (1959+ annual; monthly from Mar 1958) + Law Dome ice-core/firn spline (< 1959) |
| `primap_hist.py` | `primap_country_annual.csv` (area × year, MtCO₂e by gas + Kyoto-basket total + residual; explicit nulls), `primap_global_composition_annual.csv` (1750–latest complete year: gases, areas reporting, per-gas-sum residual), `country_crosswalk.csv` | PRIMAP-hist, latest Zenodo release (via the concept record): no-extrapolation CSV, HISTCR, category M.0.EL, AR5 baskets; **CC BY-NC-SA 4.0** |
| `owid.py` | `owid_world_co2_annual.csv` (World CO₂ incl. international transport, cumulative, national sum, international transport; through the latest complete year); provenance for `data/owid-co2-data.csv` | OWID (Global Carbon Project) — **registers the file the refresh job downloaded; does not download** |
| `harmonize.py` + `derive.py` (derived stage, runs after the sources in `all`) | `indicator_catalog.json`, `harmonized_global_annual.csv` (indicator_id, year, value), `harmonized_country_annual.csv` (indicator_id, iso3, year, value) | the other normalized series + `provenance.json` — one consistent, precomputed view (Phase 1.2) |
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

### Harmonized layer (`harmonize.py`, `derive.py`)

One key (integer calendar year, unique per indicator), one unit and one **scope** (global / country) per indicator, explicit nulls (nothing is interpolated), and a link from every indicator to its source series' provenance. `indicator_catalog.json` lists every indicator: id, name, unit, kind (`level` / `cumulative` / `anomaly` / `uncertainty` / `derived`), its own coverage, provenance link, and for derived ones the baseline year, formula and the baselines that were excluded (with why). The API reads these tables; it never recomputes them.

- **Level** series get year-on-year %, a **trailing** 5-year mean (null until 5 consecutive observations; trailing so it never uses a later year) and an index for each allowed baseline: 1990, 1970, pre-industrial (= 1850) — defined only where the baseline value exists and is > 0.
- **Cumulative** series are never indexed or averaged. **Anomalies are never indexed** (the 1850–1900 anomaly is −0.13 °C in 1850, so "= 100" is meaningless, and a year-on-year % of an anomaly is undefined); they keep both native references and the interval, and get the trailing 5-year mean only. Every derived entry inherits its base's description and caveats, and every provenance link carries the source's checksums and URLs.
- Country scope is deliberately small: PRIMAP total, per-gas and cumulative per area.
- **No dense pandas reshapes anywhere in this layer** — see the environment note below.

### Pairing (`pairing.py`) — correlation-ready aligned series

```python
from pipeline.pairing import load_harmonized, align_pair
h = load_harmonized()                       # reads data/climate/{indicator_catalog.json, harmonized_*.csv}
frame, meta = align_pair(h, "owid_co2_world_cumulative_mt", "temperature_anomaly_1850_1900_c")
```

`frame` has columns `year`, `<a>`, `<b>` and only years where **both** series have a value (no interpolation). `meta` carries both indicators' catalog entries (unit, kind, coverage, **provenance link with release / licence / checksums**, caveats), the requested / common / used ranges, **every omitted year with its reason** (`a missing` / `b missing` / `both missing`, within the requested range), `interpolated: false`, and a standing note that co-movement is interpretive context, not proof of causation. Phase 1.3's co-trends, regressions and composition outputs are built on this.

Refused, with a clear error: pairing an indicator with itself; a **global** with a **country** indicator (country pairs need one named `geography` shared by both — country emissions are never paired with the global temperature line, §1.3.4); `uncertainty` series (they describe a series, they are not one); an empty range; and fewer than `min_overlap` (default 20) shared years — a correlation over a handful of years looks authoritative and means nothing. Derived indicators pair too, and the common range follows their own coverage (a trailing 5-year mean starts four years into the record).

### Environment note: numpy 2.2.6 on Python 3.14 corrupts large dense reshapes

Found while building the harmonized layer: with the pinned stack (numpy 2.2.6, Python 3.14), `DataFrame.pivot` / `unstack` on a **fully populated** frame of more than ~32k rows (2¹⁵) silently returns wrong, duplicated year labels — no error (27,500 rows are fine, 41,250 are not). Isolated in a throwaway venv: **numpy ≥ 2.3.0 fixes it (checked 2.3.0–2.3.5 and 2.5.3, with pandas 2.3.0); pandas 2.3.3 does not fix it while numpy stays 2.2.6.** The Mac Mini runs the same stack. No production code path is currently affected (the API's world-map pivot handles 7.6k rows from 1990, ~12k from 1970), and the pipeline avoids dense reshapes, but `pipeline.run` carries a **canary** (`common.check_reshape_environment`) that reports the problem as an `environment` deviation in every run until numpy is upgraded.

### OWID notes

- **No download here.** The refresh job (`ops/ghg-data-refresh.sh`) already backs up, downloads and validates the OWID file (the week-1 notebook is the validation authority) and restores the backup on failure. `owid.py` takes the file as it stands afterwards, records provenance (path, sha256, rows, coverage, licence, citations; `retrieved_at` is the file's modification time) and publishes the small normalized World series.
- **World series (decision 15):** `co2_mt` is OWID's World total **including international aviation/shipping** (the TCRE regression X-variable); `national_sum_mt` sums the ISO-coded countries (the country-share denominator); `international_transport_mt` is OWID's aviation + shipping rows. They reconcile (2024: within 0.02%); a gap above 1% is a deviation.
- **Completeness (trailing years only):** emission-weighted country coverage ≥ 98% **and** World CO₂ within ±15% of the prior year. The last four years are checked and everything from the **first** failing year onward is trimmed (two consecutive partial years would otherwise let the second look complete relative to the first); more than two raises. Full-history year-on-year isn't tested: the World series swings −27%…+34% in 1803–1830.
- **Deviations:** file older than 45 days (the refresh job has stopped), latest year more than two years behind, row count down >5% vs the previous run, World `cumulative_co2` gaps.

### Notifications and the refresh job

`pipeline.run` writes `data/climate/last_run.json` plus `last_run.priority` / `last_run.title` / `last_run.message` (urgent = a source failed outright, high = deviations from norm, default = clean). The refresh script reads those three files and appends them to its ntfy push. The versioned script and the monthly launchd plist, and how to deploy them to the Mac Mini, are in `ops/` (nothing is deployed by merging).

### EDGAR notes — SHELVED for publication

EDGAR is **not** an active source: it is excluded from `--source all`, writes only to `data/internal/edgar/` (which the API never reads), and must not feed any public surface. Reason: the fuel-combustion CO₂ in EDGAR (88.5% of its CO₂ and 65.5% of its total GHG in 2023) is IEA data licensed CC BY-NC-ND 4.0; ND bars sharing the transformed series this pipeline produces, and IEA permission has not been obtained. It is kept to cross-check the active total-GHG source locally, and for re-activation if permission is obtained and its sector detail proves worth it (`ENHANCEMENTS.md` Release 21, decision 20).

- The gas split is built from the per-gas files (fossil CO₂; CH₄ and N₂O × AR5 GWP-100 of 28 / 265; F-gases from the AR5g CO₂e file), summed, and **reconciled against the combined AR5 workbook** every run. The per-year residual is in the output and provenance; a global residual beyond 1% in a year where all four gases exist raises a deviation.
- Known gaps in the 2026 release (explicit nulls, never interpolated; logged as `notes`, not alerts): the F-gas per-gas file has no data for 1970–1989 or 2025, and a small stable per-gas-vs-total residual exists in 1990–2024.
- International aviation/shipping (`AIR`, `SEA`) are tagged `entity_type='bunker'` and excluded from `national_total_mtco2e`, the country-share denominator; the global total includes them.
- Needs `openpyxl` (pinned in `requirements.txt`). Reads `data/owid-co2-data.csv` and `data/selected_countries.json` for the crosswalk if present.

Not yet here (later Phase 1.1 PR): the OWID step and the monthly refresh-job wiring/alerting.
