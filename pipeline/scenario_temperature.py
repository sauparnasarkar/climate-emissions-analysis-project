"""Scenario -> temperature translation. Release 21, Phase 1.3d (`ENHANCEMENTS.md` decisions 14, 38, 39; requirement §1.3.5).

A derived stage writing `correlation_scenario_temperature.json`, which the API (Phase 1.4) only reads. It translates the Week-5 emissions pathways
(`data/scenario_projections.csv`: 40 covered countries x BAU / Moderate / Aggressive) into *implied* temperature outcomes using the regression slopes of the
headline stage. It is always labelled an illustrative, partial-coverage translation: not a climate-model projection.

Method (decision 38):
- The covered countries follow the scenario pathways. **Rest-of-world is held at its last-observed share** of the World total (decision 14), so
  `global_t = covered_t / (1 - s)` with `s = 1 - covered_T0 / World_T0` (World includes international aviation and shipping, so they sit inside the rest of the world).
- Because the headline slope is per unit of *total* anthropogenic CO2 while the pathways are fossil + cement only, **land-use CO2 is held flat after the last observed
  year at its trailing 5-year mean** -- an explicit, published assumption.
- **Implied warming is incremental**: `delta_T_t = slope x (cumulative emissions since T0)`, with a band from the slope's HAC confidence interval (slope uncertainty
  only, labelled as such). A second line applies the fossil-only slope to fossil-only increments (no land-use assumption), so the effect of the definition is visible.
- The absolute level is `anchor + delta_T`, with **anchor = the trailing 5-year mean of the observed anomaly at T0**: not the single last year (which would bake in
  year-to-year noise and the unreconciled Berkeley vintage) and not the regression line (which sits below the observed anomaly, so the curve would jump at T0).

Guards (decision 39): the scenario file is produced by the notebooks, not by the monthly refresh, so it goes stale when OWID gains a year. The stage requires the first
scenario year to be T0 + 1, a complete country x year grid per scenario, and every scenario country to be present in OWID at T0; otherwise the output is explicit nulls
with the reason and a deviation, never a stale translation. The output always rewrites atomically and always carries the full metadata.
"""

from __future__ import annotations

import json
import logging
import os

import numpy as np
import pandas as pd

from .common import CLIMATE_DIR, NOTICES_PATH, ROOT, RunReport, sha256_hex, utc_now, write_json_atomic
from .correlation import METHODOLOGY, PLAIN_LANGUAGE, _vintage
from .harmonize import _LUC_LICENSE, _LUC_UNCERTAINTY
from .owid import DATA_PATH as OWID_PATH
from .pairing import CAUSATION_NOTE

SCHEMA_VERSION = 1
OUTPUT_JSON = "correlation_scenario_temperature.json"
SCENARIO_PATH = os.path.join(ROOT, "data", "scenario_projections.csv")
MT_PER_THOUSAND_GT = 1e6
LUC_FLAT_WINDOW = 5
ANCHOR_WINDOW = 5
CONTINUITY_NOTE_PCT = 2.0  # a first scenario year this far from the last observed covered-country total is called out

LABELS = ["illustrative, partial-coverage translation", "Implied temperature outcomes",
          "Dependent on the selected regression period, emissions source and model assumptions",
          "Illustrative analytical translations, not formal climate-model projections"]


class Unavailable(Exception):
    """An input problem that makes the translation meaningless: reported as explicit nulls with the reason, never a stale or partial result."""


def translate(proj: pd.DataFrame, t0: int, covered_t0: float, world_t0: float, luc_flat_mt: float, fit_headline: dict | None, fit_fossil: dict | None, anchor: float) -> dict:
    """Pure translation of the pathways in `proj` (columns: country, year, scenario, co2_projected) into cumulative and implied-temperature rows per scenario."""
    row_share = 1 - covered_t0 / world_t0
    out = {}
    for sc, g in proj.groupby("scenario", sort=True):
        covered = g.groupby("year")["co2_projected"].sum().sort_index()
        years = covered.index.to_numpy()
        glob = covered.to_numpy() / (1 - row_share)
        inc_fossil = np.cumsum(glob)  # fossil + cement only
        inc_total = np.cumsum(glob + luc_flat_mt)  # headline definition: adds land-use CO2, held flat

        def line(fit, inc):
            if fit is None:
                return None
            d = fit["slope"] * inc / MT_PER_THOUSAND_GT
            lo, hi = fit["ci95_hac"][0] * inc / MT_PER_THOUSAND_GT, fit["ci95_hac"][1] * inc / MT_PER_THOUSAND_GT
            return {"delta_t_c": d, "delta_t_ci95": (lo, hi), "level_c": anchor + d, "level_ci95": (anchor + lo, anchor + hi)}

        head, foss = line(fit_headline, inc_total), line(fit_fossil, inc_fossil)
        rows = []
        for i, y in enumerate(years):
            row = {"year": int(y), "covered_mt": float(covered.iloc[i]), "rest_of_world_mt": float(glob[i] - covered.iloc[i]), "global_fossil_mt": float(glob[i]),
                   "land_use_mt": float(luc_flat_mt), "cumulative_increment_mt": float(inc_total[i]), "fossil_only_cumulative_increment_mt": float(inc_fossil[i])}
            for key, ln in (("headline", head), ("fossil_only", foss)):
                row[key] = None if ln is None else {"delta_t_c": float(ln["delta_t_c"][i]), "delta_t_ci95": [float(ln["delta_t_ci95"][0][i]), float(ln["delta_t_ci95"][1][i])],
                                                    "level_c": float(ln["level_c"][i]), "level_ci95": [float(ln["level_ci95"][0][i]), float(ln["level_ci95"][1][i])]}
            rows.append(row)
        out[sc] = rows
    return {"rest_of_world_share": row_share, "scenarios": out}


def _round(o, nd=6):
    if isinstance(o, float):
        return round(o, nd)
    if isinstance(o, dict):
        return {k: _round(v, nd) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_round(v, nd) for v in o]
    return o


def _check_scenarios(proj: pd.DataFrame, t0: int) -> None:
    for col in ("country", "year", "scenario", "co2_projected"):
        if col not in proj.columns:
            raise Unavailable(f"scenario_projections.csv: required column missing: {col}")
    if proj["co2_projected"].isna().any() or (proj["co2_projected"] < 0).any():
        raise Unavailable("scenario_projections.csv has missing or negative projected emissions")
    if proj.duplicated(["scenario", "country", "year"]).any():
        raise Unavailable("scenario_projections.csv has duplicate scenario/country/year rows")
    first = int(proj["year"].min())
    if first != t0 + 1:
        raise Unavailable(f"scenarios are stale relative to OWID: the first scenario year is {first} but the last observed year is {t0} (expected {t0 + 1}); rerun the Week 5 notebook")
    expected_years = set(range(first, int(proj["year"].max()) + 1))
    countries = set(proj["country"])
    for sc, g in proj.groupby("scenario"):
        if set(g["year"]) != expected_years or any(set(h["year"]) != expected_years for _, h in g.groupby("country")) or set(g["country"]) != countries:
            raise Unavailable(f"scenario {sc!r} is not a complete country x year grid ({len(countries)} countries x {first}-{max(expected_years)})")


def _fit(headline_json: dict, key: str) -> dict | None:
    b = headline_json.get(key)
    return None if not b else {"slope": b["fit"]["slope"], "ci95_hac": b["fit"]["ci95_hac"], "range": b["range"], "label": b["label"], "x_indicator": b["x_indicator"]}


def build(climate_dir: str, notices_path: str, scenario_path: str, owid_path: str, report: RunReport) -> dict:
    vintage = _vintage(climate_dir, notices_path)
    caveats = [PLAIN_LANGUAGE, METHODOLOGY, _LUC_UNCERTAINTY, _LUC_LICENSE, *([vintage["caveat"]] if vintage["caveat"] else [])]
    out = {"schema_version": SCHEMA_VERSION, "generated_at": utc_now(), "name": "Scenario temperature translation", "labels": LABELS, "note": CAUSATION_NOTE,
           "temperature_source_vintage": vintage, "caveats": caveats, "scenarios": None}
    try:
        w = pd.read_csv(os.path.join(climate_dir, "owid_world_co2_annual.csv"))
        for col in ("year", "co2_mt", "total_co2_incl_luc_mt", "land_use_change_co2_mt", "cumulative_co2_mt"):
            if col not in w.columns:
                raise Unavailable(f"owid_world_co2_annual.csv: required column missing: {col}")
        w = w.set_index("year")
        t0 = int(w.index.max())
        hj = json.load(open(os.path.join(climate_dir, "correlation_headline.json")))
        fit_head, fit_foss = _fit(hj, "headline"), _fit(hj, "secondary_fossil_only")
        if fit_head is None:
            raise Unavailable("the headline regression is unavailable, so there is no slope to translate with")
        if not os.path.exists(scenario_path):
            raise Unavailable(f"{os.path.basename(scenario_path)} not found (the Week 5 notebook writes it)")
        raw = open(scenario_path, "rb").read()
        proj = pd.read_csv(scenario_path)
        _check_scenarios(proj, t0)

        names = sorted(set(proj["country"]))
        owid = pd.read_csv(owid_path, usecols=["country", "year", "co2"])
        at_t0 = owid[(owid["year"] == t0) & owid["country"].isin(names)].set_index("country")["co2"].dropna()
        missing = [n for n in names if n not in at_t0.index]
        if missing:
            raise Unavailable(f"scenario countries with no OWID CO2 value in {t0}: {', '.join(missing)}")
        covered_t0, world_t0 = float(at_t0.sum()), float(w.loc[t0, "co2_mt"])
        if not 0 < covered_t0 < world_t0:
            raise Unavailable(f"the covered countries ({covered_t0:,.0f} Mt) are not a proper part of the World total ({world_t0:,.0f} Mt) in {t0}")

        luc_flat = float(w["land_use_change_co2_mt"].loc[t0 - LUC_FLAT_WINDOW + 1:t0].mean())
        temp = pd.read_csv(os.path.join(climate_dir, "temperature_anomaly_annual.csv")).set_index("year")["anomaly_1850_1900_c"]
        window = temp.loc[t0 - ANCHOR_WINDOW + 1:t0]
        if len(window) < ANCHOR_WINDOW or not np.isfinite(luc_flat):
            raise Unavailable(f"the last {ANCHOR_WINDOW} years of the observed anomaly (or of land-use CO2) are not all available up to {t0}")
        anchor = float(window.mean())

        res = translate(proj, t0, covered_t0, world_t0, luc_flat, fit_head, fit_foss, anchor)
        first_cov = {sc: float(v) for sc, v in proj[proj["year"] == t0 + 1].groupby("scenario")["co2_projected"].sum().items()}
        jumps = {sc: (v / covered_t0 - 1) * 100 for sc, v in first_cov.items()}
        if any(abs(j) > CONTINUITY_NOTE_PCT for j in jumps.values()):
            vals = list(jumps.values())
            if max(vals) - min(vals) < 0.05:  # every scenario starts at the same level (as in the current Week 5 output)
                step = f"{vals[0]:+.1f}% from the last observed total for the covered countries ({covered_t0:,.0f} Mt in {t0} to {next(iter(first_cov.values())):,.0f} Mt in {t0 + 1})"
            else:
                step = (f"{', '.join(f'{sc} {j:+.1f}%' for sc, j in sorted(jumps.items()))} from the last observed total for the covered countries "
                        f"({covered_t0:,.0f} Mt in {t0}; {', '.join(f'{sc} {v:,.0f} Mt' for sc, v in sorted(first_cov.items()))} in {t0 + 1})")
            caveats.append(f"The scenario pathways start {step}; the translation uses the pathways as given, so each scenario carries that step.")
        out.update({
            "scenarios": _round(res["scenarios"]),
            "base": {"last_observed_year": t0, "world_co2_mt": world_t0, "covered_co2_mt": covered_t0, "covered_share_of_world": covered_t0 / world_t0,
                     "world_cumulative_total_co2_since_1850_mt": float(w.loc[1850:t0, "total_co2_incl_luc_mt"].sum()), "world_cumulative_fossil_co2_mt": float(w.loc[t0, "cumulative_co2_mt"]),
                     "first_scenario_year_covered_mt": first_cov, "first_scenario_year_vs_last_observed_pct": jumps,
                     "anchor": {"definition": f"trailing {ANCHOR_WINDOW}-year mean of the observed Berkeley Earth anomaly (1850-1900 reference), {t0 - ANCHOR_WINDOW + 1}-{t0}", "value_c": anchor,
                                "last_year_value_c": float(temp.loc[t0])}},
            "assumptions": {
                "rest_of_world": {"rule": "held at its last-observed share of the World total, so rest-of-world emissions move proportionally with the covered-country pathway; "
                                          "international aviation and shipping fall inside it", "share": res["rest_of_world_share"], "year": t0,
                                  "formula": "global_t = covered_t / (1 - share)"},
                "land_use": {"rule": f"held flat after {t0} at its trailing {LUC_FLAT_WINDOW}-year mean (the scenarios do not model it)", "mt_per_year": luc_flat,
                             "window": [t0 - LUC_FLAT_WINDOW + 1, t0]},
                "slope": {"headline": fit_head, "fossil_only": fit_foss, "unit": "°C per 1,000 GtCO2",
                          "note": "Full-range regression from correlation_headline.json; the band is the HAC 95% interval of the slope times the cumulative increment: slope uncertainty only, not scenario or climate uncertainty."},
                "method": "implied warming = slope x cumulative emissions since the last observed year; level = anchor + implied warming",
                "fossil_only_line": "applies the fossil-only slope to fossil + cement increments only (no land-use assumption), so the effect of the definition is visible"},
            "covered_countries": [{"country": n, "co2_mt_last_observed_year": float(at_t0[n])} for n in names],
            "scenario_source": {"file": os.path.basename(scenario_path), "sha256": sha256_hex(raw), "rows": int(len(proj)), "years": [int(proj["year"].min()), int(proj["year"].max())],
                                "scenarios": sorted(set(proj["scenario"]))},
            "attribution": hj.get("attribution", {})})
        if fit_foss is None:
            report.deviate("scenario_temperature: the fossil-only line is unavailable because the fossil-only regression is unavailable")
    except Exception as e:  # noqa: BLE001 -- whatever the cause: explicit nulls and a deviation, never a stale or partial translation
        if not isinstance(e, (Unavailable, OSError, ValueError, KeyError)):
            logging.exception("scenario_temperature: unexpected error")
        out["scenarios"] = None
        out["unavailable_reason"] = e.args[0] if isinstance(e, Unavailable) else f"{type(e).__name__}: {e}"
        report.deviate(f"scenario temperature translation unavailable: {out['unavailable_reason']}")
    return out


def run(climate_dir: str = CLIMATE_DIR, out_dir: str | None = None, notices_path: str = NOTICES_PATH, scenario_path: str = SCENARIO_PATH, owid_path: str = OWID_PATH) -> RunReport:
    out_dir = out_dir or climate_dir
    report = RunReport("scenario_temperature")
    out = build(climate_dir, notices_path, scenario_path, owid_path, report)
    write_json_atomic(out, os.path.join(out_dir, OUTPUT_JSON))
    report.count("correlation_scenario_temperature", sum(len(v) for v in out["scenarios"].values()) if out["scenarios"] else 0)
    if out["scenarios"]:
        end = {sc: rows[-1] for sc, rows in out["scenarios"].items()}
        report.note(f"scenario translation to {next(iter(end.values()))['year']} (anchor {out['base']['anchor']['value_c']:.2f} °C, rest-of-world share {out['assumptions']['rest_of_world']['share']:.1%}): "
                    + ", ".join(f"{sc} {r['headline']['level_c']:.2f} °C (+{r['headline']['delta_t_c']:.2f})" for sc, r in end.items()))
    return report
