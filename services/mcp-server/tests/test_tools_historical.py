import pytest

from mcp_server.resolution import CountryResolutionError
from mcp_server.tools.historical import get_gas_composition_by_decade, get_historical_emissions


async def test_get_historical_emissions_explicit_countries(api_client):
    body = await get_historical_emissions(countries=["China", "Germany"], gas="co2")
    names = {s["name"] for s in body["series"]}
    assert names <= {"China", "Germany"}
    assert body["gas"] == "co2"


async def test_get_historical_emissions_typo_in_explicit_list_resolves(api_client):
    body = await get_historical_emissions(countries=["Chinaa"], gas="co2")
    names = {s["name"] for s in body["series"]}
    assert names == {"China"}


async def test_get_historical_emissions_omitted_countries_resolves_full_scope_pool(api_client):
    # scope="sovereign" with no countries must NOT fall back to the wrapped API's own
    # FEATURED_COUNTRIES[:5] default (SPEC.md §4) -- Canada only appears at sovereign scope.
    body = await get_historical_emissions(scope="sovereign")
    names = {s["name"] for s in body["series"]}
    assert "Canada" in names


async def test_get_historical_emissions_out_of_scope_explicit_country_raises(api_client):
    with pytest.raises(CountryResolutionError, match="outside 'featured' scope"):
        await get_historical_emissions(countries=["Canada"], scope="featured")


async def test_get_gas_composition_by_decade_omitted_countries_respects_scope(api_client):
    resp_expanded = await get_gas_composition_by_decade()
    resp_sovereign = await get_gas_composition_by_decade(scope="sovereign")
    assert resp_expanded != resp_sovereign


async def test_get_gas_composition_by_decade_explicit_countries_resolved(api_client):
    body = await get_gas_composition_by_decade(countries=["Chinaa"], scope="sovereign")
    assert body["decades"]
