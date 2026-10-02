"""Global temperature anomaly: Berkeley Earth Land+Ocean annual series. Release 21, Phase 1.1.

Berkeley reports anomalies relative to 1951-1980. The platform also needs a pre-industrial
(1850-1900) reference (`SPEC.md` §5.26 decision 8), so the offset is **computed here from
Berkeley's own data** -- the mean 1850-1900 anomaly on the native baseline -- and published
with its derivation, never hardcoded from literature. Anomalies on the 1850-1900 reference
are `anomaly_1951_1980 - offset`.

Two series exist in the file: temperature over sea ice taken from *air* (Berkeley's preferred,
"more natural" description of surface warming) or from *water*. The air version is used.
"""

from __future__ import annotations

import io
import os
import re

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

# Berkeley's own data page links this S3 bucket as the canonical download location.
SUMMARY_URL = "https://berkeley-earth-temperature.s3.us-west-1.amazonaws.com/Global/Land_and_Ocean_summary.txt"
SERIES_ID = "temperature_anomaly_annual"

PREIND_START, PREIND_END = 1850, 1900
MAX_LAG_YEARS = 2  # alert if the latest year is older than this
STALE_FILE_DAYS = 400  # alert if the source file itself hasn't been updated this long


def parse_summary(text: str) -> pd.DataFrame:
    """Annual anomaly (air-above-sea-ice version) and its 95% CI from the summary file's
    first anomaly block. Comment lines start with '%'; data rows are whitespace-separated:
    year, annual anomaly, annual unc., five-year anomaly, five-year unc., then the same four
    for the water-above-sea-ice version (NaN where not defined)."""
    rows = []
    for ln in text.splitlines():
        if not ln.strip() or ln.lstrip().startswith("%"):
            continue
        parts = ln.split()
        if len(parts) < 3:
            continue
        rows.append((int(parts[0]), float(parts[1]), float(parts[2])))
    if not rows:
        raise ValueError("Berkeley summary: no data rows parsed")
    df = pd.DataFrame(rows, columns=["year", "anomaly_1951_1980_c", "uncertainty_95_c"])
    if int(df["year"].min()) != PREIND_START
        raise ValueError(f"Berkeley summary: expected first year {PREIND_START}")
    if not df["year"].is_monotonic_increasing:
        raise ValueError("Berkeley summary: years are not ordered")
    require_contiguous_years(df["year"], PREIND_START, int(df["year"].max()), "Berkeley summary")
    return df


def parse_release(text: str) -> dict:
    """Pulls the analysis-run / ocean-publish stamps and the 1951-1980 absolute mean from the
    header, so the provenance entry can identify the release and the staleness check has
    something better than the HTTP Last-Modified header to compare against."""
    out: dict = {}
    m = re.search(r"land analysis was run on ([^\n]+)", text)
    if m:
        out["land_analysis_run"] = m.group(1).strip()
    m = re.search(r"ocean analysis was published on ([^\n]+)", text)
    if m:
        out["ocean_analysis_published"] = m.group(1).strip()
    m = re.search(r"Using air temperature above sea ice:\s*([\d.]+)", text)
    if m:
        out["abs_mean_1951_1980_air_c"] = float(m.group(1))
    return out


def preindustrial_offset(df: pd.DataFrame) -> dict:
    """Mean 1850-1900 anomaly on the native 1951-1980 baseline, and its spread."""
    win = df[(df["year"] >= PREIND_START) & (df["year"] <= PREIND_END)]
    expected = PREIND_END - PREIND_START + 1
    if len(win) != expected:
        raise ValueError(f"Berkeley summary: {len(win)} of {expected} years present in {PREIND_START}-{PREIND_END}")
    return {
        "reference_period": [PREIND_START, PREIND_END],
        "value_c": round(float(win["anomaly_1951_1980_c"].mean()), 4),
        "std_c": round(float(win["anomaly_1951_1980_c"].std(ddof=1)), 4),
        "years": expected,
        "derivation": (
            f"Mean of Berkeley Earth's annual Land+Ocean anomaly (air above sea ice, native 1951-1980 baseline) over "
            f"{PREIND_START}-{PREIND_END}; subtract from any native-baseline anomaly to express it relative to {PREIND_START}-{PREIND_END}."
        ),
    }


def to_normalized(df: pd.DataFrame, offset_c: float) -> pd.DataFrame:
    out = df.assign(anomaly_1850_1900_c=(df["anomaly_1951_1980_c"] - offset_c).round(4))
    return out[["year", "anomaly_1951_1980_c", "anomaly_1850_1900_c", "uncertainty_95_c"]]


def run(fetcher=fetch, out_dir: str = CLIMATE_DIR, provenance_path: str = PROVENANCE_PATH, today=None) -> RunReport:
    from datetime import date, datetime, timezone

    today = today or date.today()
    report = RunReport("berkeley_earth")
    raw: Fetched = fetcher(SUMMARY_URL)
    text = raw.text("latin-1")

    df = parse_summary(text)
    release = parse_release(text)
    offset = preindustrial_offset(df)
    series = to_normalized(df, offset["value_c"])
    latest = int(series["year"].max())

    if today.year - latest > MAX_LAG_YEARS:
        report.deviate(f"latest Berkeley Earth year is {latest}, more than {MAX_LAG_YEARS} years behind {today.year}")
    if raw.last_modified:
        age = (datetime(today.year, today.month, today.day, tzinfo=timezone.utc) - datetime.fromisoformat(raw.last_modified)).days
        if age > STALE_FILE_DAYS:
            report.deviate(
                f"Berkeley Earth source file last modified {raw.last_modified[:10]} ({age} days ago); it ends at {latest} -- "
                f"the publisher's download location may not be receiving updates"
            )

    write_csv_atomic(series, os.path.join(out_dir, "temperature_anomaly_annual.csv"))
    report.count(SERIES_ID, len(series))
    write_provenance(
        SERIES_ID,
        {
            "source": "Berkeley Earth Land/Ocean global temperature (annual)",
            "source_urls": [SUMMARY_URL],
            "retrieved_at": raw.retrieved_at,
            "source_release": {"http_last_modified": raw.last_modified, **release},
            "raw_sha256": {"summary": raw.sha256},
            "coverage": [int(series["year"].min()), latest],
            "units": "degrees C anomaly",
            "gas_scope": "not applicable (temperature)",
            "geography": "global",
            "update_cadence": "monthly (publisher); annual values close each year",
            "reference_period_native": [1951, 1980],
            "preindustrial_offset": offset,
            "methodology": (
                "Berkeley Earth land-surface field combined with a reinterpolated HadSST4 ocean field; sea-ice regions "
                "extrapolated from air temperature (the preferred version). Uncertainty is the 95% CI for statistical "
                "and spatial undersampling effects and ocean biases. `anomaly_1850_1900_c` = native anomaly minus the "
                "computed 1850-1900 offset."
            ),
            "caveats": [
                "Anomalies are deviations from a reference period, not absolute temperatures.",
                "The 1850-1900 'pre-industrial' reference is a convention; the offset is computed from this dataset's own early record, whose uncertainty is largest.",
            ],
            "license": "Berkeley Earth data: CC BY 4.0 (cite Rohde & Hausfather 2020, ESSD 12, 3469).",
            "rows": len(series),
        },
        provenance_path,
    )
    return report
