"""SPEC.md §5 direct wraps: get_scenario_projection, get_scenario_cumulative_impact,
compare_scenarios_across_countries.
"""

from __future__ import annotations

from ..client import get_client
from ..resolution import fetch_country_lists, resolve_countries, resolve_country
from ..server import mcp
from ..trimming import trim


@mcp.tool()
async def get_scenario_projection(
    view: str = "single",
    country: str | None = None,
    scope: str = "featured",
) -> dict:
    """BAU/Moderate/Aggressive emissions trajectories, 2025-2040. `view` is 'single' (one
    country -- `country` is required) or 'global' (aggregated across `scope`'s pool).
    `scope` is 'featured' or 'expanded' -- no 'sovereign' option on this endpoint, unlike
    the historical tools -- and only has an effect when `view='global'`; it's ignored for
    `view='single'`. For `view='single'`, `country` is resolved against the expanded
    (~40-country) scope.

    Do NOT call this once per country to build a multi-country comparison -- use
    compare_scenarios_across_countries instead, which fetches every country's BAU/Moderate/
    Aggressive trajectories concurrently in one call rather than costing one MCP round trip
    per country.

    Use this family only when the question explicitly invokes scenarios, policy pathways, or
    BAU/Moderate/Aggressive (or synonyms like "business as usual", "aggressive climate
    action") -- i.e. comparing multiple possible futures. A plain "projection"/"forecast"
    question with no scenario language means the single statistical extrapolation -- use
    get_forecast/get_forecast_comparison/get_forecast_summary instead.
    """
    if view == "single" and country is None:
        # The wrapped API rejects this with a 400 too, but its detail message doesn't
        # survive httpx's raise_for_status() -> str(exc) path, so the agent would otherwise
        # see a generic "400 Bad Request" with no indication of what to fix.
        raise ValueError("country is required when view='single'")
    resolved_country = country
    if view == "single":
        lists = await fetch_country_lists()
        resolved_country = resolve_country(country, lists, scope="expanded")
    client = get_client()
    return await client.get(
        "/scenarios/timeseries",
        params={"view": view, "country": resolved_country, "scope": scope},
    )


@mcp.tool()
async def get_scenario_cumulative_impact(sort_by: str = "BAU") -> dict:
    """2025-2040 cumulative emissions by scenario, ranked. `sort_by` is one of BAU,
    Moderate, Aggressive. This tool has no country-list argument, so trimming (SPEC.md
    §3.2) always applies when there are more than 10 rows: capped to the top 10 (the
    wrapped API already returns `rows` pre-sorted by `sort_by`'s cumulative value
    descending, so this only slices, never re-sorts), with a scope_note explaining the
    cap.

    Do NOT call this once per scenario to compare BAU/Moderate/Aggressive -- every row
    already carries all three scenarios' cumulative values (`sort_by` only changes which
    scenario ranks the returned rows and which 10 get kept by the trim above, it never
    removes a scenario's values from the response). One call already answers "which
    countries rank highest under each scenario"; call it again with a different `sort_by`
    only if the top-10 set itself needs to be re-ranked by a different scenario, not to
    fetch scenario values you don't already have."""
    client = get_client()
    body = await client.get("/scenarios/cumulative", params={"sort_by": sort_by})
    trimmed, note = trim(
        body["rows"],
        scope_label="the full scenario dataset",
        sort_key_label=f"cumulative {sort_by} CO2 descending",
    )
    body["rows"] = trimmed
    if note is not None:
        body["scope_note"] = note
    return body


@mcp.tool()
async def compare_scenarios_across_countries(countries: list[str]) -> dict:
    """Per-scenario (BAU/Moderate/Aggressive) trajectories for multiple countries at once --
    one series per country per scenario, not summed across countries (unlike
    get_scenario_cumulative_impact). `countries` is required; each name is resolved against
    the expanded (~40-country) scope."""
    lists = await fetch_country_lists()
    resolved = resolve_countries(countries, lists, scope="expanded")
    client = get_client()
    return await client.get("/scenarios/compare", params={"countries": resolved})
