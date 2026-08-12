import pytest

from mcp_server.resolution import CountryResolutionError
from mcp_server.tools.scenarios import (
    compare_scenarios_across_countries,
    get_scenario_cumulative_impact,
    get_scenario_projection,
)


async def test_get_scenario_projection_single_view_resolves_country(api_client):
    body = await get_scenario_projection(view="single", country="Chinaa")
    assert body["scenarios"]


async def test_get_scenario_projection_global_view_ignores_country(api_client):
    body = await get_scenario_projection(view="global", scope="featured")
    assert body["scenarios"]


async def test_get_scenario_projection_single_view_without_country_raises_upfront(api_client):
    with pytest.raises(ValueError, match="country is required"):
        await get_scenario_projection(view="single", country=None)


async def test_get_scenario_cumulative_impact_returns_rows(api_client):
    body = await get_scenario_cumulative_impact(sort_by="BAU")
    assert isinstance(body["rows"], list)


async def test_compare_scenarios_across_countries_resolves_each_name(api_client):
    body = await compare_scenarios_across_countries(["China", "Germany"])
    assert set(body["countries"]) == {"China", "Germany"}


async def test_compare_scenarios_across_countries_out_of_scope_raises(api_client):
    with pytest.raises(CountryResolutionError, match="outside 'expanded' scope"):
        await compare_scenarios_across_countries(["Canada"])
