"""SPEC.md §5 direct wraps: get_scenario_projection, get_scenario_cumulative_impact,
compare_scenarios_across_countries.
"""

from __future__ import annotations

from ..client import get_client
from ..resolution import fetch_country_lists, resolve_countries, resolve_country
from ..server import mcp


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
    Moderate, Aggressive."""
    client = get_client()
    return await client.get("/scenarios/cumulative", params={"sort_by": sort_by})


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
