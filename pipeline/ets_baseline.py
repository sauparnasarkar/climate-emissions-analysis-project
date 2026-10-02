"""A current BAU baseline: a second ETS fit on the full data. Release 21, Backlog B2, Option A (`ENHANCEMENTS.md`).

Week 4's ETS is fitted on data through 2018 (`TRAIN_CUTOFF`) so that 2019-2023 can be held out for the forecast-vs-actual chart. That evaluation cutoff was then reused as a
production input: Week 5's BAU pathway is that forecast, so the pathways start in 2025 at a level that never saw 2019-2024 (+3.7% above the observed 2024 total, with
per-country steps from -51% to +62%). This stage is the second artifact: **the same model, ETS(A,Ad,N) with an optimised damped trend, fitted on every observed year (1990 to
the last complete OWID year)**, for use only as the BAU input of Week 5 and the Area 2 temperature translation. Week 4's fit is untouched: it keeps its teaching job.

Writes `ets_baseline_full_data.csv` (country, year, mean; point forecasts only -- the 95% bands of the Week 4 export are an unseeded Monte Carlo, Backlog B1, and are not
reproduced here) and `ets_baseline_full_data.json` (method, parameters, the step check, a backtest, data-anomaly flags and the scope limits).

- **No outlier handling.** The 2020 COVID dip is left in the training data: in a backtest, fitting through 2021 or 2022 forecasts the following years about twice as accurately
  as the fit stuck at 2018, interpolating 2020 gave no consistent benefit, and the refit shows no visible distortion (smoothing parameters barely move, the path is smooth).
- **Thresholds** (shared with the scenario translation, `pipeline/step_check.py`): the first forecast year must be within +/-2% of the last observed total in aggregate, and
  countries outside +/-5% are listed (a deviation when systematic).
- **Data anomalies are flagged, not altered**: any single year more than 2x above or below the centred 7-year median is listed with the countries' fit parameters. Kuwait 1991
  (the oil fires, 493 Mt against ~30-40 either side) is the one such value in the 40-country set today and is why Kuwait's step is outside +/-5%.
- Always rewrites both files; an input that cannot be used gives explicit nulls with the reason and a deviation, never a stale baseline.
"""

from __future__ import annotations

import json
import logging
import os
import warnings

import numpy as np
import pandas as pd

from .common import CLIMATE_DIR, ROOT, RunReport, utc_now, write_csv_atomic, write_json_atomic
from .owid import DATA_PATH as OWID_PATH
from .step_check import AGGREGATE_TOL_PCT, COUNTRY_TOL_PCT, MAX_FLAGGED_SHARE, check_step, step_messages

SCHEMA_VERSION = 1
OUTPUT_CSV = "ets_baseline_full_data.csv"
OUTPUT_JSON = "ets_baseline_full_data.json"
SELECTED_PATH = os.path.join(ROOT, "data", "selected_countries.json")
FIT_START = 1990  # the first year of the Week 1-4 data
HORIZON_END = 2043  # the Week 4 forecast end, kept for parity
STUCK_CUTOFF = 2018  # Week 4's TRAIN_CUTOFF: the fit this baseline replaces as the production input
BACKTEST_HORIZONS = (3, 2)  # fit through (last year - h), forecast the next h years
MIN_YEARS = 20
ANOMALY_RATIO = 2.0
ANOMALY_WINDOW = 7

METHODOLOGY = ("Exponential smoothing with an additive damped trend, ETS(A,Ad,N) (statsmodels `ExponentialSmoothing(trend='add', damped_trend=True, seasonal=None)`, parameters optimised), "
               "fitted separately for each covered country on every observed year of OWID fossil + cement CO2 from 1990 to the last complete year. Point forecasts only. Week 4's fit, "
               "stopped at 2018 so that 2019-2023 can be held out, is unchanged and keeps its teaching role.")
SCOPE_LIMITS = [
    "Model: ETS(A,Ad,N) only. No model selection or comparison with other model families was done for this baseline.",
    "Coverage: the covered countries only (the Week 1 expanded set); aggregates mix large and small emitters, so a total can look better than the typical country.",
    "Evidence: the backtest uses two cutoffs with short, overlapping horizons (2 and 3 years ahead). It shows that this fit is more accurate than the fit stuck at 2018 and shows no "
    "visible distortion from the COVID years; it does not establish forecast skill over the 19-year horizon.",
    "COVID: the 2020 dip is left in the training data (no outlier handling): interpolating it gave no consistent benefit in the backtest. The damped trend can still mis-handle a "
    "dip and rebound for an individual country, which is why the per-country step check exists.",
    "Anomalies: single-year data anomalies (for example Kuwait 1991, the oil fires) are flagged but not altered, and they distort the affected country's fit.",
    "Output: point forecasts only. Week 4's 95% bands are an unseeded Monte Carlo (Backlog B1) and are not reproduced.",
    "Scope of emissions: territorial fossil fuel and cement CO2; land-use change is not part of this forecast.",
]


class Unavailable(Exception):
    """An input problem that makes the baseline unusable: reported as explicit nulls with the reason, never a stale or partial baseline."""


def fit_forecast(series: pd.Series, steps: int) -> tuple[np.ndarray, dict]:
    """ETS(A,Ad,N) fit on a yearly series; returns the point forecast for the next `steps` years and the optimised parameters."""
    from statsmodels.tsa.holtwinters import ExponentialSmoothing  # submodule import: `statsmodels.api` is broken by scipy 1.17 (see requirements.txt)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        res = ExponentialSmoothing(series.astype(float), trend="add", damped_trend=True, seasonal=None).fit(optimized=True)
        fc = res.forecast(steps)
    p = res.params
    return np.asarray(fc, dtype=float), {"alpha": float(p["smoothing_level"]), "beta_star": float(p["smoothing_trend"]), "phi": float(p["damping_trend"])}


def anomalies(series: pd.Series) -> list[dict]:
    """Single-year values more than ANOMALY_RATIO times above or below the centred ANOMALY_WINDOW-year median (flag only)."""
    med = series.rolling(ANOMALY_WINDOW, center=True, min_periods=ANOMALY_WINDOW - 2).median()
    ratio = series / med
    return [{"year": int(y), "value_mt": float(series.loc[y]), "ratio_to_local_median": float(r)} for y, r in ratio.items() if np.isfinite(r) and (r > ANOMALY_RATIO or r < 1 / ANOMALY_RATIO)]


def _series_by_country(owid: pd.DataFrame, countries: list[str], first: int, last: int) -> dict[str, pd.Series]:
    out, problems = {}, []
    for c in countries:
        s = owid[(owid["country"] == c) & (owid["year"] >= first) & (owid["year"] <= last)].set_index("year")["co2"].sort_index()
        if len(s) != last - first + 1 or s.isna().any() or not np.isfinite(s.to_numpy(dtype=float)).all() or (s <= 0).any():
            problems.append(c)
        out[c] = s
    if problems:
        raise Unavailable(f"OWID CO2 for {first}-{last} is missing, non-finite or not positive for: {', '.join(problems)}")
    return out


def _backtest(series: dict[str, pd.Series], last: int, report: RunReport) -> list[dict]:
    countries = sorted(series)
    stuck_fc = {c: fit_forecast(series[c].loc[:STUCK_CUTOFF], last - STUCK_CUTOFF)[0] for c in countries} if STUCK_CUTOFF < last - max(BACKTEST_HORIZONS) else None
    out = []
    for h in BACKTEST_HORIZONS:
        cutoff = last - h
        if cutoff - FIT_START + 1 < MIN_YEARS or (stuck_fc is None):
            continue
        actual = {c: series[c].loc[cutoff + 1:last].to_numpy(dtype=float) for c in countries}
        variants = {"plain_refit": {c: fit_forecast(series[c].loc[:cutoff], h)[0] for c in countries},
                    f"fit_stuck_at_{STUCK_CUTOFF}": {c: stuck_fc[c][cutoff - STUCK_CUTOFF:] for c in countries},
                    "naive_last_value": {c: np.repeat(float(series[c].loc[cutoff]), h) for c in countries}}
        res = {}
        for name, fc in variants.items():
            err = np.array([np.abs(fc[c] - actual[c]) / actual[c] * 100 for c in countries])
            tot = (np.sum([fc[c] for c in countries], axis=0) / np.sum([actual[c] for c in countries], axis=0) - 1) * 100
            res[name] = {"median_abs_country_error_pct": [float(v) for v in np.median(err, axis=0)], "total_error_pct": [float(v) for v in tot]}
        a, b = res["plain_refit"], res[f"fit_stuck_at_{STUCK_CUTOFF}"]
        out.append({"cutoff": cutoff, "horizon": h, "years": list(range(cutoff + 1, last + 1)), "variants": res,
                    "summary": (f"Fitted through {cutoff}{' (the COVID years inside the training data)' if cutoff >= 2021 else ''}, the baseline forecast {cutoff + 1}-{last} with a median per-country error of "
                                f"{', '.join(f'{v:.1f}%' for v in a['median_abs_country_error_pct'])} against {', '.join(f'{v:.1f}%' for v in b['median_abs_country_error_pct'])} "
                                f"for the fit stuck at {STUCK_CUTOFF}; the 40-country total was off by {', '.join(f'{v:+.1f}%' for v in a['total_error_pct'])} against "
                                f"{', '.join(f'{v:+.1f}%' for v in b['total_error_pct'])}.".replace("40-country", f"{len(countries)}-country"))})
    return out


def _metadata(climate_dir: str) -> tuple[list[str], dict]:
    caveats = ["This is a statistical extrapolation of each country's own history, not a model of policy or technology; it is the BAU pathway's starting point, and the scenarios are derived from it.",
               *SCOPE_LIMITS]
    pp = os.path.join(climate_dir, "provenance.json")
    prov = (json.load(open(pp)).get("owid_world_co2_annual") or {}) if os.path.exists(pp) else {}
    return caveats, {k: prov[k] for k in ("source", "license", "citations") if k in prov}


def _skeleton(caveats: list[str], attribution: dict) -> dict:
    return {"schema_version": SCHEMA_VERSION, "generated_at": utc_now(), "name": "BAU baseline: ETS fitted on the full data", "methodology": METHODOLOGY, "scope_limits": SCOPE_LIMITS,
            "caveats": caveats, "attribution": attribution, "thresholds": {"aggregate_step_pct": AGGREGATE_TOL_PCT, "country_step_pct": COUNTRY_TOL_PCT, "max_flagged_share": MAX_FLAGGED_SHARE},
            "training_window": None, "last_observed_year": None, "forecast_years": None, "countries": None, "parameters": None, "step_check": None, "backtest": None,
            "data_anomalies": None, "inputs": {"owid-co2-data.csv": {"available": False}, "owid_world_co2_annual.csv": {"available": False}, "selected_countries.json": {"available": False}}}


def build(climate_dir: str, owid_path: str, selected_path: str, report: RunReport) -> tuple[dict, pd.DataFrame]:
    meta_error = None
    try:
        caveats, attribution = _metadata(climate_dir)
    except Exception as e:  # noqa: BLE001 -- malformed provenance must not stop the explicit-null output from being written
        logging.exception("ets_baseline: unable to read provenance")
        meta_error = f"attribution metadata: {type(e).__name__}: {e}"
        caveats, attribution = [f"Attribution metadata could not be read: {type(e).__name__}: {e}", *SCOPE_LIMITS], {}
    out = _skeleton(caveats, attribution)
    rows = pd.DataFrame(columns=["country", "year", "mean"])
    try:
        if meta_error:  # a baseline without its attribution is not published
            raise Unavailable(f"baseline metadata unavailable: {meta_error}")
        w = pd.read_csv(os.path.join(climate_dir, "owid_world_co2_annual.csv"))
        last = int(w["year"].max())
        out["inputs"]["owid_world_co2_annual.csv"] = {"available": True, "last_complete_year": last}
        countries = sorted(json.load(open(selected_path))["expanded"])
        out["inputs"]["selected_countries.json"] = {"available": True, "n_countries": len(countries)}
        if not countries:
            raise Unavailable("selected_countries.json lists no countries")
        owid = pd.read_csv(owid_path, usecols=["country", "year", "co2"])
        out["inputs"]["owid-co2-data.csv"] = {"available": True}
        series = _series_by_country(owid, countries, FIT_START, last)
        steps = HORIZON_END - last
        fcs, params, flags = {}, {}, {}
        for c in countries:
            fcs[c], params[c] = fit_forecast(series[c], steps)
            a = anomalies(series[c])
            if a:
                flags[c] = a
        if not all(np.isfinite(v).all() and (v > 0).all() for v in fcs.values()):
            bad = sorted(c for c, v in fcs.items() if not (np.isfinite(v).all() and (v > 0).all()))
            raise Unavailable(f"the fit produced non-finite or non-positive forecasts for: {', '.join(bad)}")
        years = list(range(last + 1, HORIZON_END + 1))
        rows = pd.DataFrame([(c, y, float(v)) for c in countries for y, v in zip(years, fcs[c])], columns=["country", "year", "mean"])
        step = check_step({c: float(fcs[c][0]) for c in countries}, {c: float(series[c].loc[last]) for c in countries})
        dev, notes = step_messages(step, f"ets_baseline first forecast year {last + 1}")
        for d in dev:
            report.deviate(d)
        for n in notes:
            report.note(n)
        for c, a in flags.items():
            report.note(f"data anomaly in {c}: " + "; ".join(f"{r['year']} = {r['value_mt']:,.1f} Mt ({r['ratio_to_local_median']:.1f}x the local median)" for r in a)
                        + f"; its fit is distorted (alpha {params[c]['alpha']:.3f}, step {step['country_steps_pct'][c]:+.1f}%)")
        backtest = _backtest(series, last, report)
        out.update({"training_window": [FIT_START, last], "last_observed_year": last, "forecast_years": [last + 1, HORIZON_END], "countries": countries, "parameters": params,
                    "step_check": step, "backtest": backtest, "data_anomalies": flags})
        agg = rows.groupby("year")["mean"].sum()
        report.note(f"baseline {FIT_START}-{last} fit, {len(countries)} countries: aggregate {agg.loc[last + 1]:,.0f} Mt in {last + 1} ({step['aggregate_step_pct']:+.1f}% vs the last observed total), "
                    f"{agg.loc[min(last + 16, HORIZON_END)]:,.0f} Mt in {min(last + 16, HORIZON_END)}; {step['n_within_country_tolerance']} of {step['n_countries']} countries within ±{COUNTRY_TOL_PCT:g}%")
    except Exception as e:  # noqa: BLE001 -- whatever the cause: explicit nulls and a deviation, never a stale or partial baseline
        if not isinstance(e, (Unavailable, OSError, ValueError, KeyError)):
            logging.exception("ets_baseline: unexpected error")
        for k in ("training_window", "last_observed_year", "forecast_years", "countries", "parameters", "step_check", "backtest", "data_anomalies"):
            out[k] = None
        rows = pd.DataFrame(columns=["country", "year", "mean"])
        out["unavailable_reason"] = e.args[0] if isinstance(e, Unavailable) else f"{type(e).__name__}: {e}"
        report.deviate(f"ets_baseline unavailable: {out['unavailable_reason']}")
    return out, rows


def run(climate_dir: str = CLIMATE_DIR, out_dir: str | None = None, owid_path: str = OWID_PATH, selected_path: str = SELECTED_PATH) -> RunReport:
    out_dir = out_dir or climate_dir
    report = RunReport("ets_baseline")
    meta, rows = build(climate_dir, owid_path, selected_path, report)
    write_csv_atomic(rows.assign(**{"mean": rows["mean"].astype(float).round(3)}) if len(rows) else rows, os.path.join(out_dir, OUTPUT_CSV))
    write_json_atomic(meta, os.path.join(out_dir, OUTPUT_JSON))
    report.count("ets_baseline_full_data", len(rows))
    return report
