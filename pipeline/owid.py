"""OWID CO2 data: verify and register the file the refresh job downloaded, and publish the World
annual CO2 series. Release 21, Phase 1.1c.

OWID (Our World in Data, from the Global Carbon Project) stays the primary source for the
country-level CO2 modules and the headline TCRE-style regression (`SPEC.md` §5.26). This step
**does not download**: the weekly/monthly refresh job (`~/bin/ghg-data-refresh.sh` on the Mac Mini)
already backs up, downloads and validates the file, and restores the backup on failure -- the
validation authority is the week-1 notebook (§1.1), so a second download path would just invent a
second opinion. This step takes the file *as it stands on disk after that job*, checks it, records
provenance, and writes the small normalized series the correlation API needs:

- `owid_world_co2_annual.csv`: World CO2 (Mt, **includes international aviation/shipping**) and
  its cumulative sum -- the fossil-only (secondary) regression X-variable (decision 15) and the scenario base --
  plus World **land-use-change CO2** (`land_use_change_co2_mt`, Global Carbon Project via OWID, 1850+) and the **total anthropogenic CO2**
  (`total_co2_incl_luc_mt` = fossil + cement + land-use) that the headline regression accumulates (decision 40), plus `national_sum_mt` (the sum of ISO-coded countries, the country-share denominator,
  decision 15) and `international_transport_mt` (OWID's aviation + shipping rows) so the two
  accountings are both available and reconcile to World.

Completeness (same principle as decision 22, applied to the trailing years only: the World series
swings -27%..+34% year-on-year in 1803-1830, so a whole-history yoy test would be meaningless):
a year is published only if emission-weighted country coverage is >= `COVERAGE_MIN` and World CO2
is within `YOY_MAX` of the prior year. The last few years are checked and everything from the first
failing year onward is trimmed and noted (see `assess_trailing`).
"""

from __future__ import annotations

import os
import re
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd

from .common import (
    CLIMATE_DIR,
    PROVENANCE_PATH,
    ROOT,
    RunReport,
    require_contiguous_years,
    sha256_hex,
    weighted_coverage,
    write_csv_atomic,
    write_provenance,
)

DATA_PATH = os.path.join(ROOT, "data", "owid-co2-data.csv")
REQUIRED_COLUMNS = ["country", "year", "iso_code", "co2", "cumulative_co2", "methane", "nitrous_oxide"]
# Needed for the headline (total anthropogenic CO2) but not for the fossil series, so a rename upstream raises a deviation instead of stopping the whole step.
LAND_USE_COLUMN = "land_use_change_co2"
LAND_USE_START = 1850  # the headline cumulative is labelled "since 1850"; a later first year would silently change the period
INTERNATIONAL_TRANSPORT = ("International aviation", "International shipping")

COVERAGE_MIN = 0.98
YOY_MAX = 0.15
MAX_TRIMMED_YEARS = 2  # more than this and something is wrong with the file, not just the latest year
STALE_FILE_DAYS = 45  # the refresh job is monthly; older means it has stopped running
MAX_LAG_YEARS = 2
RECONCILE_TOL_PCT = 1.0  # World vs national sum + international transport (observed ~0.02% in 2024)
ROW_DROP_DEVIATION_PCT = 5.0  # the week-1 notebook hard-fails at the same threshold

SERIES_WORLD = "owid_world_co2_annual"
SERIES_COUNTRY = "owid_country_co2"

LAND_USE_LICENSE_NOTE = (
    "Land-use CO2 data originates from the Global Carbon Project via OWID. No formal license (e.g., CC BY) is stated on the Global Carbon "
    "Project's data page; use is conditional on citing the original source per their stated terms. The required citation is included in this "
    "platform's data attribution. No non-commercial, no-derivatives, or share-alike restrictions were found."
)
GCP_CITATION_FORMAT = (
    "Global Carbon Project. (<year>). Supplemental data of Global Carbon Budget <year> (Version <n>) [Data set]. Global Carbon Project. "
    "https://doi.org/10.18160/gcp-<year>  (e.g. the 2024 edition: Global Carbon Project. (2024). Supplemental data of Global Carbon Budget 2024 "
    "(Version 1.0) [Data set]. Global Carbon Project. https://doi.org/10.18160/gcp-2024)"
)
CITATIONS = [
    "Our World in Data, CO2 and Greenhouse Gas Emissions (https://github.com/owid/co2-data), CC BY 4.0.",
    "Friedlingstein, P. et al., Global Carbon Budget (Global Carbon Project), the source of the fossil CO2 and land-use-change CO2 data.",
    "Required by the Global Carbon Project for its data: " + GCP_CITATION_FORMAT + " (use the edition OWID currently republishes).",
]


def owid_url(root: str = ROOT) -> str:
    """Read OWID_URL from notebook/constants.py -- the single source of truth (the refresh script
    keeps its own copy and says it must match)."""
    text = open(os.path.join(root, "notebook", "constants.py")).read()
    m = re.search(r'^OWID_URL\s*=\s*["\']([^"\']+)["\']', text, re.M)
    if not m:
        raise ValueError("notebook/constants.py: OWID_URL not found")
    return m.group(1)


def assess_trailing(world: pd.Series, countries_wide: pd.DataFrame) -> tuple[int, list[dict]]:
    """(last published year, trimmed trailing years with metrics).

    The last `MAX_TRIMMED_YEARS + 2` years are each tested against their predecessor. Everything from
    the **first** failing year onward is trimmed -- not just the latest: when two consecutive years are
    partial, the second looks complete *relative to the first* (coverage is measured against the
    previous year's reported emissions), so judging only the latest year would publish the partial one
    before it."""
    cov = weighted_coverage(countries_wide)
    years = [int(y) for y in world.index]
    window = years[-(MAX_TRIMMED_YEARS + 2):]
    metrics = {}
    for y in window:
        prev = world.get(y - 1)
        yoy = (world[y] / prev - 1) if prev and prev > 0 else np.nan
        c = cov.get(y, np.nan)
        why = []
        if y not in countries_wide.columns:
            # pivot_table drops a year with no ISO-coded country observations at all; NaN coverage would
            # then compare as "not below the minimum" and publish an empty-country year as complete.
            # (NaN coverage for a *present* year means the prior year had nothing to cover: that still passes.)
            why.append("no country observations")
        elif c < COVERAGE_MIN:
            why.append(f"country coverage {c:.1%} < {COVERAGE_MIN:.0%}")
        if abs(yoy) > YOY_MAX:
            why.append(f"World CO2 {yoy:+.1%} vs prior year (limit ±{YOY_MAX:.0%})")
        metrics[y] = {"year": y, "reasons": "; ".join(why), "world_co2_mt": round(float(world[y]), 1),
                      "country_coverage_pct": None if pd.isna(c) else round(float(c) * 100, 2)}
    failing = [y for y in window if metrics[y]["reasons"]]
    if not failing:
        return years[-1], []
    first = failing[0]
    trimmed = [metrics[y] for y in window if y >= first][::-1]  # newest first
    for m in trimmed:
        if not m["reasons"]:
            m["reasons"] = f"trimmed with the incomplete year {first} before it (measured against partial data)"
    if len(trimmed) > MAX_TRIMMED_YEARS or first - 1 not in world.index:
        raise ValueError(f"OWID: {len(trimmed)} trailing years fail the completeness test ({first}-{years[-1]}); more than {MAX_TRIMMED_YEARS} -- the file looks broken")
    return first - 1, trimmed


def run(path: str = DATA_PATH, out_dir: str = CLIMATE_DIR, provenance_path: str = PROVENANCE_PATH, today=None) -> RunReport:
    today = today or date.today()
    report = RunReport("owid")
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} not found -- the refresh job downloads it (see pipeline/owid.py)")
    raw = open(path, "rb").read()
    st = os.stat(path)
    modified = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).replace(microsecond=0)
    age_days = (datetime(today.year, today.month, today.day, tzinfo=timezone.utc) - modified).days

    df = pd.read_csv(path, usecols=lambda c: c in set(REQUIRED_COLUMNS) | {LAND_USE_COLUMN})
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"OWID CSV: required column(s) missing: {', '.join(missing)}")

    world = df[df["country"] == "World"].set_index("year")["co2"].dropna()
    if world.empty:
        raise ValueError("OWID CSV: no usable 'World' CO2 rows")
    require_contiguous_years(world.index, int(world.index.min()), int(world.index.max()), "OWID World CO2")
    cum = df[df["country"] == "World"].set_index("year")["cumulative_co2"]

    luc = df[df["country"] == "World"].set_index("year")[LAND_USE_COLUMN].dropna() if LAND_USE_COLUMN in df.columns else pd.Series(dtype=float)

    early = luc[luc.index < LAND_USE_START]
    if len(early):
        # the headline cumulative is "since 1850": observations before it are dropped, not accumulated, and the source change is noted
        luc = luc[luc.index >= LAND_USE_START]
        report.note(f"OWID World land-use CO2 has {len(early)} observation(s) before {LAND_USE_START} ({int(early.index.min())}-{int(early.index.max())}); ignored so the cumulative stays \"since {LAND_USE_START}\"")

    iso = df["iso_code"].fillna("").str.fullmatch(r"[A-Z]{3}")
    countries = df[iso]
    wide = countries.pivot_table(index="country", columns="year", values="co2", aggfunc="first")
    last, trimmed = assess_trailing(world, wide)
    for t in trimmed:
        report.note(f"excluded incomplete year {t['year']}: {t['reasons']}")
    if len(trimmed) > 1:
        report.deviate(f"{len(trimmed)} trailing OWID years excluded as incomplete ({trimmed[-1]['year']}-{trimmed[0]['year']}); expected at most one")
    if today.year - last > MAX_LAG_YEARS:
        report.deviate(f"latest complete OWID year is {last}, more than {MAX_LAG_YEARS} years behind {today.year}")
    if age_days > STALE_FILE_DAYS:
        report.deviate(f"OWID file last modified {modified.date()} ({age_days} days ago); the refresh job may have stopped running")

    prev = {}
    if os.path.exists(provenance_path):
        import json

        prev = json.load(open(provenance_path)).get(SERIES_COUNTRY, {})
    rows = len(df)
    if prev.get("rows_in_source"):
        delta = rows - prev["rows_in_source"]
        pct = delta / prev["rows_in_source"] * 100
        report.note(f"OWID rows {rows} ({delta:+d}, {pct:+.2f}% vs previous run)")
        if pct < -ROW_DROP_DEVIATION_PCT:
            report.deviate(f"OWID row count fell {pct:.1f}% since the previous run ({prev['rows_in_source']} -> {rows})")
    else:
        report.note(f"OWID rows {rows} (first registration)")

    years = [y for y in world.index if y <= last]
    transport = df[df["country"].isin(INTERNATIONAL_TRANSPORT)].pivot_table(index="year", columns="country", values="co2", aggfunc="first").sum(axis=1, min_count=1)
    out = pd.DataFrame(
        {
            "year": years,
            "co2_mt": [world[y] for y in years],
            "cumulative_co2_mt": [cum.get(y, np.nan) for y in years],
            "national_sum_mt": [wide[y].sum(min_count=1) if y in wide.columns else np.nan for y in years],
            "countries_reporting": [int(wide[y].notna().sum()) if y in wide.columns else 0 for y in years],
            "international_transport_mt": [transport.get(y, np.nan) for y in years],
        }
    ).round(4)
    land_use = pd.Series([luc.get(y, np.nan) for y in years], index=out.index)
    out = out.assign(land_use_change_co2_mt=land_use.round(4), total_co2_incl_luc_mt=(out["co2_mt"] + land_use).round(4))  # assign, not setitem: pandas 3.14 chained-assignment warning
    if luc.empty:
        report.deviate(f"OWID column {LAND_USE_COLUMN!r} is missing or empty: the headline regression (total anthropogenic CO2) is unavailable; the fossil-only series is unaffected")
    else:
        lo, hi = int(luc.index.min()), int(luc.index.max())
        expected_start = max(LAND_USE_START, int(world.index.min()))
        if lo > expected_start:
            report.deviate(f"OWID World land-use CO2 starts in {lo}, after {expected_start}: the cumulative total \"since {LAND_USE_START}\" would silently start later")
        gaps = [y for y in range(lo, min(hi, last) + 1) if y not in luc.index]
        if gaps:
            report.deviate(f"OWID World land-use CO2 has interior gap(s) {gaps[:5]}{'...' if len(gaps) > 5 else ''}: the cumulative total would be too small from {gaps[0]}")
        if hi < last:
            report.deviate(f"OWID World land-use CO2 ends in {hi}, before the last complete CO2 year {last}: total anthropogenic CO2 is unavailable for {hi + 1}-{last}")
        report.note(f"World land-use CO2 {lo}-{hi}; total anthropogenic CO2 published for {int(out.loc[out['total_co2_incl_luc_mt'].notna(), 'year'].min())}-{int(out.loc[out['total_co2_incl_luc_mt'].notna(), 'year'].max())}")
    if out["cumulative_co2_mt"].isna().any():
        report.deviate(f"World cumulative_co2 is missing for {int(out['cumulative_co2_mt'].isna().sum())} year(s); the regression X-variable would have gaps")
    # World should reconcile to (sum of ISO-coded countries + international aviation/shipping); a
    # large gap means entities are missing from, or double-counted in, one of the accountings.
    last_row = out[out["year"] == last].iloc[0]
    parts = last_row["national_sum_mt"] + (0 if pd.isna(last_row["international_transport_mt"]) else last_row["international_transport_mt"])
    gap_pct = (parts / last_row["co2_mt"] - 1) * 100
    report.note(f"World reconciles to national sum + international transport within {gap_pct:+.2f}% in {last}")
    if abs(gap_pct) > RECONCILE_TOL_PCT:
        report.deviate(f"World CO2 differs from national sum + international transport by {gap_pct:+.2f}% in {last} (tolerance ±{RECONCILE_TOL_PCT}%)")
    write_csv_atomic(out, os.path.join(out_dir, "owid_world_co2_annual.csv"))
    report.count(SERIES_WORLD, len(out))
    report.count(SERIES_COUNTRY, rows)

    sha = sha256_hex(raw)
    base = {
        "source": "Our World in Data CO2 and GHG emissions dataset (OWID, from the Global Carbon Project)",
        "source_urls": [owid_url()],
        "retrieved_at": modified.isoformat(),
        "retrieved_at_basis": "file modification time on disk (downloaded by the refresh job; this step does not download)",
        "raw_sha256": {"owid-co2-data.csv": sha},
        "units": "Mt CO2 (`co2`: fossil + cement, excludes land-use change; `land_use_change_co2`: land-use change, a separate column)",
        "update_cadence": "OWID updates when the Global Carbon Budget is released; the refresh job re-downloads monthly",
        "license": (
            "CC BY 4.0 for OWID's compilation (OWID's README). Per that README, third-party data it republishes (the Global Carbon Project, "
            "the Energy Institute, others) stays subject to the original authors' licence terms. Fossil CO2 and land-use CO2 are Global Carbon Project "
            "data: see `land_use_license_note`. The Energy Institute and other components are not used by the headline analysis and are not individually verified. "
            "Cite OWID and the Global Carbon Budget."
        ),
        "land_use_license_note": LAND_USE_LICENSE_NOTE,
        "attribution_required": True,
        "required_citation_format": GCP_CITATION_FORMAT,
        "citations": CITATIONS,
        "published": True,
    }
    write_provenance(
        SERIES_WORLD,
        {**base, "coverage": [int(min(years)), last], "excluded_incomplete_years": trimmed,
         "geography": "World (OWID/GCP aggregate; includes international aviation and shipping)",
         "columns": {"co2_mt": "World total CO2 incl. international transport (the TCRE regression X-variable, decision 15)",
                     "cumulative_co2_mt": "OWID's own cumulative World fossil + cement CO2 since 1750 (the secondary, fossil-only regression X-variable)",
                     "land_use_change_co2_mt": "World land-use-change CO2 (Global Carbon Project bookkeeping-model average, via OWID); 1850 onward",
                     "total_co2_incl_luc_mt": "fossil + cement + land-use-change CO2 (total anthropogenic CO2): its cumulative since 1850 is the headline regression X-variable (decision 40)",
                     "national_sum_mt": "sum of ISO-coded countries (the country-share denominator; excludes international transport)",
                     "international_transport_mt": "OWID 'International aviation' + 'International shipping' rows"},
         "completeness_rule": {"coverage_min_weighted": COVERAGE_MIN, "yoy_max": YOY_MAX, "scope": "trailing years only"},
         "caveats": ["`co2_mt` is fossil + cement only; land-use change is a separate column (`land_use_change_co2_mt`) and `total_co2_incl_luc_mt` adds the two.",
                     "Land-use CO2 is a modelled estimate (average of bookkeeping models) with a large uncertainty: the Global Carbon Budget gives about +/-0.7 GtC/yr (about +/-2.6 GtCO2/yr, 1 sigma) for recent decades. " + LAND_USE_LICENSE_NOTE,
                     "OWID/GCP and PRIMAP-hist/EDGAR differ by a few percent through scope and method; disclosed, not reconciled.",
                     "`national_sum_mt` sums ISO-coded entities, which include some non-sovereign territories."],
         "rows": len(out)},
        provenance_path,
    )
    write_provenance(
        SERIES_COUNTRY,
        {**base, "path": "data/owid-co2-data.csv", "rows_in_source": rows, "rows": rows,
         "coverage": [int(df["year"].min()), int(df["year"].max())],
         "geography": "country level (served by the existing historical/overview/country-profile endpoints)",
         "note": "Registered, not re-published: the existing API reads the CSV directly; this entry gives it provenance and a checksum."},
        provenance_path,
    )
    return report
