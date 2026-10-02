"""Correlation-ready pairing of harmonized indicators. Release 21, Phase 1.2b (`ENHANCEMENTS.md` decision 29).

`load_harmonized()` reads what the harmonize stage wrote; `align_pair()` turns two indicators into one aligned
frame plus the metadata a chart, an API response or the agent needs to describe it honestly. Phase 1.3 builds
the co-trend, regression and composition outputs on this.

Rules (all enforced, all tested):
- **Same scope only.** A global indicator is never paired with a country one; two country indicators pair only
  within one named area (`geography`). Country emissions are never paired with the global temperature line
  (requirements §1.3.4: no per-country regression against a global series).
- **Only analytical series.** `uncertainty` indicators describe a series, they are not one, so they are refused.
- **Every omitted year is listed with its reason** -- nothing disappears silently: within the requested range,
  a year where `a`, `b` or both have no value is reported as `a missing` / `b missing` / `both missing`.
- **Enough overlap or no answer.** Fewer than `min_overlap` shared years raises: a correlation over a handful
  of years would look authoritative and mean nothing.
- **Provenance travels with the pair**: both indicators' catalog entries (unit, kind, coverage, and the source
  series' release / licence / checksums) are in the metadata, and so is the standing caveat that co-movement is
  interpretive context, not proof of causation.
- No interpolation: only years where both series have a value are used.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

import pandas as pd

from .common import CLIMATE_DIR

CAUSATION_NOTE = (
    "Paired series are shown for interpretive context. Co-movement over time is not proof of causation: climate outcomes "
    "depend on several physical processes, including accumulated forcing and the response of the oceans, not only "
    "contemporaneous emissions. This is a descriptive analysis, not a climate model."
)
DEFAULT_MIN_OVERLAP = 20
SUPPORTED_SCHEMA = 1
NOT_PAIRABLE_KINDS = ("uncertainty",)


@dataclass
class Harmonized:
    """The harmonized tables, loaded."""

    catalog: dict[str, dict]
    global_long: pd.DataFrame
    country_long: pd.DataFrame
    meta: dict = field(default_factory=dict)

    def entry(self, indicator_id: str) -> dict:
        if indicator_id not in self.catalog:
            raise ValueError(f"unknown indicator {indicator_id!r}")
        return self.catalog[indicator_id]

    def series(self, indicator_id: str, geography: str | None = None) -> pd.Series:
        """The indicator as a Series indexed by integer year (absent years are simply not in the index)."""
        e = self.entry(indicator_id)
        if e["scope"] == "global":
            if geography is not None:
                raise ValueError(f"{indicator_id} is a global indicator; it takes no geography (got {geography!r})")
            d = self.global_long[self.global_long["indicator_id"] == indicator_id]
        else:
            if not geography:
                raise ValueError(f"{indicator_id} is a country indicator; geography (an ISO3 code) is required")
            d = self.country_long[(self.country_long["indicator_id"] == indicator_id) & (self.country_long["iso3"] == geography)]
            if d.empty:
                raise ValueError(f"{indicator_id} has no values for area {geography!r}")
        return d.set_index("year")["value"].astype(float).sort_index()


def load_harmonized(climate_dir: str = CLIMATE_DIR) -> Harmonized:
    path = os.path.join(climate_dir, "indicator_catalog.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found: run `python -m pipeline.run --source harmonize` first")
    doc = json.load(open(path))
    if doc.get("schema_version") != SUPPORTED_SCHEMA:
        raise ValueError(f"indicator_catalog.json has schema_version {doc.get('schema_version')!r}; this code reads {SUPPORTED_SCHEMA}")
    return Harmonized(
        catalog={e["id"]: e for e in doc["indicators"]},
        global_long=pd.read_csv(os.path.join(climate_dir, "harmonized_global_annual.csv")),
        country_long=pd.read_csv(os.path.join(climate_dir, "harmonized_country_annual.csv")),
        meta={k: doc[k] for k in ("baselines", "trailing_window_years", "generated_at") if k in doc},
    )


def _describe(entry: dict, s_in_range: pd.Series) -> dict:
    return {
        "id": entry["id"], "name": entry["name"], "unit": entry["unit"], "kind": entry["kind"], "scope": entry["scope"],
        "coverage": entry.get("coverage"), "n_values_in_range": int(s_in_range.notna().sum()),
        "provenance": json.loads(json.dumps(entry.get("provenance"))), "caveats": list(entry.get("caveats", [])),
    }


def align_pair(h: Harmonized, a: str, b: str, start: int | None = None, end: int | None = None,
               min_overlap: int = DEFAULT_MIN_OVERLAP, geography: str | None = None) -> tuple[pd.DataFrame, dict]:
    """Align indicators `a` and `b` on calendar years. Returns (frame with columns `year`, `a`, `b` -- named by indicator id --
    holding only years where both have a value, metadata)."""
    if a == b:
        raise ValueError("cannot pair an indicator with itself")
    ea, eb = h.entry(a), h.entry(b)
    if ea["scope"] != eb["scope"]:
        raise ValueError(f"cannot pair across scopes: {a} is {ea['scope']}-scope and {b} is {eb['scope']}-scope")
    for e in (ea, eb):
        if e["kind"] in NOT_PAIRABLE_KINDS:
            raise ValueError(f"{e['id']} is an {e['kind']} series (it describes another series); it is not pairable")
    sa, sb = h.series(a, geography), h.series(b, geography)

    cov_a, cov_b = (int(sa.index.min()), int(sa.index.max())), (int(sb.index.min()), int(sb.index.max()))
    common = (max(cov_a[0], cov_b[0]), min(cov_a[1], cov_b[1]))
    lo = start if start is not None else common[0]
    hi = end if end is not None else common[1]
    if lo > hi:
        raise ValueError(f"empty range: start {lo} is after end {hi}" + (" (the two series do not overlap)" if start is None and end is None else ""))

    years = range(int(lo), int(hi) + 1)
    in_a, in_b = sa.reindex(years), sb.reindex(years)
    both = in_a.notna() & in_b.notna()
    omitted = []
    for y in years:
        ma, mb = pd.isna(in_a[y]), pd.isna(in_b[y])
        if ma or mb:
            omitted.append({"year": int(y), "reason": "both missing" if ma and mb else f"{'a' if ma else 'b'} missing"})
    n_used = int(both.sum())
    if n_used < min_overlap:
        raise ValueError(f"only {n_used} shared year(s) for {a} and {b} in {lo}-{hi}; at least {min_overlap} are required for a pairing to mean anything")

    frame = pd.DataFrame({"year": [int(y) for y in years if both[y]], a: in_a[both].to_numpy(), b: in_b[both].to_numpy()})
    used = (int(frame["year"].min()), int(frame["year"].max()))
    meta = {
        "a": _describe(ea, in_a), "b": _describe(eb, in_b), "geography": geography,
        "range_requested": [start, end], "range_used": list(used), "common_range": list(common), "n_years_used": n_used,
        "omitted_years": omitted, "n_omitted_years": len(omitted), "min_overlap": min_overlap,
        "interpolated": False, "note": CAUSATION_NOTE,
    }
    return frame, meta
