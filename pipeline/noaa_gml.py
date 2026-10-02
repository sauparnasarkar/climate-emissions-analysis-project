"""Atmospheric CO2 concentration: NOAA GML Mauna Loa (modern era) spliced to the Law Dome
ice-core/firn spline (pre-modern era). Release 21, Phase 1.1; `SPEC.md` §5.26.

Splice rule: NOAA's annual-mean file starts in 1959 -- the first full calendar year (the
monthly record begins March 1958 -- the Keeling/Scripps series NOAA took over) -- so the
splice year is **1959**, not 1958: Law Dome supplies years < 1959, NOAA supplies >= 1959.
Law Dome's spline (Etheridge et al. 1996; MacFarling Meure et al. 2006) reflects Antarctic
air (Southern Hemisphere), Mauna Loa is Northern Hemisphere, and the spline attenuates
variations shorter than ~20 years by 50%, so the two do not match exactly; the overlap
(1959-2004) is measured and published in the provenance entry rather than adjusted away.
"""

from __future__ import annotations

import io
import os

import pandas as pd

from .common import (
    CLIMATE_DIR,
    PROVENANCE_PATH,
    Fetched,
    RunReport,
    fetch,
    require_contiguous_years,
    write_csv_atomic,
    write_provenance,
)

NOAA_ANNUAL_URL = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_annmean_mlo.csv"
NOAA_MONTHLY_URL = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv"
LAW_DOME_URL = "https://www.ncei.noaa.gov/pub/data/paleo/icecore/antarctica/law/law2006.txt"

SERIES_ANNUAL = "co2_concentration_annual"
SERIES_MONTHLY = "co2_concentration_monthly_mlo"

SPLICE_YEAR = 1959  # first NOAA annual-mean year; Law Dome supplies earlier years
FIRST_YEAR = 1750  # matches OWID's earliest year; Law Dome itself goes back to 1 AD
MAX_SPLICE_GAP_PPM = 1.0  # deviation alert if Law Dome and NOAA disagree this much at the splice
MAX_LAG_YEARS = 2  # alert if the latest annual value is older than this
MAX_MONTHLY_LAG_MONTHS = 3  # alert if the latest monthly reading is older than this


def parse_noaa_annual(text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text), comment="#")
    df = df.rename(columns={"mean": "co2_ppm", "unc": "uncertainty_ppm"})
    return df[["year", "co2_ppm", "uncertainty_ppm"]].astype({"year": int}).reset_index(drop=True)


def parse_noaa_monthly(text: str) -> pd.DataFrame:
    df = pd.read_csv(io.StringIO(text), comment="#")
    df = df.rename(columns={"average": "co2_ppm", "deseasonalized": "co2_deseasonalized_ppm"})
    return df[["year", "month", "co2_ppm", "co2_deseasonalized_ppm"]].astype({"year": int, "month": int})


def parse_law_dome_co2(text: str) -> pd.DataFrame:
    """Reads the CO2 spline (columns 5-6: YearAD, CO2spl) out of the spline table that follows
    the 'YearAD CH4spl ...' header. Rows that don't have all ten columns, or whose year isn't a
    whole number, are skipped -- the CO2 columns can't be located reliably in a short row."""
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.strip().startswith("YearAD")), None)
    if start is None:
        raise ValueError("Law Dome file: 'YearAD' spline header not found")
    rows = []
    for ln in lines[start + 1 :]:
        parts = ln.split()
        if len(parts) != 10:
            if rows:  # first non-table line after the table ends the block
                break
            continue
        try:
            year = float(parts[4])
            co2 = float(parts[5])
        except ValueError:
            break
        if year != round(year):
            continue
        rows.append((int(year), co2))
    if not rows:
        raise ValueError("Law Dome file: no CO2 spline rows parsed")
    return pd.DataFrame(rows, columns=["year", "co2_ppm"])


def validate_monthly(df: pd.DataFrame) -> None:
    """The monthly record must be one row per month from its first month to its last."""
    idx = df["year"] * 12 + (df["month"] - 1)
    if idx.duplicated().any() or not idx.is_monotonic_increasing:
        raise ValueError("monthly series has duplicate or unordered months")
    missing = set(range(int(idx.min()), int(idx.max()) + 1)) - set(int(i) for i in idx)
    if missing:
        first = sorted(missing)[0]
        raise ValueError(f"monthly series: {len(missing)} missing month(s), first {first // 12}-{first % 12 + 1:02d}")


def build_concentration(noaa: pd.DataFrame, law: pd.DataFrame, splice_year: int = SPLICE_YEAR) -> tuple[pd.DataFrame, dict]:
    """Law Dome for FIRST_YEAR <= year < splice_year, NOAA for year >= splice_year. Law Dome has
    no per-year uncertainty in this release, so its `uncertainty_ppm` is an explicit null
    rather than an invented number. Returns (series, splice_check)."""
    pre = law[(law["year"] >= FIRST_YEAR) & (law["year"] < splice_year)].copy()
    pre["uncertainty_ppm"] = float("nan")
    pre["source"] = "law_dome_spline"
    post = noaa[noaa["year"] >= splice_year].copy()
    post["source"] = "noaa_gml_mlo"
    if post.empty or post["year"].min() != splice_year:
        raise ValueError(f"NOAA annual series does not start at splice year {splice_year}")
    series = pd.concat([pre, post], ignore_index=True)[["year", "co2_ppm", "uncertainty_ppm", "source"]]
    if series["year"].duplicated().any() or not series["year"].is_monotonic_increasing:
        raise ValueError("concentration series has duplicate or unordered years")
    require_contiguous_years(series["year"], FIRST_YEAR, int(series["year"].max()), "concentration series")

    overlap = law.merge(noaa, on="year", suffixes=("_law", "_noaa"))
    gap = overlap["co2_ppm_law"] - overlap["co2_ppm_noaa"]
    at_splice = overlap.loc[overlap["year"] == splice_year]
    check = {
        "splice_year": splice_year,
        "overlap_years": [int(overlap["year"].min()), int(overlap["year"].max())] if len(overlap) else None,
        "gap_at_splice_ppm": round(float((at_splice["co2_ppm_law"] - at_splice["co2_ppm_noaa"]).iloc[0]), 2) if len(at_splice) else None,
        "mean_overlap_gap_ppm": round(float(gap.mean()), 2) if len(gap) else None,
        "max_abs_overlap_gap_ppm": round(float(gap.abs().max()), 2) if len(gap) else None,
    }
    return series, check


def run(fetcher=fetch, out_dir: str = CLIMATE_DIR, provenance_path: str = PROVENANCE_PATH, today=None) -> RunReport:
    from datetime import date

    today = today or date.today()
    today_year = today.year
    report = RunReport("noaa_gml")
    annual: Fetched = fetcher(NOAA_ANNUAL_URL)
    monthly: Fetched = fetcher(NOAA_MONTHLY_URL)
    law_raw: Fetched = fetcher(LAW_DOME_URL)

    noaa_df = parse_noaa_annual(annual.text())
    monthly_df = parse_noaa_monthly(monthly.text())
    law_df = parse_law_dome_co2(law_raw.text("latin-1"))
    series, check = build_concentration(noaa_df, law_df)
    validate_monthly(monthly_df)

    if check["gap_at_splice_ppm"] is not None and abs(check["gap_at_splice_ppm"]) > MAX_SPLICE_GAP_PPM:
        report.deviate(f"Law Dome vs NOAA differ by {check['gap_at_splice_ppm']} ppm at the {SPLICE_YEAR} splice (> {MAX_SPLICE_GAP_PPM})")
    latest = int(series["year"].max())
    if today_year - latest > MAX_LAG_YEARS:
        report.deviate(f"latest annual CO2 value is {latest}, more than {MAX_LAG_YEARS} years behind {today_year}")
    last = monthly_df.iloc[-1]
    monthly_lag = (today.year * 12 + today.month) - (int(last["year"]) * 12 + int(last["month"]))
    if monthly_lag > MAX_MONTHLY_LAG_MONTHS:
        report.deviate(f"latest monthly CO2 reading is {int(last['year'])}-{int(last['month']):02d}, {monthly_lag} months behind (> {MAX_MONTHLY_LAG_MONTHS})")

    write_csv_atomic(series, os.path.join(out_dir, "co2_concentration_annual.csv"))
    write_csv_atomic(monthly_df, os.path.join(out_dir, "co2_concentration_monthly_mlo.csv"))
    report.count(SERIES_ANNUAL, len(series))
    report.count(SERIES_MONTHLY, len(monthly_df))

    write_provenance(
        SERIES_ANNUAL,
        {
            "source": "NOAA GML Mauna Loa (1959+) spliced to Law Dome ice-core/firn spline (pre-1959)",
            "source_urls": [NOAA_ANNUAL_URL, LAW_DOME_URL],
            "retrieved_at": annual.retrieved_at,
            "source_release": {"noaa_last_modified": annual.last_modified, "law_dome_last_update": "2010-07 (WDC Paleo receipt; spline fits Oct 2008)"},
            "raw_sha256": {"noaa_annual": annual.sha256, "law_dome": law_raw.sha256},
            "coverage": [int(series["year"].min()), latest],
            "units": "ppm CO2 (annual mean)",
            "gas_scope": "CO2",
            "geography": "global indicator (Mauna Loa station for >= 1959; Antarctic Law Dome for < 1959)",
            "update_cadence": "NOAA updates monthly; annual mean closes each year. Law Dome record is static.",
            "splice": check,
            "methodology": (
                "Years >= 1959 are NOAA GML Mauna Loa annual means (measured, in situ; 1958-1974 are the Scripps/Keeling "
                "record NOAA took over). Years < 1959 are the Law Dome ice-core/firn spline (Etheridge et al. 1996; "
                "MacFarling Meure et al. 2006), which attenuates variations shorter than ~20 years by 50%. The two are "
                "joined at 1959 without adjustment; the measured overlap gap is in `splice`."
            ),
            "caveats": [
                "Mauna Loa is a single Northern-Hemisphere station; Law Dome reflects Southern-Hemisphere air. Pre-1959 values are not directly comparable year-to-year with later ones.",
                "Law Dome publishes no per-year uncertainty in this release; `uncertainty_ppm` is null before 1959.",
                "NOAA's monthly record was interrupted by the Nov 2022 Mauna Loa eruption; Dec 2022 - Jul 2023 values come from Maunakea.",
            ],
            "license": "NOAA GML: public domain, citation requested. Law Dome: cite Etheridge et al. 2010 (WDC Paleo) and MacFarling Meure et al. 2006.",
            "rows": len(series),
        },
        provenance_path,
    )
    write_provenance(
        SERIES_MONTHLY,
        {
            "source": "NOAA GML Mauna Loa monthly mean",
            "source_urls": [NOAA_MONTHLY_URL],
            "retrieved_at": monthly.retrieved_at,
            "source_release": {"noaa_last_modified": monthly.last_modified},
            "raw_sha256": {"noaa_monthly": monthly.sha256},
            "coverage": [int(monthly_df["year"].min()), int(monthly_df["year"].max())],
            "units": "ppm CO2 (monthly mean; deseasonalized column also provided)",
            "gas_scope": "CO2",
            "geography": "Mauna Loa station",
            "update_cadence": "monthly",
            "methodology": "Monthly mean CO2 constructed from daily means; missing months are interpolated by NOAA (flagged there by negative stdev/uncertainty, not carried here).",
            "caveats": ["Used for the 'latest reading' KPI; annual alignment with emissions uses the annual series."],
            "license": "NOAA GML: public domain, citation requested.",
            "rows": len(monthly_df),
        },
        provenance_path,
    )
    return report
