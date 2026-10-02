"""The first-year step check: how far a projected pathway starts from the last observed total. `ENHANCEMENTS.md` Backlog B2.

A pathway that begins far from where the observations end carries a discontinuity at its start. This module applies the owner's thresholds -- **+/-2% for the
aggregate** and **+/-5% per country** -- to a set of first projected-year values against the last observed values, and says what to alert on.

- The aggregate step includes one year of normal growth (about 1% a year for the 40 covered countries), so a correctly anchored path still starts a little above the last
  observation; 2% leaves room for that, and a stale fit does not fit inside it (the Week 4 fit, stuck at 2018, starts +3.7% above 2024).
- Per country, a few idiosyncratic outliers are expected in a 40-country set (one data anomaly, one shock), so a breach by a few countries is **reported** (with the
  country and its step) but is a deviation only when it is **systematic**: more than `MAX_FLAGGED_SHARE` of the countries (10%) outside the threshold. A stale fit puts
  31 of 40 outside +/-5%; a current fit puts 3. The 10% share is a judgement call, stated here and in the output.
"""

from __future__ import annotations

import math
import statistics

AGGREGATE_TOL_PCT = 2.0
COUNTRY_TOL_PCT = 5.0
MAX_FLAGGED_SHARE = 0.10


def check_step(predicted: dict[str, float], observed: dict[str, float], aggregate_tol: float = AGGREGATE_TOL_PCT, country_tol: float = COUNTRY_TOL_PCT,
               max_flagged_share: float = MAX_FLAGGED_SHARE) -> dict:
    """Compare the first projected year with the last observed year, per country and in total. Raises ValueError if the country sets differ or a value is unusable."""
    if set(predicted) != set(observed):
        only_p, only_o = sorted(set(predicted) - set(observed)), sorted(set(observed) - set(predicted))
        raise ValueError(f"the projected and observed country sets differ (only projected: {only_p}; only observed: {only_o})")
    if not predicted:
        raise ValueError("no countries to check")
    for label, d in (("projected", predicted), ("observed", observed)):
        bad = sorted(c for c, v in d.items() if not isinstance(v, (int, float)) or not math.isfinite(v))
        if bad:
            raise ValueError(f"non-finite {label} value(s) for: {', '.join(bad)}")
    nonpos = sorted(c for c, v in observed.items() if v <= 0)
    if nonpos:
        raise ValueError(f"the observed total is not positive for: {', '.join(nonpos)}, so a relative step is undefined")
    countries = sorted(predicted)
    steps = {c: (predicted[c] / observed[c] - 1) * 100 for c in countries}
    aggregate = (sum(predicted.values()) / sum(observed.values()) - 1) * 100
    flagged = sorted(({"country": c, "step_pct": s} for c, s in steps.items() if round(abs(s), 9) > country_tol), key=lambda r: r["step_pct"])
    share = len(flagged) / len(countries)
    return {
        "aggregate_step_pct": aggregate, "aggregate_tolerance_pct": aggregate_tol, "aggregate_breach": round(abs(aggregate), 9) > aggregate_tol,
        "country_tolerance_pct": country_tol, "n_countries": len(countries), "country_steps_pct": steps,
        "n_within_2pct": sum(round(abs(s), 9) <= 2.0 for s in steps.values()), "n_within_country_tolerance": len(countries) - len(flagged),
        "flagged_countries": flagged, "flagged_share": share, "max_flagged_share": max_flagged_share, "systematic_breach": share > max_flagged_share,
        "median_step_pct": statistics.median(steps.values()),
        "rule": (f"aggregate step within +/-{aggregate_tol:g}%; per-country steps reported when outside +/-{country_tol:g}% and a deviation only when more than "
                 f"{max_flagged_share:.0%} of countries are outside"),
    }


def step_messages(result: dict, label: str) -> tuple[list[str], list[str]]:
    """(deviations, notes) for a `check_step` result. Deviations: an aggregate breach, or a systematic per-country breach. Notes: a non-systematic per-country breach."""
    deviations, notes = [], []
    if result["aggregate_breach"]:
        deviations.append(f"{label}: the aggregate first-year step is {result['aggregate_step_pct']:+.1f}% from the last observed total (tolerance ±{result['aggregate_tolerance_pct']:g}%)")
    f = result["flagged_countries"]
    if f:
        shown = ", ".join(f"{r['country']} {r['step_pct']:+.1f}%" for r in f[:6]) + (f" and {len(f) - 6} more" if len(f) > 6 else "")
        text = f"{label}: {len(f)} of {result['n_countries']} countries start outside ±{result['country_tolerance_pct']:g}% of their last observed value ({shown})"
        (deviations if result["systematic_breach"] else notes).append(text + ("; more than the systematic threshold" if result["systematic_breach"] else ""))
    return deviations, notes
