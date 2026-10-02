"""Headline regression: temperature against cumulative CO2. Release 21, Phase 1.3a (`ENHANCEMENTS.md` decisions 31-33 and 40).

A derived stage that runs after `harmonize` and writes `data/climate/correlation_headline.json`, which the API (Phase 1.4) only
reads. It is deterministic: the only random draw (the bootstrap) uses a fixed, recorded seed.

- **Headline** (decision 40): OLS of the Berkeley Earth anomaly (1850-1900 reference) on **cumulative total anthropogenic CO2 since
  1850** (OWID World fossil + cement incl. international transport, plus land-use change). Slope in degrees C per 1,000 GtCO2, R^2,
  Newey-West (HAC) standard errors and 95% CI.
- **Secondary, labelled variant**: the same regression on fossil + cement CO2 alone (the common meaning of "CO2 emissions"); never hidden.
- The **IPCC AR6** TCRE range is carried beside both, so the comparison is against an uncertainty range, not a point value.
- **Stability** (Phase 1.3b, decision 34): a seeded moving-block bootstrap of the *residuals* (x held fixed), distinct from the HAC interval, plus
  decade holdouts. It publishes numbers and a generated plain-language summary, never a pass/fail label.
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
ALL_GAS_OUTPUT = "correlation_all_gas.json"
ALL_GAS_X = "primap_ghg_total_cumulative_mtco2e"
ALL_GAS_START = 1970  # decision 35: the recent all-gas relationship starts in 1970 (PRIMAP-hist multi-gas data; the headline starts in 1850)
ALL_GAS_UNIT = "°C per 1,000 GtCO2e"

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

# Stability check (decision 34). The seed is fixed and published: an unseeded Monte Carlo made the ETS bands irreproducible (Backlog B1).
BOOTSTRAP_SEED = 20261002
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_BLOCK = 10  # the primary block length (years); the others are a published sensitivity
BOOTSTRAP_BLOCKS = (5, 10, 20, 30)
HOLDOUT_SPLITS = (1980, 1990, 2000, 2010)  # decade-based: fit on the years before the split, test from the split year to the end
MIN_TRAIN_YEARS = 20
FIT_QUALITY_SPLIT = 2000  # the holdout split the headline copy quotes (fit before it, test from it)
LUC_WEIGHT_SCAN = (0.0, 0.25, 0.5, 0.7, 1.0, 1.3)  # land-use weight in x = fossil + cement + weight * land-use (0 = fossil-only, 1 = headline)
SIMILAR_RMSE_RATIO = 1.10  # out-of-sample errors within 10% of each other are described as similar
SIMILAR_R2_GAP = 0.01  # in-sample R^2 within 0.01 is described as almost identical
MIN_TEST_YEARS = 5

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


def block_indices(years: np.ndarray | None, n: int, block: int, resamples: int, rng: np.random.Generator) -> np.ndarray:
    """Row indices (resamples x n) of residual blocks built only from **calendar-consecutive** years. `align_pair` drops a year missing from
    either series, so a block of `block` rows could otherwise span a gap and treat residuals several years apart as consecutive; a start is
    allowed only if the `block` rows from it cover `block` consecutive calendar years. With no gaps the allowed starts are exactly
    0..n-block, so the draws are identical to an unconstrained moving-block bootstrap."""
    if years is None:
        valid = np.arange(0, n - block + 1)
    else:
        years = np.asarray(years)
        valid = np.flatnonzero(years[block - 1:] - years[: n - block + 1] == block - 1)
    if len(valid) == 0:
        raise ValueError(f"no run of {block} consecutive calendar years in the paired data, so {block}-year blocks cannot be formed")
    nb = -(-n // block)
    starts = valid[rng.integers(0, len(valid), size=(resamples, nb))]
    return (starts[:, :, None] + np.arange(block)).reshape(resamples, -1)[:, :n]


def bootstrap_slopes(x_mt: np.ndarray, y: np.ndarray, block: int, resamples: int, rng: np.random.Generator, years: np.ndarray | None = None) -> np.ndarray:
    """Slopes from a moving-block bootstrap of the *residuals* with x held fixed: y* = fitted + residual blocks of `block` consecutive calendar
    years (see `block_indices`; blocks concatenated and trimmed to n). A pairs bootstrap is avoided on purpose: x is a trending cumulative
    series, so resampling (x, y) blocks from different eras gives samples with little x spread and an unstable slope (decision 34)."""
    x = np.asarray(x_mt, float) / MT_PER_THOUSAND_GT
    y = np.asarray(y, float)
    n = len(x)
    if not 1 <= block <= n:
        raise ValueError(f"block length {block} is not between 1 and the {n} paired years")
    slope, intercept = np.polyfit(x, y, 1)
    fitted = intercept + slope * x
    resid = y - fitted
    y_star = fitted + resid[block_indices(years, n, block, resamples, rng)]
    xc = x - x.mean()
    return (y_star @ xc) / (xc @ xc)  # OLS slope per resample (sum of xc is 0, so y* needs no centring)


def _bootstrap_block(x: np.ndarray, y: np.ndarray, block: int, seed: int = BOOTSTRAP_SEED, resamples: int = BOOTSTRAP_RESAMPLES,
                     years: np.ndarray | None = None) -> dict:
    # each block length builds its own generator from (seed, block), so the result for a length never depends on which other lengths are computed or in what order
    rng = np.random.default_rng(np.random.SeedSequence([seed, block]))
    s = bootstrap_slopes(x, y, block, resamples, rng, years)
    lo, med, hi = (float(v) for v in np.percentile(s, [2.5, 50, 97.5]))
    return {"block_years": block, "ci95": [lo, hi], "median": med}


def holdout(frame: pd.DataFrame, x_id: str, split: int) -> dict:
    """Fit on the years before `split`, predict `split` onward. Reports the train slope and the out-of-sample error (RMSE, MAE, mean error),
    with the error of simply predicting the training-period mean as context."""
    train, test = frame[frame["year"] < split], frame[frame["year"] >= split]
    out = {"split_year": split, "train_range": [int(train["year"].min()), int(train["year"].max())] if len(train) else None,
           "test_range": [int(test["year"].min()), int(test["year"].max())] if len(test) else None, "n_train": int(len(train)), "n_test": int(len(test))}
    if len(train) < MIN_TRAIN_YEARS or len(test) < MIN_TEST_YEARS:
        return {**out, "unavailable": f"needs at least {MIN_TRAIN_YEARS} training and {MIN_TEST_YEARS} test years"}
    xt, yt = train[x_id].to_numpy() / MT_PER_THOUSAND_GT, train[TEMPERATURE].to_numpy()
    slope, intercept = np.polyfit(xt, yt, 1)
    err = test[TEMPERATURE].to_numpy() - (intercept + slope * test[x_id].to_numpy() / MT_PER_THOUSAND_GT)
    naive = test[TEMPERATURE].to_numpy() - yt.mean()
    return {**out, "train_slope": float(slope), "rmse_c": float(np.sqrt(np.mean(err**2))), "mae_c": float(np.mean(np.abs(err))), "mean_error_c": float(np.mean(err)),
            "baseline_rmse_train_mean_c": float(np.sqrt(np.mean(naive**2)))}


def _stability(frame: pd.DataFrame, x_id: str, fit: dict, windows: list[dict]) -> dict:
    x, y = frame[x_id].to_numpy(), frame[TEMPERATURE].to_numpy()
    years = frame["year"].to_numpy()
    blocks, unavailable = [], []
    for b in BOOTSTRAP_BLOCKS:
        try:
            blocks.append(_bootstrap_block(x, y, b, years=years))
        except ValueError as e:  # a length the paired data cannot support (too long, or no run of that many consecutive years)
            unavailable.append({"block_years": b, "reason": str(e)})
    primary = next((b for b in blocks if b["block_years"] == BOOTSTRAP_BLOCK), None)
    if primary is None:  # the summary and the interval are defined on the primary block length: no primary, no stability block
        raise ValueError(next(u["reason"] for u in unavailable if u["block_years"] == BOOTSTRAP_BLOCK))
    holdouts = [holdout(frame, x_id, s) for s in HOLDOUT_SPLITS]
    hac = fit["ci95_hac"]
    boot = primary["ci95"]
    ok_windows = [w for w in windows if "slope" in w]
    ref = next((h for h in holdouts if h["split_year"] == 2000 and "rmse_c" in h), None)
    parts = [f"Resampling the model's residuals in {BOOTSTRAP_BLOCK}-year blocks ({BOOTSTRAP_RESAMPLES:,} resamples, seed {BOOTSTRAP_SEED}) gives a 95% interval for the slope of "
             f"{boot[0]:.3f} to {boot[1]:.3f}, against {hac[0]:.3f} to {hac[1]:.3f} from the Newey-West standard errors; across block lengths of "
             f"{blocks[0]['block_years']} to {blocks[-1]['block_years']} years the interval's lower bound stays between {min(b['ci95'][0] for b in blocks):.3f} and "
             f"{max(b['ci95'][0] for b in blocks):.3f} and its upper bound between {min(b['ci95'][1] for b in blocks):.3f} and {max(b['ci95'][1] for b in blocks):.3f}."]
    if ok_windows:
        parts.append(f"Estimated from later start years ({', '.join(str(w['start']) for w in ok_windows)}) the slope ranges from "
                     f"{min(w['slope'] for w in ok_windows):.3f} to {max(w['slope'] for w in ok_windows):.3f}.")
    if ref:
        parts.append(f"Fitting only on years before {ref['split_year']} and predicting {ref['test_range'][0]}-{ref['test_range'][1]} gives a slope of {ref['train_slope']:.3f} and an "
                     f"out-of-sample error (RMSE) of {ref['rmse_c']:.3f} °C, against {ref['baseline_rmse_train_mean_c']:.3f} °C for simply predicting the earlier average.")
    return {
        "method": "moving-block bootstrap of the regression residuals with the predictor held fixed (distinct from the HAC standard errors), plus decade holdouts",
        "seed": BOOTSTRAP_SEED, "resamples": BOOTSTRAP_RESAMPLES, "primary_block_years": BOOTSTRAP_BLOCK,
        "bootstrap": primary, "block_length_sensitivity": blocks, "block_length_unavailable": unavailable,
        "hac_ci95": hac, "bootstrap_vs_hac_width_ratio": (boot[1] - boot[0]) / (hac[1] - hac[0]) if hac[1] > hac[0] else None,
        "holdouts": holdouts, "summary": " ".join(parts),
        "note": "These are published as measured; no pass/fail judgement is made.",
    }


def _weight_scan(frame: pd.DataFrame, fossil_from_1850: np.ndarray, luc: np.ndarray) -> dict:
    """How the slope and the out-of-sample error respond to the weight given to land-use CO2. Published to show the *shape* of the trade-off
    (decision 41), not to select a weight: a weight chosen to minimise this error would be tuned to the holdout."""
    rows = []
    for w in LUC_WEIGHT_SCAN:
        f = frame[["year", TEMPERATURE]].assign(_x=fossil_from_1850 + w * luc)
        full = fit_line(f["_x"].to_numpy(), f[TEMPERATURE].to_numpy(), hac_lags(len(f)))
        ho = holdout(f, "_x", FIT_QUALITY_SPLIT)
        rows.append({"land_use_weight": w, "slope": full["slope"], "r_squared": full["r_squared"], "holdout_split_year": FIT_QUALITY_SPLIT,
                     "holdout_train_slope": ho.get("train_slope"), "holdout_rmse_c": ho.get("rmse_c")})
    return {"definition": "x = cumulative fossil + cement CO2 + weight * cumulative land-use CO2 (weight 0 = the fossil-only variant, 1 = the headline)", "weights": rows,
            "note": "Shows how the out-of-sample error responds to the weight given to land-use CO2. It is published to show the shape of the trade-off, not to choose a "
                    "weight: a weight picked to minimise this error would be tuned to the holdout."}


def fit_quality_note(headline: dict, fossil: dict) -> dict | None:
    """The headline module's required copy on the land-use trade-off (decision 41), generated from the holdout and R^2 numbers so the UI, the
    agent and the docs quote the same figures. The wording follows what the numbers show: larger / smaller / similar out-of-sample error, and
    whether the in-sample fits agree. Returns None if either variant has no usable holdout at the reference split."""
    def ref(b):
        return next((h for h in b["stability"]["holdouts"] if h["split_year"] == FIT_QUALITY_SPLIT and "rmse_c" in h), None)

    hh, ff = ref(headline), ref(fossil)
    if not hh or not ff:
        return None
    h_rmse, f_rmse = hh["rmse_c"], ff["rmse_c"]
    h_r2, f_r2 = headline["fit"]["r_squared"], fossil["fit"]["r_squared"]
    relation = "larger" if h_rmse > f_rmse * SIMILAR_RMSE_RATIO else "smaller" if h_rmse * SIMILAR_RMSE_RATIO < f_rmse else "similar"
    insample_similar = abs(h_r2 - f_r2) < SIMILAR_R2_GAP
    a, b = hh["test_range"]
    errs = f"{h_rmse:.2f} vs {f_rmse:.2f} °C for {a}-{b}"
    s = ["Including land-use emissions aligns this estimate with the IPCC's own TCRE definition."]
    adj = {"larger": "a larger error than", "smaller": "a smaller error than", "similar": "a similar error to"}[relation]
    s.append(f"Land-use CO₂ is estimated with more uncertainty than fossil-fuel emissions, and in an out-of-sample test this headline predicted recent temperatures "
             f"with {adj} the fossil-only variant ({errs}).")
    if relation == "larger":
        s.append("The data cannot say whether that reflects land-use measurement uncertainty or something else.")
    if insample_similar:
        s.append(f"In-sample, both variants fit the historical record almost identically (R² {h_r2:.3f} vs {f_r2:.3f})"
                 + ("; the difference appears specifically in out-of-sample prediction." if relation != "similar" else "."))
    else:
        s.append(f"In-sample fit differs as well (R² {h_r2:.3f} vs {f_r2:.3f}).")
    return {"text": " ".join(s), "split_year": FIT_QUALITY_SPLIT, "test_range": [a, b], "headline_rmse_c": h_rmse, "fossil_only_rmse_c": f_rmse,
            "headline_r_squared": h_r2, "fossil_only_r_squared": f_r2, "out_of_sample_error": relation, "in_sample_fit_similar": insample_similar,
            "note": "Generated from the holdout and R-squared numbers in this file; the cause of the out-of-sample difference is not established."}


def _hac_row(x: np.ndarray, y: np.ndarray, maxlags: int) -> dict:
    f = fit_line(x, y, maxlags)
    return {"maxlags": maxlags, "se_hac": f["se_hac"], "ci95_hac": f["ci95_hac"]}


def _variant_block(h: Harmonized, x_id: str, label: str, scale_luc: bool = False, *, start: int | None = None, window_grid: tuple = START_GRID,
                   ar6: bool = True, unit: str | None = None) -> dict | None:
    """One regression block. `ar6=False` is for the all-gas view, which is not the CO2-only quantity the AR6 range describes: no AR6 verdict and no per-GtC figure."""
    frame, pair = align_pair(h, x_id, TEMPERATURE, start=start)
    x, y = frame[x_id].to_numpy(), frame[TEMPERATURE].to_numpy()
    n = len(frame)
    full = fit_line(x, y, hac_lags(n))
    lo, hi = AR6_TCRE["very_likely_range"]
    slope = full["slope"]
    block = {
        "label": label, "x_indicator": x_id, "y_indicator": TEMPERATURE, "unit": unit or AR6_TCRE["unit"],
        "range": pair["range_used"], "n_years": n, "omitted_years": pair["omitted_years"], "contiguous": not pair["omitted_years"],
        "fit": {**full, "slope_per_1000_gtc": slope * GTCO2_PER_GTC,
                "rule": "maxlags = floor(1.5 * n^(1/3)); Bartlett kernel; 95% CI from the HAC standard error (normal)"},
        "hac_sensitivity": [_hac_row(x, y, L) for L in HAC_SENSITIVITY_LAGS],
        "vs_ar6": {"within_very_likely_range": bool(lo <= slope <= hi), "ci_overlaps_range": bool(full["ci95_hac"][0] <= hi and full["ci95_hac"][1] >= lo),
                   "ratio_to_best_estimate": slope / AR6_TCRE["best_estimate"]},
        "windows": [],
    }
    for s in window_grid:
        sub = frame[frame["year"] >= s]
        if len(sub) < MIN_WINDOW_YEARS:
            block["windows"].append({"start": s, "end": int(frame["year"].max()), "n_years": int(len(sub)), "unavailable": f"fewer than {MIN_WINDOW_YEARS} years"})
            continue
        f = fit_line(sub[x_id].to_numpy(), sub[TEMPERATURE].to_numpy(), hac_lags(len(sub)))
        block["windows"].append({"start": s, "end": int(sub["year"].max()), "n_years": int(len(sub)), "slope": f["slope"], "ci95_hac": f["ci95_hac"],
                                 "r_squared": f["r_squared"], "maxlags": f["maxlags"]})
    if not ar6:
        block["fit"].pop("slope_per_1000_gtc")
        block.pop("vs_ar6")
    block["stability"] = _stability(frame, x_id, full, block["windows"])
    if scale_luc:
        yrs = frame["year"].to_numpy()
        luc = h.series(X_LUC).reindex(yrs).to_numpy()
        fossil_from_1850 = x - luc  # total cumulative minus land-use cumulative, both from 1850
        block["land_use_sensitivity"] = [{"land_use_scale": sc, "slope": fit_line(fossil_from_1850 + sc * luc, y, hac_lags(n))["slope"]} for sc in LUC_SCALES]
    if scale_luc:
        block["land_use_weight_scan"] = _weight_scan(frame, fossil_from_1850, luc)
    return block


def _provenance(climate_dir: str, series_id: str) -> dict:
    path = os.path.join(climate_dir, "provenance.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found")
    doc = json.load(open(path))
    entry = doc.get(series_id) if isinstance(doc, dict) else None
    if not entry:
        raise ValueError(f"{path}: missing provenance for {series_id}")
    return entry


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
    metadata_errors = []
    try:
        vintage = _vintage(climate_dir, notices_path)
    except Exception as e:  # noqa: BLE001 -- metadata failures must not prevent the explicit-null output from being written
        logging.exception("correlate: unable to load temperature vintage metadata")
        metadata_errors.append(f"temperature vintage metadata: {type(e).__name__}: {e}")
        vintage = {
            "file_last_modified": None,
            "reconciled": False,
            "caveat": f"Berkeley Earth vintage metadata could not be read: {type(e).__name__}: {e}",
        }
    try:
        attribution = {k: v for k, v in _provenance(climate_dir, "owid_world_co2_annual").items()
                       if k in ("citations", "attribution_required", "required_citation_format", "land_use_license_note")}
    except Exception as e:  # noqa: BLE001 -- preserve the output contract when provenance is malformed or unavailable
        logging.exception("correlate: unable to load attribution metadata")
        metadata_errors.append(f"attribution metadata: {type(e).__name__}: {e}")
        attribution = {}
    for error in metadata_errors:
        report.deviate(f"correlation metadata unavailable: {error}")
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
        if metadata_errors:
            reason = f"correlation metadata unavailable: {'; '.join(metadata_errors)}"
        elif h is None:
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
    if out.get("headline"):
        note = fit_quality_note(out["headline"], out["secondary_fossil_only"]) if out.get("secondary_fossil_only") else None
        out["headline"]["fit_quality_note"] = note
        if note is None:
            out["headline"]["fit_quality_note_unavailable_reason"] = ("the fossil-only variant is unavailable" if not out.get("secondary_fossil_only")
                                                                      else f"no usable holdout at the {FIT_QUALITY_SPLIT} split for both variants")
    validate(out, report)
    return out


def validate(out: dict, report: RunReport, keys=tuple(VARIANTS)) -> None:
    for key in keys:
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
        if b.get("contiguous") is False:
            report.deviate(f"{key}: {len(b['omitted_years'])} calendar-year gap(s) in the paired years — bootstrap blocks are formed only from consecutive years, "
                           "but the Newey-West lags count rows, so the HAC interval treats the rows either side of a gap as consecutive")
        s = b.get("stability", {}).get("bootstrap")
        if s and not (s["ci95"][0] <= f["slope"] <= s["ci95"][1]):
            report.deviate(f"{key}: the bootstrap interval does not bracket the fitted slope")
        if not 0 <= f["r_squared"] <= 1:
            report.deviate(f"{key}: R^2 {f['r_squared']} outside [0, 1]")


ALL_GAS_SCOPE = (
    "This view uses PRIMAP-hist national total greenhouse-gas emissions in CO2-equivalent terms (CO2, CH4, N2O and F-gases, AR5 100-year global-warming "
    "potentials), summed from 1970. It excludes international aviation and shipping and land-use change, covers a short window, and a steadily rising "
    "cumulative series is strongly correlated with time, so the estimate describes a recent co-movement; it is not comparable with the long-run CO2 "
    "relationship elsewhere on this platform."
)
ALL_GAS_WEIGHTING = (
    "CO2-equivalent weights use the AR5 100-year global-warming potentials; short-lived gases such as methane do not accumulate in the atmosphere the way CO2 "
    "does, so a cumulative CO2-equivalent total is a simplification."
)
ALL_GAS_NAME = "Recent all-gas relationship"


def build_all_gas(h: Harmonized | None, climate_dir: str, notices_path: str, report: RunReport, load_error: str | None = None) -> dict:
    """The recent all-gas relationship (decision 35): the same anomaly regressed on cumulative PRIMAP-hist total GHG from 1970. A separate output
    with its own name, never described as the CO2-only long-run relationship, and without an IPCC comparison: the AR6 range describes CO2 only."""
    metadata_errors = []
    try:
        prim = _provenance(climate_dir, "primap_global_composition_annual")
        excluded = sorted({int(e["year"]) for e in prim.get("excluded_incomplete_years", []) if isinstance(e, dict) and "year" in e})
    except Exception as exc:  # noqa: BLE001 -- malformed provenance must not stop the explicit-null output from being written (same contract as the headline)
        logging.exception("correlate: unable to load PRIMAP-hist attribution metadata")
        metadata_errors.append(f"attribution metadata: {type(exc).__name__}: {exc}")
        prim, excluded = {}, []
    try:
        vintage = _vintage(climate_dir, notices_path)
    except Exception as exc:  # noqa: BLE001
        logging.exception("correlate: unable to load temperature vintage metadata")
        metadata_errors.append(f"temperature vintage metadata: {type(exc).__name__}: {exc}")
        vintage = {"file_last_modified": None, "reconciled": False, "caveat": f"Berkeley Earth vintage metadata could not be read: {type(exc).__name__}: {exc}"}
    for error in metadata_errors:
        report.deviate(f"correlation metadata unavailable: {error}")
    completeness = (f"Years excluded because PRIMAP-hist's reporting for them is incomplete: {', '.join(map(str, excluded))}." if excluded
                    else "No trailing years were excluded as incomplete.")
    attribution = {k: prim[k] for k in ("source", "license", "citations", "source_release") if k in prim}
    caveats = [PLAIN_LANGUAGE, ALL_GAS_SCOPE, ALL_GAS_WEIGHTING, completeness]
    if prim.get("license"):
        caveats.append(f"PRIMAP-hist licence: {prim['license']}")
    if vintage["caveat"]:
        caveats.append(vintage["caveat"])
    e = h.catalog.get(ALL_GAS_X) if h is not None else None
    t = h.catalog.get(TEMPERATURE) if h is not None else None
    inputs = {i: ({"available": True, "name": c.get("name"), "unit": c.get("unit"), "coverage": c.get("coverage"), "provenance": c.get("provenance")} if c else {"available": False})
              for i, c in ((ALL_GAS_X, e), (TEMPERATURE, t))}
    out = {"schema_version": SCHEMA_VERSION, "generated_at": utc_now(), "note": CAUSATION_NOTE, "name": ALL_GAS_NAME,
           "method": "OLS with intercept; Newey-West (HAC) standard errors", "definition": f"cumulative PRIMAP-hist total greenhouse gases (CO2-equivalent) from {ALL_GAS_START}",
           "temperature_source_vintage": vintage, "attribution": attribution, "caveats": caveats, "inputs": inputs}
    reason = None
    if metadata_errors:
        reason = f"correlation metadata unavailable: {'; '.join(metadata_errors)}"
    elif h is None:
        reason = f"harmonized layer unavailable: {load_error}"
    elif (missing := [i for i in (TEMPERATURE, ALL_GAS_X) if i not in h.catalog]):
        reason = f"missing indicators: {', '.join(missing)}"
    else:
        try:
            out["recent_all_gas"] = _variant_block(h, ALL_GAS_X, f"{ALL_GAS_NAME}: all gases, national totals, {ALL_GAS_START} onward", start=ALL_GAS_START,
                                                   window_grid=tuple(s for s in START_GRID if s >= ALL_GAS_START), ar6=False, unit=ALL_GAS_UNIT)
        except (ValueError, KeyError) as exc:
            reason = f"pairing refused: {exc}"
        except Exception as exc:  # noqa: BLE001 -- last resort: explicit nulls, never a stale file
            logging.exception("correlate: unexpected error computing the all-gas relationship")
            reason = f"unexpected error: {type(exc).__name__}: {exc}"
    if reason:
        out["recent_all_gas"] = None
        out["recent_all_gas_unavailable_reason"] = reason
        report.deviate(f"recent_all_gas regression unavailable: {reason}")
    validate(out, report, keys=("recent_all_gas",))
    return out


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
    all_gas = build_all_gas(h, climate_dir, notices_path, report, load_error)
    write_json_atomic(all_gas, os.path.join(out_dir, ALL_GAS_OUTPUT))
    report.count("correlation_all_gas", 1 if all_gas.get("recent_all_gas") else 0)
    if all_gas.get("recent_all_gas"):
        g = all_gas["recent_all_gas"]["fit"]
        report.note(f"recent all-gas relationship {g['slope']:.3f} °C per 1,000 GtCO2e, HAC 95% CI [{g['ci95_hac'][0]:.3f}, {g['ci95_hac'][1]:.3f}], R^2 {g['r_squared']:.3f}, n={g['n']}")
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
