"""GHG composition: each gas's contribution to the CO2-equivalent total. Release 21, Phase 1.3c-ii (`ENHANCEMENTS.md` decision 36; requirement §1.3.3).

A derived stage that reads PRIMAP-hist's global composition series (the source step already restricted it to years that passed the completeness
test) and writes two files the API (Phase 1.4) only reads:

- `correlation_composition_annual.csv` -- the long file: year, gas, gas name, MtCO2e and share of the total, one row per year and gas. A selected-year
  view (treemap, stacked bar) is a filter on this file, not a second computation.
- `correlation_composition.json` -- the metadata the numbers need to be described honestly: basis, units, coverage, per-year `gases_included`,
  the reconciliation to PRIMAP-hist's own national total, caveats and attribution.

Rules (decision 36):
- **Nulls are explicit.** If a gas has no value for a year its value and share are empty and the year's `gases_included` says so: no zero is invented. A
  zero PRIMAP-hist itself reports (F-gases are 0.0 in 1750) is a real value and stays a zero.
- **Shares are over the gases that are included** (the sum of the components), so they sum to 100 within 1e-6 or the stage fails; the difference between
  that sum and PRIMAP-hist's own national total is published per year (`residual_pct`) and checked, not hidden.
- **Nothing is renormalised quietly**: a year with a missing gas is flagged in `gases_included`, and a missing CO2, CH4 or N2O is a deviation.
- Years outside the completeness-tested coverage recorded in provenance are a deviation (an incomplete year must not slip into a composition).
"""

from __future__ import annotations

import json
import logging
import os

import numpy as np
import pandas as pd

from .common import CLIMATE_DIR, RunReport, require_contiguous_years, utc_now, write_csv_atomic, write_json_atomic

SCHEMA_VERSION = 1
SERIES_ID = "primap_global_composition_annual"
INPUT_CSV = "primap_global_composition_annual.csv"
OUTPUT_CSV = "correlation_composition_annual.csv"
OUTPUT_JSON = "correlation_composition.json"
SHARE_SUM_TOL = 1e-6  # percentage points
RESIDUAL_TOL_PCT = 1.0  # the four gases must reconcile to PRIMAP-hist's national total within this
CSV_COLUMNS = ["year", "gas", "gas_name", "mtco2e", "share_pct"]

# (id, source column, display name). CO2 is in Mt CO2; the others are already CO2-equivalent (AR5 GWP-100).
GASES = [("co2", "co2_mt", "CO₂"), ("ch4", "ch4_mtco2e", "CH₄"), ("n2o", "n2o_mtco2e", "N₂O"), ("fgas", "fgas_mtco2e", "Fluorinated gases")]
REQUIRED_GASES = ("co2", "ch4", "n2o")  # F-gases were reported later historically, so their absence is a note, not a deviation

BASIS = ("PRIMAP-hist national total greenhouse-gas emissions in CO2-equivalent terms, IPCC AR5 100-year global-warming potentials "
         "(CH4 28, N2O 265; F-gases from the AR5 basket), country-reported scenario, summed over reporting areas")
SCOPE_NOTE = ("Excludes international aviation and shipping and land-use change (national totals), so the share of CO2 in particular excludes deforestation "
              "while agricultural methane is included.")
SHARE_NOTE = "Shares are each gas's part of the sum of the gases included for that year (`gases_included`), so they sum to 100; the difference from PRIMAP-hist's own national total is `residual_pct`."


def _empty_long() -> pd.DataFrame:
    return pd.DataFrame(columns=CSV_COLUMNS)


def _metadata(climate_dir: str) -> tuple[dict, list[str], dict]:
    """(provenance entry, caveats, attribution) from provenance.json: the output's metadata does not depend on the data being usable."""
    pp = os.path.join(climate_dir, "provenance.json")
    prov = (json.load(open(pp)).get(SERIES_ID) or {}) if os.path.exists(pp) else {}
    caveats = [SCOPE_NOTE, SHARE_NOTE, *[c for c in prov.get("caveats", []) if isinstance(c, str)]]
    if prov.get("license"):
        caveats.append(f"PRIMAP-hist licence: {prov['license']}")
    return prov, caveats, {k: prov[k] for k in ("source", "license", "citations", "source_release") if k in prov}


def _skeleton(caveats: list[str], attribution: dict) -> dict:
    return {"schema_version": SCHEMA_VERSION, "generated_at": utc_now(), "name": "Global greenhouse-gas composition", "basis": BASIS,
            "gases": [{"id": g, "name": n, "source_column": c} for g, c, n in GASES], "units": "MtCO2e (CO2 in Mt CO2)",
            "caveats": caveats, "attribution": attribution, "years": [], "coverage": None}


def build(climate_dir: str, report: RunReport) -> tuple[dict, pd.DataFrame]:
    prov, caveats, attribution = _metadata(climate_dir)
    base = _skeleton(caveats, attribution)

    df = pd.read_csv(os.path.join(climate_dir, INPUT_CSV))
    missing = [c for c in ("year", "total_ghg_mtco2e", *[c for _, c, _ in GASES]) if c not in df.columns]
    if missing:
        raise ValueError(f"{INPUT_CSV}: required column(s) missing: {', '.join(missing)}")
    df = df.sort_values("year").reset_index(drop=True)
    years = df["year"].astype(int).tolist()
    require_contiguous_years(years, years[0], years[-1], "PRIMAP-hist composition")

    cov = prov.get("coverage")
    if not (isinstance(cov, list) and len(cov) == 2 and all(isinstance(c, int) and not isinstance(c, bool) for c in cov) and cov[0] <= cov[1]):
        # without the recorded coverage there is no proof that the years passed the completeness test, so nothing is published
        raise ValueError(f"provenance for {SERIES_ID} has no valid [first, last] coverage ({cov!r}): cannot show that the years passed the completeness test")
    outside = [y for y in years if not cov[0] <= y <= cov[1]]
    if outside:
        report.deviate(f"composition includes year(s) outside the completeness-tested coverage {cov}: {outside}")

    rows, per_year = [], []
    for _, r in df.iterrows():
        year = int(r["year"])
        vals = {g: (float(r[c]) if pd.notna(r[c]) else None) for g, c, _ in GASES}
        included = [g for g, _, _ in GASES if vals[g] is not None]
        absent = [g for g, _, _ in GASES if vals[g] is None]
        if absent:
            bad = [g for g in absent if g in REQUIRED_GASES]
            if bad:
                report.deviate(f"{year}: no value for {', '.join(bad)}; its composition is computed over the remaining gases ({', '.join(included)})")
        total = sum(vals[g] for g in included)
        if not included or not np.isfinite(total) or total <= 0:
            # skipping it would leave a gap in a series whose coverage claims to be contiguous
            raise ValueError(f"{year}: no usable gas values (none present, or the total is not positive)")
        shares = {g: vals[g] / total * 100 for g in included}
        s = sum(shares.values())
        if abs(s - 100) > SHARE_SUM_TOL:
            raise ValueError(f"{year}: shares sum to {s!r}, not 100")
        national = float(r["total_ghg_mtco2e"]) if pd.notna(r["total_ghg_mtco2e"]) else float("nan")
        if not np.isfinite(national) or national <= 0:
            raise ValueError(f"{year}: PRIMAP-hist's national total is missing or not positive ({r['total_ghg_mtco2e']!r}), so the year cannot be reconciled")
        resid = (total - national) / national * 100
        if abs(resid) > RESIDUAL_TOL_PCT:
            report.deviate(f"{year}: the gases sum to {total:,.0f} MtCO2e, {resid:+.2f}% from PRIMAP-hist's national total (tolerance ±{RESIDUAL_TOL_PCT}%)")
        for g, _, name in GASES:
            rows.append({"year": year, "gas": g, "gas_name": name, "mtco2e": vals[g], "share_pct": shares.get(g)})
        per_year.append({"year": year, "gases_included": included, "components_total_mtco2e": total, "national_total_mtco2e": national, "residual_pct": resid})

    long = pd.DataFrame(rows, columns=CSV_COLUMNS)
    first = long[long["year"] == per_year[0]["year"]].set_index("gas")["share_pct"]
    if first.notna().any() and first.idxmax() != "co2":
        top = first.idxmax()
        name = {g: n for g, _, n in GASES}[top]
        caveats.append(f"In {per_year[0]['year']} {name} is {first.max():.0f}% of the CO2-equivalent total and CO2 only {first.get('co2', float('nan')):.0f}%: the earliest "
                       f"composition is a reconstruction dominated by {name}, and national CO2 here excludes land-use change, which understates early CO2; read the earliest "
                       "decades as an estimate, not an observation.")
    fg_missing = sorted(y["year"] for y in per_year if "fgas" not in y["gases_included"])
    if fg_missing:
        report.note(f"F-gases have no value for {len(fg_missing)} year(s) ({fg_missing[0]}-{fg_missing[-1]}); shown as null, shares over the other gases")
    resids = [abs(y["residual_pct"]) for y in per_year]  # every published year reconciles (a year without a valid national total raises)
    meta = {**base, "years": per_year, "coverage": [per_year[0]["year"], per_year[-1]["year"]], "n_years": len(per_year), "caveats": caveats,
            "reconciliation": {"max_abs_residual_pct": max(resids) if resids else None, "tolerance_pct": RESIDUAL_TOL_PCT,
                               "note": "components sum vs PRIMAP-hist's own national total, per year (`years[].residual_pct`)"},
            "excluded_incomplete_years": sorted({int(e["year"]) for e in prov.get("excluded_incomplete_years", []) if isinstance(e, dict) and "year" in e})}
    last = long[long["year"] == per_year[-1]["year"]]
    report.note(f"composition {meta['coverage'][0]}-{meta['coverage'][1]}: " + ", ".join(f"{r.gas_name} {r.share_pct:.1f}%" for r in last.itertuples() if pd.notna(r.share_pct))
                + f" in {meta['coverage'][1]}")
    return meta, long


def run(climate_dir: str = CLIMATE_DIR, out_dir: str | None = None) -> RunReport:
    """Always rewrites both outputs atomically: if the input is unavailable they become an explicit-null JSON (with the reason) and a header-only CSV, so a stale
    composition is never served as current. The failure is a deviation (an alert), not a crash."""
    out_dir = out_dir or climate_dir
    report = RunReport("composition")
    try:
        meta, long = build(climate_dir, report)
    except Exception as e:  # noqa: BLE001 -- whatever the cause, explicit nulls and a deviation, never a stale file
        if not isinstance(e, (OSError, ValueError, KeyError)):
            logging.exception("composition: unexpected error")
        reason = f"{type(e).__name__}: {e}"
        report.deviate(f"composition unavailable: {reason}")
        try:
            _, caveats, attribution = _metadata(climate_dir)
        except Exception:  # noqa: BLE001 -- malformed provenance: still write the explicit-null output
            logging.exception("composition: unable to read provenance for the attribution metadata")
            caveats, attribution = [SCOPE_NOTE, SHARE_NOTE], {}
        meta = {**_skeleton(caveats, attribution), "unavailable_reason": reason}
        long = _empty_long()
    # rounded so the published file stays within the stage's own sum tolerance: 4 shares each off by <= 5e-9 sum to 100 within 2e-8
    write_csv_atomic(long.assign(mtco2e=pd.to_numeric(long["mtco2e"]).round(6), share_pct=pd.to_numeric(long["share_pct"]).round(8)), os.path.join(out_dir, OUTPUT_CSV))
    write_json_atomic(meta, os.path.join(out_dir, OUTPUT_JSON))
    report.count("correlation_composition", len(long))
    return report
