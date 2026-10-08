"""SPEC.md §5 composed tools: get_top_emitters, get_methodology_notes,
get_forecast_comparison, get_emissions_change_summary.

None is a near-1:1 endpoint wrap -- get_top_emitters ranks a raw time-series payload in
memory (no ranked-by-year endpoint exists), get_methodology_notes is static text by default
(and, for topic='climate'/'all', static text plus the live fit figures read from
/correlation/emissions-temperature -- composed, not a pass-through), get_forecast_comparison fans out to /forecasts/{country} once per country concurrently
(no multi-country forecast-with-full-series endpoint exists either), and
get_emissions_change_summary is the one direct 1:1 wrap in this file (bounded output is a
property of the endpoint it wraps, not something composed here) -- it lives here rather than
historical.py because its job (steer the model away from get_historical_emissions for
counting/ranking questions) is the same "composed, task-shaped tool" role as its siblings,
not a raw data passthrough.
"""

from __future__ import annotations

import asyncio

from ..client import get_client
from ..climate import fetch_correlation
from ..methodology import (
    CLIMATE_METHODOLOGY,
    HEADLINE_DERIVATION_OUTLINE,
    SCOPE_LABELS,
    methodology_notes,
)
from ..resolution import fetch_country_lists, resolve_countries
from ..server import mcp
from ..trimming import trim


@mcp.tool()
async def get_top_emitters(year: int | None = None, n: int = 10) -> dict:
    """The top `n` CO2 emitters for a `year`, ranked descending. **Omit `year` to use the latest
    year with data** (the same year the dashboard defaults to) -- pass it only when the user names
    a specific year. Composed from /overview/world-map-series -- fetched fresh on every call, no
    server-side cache (SPEC.md §6.2), since no ranked-by-year endpoint exists to wrap directly.
    Countries with no data at `year` are excluded from the ranking, not treated as zero. The
    response's `year` is the year actually used."""
    client = get_client()
    data = await client.get("/overview/world-map-series")
    if year is None:
        # The latest year in which at least one country has a value; a trailing all-null year
        # (a data vintage that has the column but no values yet) must not be ranked as "latest".
        populated = [i for i, row in enumerate(data["values"]) if any(v is not None for v in row)]
        if not populated:
            raise ValueError("The emissions series has no data for any year.")
        year_idx = populated[-1]
        year = data["years"][year_idx]
    else:
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

    IMPORTANT: each entry in `countries` must be a real country's common English name (e.g.
    "China", "United States", "United Kingdom"), never an ISO code or abbreviation ("CHN",
    "USA") -- the resolution guard fuzzy-matches against full names and will reject or badly
    mismatch a code. Sovereign countries only -- supranational blocs and regions ("European
    Union", "Middle East", "Sub-Saharan Africa") are out of scope and will also fail
    resolution. If you're not certain a name is real and in scope, call list_countries first
    and pick from its `sovereign` list rather than guessing -- a failed resolution here costs
    a full extra round trip the user waits through; list_countries doesn't.
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
async def get_emissions_change_summary(scope: str = "sovereign", top_n: int = 10) -> dict:
    """How many countries increased vs. decreased CO2 emissions since 1990, plus the
    biggest movers in each direction, ranked by absolute Mt change. Composed from
    /historical/change-summary -- returns real counts and a bounded top-N list regardless
    of scope size, not a full per-country time series.

    USE THIS instead of get_historical_emissions whenever the question is shaped like "how
    many countries increased/decreased", "which countries cut emissions the most", or
    "biggest gainers/decliners since 1990" -- across many or all countries.
    get_historical_emissions returns one full time series per country with no way to reduce
    that to a count; passing it every sovereign country to answer a counting question
    returns an oversized, unreduced payload that has to be read off a chart by eye. This
    tool does the counting server-side.

    `scope` is 'featured' (10), 'expanded' (~40), or 'sovereign' (~209, default -- use this
    for an unqualified "how many countries" question). `top_n` (default 10, max 25) bounds
    each direction's movers list -- response size never scales with scope size.
    """
    if scope not in ("featured", "expanded", "sovereign"):
        raise ValueError(f"scope must be 'featured', 'expanded', or 'sovereign', got '{scope}'")
    client = get_client()
    return await client.get("/historical/change-summary", params={"scope": scope, "top_n": top_n})


@mcp.tool()
async def get_methodology_notes(topic: str | None = None) -> dict:
    """Static methodology reference. With no `topic`: the ETS(A,Ad,N) forecasting explanation,
    the five-model comparison set, OWID dataset provenance/caveats, and expanded-scope
    selection criteria. With `topic='climate'`: the climate-context methodology -- the
    emissions -> concentration -> forcing -> temperature chain, the headline long-run
    relationship vs the recent all-gas relationship, country cumulative share, the scenario
    temperature translation, OWID-vs-PRIMAP source reconciliation, licences, and the limits of
    the analysis -- plus `headline_derivation`: the live fitted figures (slope, HAC interval, R²,
    stability, land-use sensitivity, AR6 comparison, and the fossil-only fit beside it) read
    from the API, never typed here. `topic='all'` returns both. Quote this instead of
    improvising a methodology explanation."""
    if topic not in (None, "climate", "all"):
        raise ValueError(f"Unknown topic {topic!r} -- use 'climate', 'all', or omit it.")
    out: dict = {} if topic == "climate" else methodology_notes()
    if topic in ("climate", "all"):
        total, fossil = await asyncio.gather(
            fetch_correlation("emissions-temperature", {"source": "owid_co2"}),
            fetch_correlation("emissions-temperature", {"source": "owid_co2", "variant": "fossil"}),
        )
        ctx = total.get("fit_context") or {}
        out.update(CLIMATE_METHODOLOGY)
        out["headline_derivation"] = {
            "outline": HEADLINE_DERIVATION_OUTLINE,
            "window": total["window"],
            "fit": total["fit"],
            "fit_context": {k: ctx.get(k) for k in (
                "method", "hac_sensitivity", "stability", "vs_ar6", "ar6_reference",
                "fit_quality_note", "land_use_sensitivity", "land_use_weight_scan",
            )},
            "secondary_fossil_only_fit": fossil["fit"],
            "caveats": total["caveats"],
        }
    return out
