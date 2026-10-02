"""PRIMAP-hist total-GHG / gas-composition / country-share ingestion. Release 21, Phase 1.1b'.

PRIMAP-hist (Gütschow & Pflüger) replaces EDGAR as the active total-GHG source (`SPEC.md` §5.26
decision 21): EDGAR's fuel-combustion CO2 is IEA data under CC BY-NC-ND 4.0 and is shelved
(decision 20). PRIMAP-hist is CC BY-NC-SA 4.0 since v2.8 -- fine for this non-commercial site;
published derived data must carry the notice and attribution.

What is ingested: the latest Zenodo release (discovered through the concept record, so a new
version needs no code change), the **no-extrapolation** CSV, scenario HISTCR (country-reported
priority), category M.0.EL (national total excluding LULUCF), entities CO2, CH4, N2O, the AR5
F-gas basket and the AR5 Kyoto-GHG basket. The download's MD5 is verified against Zenodo's own
checksum. International aviation/shipping are not in the dataset and there is no world aggregate
in the file, so the world total is the sum of areas.

Completeness (decision 22): a year is published only if, for each of the four gas series,
**emission-weighted coverage** is at least `COVERAGE_MIN` (the share of the previous year's
emissions that is still reported this year) and the national total is within `YOY_MAX` of the
prior year. Emission-weighted, not area-count: F-gas reporting drifts from 169 to 151 areas over
2017-2024 but the missing areas hold ~0.04% of emissions, whereas the no-extrapolation file's
2025 has CH4 for 2% of emissions, N2O 0.06%, F-gases none. Failing *trailing* years are
trimmed and recorded; a failing year followed by a passing one raises (an interior gap is never
silently dropped). Extrapolated values are never ingested.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
from datetime import date

import numpy as np
import pandas as pd

from .common import (
    CLIMATE_DIR,
    PROVENANCE_PATH,
    ROOT,
    RunReport,
    fetch,
    require_contiguous_years,
    write_csv_atomic,
    write_provenance,
)
from .crosswalk import build_crosswalk, expanded_gaps

ZENODO_CONCEPT_URL = "https://zenodo.org/api/records/4479171"  # concept record: resolves to the latest version

SCENARIO = "HISTCR"
CATEGORY = "M.0.EL"
ENTITIES = {"co2": "CO2", "ch4": "CH4", "n2o": "N2O", "fgas": "FGASES (AR5GWP100)", "total": "KYOTOGHG (AR5GWP100)"}
GWP_AR5 = {"ch4": 28, "n2o": 265}  # IPCC AR5 GWP-100, matching the AR5 baskets used for FGASES/KYOTOGHG
GAS_KEYS = ("co2", "ch4", "n2o", "fgas")

COVERAGE_MIN = 0.98  # emission-weighted share of last year's emissions still reported
YOY_MAX = 0.15  # |national total / prior-year total - 1|; history peaks at +9.85% (1920), -9.21% (1945)
CONSISTENCY_TOL_PCT = 0.5  # components (CO2 + CH4*28 + N2O*265 + F-gases) vs the Kyoto basket
MAX_LAG_YEARS = 2
MAX_RELEASE_AGE_DAYS = 500  # PRIMAP-hist releases roughly yearly (Sep/Oct)

SERIES_COUNTRY = "primap_country_annual"
SERIES_GLOBAL = "primap_global_composition_annual"
SERIES_CROSSWALK = "country_crosswalk"

CITATIONS = [
    "Gütschow, J.; Pflüger, M. (2026): The PRIMAP-hist national historical emissions time series v2.8 (1750-2025). zenodo. doi:10.5281/zenodo.22876287 (cite the DOI of the version used).",
    "Gütschow, J.; Jeffery, L.; Gieseke, R.; Gebel, R.; Stevens, D.; Krapp, M.; Rocha, M. (2016): The PRIMAP-hist national historical emissions time series, Earth Syst. Sci. Data, 8, 571-603, doi:10.5194/essd-8-571-2016",
]


# ---------------------------------------------------------------- discovery & integrity


def pick_files(release: dict) -> dict[str, dict]:
    """The no-extrapolation, default-rounding CSV and its YAML from a Zenodo record.
    (`..._no_extrap_no_rounding_...` and the extrapolated files are deliberately not matched.)"""
    pats = {
        "csv": r"^Guetschow_et_al_\d{4}-PRIMAP-hist_v[\d.]+_final_no_extrap_\d{2}-[A-Za-z]{3}-\d{4}\.csv$",
        "yaml": r"^Guetschow_et_al_\d{4}-PRIMAP-hist_v[\d.]+_final_no_extrap_\d{2}-[A-Za-z]{3}-\d{4}\.yaml$",
    }
    out = {}
    for kind, pat in pats.items():
        hits = [f for f in release.get("files", []) if re.match(pat, f["key"])]
        if len(hits) != 1:
            raise ValueError(f"PRIMAP-hist release: expected exactly one {kind} file matching the no-extrapolation pattern, found {len(hits)}")
        out[kind] = hits[0]
    return out


def verify_checksum(content: bytes, checksum: str, label: str) -> None:
    algo, _, expected = checksum.partition(":")
    if algo != "md5":
        raise ValueError(f"{label}: unsupported checksum algorithm {algo!r}")
    got = hashlib.md5(content).hexdigest()
    if got != expected:
        raise ValueError(f"{label}: MD5 mismatch (expected {expected}, got {got}) -- corrupt or truncated download")


# ---------------------------------------------------------------- parsing


def parse_primap(csv_bytes: bytes) -> dict[str, pd.DataFrame]:
    """Wide frames (area x year, Gg) for each entity, for HISTCR / M.0.EL. Column names are matched
    by prefix so a re-labelled suffix (e.g. a renamed category scheme) fails loudly, not silently."""
    df = pd.read_csv(io.BytesIO(csv_bytes))
    need = {"scenario": "scenario (PRIMAP-hist)", "category": "category (IPCC2006_PRIMAP)", "area": "area (ISO3)", "entity": "entity"}
    for k, col in need.items():
        if col not in df.columns:
            raise ValueError(f"PRIMAP-hist CSV: expected column {col!r}")
    ycols = [c for c in df.columns if re.fullmatch(r"\d{4}", str(c))]
    if not ycols:
        raise ValueError("PRIMAP-hist CSV: no year columns")
    sel = df[(df[need["scenario"]] == SCENARIO) & (df[need["category"]] == CATEGORY)]
    out = {}
    for key, ent in ENTITIES.items():
        e = sel[sel[need["entity"]] == ent]
        if e.empty:
            raise ValueError(f"PRIMAP-hist CSV: no rows for entity {ent!r} ({SCENARIO}, {CATEGORY})")
        if e[need["area"]].duplicated().any():
            raise ValueError(f"PRIMAP-hist CSV: duplicate areas for entity {ent!r}")
        w = e.set_index(need["area"])[ycols].astype(float)
        w.columns = [int(c) for c in w.columns]
        out[key] = w
    return out


# ---------------------------------------------------------------- completeness


def weighted_coverage(wide: pd.DataFrame) -> pd.Series:
    """Per year: the share of the previous year's emissions held by areas that still report this
    year. NaN where the previous year has no emissions (nothing to cover) -- such years pass."""
    years = list(wide.columns)
    cov = {}
    for i in range(1, len(years)):
        prev, cur = wide[years[i - 1]].clip(lower=0), wide[years[i]]
        den = prev.sum()
        cov[years[i]] = prev.where(cur.notna(), 0).sum() / den if den > 0 else np.nan
    return pd.Series(cov, dtype=float)


def assess_years(wides: dict[str, pd.DataFrame]) -> pd.DataFrame:
    years = list(wides["total"].columns)
    rows = {y: {"year": y} for y in years}
    for k in GAS_KEYS:
        cov = weighted_coverage(wides[k])
        for y in years:
            rows[y][f"coverage_{k}"] = cov.get(y, np.nan)
            rows[y][f"areas_{k}"] = int(wides[k][y].notna().sum())
    total = wides["total"].sum(min_count=1)
    for i, y in enumerate(years):
        prev = total.iloc[i - 1] if i else np.nan
        rows[y]["total_gt"] = total[y] / 1e6
        rows[y]["yoy"] = (total[y] / prev - 1) if (i and prev and prev > 0) else np.nan
    a = pd.DataFrame(rows.values())
    reasons = []
    for _, r in a.iterrows():
        why = [f"{k} coverage {r[f'coverage_{k}']:.1%} < {COVERAGE_MIN:.0%}" for k in GAS_KEYS if r[f"coverage_{k}"] < COVERAGE_MIN]
        if abs(r["yoy"]) > YOY_MAX:
            why.append(f"total {r['yoy']:+.1%} vs prior year (limit ±{YOY_MAX:.0%})")
        reasons.append("; ".join(why))
    return a.assign(reasons=reasons, complete=[r == "" for r in reasons])


def trim_incomplete(assessment: pd.DataFrame) -> tuple[int, list[dict]]:
    """(last complete year, excluded trailing years with their metrics). Raises if a failing year
    precedes a passing one: an interior gap must never be silently dropped."""
    passing = assessment.loc[assessment["complete"], "year"]
    if passing.empty:
        raise ValueError("PRIMAP-hist: no year passes the completeness test")
    last = int(passing.max())
    interior = assessment[(assessment["year"] < last) & (~assessment["complete"])]
    if len(interior):
        r = interior.iloc[0]
        raise ValueError(f"PRIMAP-hist: interior year {int(r['year'])} fails the completeness test ({r['reasons']}); {len(interior)} interior failure(s)")
    excluded = []
    for _, r in assessment[assessment["year"] > last].iterrows():
        excluded.append(
            {"year": int(r["year"]), "reasons": r["reasons"], "total_gt": round(float(r["total_gt"]), 2),
             "yoy_pct": None if pd.isna(r["yoy"]) else round(float(r["yoy"]) * 100, 1),
             "areas": {k: int(r[f"areas_{k}"]) for k in GAS_KEYS},
             "weighted_coverage_pct": {k: round(float(r[f"coverage_{k}"]) * 100, 2) for k in GAS_KEYS}}
        )
    return last, excluded


# ---------------------------------------------------------------- tables


def build_tables(wides: dict[str, pd.DataFrame], last_year: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(country-year, global) tables in MtCO2e through `last_year`. Missing values stay explicit
    nulls (never zero-filled); the global figure sums the areas that report."""
    years = [y for y in wides["total"].columns if y <= last_year]
    mt = {
        "co2_mt": wides["co2"][years] / 1000,
        "ch4_mtco2e": wides["ch4"].reindex(wides["total"].index)[years] * GWP_AR5["ch4"] / 1000,
        "n2o_mtco2e": wides["n2o"].reindex(wides["total"].index)[years] * GWP_AR5["n2o"] / 1000,
        "fgas_mtco2e": wides["fgas"].reindex(wides["total"].index)[years] / 1000,
        "total_ghg_mtco2e": wides["total"][years] / 1000,
    }
    idx = wides["total"].index
    mt["co2_mt"] = mt["co2_mt"].reindex(idx)

    def long(df, name):
        s = df.stack(future_stack=True)  # keep NaN rows: missing stays an explicit null
        s.index.names = ["iso3", "year"]
        return s.rename(name)

    country = pd.concat([long(v, k) for k, v in mt.items()], axis=1).reset_index()
    country = country.assign(year=country["year"].astype(int), entity_type="country").sort_values(["iso3", "year"]).reset_index(drop=True)
    comp = country[["co2_mt", "ch4_mtco2e", "n2o_mtco2e", "fgas_mtco2e"]].sum(axis=1, min_count=1)
    country = country.assign(components_sum_mtco2e=comp, residual_mtco2e=comp - country["total_ghg_mtco2e"])

    g = pd.DataFrame({"year": years})
    for k, df in mt.items():
        g[k] = df.sum(min_count=1).values
    for k in GAS_KEYS:
        g[f"areas_{k}"] = [int(wides[k][y].notna().sum()) for y in years]
    g["areas_total"] = [int(wides["total"][y].notna().sum()) for y in years]
    comp_sum = g[["co2_mt", "ch4_mtco2e", "n2o_mtco2e", "fgas_mtco2e"]].sum(axis=1, min_count=1)
    g = g.assign(components_sum_mtco2e=comp_sum, residual_mtco2e=comp_sum - g["total_ghg_mtco2e"],
                 residual_pct=(comp_sum - g["total_ghg_mtco2e"]) / g["total_ghg_mtco2e"] * 100)
    return country.round(6), g.round(6)


def check_consistency(g: pd.DataFrame, report: RunReport) -> None:
    """The per-gas sum should reproduce PRIMAP-hist's own Kyoto basket; a larger gap means a GWP
    or basket mismatch (the analogue of the EDGAR per-gas-vs-total reconciliation)."""
    res = g["residual_pct"].dropna()
    bad = g[g["residual_pct"].abs() > CONSISTENCY_TOL_PCT]
    if len(bad):
        w = bad.loc[bad["residual_pct"].abs().idxmax()]
        report.deviate(f"per-gas sum differs from the Kyoto basket by more than {CONSISTENCY_TOL_PCT}% in {len(bad)} year(s) (worst {int(w['year'])}: {w['residual_pct']:.2f}%)")
    report.note(f"per-gas sum vs Kyoto basket, global residual {res.min():.3f}% to {res.max():.3f}% over {int(g['year'].min())}-{int(g['year'].max())}")


# ---------------------------------------------------------------- run


def _default_owid_and_expanded(root: str = ROOT):
    owid_path = os.path.join(root, "data", "owid-co2-data.csv")
    sel_path = os.path.join(root, "data", "selected_countries.json")
    owid = pd.read_csv(owid_path, usecols=["country", "iso_code"]) if os.path.exists(owid_path) else None
    expanded = json.load(open(sel_path)).get("expanded") if os.path.exists(sel_path) else None
    return owid, expanded


def run(fetcher=fetch, out_dir: str = CLIMATE_DIR, provenance_path: str = PROVENANCE_PATH, today=None, owid=None, expanded=None, concept_url: str = ZENODO_CONCEPT_URL) -> RunReport:
    today = today or date.today()
    report = RunReport("primap_hist")

    release = json.loads(fetcher(concept_url).content)
    meta = release["metadata"]
    files = pick_files(release)
    csv_f = fetcher(files["csv"]["links"]["self"])
    yaml_f = fetcher(files["yaml"]["links"]["self"])
    verify_checksum(csv_f.content, files["csv"]["checksum"], files["csv"]["key"])
    verify_checksum(yaml_f.content, files["yaml"]["checksum"], files["yaml"]["key"])

    pub = date.fromisoformat(meta["publication_date"])
    if (today - pub).days > MAX_RELEASE_AGE_DAYS:
        report.deviate(f"latest PRIMAP-hist release {meta.get('version')} is from {pub} ({(today - pub).days} days ago)")
    lic = (meta.get("license") or {}).get("id")
    if lic != "cc-by-nc-sa-4.0":
        report.deviate(f"PRIMAP-hist licence changed: Zenodo reports {lic!r}, expected 'cc-by-nc-sa-4.0' -- review before publishing derived data")

    wides = parse_primap(csv_f.content)
    require_contiguous_years(wides["total"].columns, int(wides["total"].columns.min()), int(wides["total"].columns.max()), "PRIMAP-hist")
    assessment = assess_years(wides)
    last, excluded = trim_incomplete(assessment)
    for e in excluded:
        report.note(f"excluded incomplete year {e['year']}: {e['reasons']}")
    if len(excluded) > 1:
        report.deviate(f"{len(excluded)} trailing years excluded as incomplete ({excluded[0]['year']}-{excluded[-1]['year']}); expected at most one")
    if today.year - last > MAX_LAG_YEARS:
        report.deviate(f"latest complete PRIMAP-hist year is {last}, more than {MAX_LAG_YEARS} years behind {today.year}")

    country, glob = build_tables(wides, last)
    check_consistency(glob, report)

    if owid is None and expanded is None:
        owid, expanded = _default_owid_and_expanded()
    crosswalk = None
    if owid is not None:
        owid_names = owid.dropna(subset=["iso_code"]).drop_duplicates("iso_code").set_index("iso_code")["country"].to_dict()
        crosswalk = build_crosswalk({a: owid_names.get(a) for a in wides["total"].index}, owid, expanded, source_label="primap")
        if expanded:
            gaps = expanded_gaps(crosswalk, expanded)
            if gaps:
                report.deviate(f"expanded-set countries without a PRIMAP-hist area: {', '.join(gaps)}")
        report.note(f"crosswalk: {crosswalk['match'].value_counts().to_dict()}")
        if crosswalk.attrs.get("excluded_owid_codes"):
            report.note(f"OWID non-ISO3 codes excluded from the crosswalk: {', '.join(crosswalk.attrs['excluded_owid_codes'])}")
    else:
        report.deviate("country crosswalk not built: data/owid-co2-data.csv not found")

    write_csv_atomic(country, os.path.join(out_dir, "primap_country_annual.csv"))
    write_csv_atomic(glob, os.path.join(out_dir, "primap_global_composition_annual.csv"))
    report.count(SERIES_COUNTRY, len(country))
    report.count(SERIES_GLOBAL, len(glob))
    if crosswalk is not None:
        write_csv_atomic(crosswalk, os.path.join(out_dir, "country_crosswalk.csv"))
        report.count(SERIES_CROSSWALK, len(crosswalk))

    first = int(glob["year"].min())
    common_meta = {
        "source": f"PRIMAP-hist {meta.get('version')} (Gütschow & Pflüger), Zenodo doi:{release.get('doi')}",
        "source_urls": [files["csv"]["links"]["self"], files["yaml"]["links"]["self"]],
        "retrieved_at": csv_f.retrieved_at,
        "source_release": {"version": meta.get("version"), "doi": release.get("doi"), "concept_doi": release.get("conceptdoi"),
                           "published": meta["publication_date"], "csv": files["csv"]["key"], "yaml": files["yaml"]["key"]},
        "raw_sha256": {"csv": csv_f.sha256, "yaml": yaml_f.sha256},
        "checksum_verified": {"csv": files["csv"]["checksum"], "yaml": files["yaml"]["checksum"]},
        "coverage": [first, last],
        "excluded_incomplete_years": excluded,
        "units": "MtCO2e (CO2 in Mt; CH4/N2O converted with IPCC AR5 GWP-100: 28 / 265; F-gases from the AR5 basket)",
        "gas_scope": "CO2, CH4, N2O, F-gases (AR5 GWP-100); national total excluding LULUCF",
        "scenario": f"{SCENARIO} (country-reported priority); file: no-extrapolation",
        "category": f"{CATEGORY} (national total excluding LULUCF)",
        "update_cadence": "annual release (Sep/Oct); concept record resolves to the latest; pipeline runs monthly",
        "license": (
            "CC BY-NC-SA 4.0 (Zenodo/description; since v2.8; the dataset's YAML 'rights' says Attribution-NonCommercial -- authors asked which is authoritative). "
            "Non-commercial use only; derived datasets published by this platform must carry the CC BY-NC-SA 4.0 notice with attribution; authors request notification of use. "
            "Upstream sources (EDGAR non-energy parts, CDIAC, Energy Institute, FAOSTAT, others) have their own terms -- not yet verified."
        ),
        "citations": CITATIONS,
        "attribution_required": True,
        "published": True,
    }
    write_provenance(
        SERIES_GLOBAL,
        {
            **common_meta,
            "geography": "global = sum of reporting areas (no world aggregate in the file); excludes international aviation and shipping",
            "consistency": {"tolerance_pct": CONSISTENCY_TOL_PCT, "residual_pct_by_year": {int(y): (None if pd.isna(r) else round(float(r), 4)) for y, r in zip(glob["year"], glob["residual_pct"])}},
            "completeness_rule": {"coverage_min_weighted": COVERAGE_MIN, "yoy_max": YOY_MAX, "basis": "emission-weighted coverage of the previous year's emissions, per gas; plus national-total change vs prior year"},
            "methodology": "total_ghg_mtco2e is PRIMAP-hist's own Kyoto-GHG (AR5) basket; components_sum is CO2 + CH4*28 + N2O*265 + F-gas basket; residual = components_sum - total.",
            "caveats": [
                "PRIMAP-hist is a composite of country-reported and third-party data (CDIAC, Energy Institute, FAOSTAT, EDGAR, others) harmonised into one series, not a single measured inventory; values before ~1970 are reconstructions from historical datasets.",
                "International aviation and shipping are not included; LULUCF is excluded; there is no world aggregate in the file.",
                "The country-reported (HISTCR) and third-party (HISTTP) scenarios differ by about 4.7% in 2023; HISTCR is used.",
                "Trailing years that are incomplete in the no-extrapolation file (v2.8: 2025) are excluded, not extrapolated.",
                "About 3% below EDGAR national totals by 2023 (India -14%, US +6%, China -2.7%); the OWID/GCP and EDGAR differences disclosed elsewhere do not transfer.",
            ],
            "rows": len(glob),
        },
        provenance_path,
    )
    write_provenance(
        SERIES_COUNTRY,
        {**common_meta, "geography": "country/territory areas by ISO3 (207 in v2.8)",
         "methodology": "Same construction as the global series, per area; missing values are explicit nulls.",
         "caveats": ["CH4/N2O cover 206 areas, F-gases about 150-171; areas without a gas are null for it, not zero."], "rows": len(country)},
        provenance_path,
    )
    if crosswalk is not None:
        write_provenance(
            SERIES_CROSSWALK,
            {"source": "Derived: PRIMAP-hist area codes x OWID iso_code/country", "retrieved_at": csv_f.retrieved_at,
             "methodology": "Matched on ISO3; unmatched areas flagged from the data (see pipeline/crosswalk.py). Rebuilt every run.",
             "match_counts": crosswalk["match"].value_counts().to_dict(), "license": "Derived metadata", "rows": len(crosswalk)},
            provenance_path,
        )
    return report
