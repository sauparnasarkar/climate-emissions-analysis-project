"""Country cumulative share of global emissions. Release 21, Phase 1.3c-iii (`ENHANCEMENTS.md` decision 37; requirement §1.3.4).

A derived stage writing two files the API (Phase 1.4) only reads:

- `correlation_country_share.csv` -- the long file: country (ISO3), year, source, gas_scope, cumulative (Mt, MtCO2e) and share (%), plus the year's own emissions and annual share (decision 60).
- `correlation_country_share.json` -- per combination: coverage, the denominator and how it reconciles, the countries with gaps, the latest top
  emitters, plus the caveats and attribution the numbers need.

Three combinations: `owid_co2` x `co2` (OWID fossil + cement CO2), `primap_hist` x `co2` and `primap_hist` x `total_ghg` (PRIMAP-hist, AR5 GWP-100).

Rules (decisions 15 and 37):
- **Share = a country's cumulative emissions / the sum of every country's cumulative emissions** in that year (the national sum: ISO3 countries, international
  aviation and shipping and non-ISO aggregates excluded), so shares sum to 100 (1e-6). This is deliberately not the World series used by the headline regression.
- **Cumulative from the source's first year, published from 1850.** A country has rows from its first observation (an absent row means no emissions recorded yet,
  i.e. a cumulative of zero).
- **A missing year inside a country's record counts as zero and is listed**, not interpolated; a series that ends before the last year simply stops growing and is listed.
  The denominator is the sum of the same cumulatives, so shares stay consistent; OWID's World series excludes the same years.
- **Reconciled to the artifacts already published**: the OWID sum equals the cumulative of `owid_world_co2_annual.national_sum_mt`; the PRIMAP sum equals the cumulative
  of the global composition series. A mismatch is a deviation.
- **No attribution is claimed**: shares describe where emissions occurred, and no country series is ever regressed against the global temperature series.
- Each combination fails independently (explicit `available: false` with a reason), and both files are always rewritten, so a stale share is never served.
"""

from __future__ import annotations

import json
import logging
import os

import numpy as np
import pandas as pd

from .common import CLIMATE_DIR, RunReport, utc_now, write_csv_atomic, write_json_atomic
from .owid import DATA_PATH as OWID_PATH

SCHEMA_VERSION = 1
OUTPUT_CSV = "correlation_country_share.csv"
OUTPUT_JSON = "correlation_country_share.json"
CSV_COLUMNS = ["country", "year", "source", "gas_scope", "cumulative_mt", "share_pct", "annual_mt", "annual_share_pct"]
SHARE_START = 1850
SHARE_SUM_TOL = 1e-6  # percentage points, on the unrounded values
RECONCILE_REL_TOL = 1e-6
TOP_N = 10

COMBOS = {
    ("owid_co2", "co2"): {"label": "OWID fossil + cement CO2", "unit": "Mt CO2"},
    ("primap_hist", "co2"): {"label": "PRIMAP-hist CO2", "unit": "Mt CO2"},
    ("primap_hist", "total_ghg"): {"label": "PRIMAP-hist total greenhouse gases (CO2-equivalent, AR5 GWP-100)", "unit": "MtCO2e"},
}

NO_ATTRIBUTION = ("Emissions shares (cumulative and annual) describe where emissions occurred over time. They are not a measure of responsibility for warming or a causal "
                  "attribution, and no country's emissions are regressed against the global temperature series.")
DENOMINATOR_NOTE = ("A cumulative share (`share_pct`) is a country's cumulative emissions divided by the sum of all countries' cumulative emissions; an annual share "
                    "(`annual_share_pct`) is the country's emissions in that one year divided by the sum of all countries' emissions in the same year. Both denominators are the "
                    "national sum, which excludes international aviation and shipping, so each set of shares sums to 100% of national emissions in its year. This differs by design "
                    "from the World series, which includes international transport, used for the headline regression.")
TERRITORIAL_NOTE = ("Emissions are territorial (where they occurred), not adjusted for trade or consumption. Emissions before a country existed in its current borders are "
                    "allocated to it by the data provider; this platform does not re-allocate them.")
GAP_NOTE = ("A year missing from a country's record is counted as zero and listed under `gaps`, not interpolated; a series that ends before the last year stops growing and is "
            "listed under `ended_before_last_year`. Rows start at a country's first observation: an absent row means no emissions recorded yet (a cumulative of zero).")


def cumulate(df: pd.DataFrame, id_col: str, value_col: str, last_year: int) -> dict:
    """Cumulative emissions per country by year, built without a dense pandas reshape. Missing years inside a record count as zero and are reported;
    a country never observed contributes nothing."""
    # built from arrays: any setitem/assign on a subset frame trips pandas' chained-assignment warning on Python 3.14 (a false positive)
    d = pd.DataFrame({id_col: df[id_col].to_numpy(), "year": df["year"].to_numpy().astype(int), value_col: df[value_col].to_numpy(dtype=float)})
    if d.duplicated([id_col, "year"]).any():
        raise ValueError(f"duplicate {id_col}/year rows in the input")
    d = d[d["year"] <= last_year]
    first_year = int(d.loc[d[value_col].notna(), "year"].min())
    years = np.arange(first_year, last_year + 1)
    ids = sorted(d[id_col].unique())
    annual = np.zeros((len(years), len(ids)))
    first_obs, gaps, ended = {}, {}, {}
    for i, (k, g) in enumerate(d.groupby(id_col, sort=True)):
        s = g.dropna(subset=[value_col]).set_index("year")[value_col]
        if s.empty:
            first_obs[k] = None
            continue
        annual[s.index.to_numpy() - first_year, i] = s.to_numpy()
        first_obs[k] = int(s.index.min())
        last_obs = int(s.index.max())
        missing = sorted(set(range(first_obs[k], last_obs + 1)) - set(s.index.tolist()))
        if missing:
            gaps[k] = {"n_years": len(missing), "first": missing[0], "last": missing[-1]}
        if last_obs < last_year:
            ended[k] = last_obs
    return {"years": years, "ids": ids, "annual": annual, "cum": annual.cumsum(axis=0), "first_obs": first_obs, "gaps": gaps, "ended": ended}


def shares_rows(c: dict, source: str, gas_scope: str) -> tuple[pd.DataFrame, np.ndarray]:
    """Long rows (from max(first observation, SHARE_START)) and the per-year sum of the published shares, validated to be 100."""
    years, ids, cum = c["years"], c["ids"], c["cum"]
    den = cum.sum(axis=1)
    visible = years >= SHARE_START
    if not np.all(den[visible] > 0):
        raise ValueError(f"{source}/{gas_scope}: a published year has a zero total, so shares are undefined")
    share = cum / den[:, None] * 100
    sums = share[visible].sum(axis=1)
    if np.abs(sums - 100).max() > SHARE_SUM_TOL:
        raise ValueError(f"{source}/{gas_scope}: shares sum to {sums[np.abs(sums - 100).argmax()]!r}, not 100")
    # The same national-sum denominator, for the year's own emissions (decision 60): the "flow" beside the cumulative "stock".
    annual = c["annual"]
    aden = annual.sum(axis=1)
    if not np.all(aden[visible] > 0):
        raise ValueError(f"{source}/{gas_scope}: a published year has a zero annual total, so annual shares are undefined")
    ashare = annual / aden[:, None] * 100
    asums = ashare[visible].sum(axis=1)
    if np.abs(asums - 100).max() > SHARE_SUM_TOL:
        raise ValueError(f"{source}/{gas_scope}: annual shares sum to {asums[np.abs(asums - 100).argmax()]!r}, not 100")
    start = np.array([max(c["first_obs"][k] or 10**9, SHARE_START) for k in ids])
    mask = (years[:, None] >= start[None, :])
    yi, ci = np.nonzero(mask)
    rows = pd.DataFrame({"country": np.array(ids)[ci], "year": years[yi], "source": source, "gas_scope": gas_scope, "cumulative_mt": cum[yi, ci], "share_pct": share[yi, ci],
                         "annual_mt": annual[yi, ci], "annual_share_pct": ashare[yi, ci]})
    return rows, sums


def _combo_meta(c: dict, rows: pd.DataFrame, source: str, gas_scope: str) -> dict:
    last = int(c["years"][-1])
    latest = rows[rows["year"] == last].sort_values("share_pct", ascending=False)
    return {"source": source, "gas_scope": gas_scope, **COMBOS[(source, gas_scope)], "available": True,
            "coverage": [int(max(SHARE_START, c["years"][0])), last], "cumulative_from": int(c["years"][0]), "n_countries": int(sum(v is not None for v in c["first_obs"].values())),
            "n_rows": int(len(rows)),
            "latest": {"year": last, "total_cumulative_mt": float(c["cum"][-1].sum()),
                       "top": [{"country": r.country, "share_pct": float(r.share_pct), "cumulative_mt": float(r.cumulative_mt)} for r in latest.head(TOP_N).itertuples()]},
            "gaps": [{"country": k, **v} for k, v in sorted(c["gaps"].items())],
            "ended_before_last_year": [{"country": k, "last_observation": v} for k, v in sorted(c["ended"].items())]}


def _check_reconciliation(c: dict, ref_years: np.ndarray, ref_values: np.ndarray, label: str, report: RunReport) -> dict:
    """The sum of country cumulatives against the cumulative of an artifact already published. Returns the worst relative difference."""
    ref = pd.Series(ref_values, index=ref_years).cumsum()
    mine = pd.Series(c["cum"].sum(axis=1), index=c["years"])
    common = mine.index.intersection(ref.index)
    if len(common) == 0:
        raise ValueError(f"{label}: no overlapping years to reconcile against")
    rel = ((mine.loc[common] - ref.loc[common]).abs() / ref.loc[common].abs().clip(lower=1e-12)).max()
    if rel > RECONCILE_REL_TOL:
        report.deviate(f"{label}: the sum of country cumulatives differs from the published series by {rel:.2e} (relative; tolerance {RECONCILE_REL_TOL:g})")
    return {"against": label, "max_relative_difference": float(rel), "tolerance": RECONCILE_REL_TOL, "years_compared": [int(common.min()), int(common.max())]}


def _owid_combo(climate_dir: str, owid_path: str, report: RunReport):
    w = pd.read_csv(os.path.join(climate_dir, "owid_world_co2_annual.csv"))
    for col in ("year", "national_sum_mt", "co2_mt"):
        if col not in w.columns:
            raise ValueError(f"owid_world_co2_annual.csv: required column missing: {col}")
    last = int(w["year"].max())
    raw = pd.read_csv(owid_path, usecols=["country", "year", "iso_code", "co2"])
    iso = raw[raw["iso_code"].fillna("").str.fullmatch(r"[A-Z]{3}")]
    c = cumulate(iso, "iso_code", "co2", last)
    if np.any(c["annual"] < 0):
        report.deviate("owid_co2/co2: negative annual emissions in the country data; check the input before relying on the shares")
    rows, _ = shares_rows(c, "owid_co2", "co2")
    meta = _combo_meta(c, rows, "owid_co2", "co2")
    meta["reconciliation"] = _check_reconciliation(c, w["year"].to_numpy(), w["national_sum_mt"].to_numpy(), "owid_world_co2_annual.national_sum_mt", report)
    world_cum = float(w["co2_mt"].sum())
    meta["denominator"] = {"definition": "sum over ISO3 countries of cumulative OWID CO2 (excludes international aviation and shipping and non-ISO entities)",
                           "total_cumulative_mt": meta["latest"]["total_cumulative_mt"], "world_cumulative_mt": world_cum,
                           "difference_from_world_pct": (meta["latest"]["total_cumulative_mt"] / world_cum - 1) * 100}
    return rows, meta


def _primap_combos(climate_dir: str, report: RunReport):
    p = pd.read_csv(os.path.join(climate_dir, "primap_country_annual.csv"))
    for col in ("iso3", "year", "co2_mt", "total_ghg_mtco2e"):
        if col not in p.columns:
            raise ValueError(f"primap_country_annual.csv: required column missing: {col}")
    if "entity_type" in p.columns:
        p = p[p["entity_type"] == "country"]
    g = pd.read_csv(os.path.join(climate_dir, "primap_global_composition_annual.csv"))
    last = int(p["year"].max())
    out = {}
    for scope, col, gcol in (("co2", "co2_mt", "co2_mt"), ("total_ghg", "total_ghg_mtco2e", "total_ghg_mtco2e")):
        try:
            c = cumulate(p, "iso3", col, last)
            if np.any(c["annual"] < 0):
                report.deviate(f"primap_hist/{scope}: negative annual emissions in the country data; check the input before relying on the shares")
            rows, _ = shares_rows(c, "primap_hist", scope)
            meta = _combo_meta(c, rows, "primap_hist", scope)
            meta["reconciliation"] = _check_reconciliation(c, g["year"].to_numpy(), g[gcol].to_numpy(), f"primap_global_composition_annual.{gcol}", report)
            meta["denominator"] = {"definition": "sum over PRIMAP-hist reporting areas of cumulative emissions (national totals; international aviation and shipping and land-use change excluded)",
                                   "total_cumulative_mt": meta["latest"]["total_cumulative_mt"]}
            out[("primap_hist", scope)] = (rows, meta)
        except Exception as e:  # noqa: BLE001 -- one scope failing must not hide the other
            out[("primap_hist", scope)] = (None, _unavailable("primap_hist", scope, e))
    return out


def _unavailable(source: str, gas_scope: str, e: Exception) -> dict:
    if not isinstance(e, (OSError, ValueError, KeyError)):
        logging.exception("country_share: unexpected error for %s/%s", source, gas_scope)
    return {"source": source, "gas_scope": gas_scope, **COMBOS[(source, gas_scope)], "available": False, "unavailable_reason": f"{type(e).__name__}: {e}"}


def _attribution(climate_dir: str) -> dict:
    pp = os.path.join(climate_dir, "provenance.json")
    prov = json.load(open(pp)) if os.path.exists(pp) else {}
    keep = ("source", "license", "citations", "source_release")
    return {"owid": {k: v for k, v in (prov.get("owid_world_co2_annual") or {}).items() if k in keep},
            "primap_hist": {k: v for k, v in (prov.get("primap_country_annual") or {}).items() if k in keep}}


def _countries(climate_dir: str, used: set[str]) -> list[dict]:
    path = os.path.join(climate_dir, "country_crosswalk.csv")
    names = {}
    if os.path.exists(path):
        cw = pd.read_csv(path)
        for r in cw.itertuples():
            names[r.iso3] = {"name": r.primap_name if isinstance(r.primap_name, str) else (r.owid_name if isinstance(r.owid_name, str) else r.iso3),
                             "expanded": bool(getattr(r, "expanded", False))}
    return [{"iso3": k, "name": names.get(k, {}).get("name", k), "expanded": names.get(k, {}).get("expanded", False)} for k in sorted(used)]


def run(climate_dir: str = CLIMATE_DIR, out_dir: str | None = None, owid_path: str = OWID_PATH) -> RunReport:
    out_dir = out_dir or climate_dir
    report = RunReport("country_share")
    parts, metas = [], []
    try:
        rows, meta = _owid_combo(climate_dir, owid_path, report)
        parts.append(rows)
        metas.append(meta)
    except Exception as e:  # noqa: BLE001 -- OWID unreadable: its combination is an explicit null; PRIMAP-hist is unaffected
        metas.append(_unavailable("owid_co2", "co2", e))
    try:
        for rows, meta in _primap_combos(climate_dir, report).values():
            if rows is not None:
                parts.append(rows)
            metas.append(meta)
    except Exception as e:  # noqa: BLE001 -- PRIMAP-hist unreadable: both of its combinations are explicit nulls
        metas.extend(_unavailable("primap_hist", s, e) for s in ("co2", "total_ghg"))
    for m in metas:
        if not m["available"]:
            report.deviate(f"{m['source']}/{m['gas_scope']} country shares unavailable: {m['unavailable_reason']}")
    long = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=CSV_COLUMNS)
    long = long.sort_values(["source", "gas_scope", "country", "year"]).reset_index(drop=True) if len(long) else long
    try:
        attribution = _attribution(climate_dir)
    except Exception:  # noqa: BLE001 -- malformed provenance must not stop the explicit-null output
        logging.exception("country_share: unable to read provenance for the attribution metadata")
        attribution = {}
    try:
        countries = _countries(climate_dir, set(long["country"]) if len(long) else set())
    except Exception:  # noqa: BLE001
        logging.exception("country_share: unable to read the country crosswalk")
        countries = [{"iso3": k, "name": k, "expanded": False} for k in sorted(set(long["country"]))] if len(long) else []
    caveats = [NO_ATTRIBUTION, DENOMINATOR_NOTE, TERRITORIAL_NOTE, GAP_NOTE,
               "OWID: fossil fuel and cement CO2 only (land-use change excluded); the ISO-coded entities include some non-sovereign territories.",
               "PRIMAP-hist: national totals excluding land-use change and international aviation and shipping; a composite of country-reported and third-party data."]
    prim_lic = attribution.get("primap_hist", {}).get("license")
    if prim_lic:
        caveats.append(f"PRIMAP-hist licence: {prim_lic}")
    meta = {"schema_version": SCHEMA_VERSION, "generated_at": utc_now(), "name": "Country cumulative share of global emissions", "note": NO_ATTRIBUTION,
            "method": ("cumulative share (share_pct) = country cumulative emissions / sum of all countries' cumulative emissions; "
                      "annual share (annual_share_pct) = country emissions in the year / sum of all countries' emissions in that year"), "published_from": SHARE_START,
            "combinations": metas, "countries": countries, "caveats": caveats, "attribution": attribution}
    write_csv_atomic(long.assign(cumulative_mt=pd.to_numeric(long["cumulative_mt"]).round(6), share_pct=pd.to_numeric(long["share_pct"]).round(10),
                                 annual_mt=pd.to_numeric(long["annual_mt"]).round(6), annual_share_pct=pd.to_numeric(long["annual_share_pct"]).round(10)), os.path.join(out_dir, OUTPUT_CSV))
    write_json_atomic(meta, os.path.join(out_dir, OUTPUT_JSON))
    report.count("correlation_country_share", len(long))
    for m in metas:
        if m["available"]:
            top = m["latest"]["top"][:3]
            report.note(f"{m['source']}/{m['gas_scope']} {m['coverage'][0]}-{m['coverage'][1]}, {m['n_countries']} countries; top in {m['latest']['year']}: "
                        + ", ".join(f"{t['country']} {t['share_pct']:.1f}%" for t in top))
    return report
