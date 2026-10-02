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
from .step_check import AGGREGATE_TOL_PCT, check_step, step_messages

SCHEMA_VERSION = 1
OUTPUT_JSON = "correlation_scenario_temperature.json"
SCENARIO_PATH = os.path.join(ROOT, "data", "scenario_projections.csv")
MT_PER_THOUSAND_GT = 1e6
LUC_FLAT_WINDOW = 5
ANCHOR_WINDOW = 5
READING_NOTE_MIN_RATIO = 1.25  # the note explains a small temperature gap despite large emissions divergence: it is only true (and only generated) above this ratio
BASELINE_CSV = "ets_baseline_full_data.csv"
BASELINE_JSON = "ets_baseline_full_data.json"
BASELINE_TOL_MT = 0.01  # both files round to 3 decimals, so the same fit on the same data agrees to well within this per country-year

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


def _spread(scenarios: dict, t0: int, anchor: float, n_years_observed: int) -> tuple[dict, str | None]:
    """Per-year spread across scenarios (max - min of annual global emissions and of the implied headline level) and, when the premise holds, the generated reading note
    (decision 43). Every figure in the note comes from `scenarios`, so the UI, the agent and the docs quote identical numbers."""
    names = sorted(scenarios)
    years = [r["year"] for r in scenarios[names[0]]]
    per_year = []
    for i, y in enumerate(years):
        em = {sc: scenarios[sc][i]["global_fossil_mt"] for sc in names}
        row = {"year": y, "emissions_max_mt": max(em.values()), "emissions_min_mt": min(em.values()), "emissions_ratio": max(em.values()) / min(em.values())}
        lv = {sc: scenarios[sc][i]["headline"]["level_c"] for sc in names if scenarios[sc][i]["headline"] is not None}
        row["level_gap_c"] = (max(lv.values()) - min(lv.values())) if len(lv) == len(names) else None
        per_year.append(row)
    last = scenarios[names[0]][-1]["year"]
    out = {"per_year": per_year, "min_ratio_for_reading_note": READING_NOTE_MIN_RATIO, "reading_note_omitted_reason": None}
    em_last = {sc: scenarios[sc][-1]["global_fossil_mt"] for sc in names}
    hi, lo = max(em_last, key=em_last.get), min(em_last, key=em_last.get)
    ratio = em_last[hi] / em_last[lo]
    if any(scenarios[sc][-1]["headline"] is None for sc in names):
        out["reading_note_omitted_reason"] = "the headline regression is unavailable, so there is no temperature to compare"
        return out, None
    if ratio < READING_NOTE_MIN_RATIO:
        out["reading_note_omitted_reason"] = f"the scenarios' {last} emissions differ by {ratio:.2f}x, below the {READING_NOTE_MIN_RATIO}x at which the note's premise (large emissions divergence, small temperature gap) holds"
        return out, None
    inc = {sc: scenarios[sc][-1]["headline"]["delta_t_c"] for sc in names}
    if inc[hi] <= 0 or len(years) < 2:
        out["reading_note_omitted_reason"] = "the highest scenario adds no warming, or there are fewer than two scenario years: the relative comparison is undefined"
        return out, None
    lvl = {sc: scenarios[sc][-1]["headline"]["level_c"] for sc in names}
    pcts = [anchor / v * 100 for v in lvl.values()]
    gap_end = per_year[-1]["level_gap_c"]
    mid = per_year[len(per_year) // 2 - 1 if len(per_year) > 2 else 0]
    less = (1 - inc[lo] / inc[hi]) * 100
    out["reading_note_facts"] = {"year": last, "highest": hi, "lowest": lo, "emissions_ratio": ratio, "already_observed_pct_range": [min(pcts), max(pcts)],
                                 "additional_warming_highest_c": inc[hi], "lowest_adds_less_pct": less, "gap_mid_year": mid["year"], "gap_mid_c": mid["level_gap_c"], "gap_end_c": gap_end}
    note = (f"Scenarios diverge sharply in annual emissions by {last} ({hi} {em_last[hi]:,.0f} vs {lo} {em_last[lo]:,.0f} Mt a year, {ratio:.1f}×), but the implied temperatures differ by only "
            f"{gap_end:.2f} °C. {years[0]}–{last} is a short window against the {n_years_observed} years of emissions already accumulated, and {min(pcts):.0f}–{max(pcts):.0f}% of the {last} implied level "
            f"({anchor:.2f} °C) is warming already observed by {t0}, before any scenario begins. What the scenarios change is only the emissions still to come: relative to the {inc[hi]:.2f} °C of additional "
            f"warming, the {lo} pathway adds {less:.0f}% less than {hi}. The gap widens every year the pathways stay apart ({mid['level_gap_c']:.3f} °C in {mid['year']}, {gap_end:.3f} °C in {last}).")
    return out, note


def _round(o, nd=6):
    if isinstance(o, float):
        return round(o, nd)
    if isinstance(o, dict):
        return {k: _round(v, nd) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_round(v, nd) for v in o]
    return o


def _finite(x) -> bool:
    return isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, bool) and bool(np.isfinite(x))


def _require_finite(o, where: str = "output") -> None:
    """A last line of defence: no NaN or infinity may reach the JSON file (they are written as non-standard `NaN`/`Infinity` that strict clients cannot parse)."""
    if isinstance(o, float):
        if not np.isfinite(o):
            raise Unavailable(f"a non-finite number ({o}) in the translation {where}; check the inputs")
    elif isinstance(o, dict):
        for k, v in o.items():
            _require_finite(v, f"{where}.{k}")
    elif isinstance(o, (list, tuple)):
        for i, v in enumerate(o):
            _require_finite(v, f"{where}[{i}]")


def _scrub_non_finite(o, path: str = "output") -> tuple[object, list[str]]:
    """A copy of `o` with every non-finite float replaced by None, and the paths that were replaced. Used on the failure path: metadata is recorded as soon as it is read, so a
    rejected non-finite value must not survive in an unavailable output (`NaN`/`Infinity` are not valid JSON)."""
    if isinstance(o, float):
        return (o, []) if np.isfinite(o) else (None, [path])
    if isinstance(o, dict):
        bad, out = [], {}
        for k, v in o.items():
            out[k], b = _scrub_non_finite(v, f"{path}.{k}")
            bad += b
        return out, bad
    if isinstance(o, (list, tuple)):
        bad, out = [], []
        for i, v in enumerate(o):
            c, b = _scrub_non_finite(v, f"{path}[{i}]")
            out.append(c)
            bad += b
        return out, bad
    return o, []


def _check_scenarios(proj: pd.DataFrame, t0: int) -> pd.DataFrame:
    """Validate the scenario file and return it with numeric, finite, non-negative projected emissions."""
    for col in ("country", "year", "scenario", "co2_projected"):
        if col not in proj.columns:
            raise Unavailable(f"scenario_projections.csv: required column missing: {col}")
    values = pd.to_numeric(proj["co2_projected"], errors="coerce")
    years = pd.to_numeric(proj["year"], errors="coerce")
    if not np.isfinite(values.to_numpy(dtype=float)).all() or (values < 0).any():
        raise Unavailable("scenario_projections.csv has missing, non-numeric, non-finite or negative projected emissions")
    if not np.isfinite(years.to_numpy(dtype=float)).all() or (years % 1 != 0).any():
        raise Unavailable("scenario_projections.csv has a missing or non-integer year")
    proj = pd.DataFrame({"country": proj["country"].to_numpy(), "year": years.to_numpy().astype(int), "scenario": proj["scenario"].to_numpy(), "co2_projected": values.to_numpy(dtype=float)})
    if proj.duplicated(["scenario", "country", "year"]).any():
        raise Unavailable("scenario_projections.csv has duplicate scenario/country/year rows")
    first = int(proj["year"].min())
    if first != t0 + 1:
        raise Unavailable(f"scenarios are stale relative to OWID: the first scenario year is {first} but the last observed year is {t0} (expected {t0 + 1}); rerun the Week 5 notebook")
    expected_years = set(range(first, int(proj["year"].max()) + 1))
    scenarios = set(proj["scenario"])
    if scenarios != {"BAU", "Moderate", "Aggressive"}:
        raise Unavailable(f"scenario_projections.csv must contain exactly BAU, Moderate and Aggressive; found {sorted(map(str, scenarios))}")
    countries = set(proj["country"])
    for sc, g in proj.groupby("scenario"):
        if set(g["year"]) != expected_years or any(set(h["year"]) != expected_years for _, h in g.groupby("country")) or set(g["country"]) != countries:
            raise Unavailable(f"scenario {sc!r} is not a complete country x year grid ({len(countries)} countries x {first}-{max(expected_years)})")
    return proj


def _fit(headline_json: dict, key: str) -> dict | None:
    b = headline_json.get(key)
    if not b:
        return None
    f = {"slope": b["fit"]["slope"], "ci95_hac": b["fit"]["ci95_hac"], "range": b["range"], "label": b["label"], "x_indicator": b["x_indicator"]}
    if not (_finite(f["slope"]) and len(f["ci95_hac"]) == 2 and all(_finite(v) for v in f["ci95_hac"])):
        raise Unavailable(f"the {key} regression statistics in correlation_headline.json are not finite numbers")
    return f


def _step_checks(proj: pd.DataFrame, at_t0: pd.Series, t0: int) -> dict:
    """The shared first-year step check (pipeline/step_check.py, Backlog B2) applied to each scenario's first projected year against the last observed value, per country."""
    observed = {c: float(v) for c, v in at_t0.items()}
    first = proj[proj["year"] == t0 + 1]
    out = {}
    for sc, g in first.groupby("scenario"):
        try:
            out[sc] = check_step(g.groupby("country")["co2_projected"].sum().to_dict(), observed)
        except ValueError as e:
            raise Unavailable(f"the first-year step check cannot be computed for scenario {sc}: {e}") from e
    return out


def _report_steps(steps: dict, t0: int, report: RunReport) -> None:
    """Deviations and notes from the step checks. Scenarios that start identically (the Week 5 notebook starts all three from the BAU first year) are reported once."""
    groups: list[tuple[list[str], dict]] = []
    for sc in sorted(steps):
        for names, res in groups:
            if res["country_steps_pct"].keys() == steps[sc]["country_steps_pct"].keys() and all(abs(res["country_steps_pct"][c] - steps[sc]["country_steps_pct"][c]) < 1e-9 for c in res["country_steps_pct"]):
                names.append(sc)
                break
        else:
            groups.append(([sc], steps[sc]))
    for names, res in groups:
        label = f"scenario pathways ({', '.join(names)}), first year {t0 + 1}"
        dev, notes = step_messages(res, label)
        for d in dev:
            report.deviate(d)
        for n in notes:
            report.note(n)


def _baseline_consistency(climate_dir: str, proj: pd.DataFrame, t0: int) -> dict:
    """Is the scenario file's BAU the current baseline (the pipeline's ets_baseline_full_data.csv)? 'current', 'stale' (generated from an older fit) or 'unavailable'."""
    path, meta_path = os.path.join(climate_dir, BASELINE_CSV), os.path.join(climate_dir, BASELINE_JSON)
    if not os.path.exists(path):
        return {"status": "unavailable", "reason": f"{BASELINE_CSV} not found: the ets_baseline stage has not run"}
    if os.path.exists(meta_path):
        meta = json.load(open(meta_path))
        if isinstance(meta, dict) and meta.get("unavailable_reason"):
            return {"status": "unavailable", "reason": f"the current baseline is unavailable: {meta['unavailable_reason']}"}
    base = pd.read_csv(path)
    if base.empty or not {"country", "year", "mean"} <= set(base.columns):
        return {"status": "unavailable", "reason": f"{BASELINE_CSV} is empty or lacks country/year/mean columns"}
    bau = proj[proj["scenario"] == "BAU"][["country", "year", "co2_projected"]]
    merged = bau.merge(base[["country", "year", "mean"]], on=["country", "year"], how="left")
    missing = merged[merged["mean"].isna()]
    if len(missing):
        return {"status": "unavailable", "reason": f"the current baseline has no value for {len(missing)} of the scenario file's BAU country-years (e.g. {missing.iloc[0]['country']} {int(missing.iloc[0]['year'])})"}
    diff = (merged["co2_projected"] - merged["mean"]).abs()
    first, last = t0 + 1, int(merged["year"].max())
    tot = lambda col, y: float(merged.loc[merged["year"] == y, col].sum())  # noqa: E731
    out = {"status": "current" if float(diff.max()) <= BASELINE_TOL_MT else "stale", "max_abs_difference_mt": float(diff.max()), "tolerance_mt": BASELINE_TOL_MT,
           "n_country_years_compared": int(len(merged)), "file": BASELINE_CSV,
           "aggregate": {str(y): {"scenario_bau_mt": tot("co2_projected", y), "current_baseline_mt": tot("mean", y),
                                  "difference_pct": (tot("co2_projected", y) / tot("mean", y) - 1) * 100} for y in (first, last)}}
    return out


INPUT_FILES = ("owid_world_co2_annual.csv", "correlation_headline.json", "scenario_projections.csv", "owid-co2-data.csv", "temperature_anomaly_annual.csv")


def _skeleton(vintage: dict, caveats: list[str]) -> dict:
    """The complete output schema. Everything that does not depend on the data is filled in now; each input's metadata is added as soon as it is read, so an
    unavailable result still carries the method, the assumptions, the attribution, the scenario file's checksum (when it was readable) and what was available."""
    return {
        "schema_version": SCHEMA_VERSION, "generated_at": utc_now(), "name": "Scenario temperature translation", "labels": LABELS, "note": CAUSATION_NOTE,
        "method": "implied warming = slope x cumulative emissions since the last observed year; level = anchor + implied warming",
        "temperature_source_vintage": vintage, "caveats": caveats, "scenarios": None, "base": None, "covered_countries": None, "scenario_source": None, "spread": None, "reading_note": None,
        "inputs": {f: {"available": False} for f in INPUT_FILES}, "attribution": {},
        "assumptions": {
            "rest_of_world": {"rule": "held at its last-observed share of the World total, so rest-of-world emissions move proportionally with the covered-country pathway; "
                                      "international aviation and shipping fall inside it", "share": None, "year": None, "formula": "global_t = covered_t / (1 - share)"},
            "land_use": {"rule": f"held flat after the last observed year at its trailing {LUC_FLAT_WINDOW}-year mean (the scenarios do not model it)", "mt_per_year": None, "window": None},
            "slope": {"headline": None, "fossil_only": None, "unit": "°C per 1,000 GtCO2",
                      "note": "Full-range regression from correlation_headline.json; the band is the HAC 95% interval of the slope times the cumulative increment: slope uncertainty only, not scenario or climate uncertainty."},
            "fossil_only_line": "applies the fossil-only slope to fossil + cement increments only (no land-use assumption), so the effect of the definition is visible"}}


def build(climate_dir: str, notices_path: str, scenario_path: str, owid_path: str, report: RunReport) -> dict:
    metadata_errors = []
    try:
        vintage = _vintage(climate_dir, notices_path)
    except Exception as e:  # noqa: BLE001 -- malformed provenance/notices must not stop the explicit-null output from being written
        logging.exception("scenario_temperature: unable to load the temperature vintage metadata")
        metadata_errors.append(f"temperature vintage metadata: {type(e).__name__}: {e}")
        vintage = {"file_last_modified": None, "reconciled": False, "caveat": f"Berkeley Earth vintage metadata could not be read: {type(e).__name__}: {e}"}
    caveats = [PLAIN_LANGUAGE, METHODOLOGY, _LUC_UNCERTAINTY, _LUC_LICENSE, *([vintage["caveat"]] if vintage["caveat"] else [])]
    out = _skeleton(vintage, caveats)
    try:
        if metadata_errors:
            raise Unavailable(f"scenario metadata unavailable: {'; '.join(metadata_errors)}")
        w = pd.read_csv(os.path.join(climate_dir, "owid_world_co2_annual.csv"))
        for col in ("year", "co2_mt", "total_co2_incl_luc_mt", "land_use_change_co2_mt", "cumulative_co2_mt"):
            if col not in w.columns:
                raise Unavailable(f"owid_world_co2_annual.csv: required column missing: {col}")
        w = w.set_index("year")
        t0 = int(w.index.max())
        out["inputs"]["owid_world_co2_annual.csv"] = {"available": True, "last_observed_year": t0}
        hj = json.load(open(os.path.join(climate_dir, "correlation_headline.json")))
        out["attribution"] = hj.get("attribution", {}) if isinstance(hj, dict) else {}
        fit_head, fit_foss = _fit(hj, "headline"), _fit(hj, "secondary_fossil_only")
        out["inputs"]["correlation_headline.json"] = {"available": True, "headline_regression": fit_head is not None, "fossil_only_regression": fit_foss is not None}
        out["assumptions"]["slope"].update({"headline": fit_head, "fossil_only": fit_foss})
        if fit_head is None:
            raise Unavailable("the headline regression is unavailable, so there is no slope to translate with")
        if not os.path.exists(scenario_path):
            raise Unavailable(f"{os.path.basename(scenario_path)} not found (the Week 5 notebook writes it)")
        raw = open(scenario_path, "rb").read()
        out["scenario_source"] = {"file": os.path.basename(scenario_path), "sha256": sha256_hex(raw)}  # known as soon as the bytes are readable
        proj_raw = pd.read_csv(scenario_path)
        out["inputs"]["scenario_projections.csv"] = {"available": True, "rows": int(len(proj_raw))}
        proj = _check_scenarios(proj_raw, t0)
        out["scenario_source"].update({"rows": int(len(proj)), "years": [int(proj["year"].min()), int(proj["year"].max())], "scenarios": sorted(set(proj["scenario"]))})

        names = sorted(set(proj["country"]))
        owid = pd.read_csv(owid_path, usecols=["country", "year", "co2"])
        out["inputs"]["owid-co2-data.csv"] = {"available": True}
        at_t0 = owid[(owid["year"] == t0) & owid["country"].isin(names)].set_index("country")["co2"].dropna()
        missing = [n for n in names if n not in at_t0.index]
        if missing:
            raise Unavailable(f"scenario countries with no OWID CO2 value in {t0}: {', '.join(missing)}")
        if not np.isfinite(at_t0.to_numpy(dtype=float)).all():
            raise Unavailable(f"a scenario country has a non-finite OWID CO2 value in {t0}")
        covered_t0, world_t0 = float(at_t0.sum()), float(w.loc[t0, "co2_mt"])
        if not (np.isfinite(covered_t0) and np.isfinite(world_t0) and 0 < covered_t0 < world_t0):
            raise Unavailable(f"the covered countries ({covered_t0:,.0f} Mt) are not a proper part of the World total ({world_t0:,.0f} Mt) in {t0}")

        luc_window = w["land_use_change_co2_mt"].loc[t0 - LUC_FLAT_WINDOW + 1:t0]
        luc_flat = float(luc_window.mean(skipna=False)) if len(luc_window) == LUC_FLAT_WINDOW else float("nan")
        temp = pd.read_csv(os.path.join(climate_dir, "temperature_anomaly_annual.csv")).set_index("year")["anomaly_1850_1900_c"]
        out["inputs"]["temperature_anomaly_annual.csv"] = {"available": True}
        window = temp.loc[t0 - ANCHOR_WINDOW + 1:t0]
        if len(window) < ANCHOR_WINDOW or not np.isfinite(window.to_numpy(dtype=float)).all() or not np.isfinite(luc_flat):
            raise Unavailable(f"the last {ANCHOR_WINDOW} years of the observed anomaly (or of land-use CO2) are not all available up to {t0}")
        anchor = float(window.mean())

        res = translate(proj, t0, covered_t0, world_t0, luc_flat, fit_head, fit_foss, anchor)
        first_cov = {sc: float(v) for sc, v in proj[proj["year"] == t0 + 1].groupby("scenario")["co2_projected"].sum().items()}
        steps = _step_checks(proj, at_t0, t0)
        jumps = {sc: steps[sc]["aggregate_step_pct"] for sc in first_cov}  # the same number as (first_cov / covered_t0 - 1): the covered set is the checked set
        _report_steps(steps, t0, report)
        pathway_baseline = _baseline_consistency(climate_dir, proj, t0)
        if pathway_baseline["status"] == "stale":
            a = pathway_baseline["aggregate"]
            first_y, last_y = str(t0 + 1), str(max(int(k) for k in a))
            report.deviate(f"scenario pathways' BAU is not the current baseline: it differs from {BASELINE_CSV} by up to {pathway_baseline['max_abs_difference_mt']:,.1f} Mt per country-year "
                           f"(aggregate {first_y}: {a[first_y]['difference_pct']:+.1f}%, {last_y}: {a[last_y]['difference_pct']:+.1f}%): the scenario file was generated from an older fit; rerun the Week 5 notebook (Backlog B2)")
            caveats.append(f"The BAU in these scenario pathways comes from an older ETS fit than the current baseline ({BASELINE_CSV}): the aggregate differs by {a[first_y]['difference_pct']:+.1f}% in {first_y} and "
                           f"{a[last_y]['difference_pct']:+.1f}% in {last_y}. The translation uses the pathways as given.")
        elif pathway_baseline["status"] == "unavailable":
            report.note(f"scenario pathways were not compared with the current baseline: {pathway_baseline['reason']}")
        if any(abs(j) > AGGREGATE_TOL_PCT for j in jumps.values()):
            vals = list(jumps.values())
            if max(vals) - min(vals) < 0.05:  # every scenario starts at the same level (as in the current Week 5 output)
                step = f"{vals[0]:+.1f}% from the last observed total for the covered countries ({covered_t0:,.0f} Mt in {t0} to {next(iter(first_cov.values())):,.0f} Mt in {t0 + 1})"
            else:
                step = (f"{', '.join(f'{sc} {j:+.1f}%' for sc, j in sorted(jumps.items()))} from the last observed total for the covered countries "
                        f"({covered_t0:,.0f} Mt in {t0}; {', '.join(f'{sc} {v:,.0f} Mt' for sc, v in sorted(first_cov.items()))} in {t0 + 1})")
            caveats.append(f"The scenario pathways start {step}; the translation uses the pathways as given, so each scenario carries that step.")
        _require_finite(res["scenarios"], "scenarios")  # before anything is derived from it
        spread, reading_note = _spread(res["scenarios"], t0, anchor, t0 - 1850 + 1)
        filled = {
            "spread": _round(spread), "reading_note": reading_note,
            "scenarios": _round(res["scenarios"]),
            "base": {"last_observed_year": t0, "world_co2_mt": world_t0, "covered_co2_mt": covered_t0, "covered_share_of_world": covered_t0 / world_t0,
                     "world_cumulative_total_co2_since_1850_mt": float(w.loc[1850:t0, "total_co2_incl_luc_mt"].sum(skipna=False)), "world_cumulative_fossil_co2_mt": float(w.loc[t0, "cumulative_co2_mt"]),
                     "first_scenario_year_covered_mt": first_cov, "first_scenario_year_vs_last_observed_pct": jumps,
                     "step_check": steps, "pathway_baseline": pathway_baseline,
                     "anchor": {"definition": f"trailing {ANCHOR_WINDOW}-year mean of the observed Berkeley Earth anomaly (1850-1900 reference), {t0 - ANCHOR_WINDOW + 1}-{t0}", "value_c": anchor,
                                "last_year_value_c": float(temp.loc[t0])}},
            "covered_countries": [{"country": n, "co2_mt_last_observed_year": float(at_t0[n])} for n in names]}
        rest = {"share": res["rest_of_world_share"], "year": t0}
        luc = {"mt_per_year": luc_flat, "window": [t0 - LUC_FLAT_WINDOW + 1, t0]}
        _require_finite({"attribution": out["attribution"], "slope": out["assumptions"]["slope"], **filled, "rest_of_world": rest, "land_use": luc})  # nothing non-finite may reach the file
        out.update(filled)
        out["assumptions"]["rest_of_world"].update(rest)
        out["assumptions"]["land_use"].update(luc)
        if fit_foss is None:
            report.deviate("scenario_temperature: the fossil-only line is unavailable because the fossil-only regression is unavailable")
    except Exception as e:  # noqa: BLE001 -- whatever the cause: explicit nulls and a deviation, never a stale or partial translation
        if not isinstance(e, (Unavailable, OSError, ValueError, KeyError)):
            logging.exception("scenario_temperature: unexpected error")
        out["scenarios"], out["base"], out["covered_countries"], out["spread"], out["reading_note"] = None, None, None, None, None  # a failure after partial work must leave no partial translation behind
        out["unavailable_reason"] = e.args[0] if isinstance(e, Unavailable) else f"{type(e).__name__}: {e}"
        out, scrubbed = _scrub_non_finite(out)  # the metadata read before the failure may itself hold the non-finite value that caused it
        if scrubbed:
            out["unavailable_reason"] += f" (non-finite value(s) removed from the metadata: {', '.join(scrubbed)})"
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
