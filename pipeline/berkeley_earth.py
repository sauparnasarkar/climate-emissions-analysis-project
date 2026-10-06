"""Global temperature anomaly: Berkeley Earth Land+Ocean annual series. Release 21, Phase 1.1; source moved to the
high-resolution dataset 2026-10-06 (`ENHANCEMENTS.md` decision 83) after the provider's reply -- the S3 summary file is retired.

Berkeley reports anomalies relative to 1951-1980. The platform also needs a pre-industrial
(1850-1900) reference (`SPEC.md` §5.26 decision 8), so the offset is **computed here from
Berkeley's own data** -- the mean 1850-1900 anomaly on the native baseline -- and published
with its derivation, never hardcoded from literature. Anomalies on the 1850-1900 reference
are `anomaly_1951_1980 - offset`.

The high-resolution annual file carries one series (sea-ice regions extrapolated from air temperature where ice is
present, as in the retired file's preferred version). It is a **preliminary** release -- not yet peer reviewed, subject
to change without notice, with a description paper under review at ESSD -- and provenance says so.
"""

from __future__ import annotations

import io
import os
import re

import pandas as pd

from .common import (
    CLIMATE_DIR,
    NOTICES_PATH,
    PROVENANCE_PATH,
    Fetched,
    RunReport,
    fetch,
    load_source_notices,
    require_contiguous_years,
    write_csv_atomic,
    write_provenance,
)

# Berkeley's data page (berkeleyearth.org/data) links this as the "annual file" of the high-resolution dataset, their operational product.
SUMMARY_URL = "https://storage.googleapis.com/berkeley-earth-temperature-hr/global/Global_TAVG_annual.txt"
SERIES_ID = "temperature_anomaly_annual"

PREIND_START, PREIND_END = 1850, 1900
# One wording, used by this module's provenance, the harmonized catalog and the correlation outputs; shown only while the parsed header says so.
PRELIMINARY_NOTE = "Berkeley Earth's high-resolution temperature dataset is a preliminary release (not yet peer reviewed; values may be revised)."
MAX_LAG_YEARS = 2  # alert if the latest year is older than this
STALE_FILE_DAYS = 400  # alert if the source file itself hasn't been updated this long


def parse_summary(text: str) -> pd.DataFrame:
    """Annual anomaly and its 95% CI from the annual file. Comment lines start with '%'; data rows are
    whitespace-separated: year, annual anomaly, annual unc., five-year anomaly, five-year unc. (NaN where not defined)."""
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
    if int(df["year"].min()) != PREIND_START:
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
    # The header's line is `%    14.107 +/- ...` under "Estimated Jan 1951-Dec 1980 global mean temperature"; the uncertainty text is
    # garbled in the preliminary release, so only the leading value is read, and its absence is not an error.
    m = re.search(r"Estimated Jan 1951-Dec 1980 global mean temperature[^\n]*\n%\s*(\d+\.\d+)", text)
    if m:
        out["abs_mean_1951_1980_c"] = float(m.group(1))
    out["preliminary"] = bool(re.search(r"PRELIMINARY DATA", text))
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


def run(fetcher=fetch, out_dir: str = CLIMATE_DIR, provenance_path: str = PROVENANCE_PATH, today=None, notices_path: str = NOTICES_PATH) -> RunReport:
    from datetime import date, datetime, timezone

    today = today or date.today()
    report = RunReport("berkeley_earth")
    raw: Fetched = fetcher(SUMMARY_URL)
    text = raw.text("latin-1")

    df = parse_summary(text)
    release = parse_release(text)
    offset = preindustrial_offset(df)
    series = to_normalized(df, offset["value_c"])
    preliminary = bool(release.get("preliminary"))
    latest = int(series["year"].max())

    if today.year - latest > MAX_LAG_YEARS:
        report.deviate(f"latest Berkeley Earth year is {latest}, more than {MAX_LAG_YEARS} years behind {today.year}")
    if raw.last_modified:
        age = (datetime(today.year, today.month, today.day, tzinfo=timezone.utc) - datetime.fromisoformat(raw.last_modified)).days
        if age > STALE_FILE_DAYS:
            report.deviate(
                f"Berkeley Earth source file last modified {raw.last_modified[:10]} ({age} days ago); it ends at {latest} -- "
                f"the publisher's download location may not be receiving updates (the previous S3 file went stale this way)"
            )

    # Correspondence with the provider (pipeline/source_notices.json, tracked) is copied into provenance each run, like PRIMAP-hist's.
    # Nothing here is required by the provider, so an unanswered inquiry is a note, never an alert; the stale-source deviation above is the alert.
    notices = load_source_notices("berkeley_earth", notices_path)
    open_inquiries = [n for n in notices if n["type"] == "inquiry" and not n.get("replies")]
    for n in open_inquiries:
        sent = datetime.fromisoformat(n["sent_at"].replace("Z", "+00:00"))
        report.note(f"inquiry to Berkeley Earth about this stale download sent {n['sent_at'][:10]} ({(date(today.year, today.month, today.day) - sent.date()).days} days ago) has no recorded reply")
        if raw.last_modified and datetime.fromisoformat(raw.last_modified) > sent:
            report.note(f"the source file has changed since that inquiry (last modified {raw.last_modified[:10]}): it may now be answered in practice -- check, and record the reply")
    write_csv_atomic(series, os.path.join(out_dir, "temperature_anomaly_annual.csv"))
    report.count(SERIES_ID, len(series))
    write_provenance(
        SERIES_ID,
        {
            "source": "Berkeley Earth High-Resolution Land/Ocean global temperature (annual" + ("; preliminary)" if preliminary else ")"),
            "source_urls": [SUMMARY_URL],
            "retrieved_at": raw.retrieved_at,
            "source_release": {"http_last_modified": raw.last_modified, **release},
            "raw_sha256": {"summary": raw.sha256},
            "coverage": [int(series["year"].min()), latest],
            "units": "degrees C anomaly",
            "gas_scope": "not applicable (temperature)",
            "geography": "global",
            "update_cadence": "monthly (publisher); annual values close each year",
            "preliminary": preliminary,
            "retired_source": "https://berkeley-earth-temperature.s3.us-west-1.amazonaws.com/Global/Land_and_Ocean_summary.txt (last modified 2025-01-10, ends 2024; superseded per the provider's reply of 2026-10-06)",
            "reference_period_native": [1951, 1980],
            "preindustrial_offset": offset,
            "methodology": (
                "Berkeley Earth High-Resolution (0.25 deg) land-surface field, with predictive structures from historical weather patterns, "
                "combined with a reinterpolated HadSST4 ocean field; sea-ice regions extrapolated from land air temperature when ice is "
                "present. Uncertainty is the 95% CI for statistical "
                "and spatial undersampling effects and ocean biases. `anomaly_1850_1900_c` = native anomaly minus the "
                "computed 1850-1900 offset."
            ),
            "caveats": [
                *(["PRELIMINARY: Berkeley Earth labels this dataset 'preliminary data - subject to change without notice - not yet peer reviewed'; values may be revised, and no final citation exists yet."] if preliminary else []),
                "Anomalies are deviations from a reference period, not absolute temperatures.",
                "The 1850-1900 'pre-industrial' reference is a convention; the offset is computed from this dataset's own early record, whose uncertainty is largest.",
                "Non-commercial use only (CC BY-NC): fine for this platform; any commercial use would need a licence from Berkeley Earth.",
            ],
            "license": (
                "CC BY-NC 4.0 International (Berkeley Earth's data page: 'in general ... for non-commercial use only'; commercial use needs "
                "a licence from admin@berkeleyearth.org). Attribution to Berkeley Earth, including a reference to www.berkeleyearth.org. "
                "The page's terms are stated for its data in general, including the beta high-resolution files; no separate licence is stated for this product. "
                "Cite the dataset's description paper (a preprint under review when this source was adopted): Berkeley Earth Surface Temperature - High-Resolution (BEST-HR), ESSD Discussions, doi:10.5194/essd-2026-412."
            ),
            "attribution_required": True,
            "non_commercial_only": True,
            "provider_correspondence": {"notices": notices, "record": "pipeline/source_notices.json (tracked); copied here on every run"},
            "citations": [
                "Berkeley Earth Surface Temperature - High-Resolution (BEST-HR): a 0.25 deg Global Gridded Temperature Data Set for Climate Monitoring, Earth Syst. Sci. Data Discuss. (preprint under review), https://doi.org/10.5194/essd-2026-412, 2026.",
                "Background (previous product): Rohde, R. A. and Hausfather, Z., Earth Syst. Sci. Data, 12, 3469-3479, https://doi.org/10.5194/essd-12-3469-2020, 2020.",
            ],
            "published": True,
            "rows": len(series),
        },
        provenance_path,
    )
    return report
