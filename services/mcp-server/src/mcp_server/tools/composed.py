"""SPEC.md §5 composed tools: get_top_emitters, get_methodology_notes,
get_forecast_comparison.

None is a near-1:1 endpoint wrap -- get_top_emitters ranks a raw time-series payload in
memory (no ranked-by-year endpoint exists), get_methodology_notes isn't endpoint-backed at
all, and get_forecast_comparison fans out to /forecasts/{country} once per country
concurrently (no multi-country forecast-with-full-series endpoint exists either).
"""

from __future__ import annotations

import asyncio

from ..client import get_client
from ..methodology import SCOPE_LABELS, methodology_notes
from ..resolution import fetch_country_lists, resolve_countries
from ..server import mcp
from ..trimming import trim


@mcp.tool()
async def get_top_emitters(year: int, n: int = 10) -> dict:
    """The top `n` CO2 emitters for a specific `year`, ranked descending. Composed from
    /overview/world-map-series -- fetched fresh on every call, no server-side cache (SPEC.md
    §6.2), since no ranked-by-year endpoint exists to wrap directly. Countries with no data
    at `year` are excluded from the ranking, not treated as zero."""
    client = get_client()
    data = await client.get("/overview/world-map-series")
    try:
        year_idx = data["years"].index(year)
    except ValueError:
        raise ValueError(
            f"No data for year {year}. Available years: {data['years'][0]}-{data['years'][-1]}."
        ) from None

    year_values = data["values"][year_idx]
    ranked = sorted(
        (
            {"country": country, "iso_code": iso_code, "co2": value}
            for country, iso_code, value in zip(data["countries"], data["iso_codes"], year_values)
            if value is not None
        ),
        key=lambda row: row["co2"],
        reverse=True,
    )
    return {"year": year, "emitters": ranked[:n]}


@mcp.tool()
async def get_forecast_comparison(countries: list[str] | None = None, scope: str = "expanded") -> dict:
    """ETS(A,Ad,N) forecast (historical actuals, holdout, forecast mean, confidence
    interval) for multiple countries in one call -- the multi-country equivalent of
    get_forecast. Do NOT call get_forecast once per country to build a comparison: that
    costs one MCP round trip (plus a redundant country-list resolution) per country instead
    of one call total, and produces the same non-reproducible ad hoc selection risk as
    looping any other single-country tool. This tool fetches every country's forecast
    concurrently internally, so it's one call from your side regardless of how many
    countries are involved.

    `scope` is 'featured' (10) or 'expanded' (~40) -- no 'sovereign' option, since forecasts
    only exist for the expanded ~40 countries (same restriction as get_forecast_summary).
    It only picks the default pool when `countries` is omitted; every country (explicit or
    pool-resolved) is always checked against the expanded scope specifically, matching
    get_forecast's own single-country behavior.

    When `countries` is omitted and the resolved pool has more than 10 countries, the
    response is capped at the 10 with the highest latest historical actual value and
    carries a scope_note (SPEC.md §3.2). An explicit `countries` list is always returned in
    full, uncapped.
    """
    if scope not in ("featured", "expanded"):
        raise ValueError(f"scope must be 'featured' or 'expanded' for forecasts, got '{scope}'")

    lists = await fetch_country_lists()
    omitted = countries is None
    resolved = lists.pool(scope) if omitted else resolve_countries(countries, lists, scope="expanded")

    client = get_client()
    forecasts = await asyncio.gather(*(client.get(f"/forecasts/{country}") for country in resolved))

    body = {"forecasts": forecasts}
    if omitted:
        trimmed, note = trim(
            forecasts,
            scope_label=SCOPE_LABELS[scope],
            sort_key_label="latest historical actual value descending",
            sort_key=lambda f: next((v for v in reversed(f["hist_co2"]) if v is not None), float("-inf")),
        )
        body["forecasts"] = trimmed
        if note is not None:
            body["scope_note"] = note
    return body


@mcp.tool()
async def get_methodology_notes() -> dict:
    """Static methodology reference: the ETS(A,Ad,N) forecasting explanation, the five-model
    comparison set, OWID dataset provenance/caveats, and expanded-scope selection criteria.
    Not endpoint-backed -- quote this instead of improvising a methodology explanation."""
    return methodology_notes()
