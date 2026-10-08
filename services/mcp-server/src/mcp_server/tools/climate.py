"""SPEC.md §5.1 Area 2 indicator tools: get_co2_concentration, get_temperature_anomaly,
get_correlation_metadata.

Each returns the API body unchanged (full series + envelope) with a deterministic `summary`
added. Capping what the *model* sees is the agent's job (agent SPEC.md §15.4), not this server's.
"""

from __future__ import annotations

from ..climate import fetch_correlation, summarize_points
from ..server import mcp

# Tool-facing reference label -> the API's `baseline` value.
TEMPERATURE_REFERENCES = {"1850-1900": "1850_1900", "1951-1980": "1951_1980"}


@mcp.tool()
async def get_co2_concentration(start_year: int | None = None, end_year: int | None = None) -> dict:
    """Annual atmospheric CO2 concentration in ppm: NOAA GML Mauna Loa measurements from 1959,
    spliced to the Law Dome ice-core record before 1959. This is a measured quantity (the
    accumulated stock of CO2 in the atmosphere), not an emissions flow and not a model output.
    Optionally restrict to `start_year`..`end_year` (inclusive; clipped to the available
    coverage, which is read from the data). The response carries `summary` (first/last value,
    change, percent change) -- quote that rather than deriving figures from the series -- plus
    `details.splice` (the splice year and the measured overlap gap between the two records;
    mention it when comparing across 1959) and the source `caveats`/`attribution`.
    Annual resolution only. Concentration and emissions move together over the long run, but
    this tool does not establish cause."""
    body = await fetch_correlation(
        "concentration", {"view": "level", "resolution": "annual", "start_year": start_year, "end_year": end_year}
    )
    body["summary"] = summarize_points(body["points"], include_pct=True)
    return body


@mcp.tool()
async def get_temperature_anomaly(
    start_year: int | None = None, end_year: int | None = None, reference: str = "1850-1900"
) -> dict:
    """Global mean surface temperature anomaly in °C (Berkeley Earth Land/Ocean, annual), i.e.
    the deviation from a reference period, not an absolute temperature. `reference` is
    '1850-1900' (pre-industrial, the default and what the dashboard shows) or '1951-1980'
    (Berkeley Earth's native baseline); the 1850-1900 offset is computed from Berkeley Earth's
    own early record and its derivation is in `details.offset`. Optionally restrict to
    `start_year`..`end_year` (inclusive; clipped to coverage, read from the data). The response
    carries `summary` (first/last value and change in °C -- quote it rather than deriving
    figures) and the source `caveats`, which include the note that this dataset is a
    preliminary, not-yet-peer-reviewed release whose values may be revised; mention that
    whenever you quote a temperature figure. The temperature series can run one year past the
    emissions data. This is an observed global quantity: never attribute it to any single
    country, and do not present it as proof that emissions caused a given change."""
    if reference not in TEMPERATURE_REFERENCES:
        raise ValueError(
            f"Unknown reference {reference!r} -- use one of: {', '.join(sorted(TEMPERATURE_REFERENCES))}."
        )
    body = await fetch_correlation(
        "temperature",
        {"view": "level", "baseline": TEMPERATURE_REFERENCES[reference], "start_year": start_year, "end_year": end_year},
    )
    summary = summarize_points(body["points"], include_pct=False)
    summary["reference"] = reference
    body["summary"] = summary
    return body


@mcp.tool()
async def get_correlation_metadata() -> dict:
    """Provenance and methodology for the climate-context data behind the other climate tools:
    every source (OWID, PRIMAP-hist, Berkeley Earth, NOAA GML) with its licence, coverage years,
    release/vintage and caveats; the Berkeley Earth 1850-1900 offset and how it was derived; the
    source/baseline combinations that are valid for the emissions-temperature relationship; the
    statement of why two different global totals are used; and freshness (`summary.stale_outputs`
    lists any pipeline output that is missing or out of date -- tell the user if it is non-empty).
    Use this to answer 'where does this data come from', 'how current is it' and 'what are its
    limits'. It is documentation of the data layer, not a climate model, and says nothing about
    individual countries' contribution to warming."""
    body = await fetch_correlation("meta")
    # The indicator catalog is a data dictionary, not something to answer questions from.
    body["indicator_count"] = len(body.pop("indicators", []))
    outputs = body.get("outputs", {})
    body["summary"] = {
        "sources": [
            {"id": s["id"], "coverage": s.get("coverage"), "retrieved_at": s.get("retrieved_at"), "license": s.get("license")}
            for s in body.get("sources", [])
        ],
        "stale_outputs": sorted(
            name for name, o in outputs.items() if o.get("status") != "available" or o.get("stale")
        ),
        "temperature_offset": body.get("temperature_offset"),
        "pipeline_failures": (body.get("pipeline_last_run") or {}).get("failures", {}),
    }
    return body
