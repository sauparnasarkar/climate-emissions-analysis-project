"""The harmonized analytical layer. Release 21, Phase 1.2a (`ENHANCEMENTS.md` decisions 25-28).

A *derived* pipeline stage: it reads the normalized series the source steps wrote to `data/climate/`
and writes one consistent view of them, precomputed so the API, the frontend and the agent all serve the
same numbers (the API reads these tables and never recomputes them):

- `indicator_catalog.json`      -- every indicator: id, name, unit, scope, kind, coverage, the provenance
                                   of its source series, and for derived ones the baseline year, formula
                                   and excluded baselines (SPEC §2.5 asks the API/UI to expose these);
- `harmonized_global_annual.csv`  -- long: indicator_id, year, value (global-scope indicators);
- `harmonized_country_annual.csv` -- long: indicator_id, iso3, year, value (country-scope indicators).

What "harmonized" means here, concretely:
- one key: the integer calendar year, unique per indicator; each indicator keeps its **own** coverage
  (a "common range" only exists for a pair of indicators -- see `align_pair`);
- one unit per indicator, declared in the catalog; one **scope** (global or country) that can never be
  mixed in a pair;
- gaps are explicit nulls, never interpolated (`derive.py` documents the rules);
- every number links back to its source series' provenance entry (release, licence, checksums).

Derived indicators (`level` kind only): year-on-year %, trailing 5-year mean, and an index for each
allowed baseline (1990, 1970, pre-industrial = 1850) where the baseline value exists and is > 0.
`cumulative` series get none of these; `anomaly` series are **never indexed** (the 1850-1900 anomaly is
-0.13 C in 1850, so "= 100" is meaningless): they carry both native references and the trailing 5-year mean.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import derive
from .common import CLIMATE_DIR, PROVENANCE_PATH, RunReport, utc_now, write_csv_atomic, write_json_atomic

SCHEMA_VERSION = 1

SERIES_GLOBAL = "harmonized_global_annual"
SERIES_COUNTRY = "harmonized_country_annual"
SERIES_CATALOG = "indicator_catalog"


@dataclass
class Spec:
    id: str
    name: str
    unit: str
    kind: str  # level | cumulative | anomaly | uncertainty
    scope: str  # global | country
    file: str  # normalized CSV in data/climate/
    column: str | None  # None => computed (cumulative of `from_id`)
    source_series: str  # key into provenance.json
    description: str
    decimals: int = 2
    default_baseline: str | None = None  # one of derive.BASELINES (level indicators)
    default_reference: str | None = None  # for anomalies
    from_id: str | None = None  # cumulative: the level indicator it accumulates
    caveats: list[str] = field(default_factory=list)


_CO2E = "MtCO2e"
_LUC_UNCERTAINTY = (
    "Land-use CO2 is a modelled estimate (average of bookkeeping models) with a large uncertainty: the Global Carbon Budget gives about +/-0.7 GtC/yr "
    "(about +/-2.6 GtCO2/yr, 1 sigma) for recent decades."
)
_LUC_LICENSE = (
    "Land-use CO2 data originates from the Global Carbon Project via OWID. No formal license (e.g., CC BY) is stated on the Global Carbon Project's data page; "
    "use is conditional on citing the original source per their stated terms. The required citation is included in this platform's data attribution. "
    "No non-commercial, no-derivatives, or share-alike restrictions were found."
)

GLOBAL_SPECS: list[Spec] = [
    Spec("co2_concentration_ppm", "Atmospheric CO2 concentration", "ppm", "level", "global", "co2_concentration_annual.csv", "co2_ppm",
         "co2_concentration_annual", "Annual mean CO2: NOAA GML Mauna Loa from 1959, Law Dome ice-core/firn spline before.", 1, "preindustrial",
         caveats=["Spliced at 1959 from two stations/hemispheres; the overlap gap is in the source provenance."]),
    Spec("co2_concentration_uncertainty_ppm", "CO2 concentration uncertainty", "ppm", "uncertainty", "global", "co2_concentration_annual.csv", "uncertainty_ppm",
         "co2_concentration_annual", "NOAA's annual-mean uncertainty; null before 1959 (the Law Dome record publishes none).", 2),
    Spec("temperature_anomaly_1850_1900_c", "Global temperature anomaly (vs 1850-1900)", "°C", "anomaly", "global", "temperature_anomaly_annual.csv", "anomaly_1850_1900_c",
         "temperature_anomaly_annual", "Berkeley Earth land+ocean annual anomaly relative to the computed 1850-1900 mean.", 2, default_reference="1850_1900",
         caveats=["The 1850-1900 offset is computed from Berkeley Earth's own early record; the source is Berkeley Earth's preliminary high-resolution release (see provenance)."]),
    Spec("temperature_anomaly_1951_1980_c", "Global temperature anomaly (vs 1951-1980)", "°C", "anomaly", "global", "temperature_anomaly_annual.csv", "anomaly_1951_1980_c",
         "temperature_anomaly_annual", "Berkeley Earth land+ocean annual anomaly on its native 1951-1980 reference.", 2, default_reference="1951_1980"),
    Spec("temperature_uncertainty_95_c", "Temperature anomaly 95% interval", "°C", "uncertainty", "global", "temperature_anomaly_annual.csv", "uncertainty_95_c",
         "temperature_anomaly_annual", "Berkeley Earth's 95% confidence interval (statistical + spatial undersampling + ocean biases).", 3),
    Spec("owid_co2_world_mt", "World CO2 emissions (incl. international transport)", "Mt CO2", "level", "global", "owid_world_co2_annual.csv", "co2_mt",
         "owid_world_co2_annual", "OWID/GCP World fossil + cement CO2, including international aviation and shipping (the TCRE regression X-variable's annual flow).", 0, "1990"),
    Spec("owid_co2_world_cumulative_mt", "World cumulative CO2 emissions", "Mt CO2", "cumulative", "global", "owid_world_co2_annual.csv", "cumulative_co2_mt",
         "owid_world_co2_annual", "OWID's own cumulative World fossil + cement CO2 since 1750 (the secondary, fossil-only regression X-variable; the headline uses owid_total_co2_world_cumulative_mt, decision 40).", 0),
    Spec("owid_luc_co2_world_mt", "World land-use-change CO2 emissions", "Mt CO2", "level", "global", "owid_world_co2_annual.csv", "land_use_change_co2_mt",
         "owid_world_co2_annual", "OWID/Global Carbon Project World land-use-change CO2 (bookkeeping-model average), 1850 onward; a separate column from the fossil + cement total.", 0, "1990",
         caveats=[_LUC_UNCERTAINTY, _LUC_LICENSE]),
    Spec("owid_luc_co2_world_cumulative_mt", "World cumulative land-use-change CO2 since 1850", "Mt CO2", "cumulative", "global", "owid_world_co2_annual.csv", None,
         "owid_world_co2_annual", "Running total of OWID/Global Carbon Project land-use-change CO2 from 1850, the first year of the series (the land-use part of the headline X-variable).", 0,
         from_id="owid_luc_co2_world_mt", caveats=[_LUC_UNCERTAINTY, _LUC_LICENSE]),
    Spec("owid_total_co2_world_mt", "World total anthropogenic CO2 emissions (fossil + cement + land-use)", "Mt CO2", "level", "global", "owid_world_co2_annual.csv", "total_co2_incl_luc_mt",
         "owid_world_co2_annual", "Fossil + cement (incl. international aviation and shipping) plus land-use-change CO2: the annual flow behind the headline regression's X-variable.", 0, "1990",
         caveats=[_LUC_UNCERTAINTY, _LUC_LICENSE]),
    Spec("owid_total_co2_world_cumulative_mt", "World cumulative total anthropogenic CO2 since 1850", "Mt CO2", "cumulative", "global", "owid_world_co2_annual.csv", None,
         "owid_world_co2_annual", "Running total of total anthropogenic CO2 (fossil + cement + land-use) from 1850, the first year of the land-use series: the headline TCRE-style regression's X-variable (decision 40). "
         "Not comparable to the 1750-based fossil cumulative; a regression slope is unaffected by the choice of start year.", 0, from_id="owid_total_co2_world_mt",
         caveats=[_LUC_UNCERTAINTY, _LUC_LICENSE]),
    Spec("owid_co2_national_sum_mt", "Sum of national CO2 emissions", "Mt CO2", "level", "global", "owid_world_co2_annual.csv", "national_sum_mt",
         "owid_world_co2_annual", "Sum of ISO-coded countries; excludes international transport (the country-share denominator).", 0, "1990",
         caveats=["Includes some non-sovereign territories (ISO-coded OWID entities)."]),
    Spec("owid_co2_international_transport_mt", "International aviation + shipping CO2", "Mt CO2", "level", "global", "owid_world_co2_annual.csv", "international_transport_mt",
         "owid_world_co2_annual", "OWID's international aviation and shipping rows; null before the series starts.", 1, "1990"),
    Spec("primap_ghg_total_mtco2e", "Total GHG emissions, national (PRIMAP-hist)", _CO2E, "level", "global", "primap_global_composition_annual.csv", "total_ghg_mtco2e",
         "primap_global_composition_annual", "PRIMAP-hist Kyoto-GHG (AR5 GWP-100) national total excluding LULUCF and international transport; sum of reporting areas.", 0, "1970",
         caveats=["Excludes international aviation and shipping; values before ~1970 are reconstructions."]),
    Spec("primap_co2_mt", "CO2 (PRIMAP-hist national)", "Mt CO2", "level", "global", "primap_global_composition_annual.csv", "co2_mt",
         "primap_global_composition_annual", "PRIMAP-hist national CO2 (fossil + industrial), excluding LULUCF.", 0, "1970"),
    Spec("primap_ch4_mtco2e", "CH4 in CO2e (PRIMAP-hist national)", _CO2E, "level", "global", "primap_global_composition_annual.csv", "ch4_mtco2e",
         "primap_global_composition_annual", "PRIMAP-hist national CH4 x 28 (AR5 GWP-100).", 0, "1970"),
    Spec("primap_n2o_mtco2e", "N2O in CO2e (PRIMAP-hist national)", _CO2E, "level", "global", "primap_global_composition_annual.csv", "n2o_mtco2e",
         "primap_global_composition_annual", "PRIMAP-hist national N2O x 265 (AR5 GWP-100).", 0, "1970"),
    Spec("primap_fgas_mtco2e", "F-gases in CO2e (PRIMAP-hist national)", _CO2E, "level", "global", "primap_global_composition_annual.csv", "fgas_mtco2e",
         "primap_global_composition_annual", "PRIMAP-hist national F-gas basket (AR5 GWP-100).", 1, "1970"),
    Spec("primap_ghg_total_cumulative_mtco2e", "Cumulative total GHG emissions, national (PRIMAP-hist)", _CO2E, "cumulative", "global", "primap_global_composition_annual.csv", None,
         "primap_global_composition_annual", "Running total of the PRIMAP-hist national total from its first year.", 0, from_id="primap_ghg_total_mtco2e"),
]

COUNTRY_SPECS: list[Spec] = [
    Spec("primap_country_ghg_total_mtco2e", "Total GHG emissions by area (PRIMAP-hist)", _CO2E, "level", "country", "primap_country_annual.csv", "total_ghg_mtco2e",
         "primap_country_annual", "PRIMAP-hist Kyoto-GHG (AR5 GWP-100) per area, excluding LULUCF.", 1),
    Spec("primap_country_co2_mt", "CO2 by area (PRIMAP-hist)", "Mt CO2", "level", "country", "primap_country_annual.csv", "co2_mt",
         "primap_country_annual", "PRIMAP-hist CO2 per area.", 1),
    Spec("primap_country_ch4_mtco2e", "CH4 in CO2e by area (PRIMAP-hist)", _CO2E, "level", "country", "primap_country_annual.csv", "ch4_mtco2e",
         "primap_country_annual", "PRIMAP-hist CH4 x 28 per area.", 1),
    Spec("primap_country_n2o_mtco2e", "N2O in CO2e by area (PRIMAP-hist)", _CO2E, "level", "country", "primap_country_annual.csv", "n2o_mtco2e",
         "primap_country_annual", "PRIMAP-hist N2O x 265 per area.", 1),
    Spec("primap_country_fgas_mtco2e", "F-gases in CO2e by area (PRIMAP-hist)", _CO2E, "level", "country", "primap_country_annual.csv", "fgas_mtco2e",
         "primap_country_annual", "PRIMAP-hist F-gas basket per area; null where the area reports none.", 2),
    Spec("primap_country_ghg_total_cumulative_mtco2e", "Cumulative total GHG emissions by area (PRIMAP-hist)", _CO2E, "cumulative", "country", "primap_country_annual.csv", None,
         "primap_country_annual", "Running total per area from its first year (null from the first interior gap on).", 0, from_id="primap_country_ghg_total_mtco2e"),
]


_ATTRIBUTION_FIELDS = ("citations", "attribution_required", "required_citation_format", "land_use_license_note")


def _provenance_link(prov: dict, series_id: str) -> dict | None:
    e = prov.get(series_id)
    if not e:
        return None
    rel = e.get("source_release")
    return {"series": series_id, "source": e.get("source"), "retrieved_at": e.get("retrieved_at"), "coverage": e.get("coverage"),
            "license": e.get("license"), "source_release": rel if isinstance(rel, (dict, str)) else None,
            # the exact source artifacts: raw-file checksums (and the provider's own, where verified) travel with every indicator
            "raw_sha256": e.get("raw_sha256"), "checksum_verified": e.get("checksum_verified"), "source_urls": e.get("source_urls"),
            # attribution travels with the indicator too (a licence string can say "see land_use_license_note"): only the fields a source actually records
            **{k: e[k] for k in _ATTRIBUTION_FIELDS if k in e}}


def _derived_entries(spec: Spec, series: pd.Series) -> tuple[list[dict], dict[str, pd.Series], dict[str, str]]:
    """Derived catalog entries + their series, and the baselines that were excluded (with why).

    `level` indicators get year-on-year %, a trailing 5-year mean and an index per allowed baseline. `anomaly` indicators get
    **only** the trailing mean (decision 28): an anomaly can be zero or negative, so "= 100" has no meaning and a year-on-year
    percentage is undefined. Every derived entry inherits its base's description and caveats, so a consumer that is served only a
    derived metric still receives the limitation (e.g. the CO2 splice)."""
    entries, data, excluded = [], {}, {}
    base = {"derived_from": spec.id, "scope": spec.scope, "kind": "derived", "decimals": spec.decimals, "source_series": spec.source_series,
            "description": spec.description, "caveats": list(spec.caveats)}

    if spec.kind == "level":
        data[f"{spec.id}__yoy_pct"] = derive.yoy_pct(series)
        entries.append({**base, "id": f"{spec.id}__yoy_pct", "name": f"{spec.name}: year-on-year change", "unit": "%", "metric": "yoy_pct",
                        "formula": "100 × (value[y] / value[y-1] - 1); null if the previous calendar year is missing or not > 0", "decimals": 1})
    data[f"{spec.id}__mean5y"] = derive.trailing_mean(series)
    entries.append({**base, "id": f"{spec.id}__mean5y", "name": f"{spec.name}: trailing 5-year mean", "unit": spec.unit, "metric": "trailing_mean_5y",
                    "formula": "mean of the current and previous 4 calendar years; null until 5 consecutive observations (trailing, no look-ahead)"})
    if spec.kind != "level":
        return entries, data, excluded
    for key, year in derive.BASELINES.items():
        idx, problem = derive.index_to_baseline(series, year)
        if problem:
            excluded[key] = problem
            continue
        sid = f"{spec.id}__index_{key}"
        data[sid] = idx
        entries.append({**base, "id": sid, "name": f"{spec.name}: index ({'pre-industrial 1850' if key == 'preindustrial' else key} = 100)", "unit": f"index ({year} = 100)", "metric": "index",
                        "baseline": {"key": key, "year": year, "reference_period": f"calendar year {year}",
                                     "formula": f"100 × value[y] / value[{year}]", "baseline_value": float(series.loc[year])}, "decimals": 1,
                        "is_default_baseline": key == spec.default_baseline})
    return entries, data, excluded


def _span(s: pd.Series) -> list[int] | None:
    v = derive.first_last_valid(s)
    return list(v) if v else None


def build(climate_dir: str, provenance: dict, report: RunReport) -> tuple[pd.DataFrame, pd.DataFrame, list[dict]]:
    """(global long table, country long table, catalog entries)."""
    cache: dict[str, pd.DataFrame | None] = {}

    def load(fname: str) -> pd.DataFrame | None:
        if fname not in cache:
            path = os.path.join(climate_dir, fname)
            cache[fname] = pd.read_csv(path) if os.path.exists(path) else None
            if cache[fname] is None:
                report.deviate(f"input {fname} not found: every indicator built from it is skipped")
        return cache[fname]

    catalog: list[dict] = []
    missing_prov: set[str] = set()
    glob_rows: list[pd.DataFrame] = []
    ctry_rows: list[pd.DataFrame] = []
    base_series: dict[str, pd.Series] = {}  # global-scope level series by id (for cumulative)

    def check_provenance_coverage(spec: Spec, df: pd.DataFrame):
        prov = provenance.get(spec.source_series)
        if not prov:
            if spec.source_series not in missing_prov:  # once per series, not once per indicator built from it
                missing_prov.add(spec.source_series)
                report.deviate(f"source series {spec.source_series!r} has no entry in provenance.json (its indicators have no provenance link)")
            return
        cov = prov.get("coverage")
        years = df["year"]
        if cov and [int(years.min()), int(years.max())] != [int(cov[0]), int(cov[1])]:
            report.deviate(f"{spec.id}: {spec.file} spans {int(years.min())}-{int(years.max())} but provenance says {cov[0]}-{cov[1]} (stale provenance or a half-written source)")

    # ---------------- global scope
    for spec in GLOBAL_SPECS:
        df = load(spec.file)
        if df is None:
            continue
        check_provenance_coverage(spec, df)
        if spec.column is None:
            src = base_series.get(spec.from_id)
            if src is None:
                report.deviate(f"{spec.id}: its source indicator {spec.from_id} was not built; skipped")
                continue
            s = derive.cumulative(src)
        else:
            if spec.column not in df.columns:
                report.deviate(f"{spec.id}: column {spec.column!r} missing from {spec.file}; skipped")
                continue
            s = df.set_index("year")[spec.column].astype(float)
            if s.index.has_duplicates:
                raise ValueError(f"{spec.file}: duplicate years")
        if s.isna().all():
            report.deviate(f"{spec.id}: no values at all; skipped")
            continue
        if spec.kind == "level":
            base_series[spec.id] = s
        entry = {"id": spec.id, "name": spec.name, "unit": spec.unit, "kind": spec.kind, "scope": spec.scope, "description": spec.description,
                 "decimals": spec.decimals, "source_series": spec.source_series, "provenance": _provenance_link(provenance, spec.source_series),
                 "coverage": _span(s), "n_values": int(s.notna().sum()), "caveats": spec.caveats}
        if spec.default_baseline and spec.kind == "level":  # only level indicators have indices; never advertise a baseline that cannot be applied
            entry["default_baseline"] = spec.default_baseline
        if spec.default_reference:
            entry["default_reference"] = spec.default_reference
        series_map = {spec.id: s}
        derived_entries: list[dict] = []
        if spec.kind in ("level", "anomaly"):
            derived_entries, derived_data, excluded = _derived_entries(spec, s)
            series_map.update(derived_data)
            if spec.kind == "level":
                entry["allowed_baselines"] = [k for k in derive.BASELINES if k not in excluded]
                entry["excluded_baselines"] = excluded
            for e in derived_entries:
                e["provenance"] = entry["provenance"]
                e["coverage"] = _span(derived_data[e["id"]])
                e["n_values"] = int(derived_data[e["id"]].notna().sum())
        catalog.append(entry)
        catalog.extend(derived_entries)
        for sid, ser in series_map.items():
            part = ser.dropna().rename("value").rename_axis("year").reset_index()
            part.insert(0, "indicator_id", sid)
            glob_rows.append(part[["indicator_id", "year", "value"]])

    # ---------------- country scope
    # No pandas pivot/unstack here, deliberately: on numpy 2.2.6 + Python 3.14 (the pinned production stack) a dense
    # reshape of more than ~32k rows silently returns corrupted year labels (see common.check_reshape_environment).
    # Per-area groupby loops and plain row filtering are exact on every stack.
    cdf = load("primap_country_annual.csv")
    if cdf is not None:
        if cdf.duplicated(["iso3", "year"]).any():
            raise ValueError("primap_country_annual.csv: duplicate (iso3, year)")
        col_of = {s.id: s.column for s in COUNTRY_SPECS}
        for spec in COUNTRY_SPECS:
            check_provenance_coverage(spec, cdf)
            if spec.column is None:
                src_col = col_of.get(spec.from_id)
                if src_col is None or src_col not in cdf.columns:
                    report.deviate(f"{spec.id}: its source column {src_col!r} (for {spec.from_id}) is missing from {spec.file}; skipped")
                    continue
                parts = []
                for iso, g in cdf.groupby("iso3", sort=True):
                    cum = derive.cumulative(g.set_index("year")[src_col].astype(float)).dropna()
                    parts.append(pd.DataFrame({"iso3": iso, "year": cum.index.astype(int), "value": cum.to_numpy()}))
                long = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=["iso3", "year", "value"])
            else:
                if spec.column not in cdf.columns:
                    report.deviate(f"{spec.id}: column {spec.column!r} missing from {spec.file}; skipped")
                    continue
                long = cdf[["iso3", "year", spec.column]].dropna().rename(columns={spec.column: "value"})  # null rows are absent, never fabricated
            if long.empty:
                report.deviate(f"{spec.id}: no values at all; skipped")
                continue
            long = long.assign(indicator_id=spec.id)
            ctry_rows.append(long[["indicator_id", "iso3", "year", "value"]])
            catalog.append({"id": spec.id, "name": spec.name, "unit": spec.unit, "kind": spec.kind, "scope": spec.scope, "description": spec.description,
                            "decimals": spec.decimals, "source_series": spec.source_series, "provenance": _provenance_link(provenance, spec.source_series),
                            "coverage": [int(long["year"].min()), int(long["year"].max())], "n_values": int(len(long)), "n_areas": int(long["iso3"].nunique()),
                            "caveats": spec.caveats})

    glob = pd.concat(glob_rows, ignore_index=True) if glob_rows else pd.DataFrame(columns=["indicator_id", "year", "value"])
    ctry = pd.concat(ctry_rows, ignore_index=True) if ctry_rows else pd.DataFrame(columns=["indicator_id", "iso3", "year", "value"])
    glob = glob.assign(year=glob["year"].astype(int))
    ctry = ctry.assign(year=ctry["year"].astype(int))
    return glob, ctry, catalog


def validate(glob: pd.DataFrame, ctry: pd.DataFrame, catalog: list[dict], report: RunReport) -> None:
    """Structural guarantees of the layer; each failure is a deviation (or an error where the data is unusable)."""
    ids = [e["id"] for e in catalog]
    if len(ids) != len(set(ids)):
        raise ValueError("indicator_catalog: duplicate indicator ids")
    if glob.duplicated(["indicator_id", "year"]).any():
        raise ValueError("harmonized_global_annual: duplicate (indicator_id, year)")
    if ctry.duplicated(["indicator_id", "iso3", "year"]).any():
        raise ValueError("harmonized_country_annual: duplicate (indicator_id, iso3, year)")
    scope = {e["id"]: e["scope"] for e in catalog}
    stray = (set(glob["indicator_id"]) - {i for i, s in scope.items() if s == "global"}) | (set(ctry["indicator_id"]) - {i for i, s in scope.items() if s == "country"})
    if stray:
        raise ValueError(f"harmonized tables hold indicators outside their scope: {sorted(stray)}")
    if np.isinf(glob["value"]).any() or np.isinf(ctry["value"]).any():
        raise ValueError("harmonized tables contain infinite values")


def run(climate_dir: str = CLIMATE_DIR, provenance_path: str = PROVENANCE_PATH, out_dir: str | None = None) -> RunReport:
    out_dir = out_dir or climate_dir
    report = RunReport("harmonize")
    provenance = json.load(open(provenance_path)) if os.path.exists(provenance_path) else {}
    if not provenance:
        report.deviate("provenance.json not found or empty: no indicator can link its source")
    glob, ctry, catalog = build(climate_dir, provenance, report)
    if glob.empty and ctry.empty:
        raise ValueError("harmonize: no input series found in " + climate_dir)
    validate(glob, ctry, catalog, report)

    write_csv_atomic(glob.sort_values(["indicator_id", "year"]).round(6), os.path.join(out_dir, "harmonized_global_annual.csv"))
    write_csv_atomic(ctry.sort_values(["indicator_id", "iso3", "year"]).round(6), os.path.join(out_dir, "harmonized_country_annual.csv"))
    write_json_atomic(
        {"schema_version": SCHEMA_VERSION, "generated_at": utc_now(), "baselines": {k: {"year": y, "reference_period": f"calendar year {y}"} for k, y in derive.BASELINES.items()},
         "trailing_window_years": derive.TRAILING_WINDOW,
         "notes": ["Gaps are explicit nulls; nothing is interpolated.", "Anomaly indicators are never indexed; level indicators are, where the baseline value exists and is > 0.",
                   "Correlation features are interpretive context, not proof of causation."],
         "indicators": catalog},
        os.path.join(out_dir, "indicator_catalog.json"),
    )
    report.count(SERIES_GLOBAL, len(glob))
    report.count(SERIES_COUNTRY, len(ctry))
    report.count(SERIES_CATALOG, len(catalog))
    base = [e for e in catalog if e["kind"] != "derived"]
    report.note(f"{len(base)} base + {len(catalog) - len(base)} derived indicators ({sum(e['scope'] == 'global' for e in catalog)} global, {sum(e['scope'] == 'country' for e in catalog)} country)")
    undef = {e["id"]: e["excluded_baselines"] for e in catalog if e.get("excluded_baselines")}
    if undef:
        report.note("baselines not defined for: " + "; ".join(f"{i}: {', '.join(v)}" for i, v in undef.items()))
    return report
