"""Headline regression: temperature against cumulative CO2. Release 21, Phase 1.3a (`ENHANCEMENTS.md` decisions 31-33 and 40).

A derived stage that runs after `harmonize` and writes `data/climate/correlation_headline.json`, which the API (Phase 1.4) only
reads. It is deterministic: there is no random draw anywhere in this module (the bootstrap of Phase 1.3b is seeded).

- **Headline** (decision 40): OLS of the Berkeley Earth anomaly (1850-1900 reference) on **cumulative total anthropogenic CO2 since
  1850** (OWID World fossil + cement incl. international transport, plus land-use change). Slope in degrees C per 1,000 GtCO2, R^2,
  Newey-West (HAC) standard errors and 95% CI.
- **Secondary, labelled variant**: the same regression on fossil + cement CO2 alone (the common meaning of "CO2 emissions"); never hidden.
- The **IPCC AR6** TCRE range is carried beside both, so the comparison is against an uncertainty range, not a point value.
- **HAC bandwidth** is floor(1.5 n^(1/3)); the CI under other bandwidths is published, as are the slopes by estimation window (a fixed
  grid of start years, because outputs are precomputed) and the sensitivity to the land-use estimate (scaled 0.7 / 1.0 / 1.3).

The slope does not depend on the year the cumulative starts (a constant added to x moves only the intercept), so the 1750-based fossil
cumulative and the 1850-based total are comparable as slopes.

Statsmodels is imported from its submodules, never `statsmodels.api` (broken by scipy 1.17; see `requirements.txt`).
"""

from __future__ import annotations

import json
import logging
import math
import os

import numpy as np
import pandas as pd
from statsmodels.regression.linear_model import OLS
from statsmodels.stats.stattools import durbin_watson
from statsmodels.tools.tools import add_constant

from .common import CLIMATE_DIR, NOTICES_PATH, RunReport, utc_now, write_json_atomic
from .harmonize import _LUC_LICENSE, _LUC_UNCERTAINTY
from .pairing import CAUSATION_NOTE, Harmonized, align_pair, load_harmonized

SCHEMA_VERSION = 1
OUTPUT_NAME = "correlation_headline.json"

TEMPERATURE = "temperature_anomaly_1850_1900_c"
X_TOTAL = "owid_total_co2_world_cumulative_mt"
X_FOSSIL = "owid_co2_world_cumulative_mt"
X_LUC = "owid_luc_co2_world_cumulative_mt"

START_GRID = (1850, 1900, 1950, 1970)  # decision 33: the only start years the API will accept
HAC_SENSITIVITY_LAGS = (4, 8, 16)
LUC_SCALES = (0.7, 1.0, 1.3)
MT_PER_THOUSAND_GT = 1e6  # x is Mt CO2; the slope is per 1,000 GtCO2 = 1,000,000 Mt
GTCO2_PER_GTC = 44.009 / 12.011  # 3.664
Z95 = 1.959963984540054
MIN_WINDOW_YEARS = 20

AR6_TCRE = {
    "unit": "°C per 1,000 GtCO2",
    "best_estimate": 0.45,
    "very_likely_range": [0.27, 0.63],
    "as_per_1000_gtc": {"best_estimate": 1.65, "very_likely_range": [1.0, 2.3]},
    "source": "IPCC AR6 WGI: transient climate response to cumulative CO2 emissions (very likely range 1.0-2.3 °C per 1,000 GtC, best estimate 1.65).",
    "note": "Derived from CO2-only forcing in Earth-system models with land-use emissions included; this platform's figure is a simplified, data-driven analog, not a restatement.",
}

METHODOLOGY = (
    "Derived from OWID cumulative CO2 from fossil fuels, cement and land-use change (Global Carbon Project), regressed against the Berkeley Earth "
    "anomaly. A simplified, data-driven analog to the IPCC's TCRE (AR6 best estimate about 0.45 °C per 1,000 GtCO2, very likely range 0.27-0.63), "
    "not a restatement of it: this regression also absorbs warming from non-CO2 gases and aerosols that varies with CO2, uses one observed climate "
    "history rather than a multi-model ensemble, and depends on land-use emission estimates that are themselves uncertain."
)
PLAIN_LANGUAGE = (
    "This describes a long-run statistical relationship between the CO2 humans have emitted and the global temperature record. "
    "It is not a complete climate model and does not by itself prove cause and effect."
)
DENOMINATOR_NOTE = (
    "The cumulative emissions used here are OWID's World series, which includes international aviation and shipping (they entered the atmosphere). "
    "Country shares elsewhere on the platform use the sum of national emissions, which excludes them, so shares sum to 100% of national emissions; "
    "the two differ by design."
)


def hac_lags(n: int) -> int:
    """Newey-West bandwidth floor(1.5 n^(1/3)): the textbook floor(4 (n/100)^(2/9)) under-corrects at the residual autocorrelation seen here."""
    return int(1.5 * n ** (1 / 3))


def fit_line(x_mt: np.ndarray, y: np.ndarray, maxlags: int) -> dict:
    """OLS with intercept of y on x (x in Mt CO2, reported per 1,000 GtCO2) with Newey-West HAC errors (Bartlett kernel, normal 95% CI)."""
    x = np.asarray(x_mt, float) / MT_PER_THOUSAND_GT
    y = np.asarray(y, float)
    if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)):
        raise ValueError("non-finite values in the regression inputs")
    if np.ptp(x) == 0:  # add_constant would silently skip the intercept for a constant column and the slope would not exist
        raise ValueError("the cumulative-emissions predictor has no variation over the paired years, so a slope is undefined")
    X = add_constant(x, has_constant="add")
    ols = OLS(y, X).fit()
    hac = OLS(y, X).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    slope, se_hac = float(hac.params[1]), float(hac.bse[1])
    res = ols.resid
    return {
        "slope": slope, "intercept": float(hac.params[0]), "r_squared": float(ols.rsquared), "n": int(len(y)),
        "se_ols": float(ols.bse[1]), "se_hac": se_hac, "ci95_hac": [slope - Z95 * se_hac, slope + Z95 * se_hac],
        "maxlags": maxlags,
        "residual_lag1_autocorrelation": float(np.corrcoef(res[1:], res[:-1])[0, 1]), "durbin_watson": float(durbin_watson(res)),
    }


def _hac_row(x: np.ndarray, y: np.ndarray, maxlags: int) -> dict:
    f = fit_line(x, y, maxlags)
    return {"maxlags": maxlags, "se_hac": f["se_hac"], "ci95_hac": f["ci95_hac"]}


def _variant_block(h: Harmonized, x_id: str, label: str, scale_luc: bool = False) -> dict | None:
    frame, pair = align_pair(h, x_id, TEMPERATURE)
    x, y = frame[x_id].to_numpy(), frame[TEMPERATURE].to_numpy()
    n = len(frame)
    full = fit_line(x, y, hac_lags(n))
    lo, hi = AR6_TCRE["very_likely_range"]
    slope = full["slope"]
    block = {
        "label": label, "x_indicator": x_id, "y_indicator": TEMPERATURE, "unit": AR6_TCRE["unit"],
        "range": pair["range_used"], "n_years": n, "omitted_years": pair["omitted_years"],
        "fit": {**full, "slope_per_1000_gtc": slope * GTCO2_PER_GTC,
                "rule": "maxlags = floor(1.5 * n^(1/3)); Bartlett kernel; 95% CI from the HAC standard error (normal)"},
        "hac_sensitivity": [_hac_row(x, y, L) for L in HAC_SENSITIVITY_LAGS],
        "vs_ar6": {"within_very_likely_range": bool(lo <= slope <= hi), "ci_overlaps_range": bool(full["ci95_hac"][0] <= hi and full["ci95_hac"][1] >= lo),
                   "ratio_to_best_estimate": slope / AR6_TCRE["best_estimate"]},
        "windows": [],
    }
    for s in START_GRID:
        sub = frame[frame["year"] >= s]
        if len(sub) < MIN_WINDOW_YEARS:
            block["windows"].append({"start": s, "end": int(frame["year"].max()), "n_years": int(len(sub)), "unavailable": f"fewer than {MIN_WINDOW_YEARS} years"})
            continue
        f = fit_line(sub[x_id].to_numpy(), sub[TEMPERATURE].to_numpy(), hac_lags(len(sub)))
        block["windows"].append({"start": s, "end": int(sub["year"].max()), "n_years": int(len(sub)), "slope": f["slope"], "ci95_hac": f["ci95_hac"],
                                 "r_squared": f["r_squared"], "maxlags": f["maxlags"]})
    if scale_luc:
        yrs = frame["year"].to_numpy()
        luc = h.series(X_LUC).reindex(yrs).to_numpy()
        fossil_from_1850 = x - luc  # total cumulative minus land-use cumulative, both from 1850
        block["land_use_sensitivity"] = [{"land_use_scale": sc, "slope": fit_line(fossil_from_1850 + sc * luc, y, hac_lags(n))["slope"]} for sc in LUC_SCALES]
    return block


def _provenance(climate_dir: str, series_id: str) -> dict:
    path = os.path.join(climate_dir, "provenance.json")
    return (json.load(open(path)).get(series_id) or {}) if os.path.exists(path) else {}


def _vintage(climate_dir: str, notices_path: str) -> dict:
    """The temperature source's vintage and the caveat that stays until the owner records a reconciliation (decision 39).
    Read from provenance.json, not the catalog, so it is available even when the harmonized layer is not."""
    rel = _provenance(climate_dir, "temperature_anomaly_annual").get("source_release")
    last_modified = rel.get("http_last_modified") if isinstance(rel, dict) else None
    reconciled = False
    if os.path.exists(notices_path):
        reconciled = bool(json.load(open(notices_path)).get("berkeley_earth", {}).get("vintage_reconciled", False))
    date = last_modified[:10] if last_modified else "an unknown date"
    caveat = (f"Based on Berkeley Earth file vintage {date}; a possible ~0.1 °C discrepancy with Berkeley Earth's most recent published report text "
              "has not yet been reconciled.")
    return {"file_last_modified": last_modified, "reconciled": reconciled, "caveat": None if reconciled else caveat}


# each variant is judged on its own inputs: the independent secondary must survive the headline's inputs being absent, and vice versa
VARIANTS = {
    "headline": dict(x=X_TOTAL, needs=[TEMPERATURE, X_TOTAL, X_LUC], label="Total anthropogenic CO2 (fossil + cement + land-use change)", scale_luc=True),
    "secondary_fossil_only": dict(x=X_FOSSIL, needs=[TEMPERATURE, X_FOSSIL], label="Fossil fuel + cement CO2 only (excludes land-use change)", scale_luc=False),
}
INPUT_IDS = [TEMPERATURE, X_TOTAL, X_FOSSIL, X_LUC]


def build(h: Harmonized | None, climate_dir: str, notices_path: str, report: RunReport, load_error: str | None = None) -> dict:
    """The output is always complete in its metadata (method, caveats, vintage, attribution, inputs): an unavailable result is explicit
    nulls with a reason, never a missing field, a stale file, or a crash. Metadata comes from provenance.json and module constants, so it
    does not depend on the harmonized catalog having loaded."""
    vintage = _vintage(climate_dir, notices_path)
    attribution = {k: v for k, v in _provenance(climate_dir, "owid_world_co2_annual").items()
                   if k in ("citations", "attribution_required", "required_citation_format", "land_use_license_note")}
    caveats = [PLAIN_LANGUAGE, METHODOLOGY, DENOMINATOR_NOTE, _LUC_UNCERTAINTY, _LUC_LICENSE] + ([vintage["caveat"]] if vintage["caveat"] else [])
    inputs = {}
    for i in INPUT_IDS:
        e = h.catalog.get(i) if h is not None else None
        inputs[i] = ({"available": True, "name": e.get("name"), "unit": e.get("unit"), "coverage": e.get("coverage"), "provenance": e.get("provenance")}
                     if e else {"available": False})
    out = {"schema_version": SCHEMA_VERSION, "generated_at": utc_now(), "note": CAUSATION_NOTE, "ar6_reference": AR6_TCRE,
           "method": "OLS with intercept; Newey-West (HAC) standard errors", "methodology": METHODOLOGY, "definition": "total anthropogenic CO2 since 1850",
           "temperature_source_vintage": vintage, "attribution": attribution, "caveats": caveats, "inputs": inputs}
    for key, spec in VARIANTS.items():
        reason = None
        if h is None:
            reason = f"harmonized layer unavailable: {load_error}"
        elif (missing := [i for i in spec["needs"] if i not in h.catalog]):
            reason = f"missing indicators: {', '.join(missing)}"
        else:
            try:
                out[key] = _variant_block(h, spec["x"], spec["label"], scale_luc=spec["scale_luc"])
            except (ValueError, KeyError) as e:  # too few shared years, an unusable pairing, a degenerate predictor, a column that slipped past the load check
                reason = f"pairing refused: {e}"
            except Exception as e:  # noqa: BLE001 -- last resort: whatever the cause, the output is rewritten with explicit nulls, never left stale
                logging.exception("correlate: unexpected error computing %s", key)
                reason = f"unexpected error: {type(e).__name__}: {e}"
        if reason:
            out[key] = None
            out[f"{key}_unavailable_reason"] = reason
            report.deviate(f"{key} regression unavailable: {reason}")
    validate(out, report)
    return out


def validate(out: dict, report: RunReport) -> None:
    for key in VARIANTS:
        b = out.get(key)
        if not b:
            continue
        f = b["fit"]
        vals = [f["slope"], f["intercept"], f["r_squared"], f["se_hac"], *f["ci95_hac"]]
        if not all(math.isfinite(v) for v in vals):
            report.deviate(f"{key}: non-finite regression statistic")
            continue
        if not (f["ci95_hac"][0] <= f["slope"] <= f["ci95_hac"][1]):
            report.deviate(f"{key}: the confidence interval does not bracket the slope")
        if f["slope"] <= 0:
            report.deviate(f"{key}: slope {f['slope']:.3f} is not positive; check the inputs before publishing")
        if not 0 <= f["r_squared"] <= 1:
            report.deviate(f"{key}: R^2 {f['r_squared']} outside [0, 1]")


def run(climate_dir: str = CLIMATE_DIR, out_dir: str | None = None, notices_path: str = NOTICES_PATH) -> RunReport:
    """Always replaces the output (atomically): when the inputs are unavailable the previous file is overwritten with explicit nulls and a
    reason, so a stale regression is never served as current. The failure is a deviation (an alert), not a crash."""
    out_dir = out_dir or climate_dir
    report = RunReport("correlate")
    h, load_error = None, None
    try:
        h = load_harmonized(climate_dir)
    except Exception as e:  # noqa: BLE001 -- a missing or invalid catalog/table of ANY kind: explicit nulls and a deviation, never a stale file
        if not isinstance(e, (OSError, ValueError, KeyError)):
            logging.exception("correlate: unexpected error loading the harmonized layer")
        load_error = f"{type(e).__name__}: {e}"
    out = build(h, climate_dir, notices_path, report, load_error)
    write_json_atomic(out, os.path.join(out_dir, OUTPUT_NAME))
    report.count("correlation_headline", sum(1 for k in VARIANTS if out.get(k)))
    if out.get("headline"):
        f = out["headline"]["fit"]
        report.note(f"headline (total anthropogenic CO2) {f['slope']:.3f} °C per 1,000 GtCO2, HAC 95% CI [{f['ci95_hac'][0]:.3f}, {f['ci95_hac'][1]:.3f}], "
                    f"R^2 {f['r_squared']:.3f}, n={f['n']}; AR6 range {AR6_TCRE['very_likely_range']}")
    if out.get("secondary_fossil_only"):
        report.note(f"fossil-only variant {out['secondary_fossil_only']['fit']['slope']:.3f} °C per 1,000 GtCO2")
    if not out["temperature_source_vintage"]["reconciled"]:
        report.note("Berkeley Earth vintage caveat is attached (owner has not recorded a reconciliation)")
    return report
