import pytest

from api.tests.conftest import owid_raw_headline_df
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


async def test_get_historical_emissions_includes_per_capita_and_co2_only_fields(api_client):
    # Values match owid_raw_df()'s fixture literals exactly (api/tests/conftest.py).
    body = await get_historical_emissions(countries=["China"], gas="co2")
    series = body["series"][0]
    assert series["per_capita"] == [7.0, 7.5, 8.0, 8.5, 9.0]
    assert series["yoy_pct_change"] == [None, 2.1, 2.2, 2.3, 2.4]
    assert series["per_gdp"] == [0.40, 0.42, 0.44, 0.46, 0.48]


async def test_get_historical_emissions_non_co2_gas_has_per_capita_but_not_growth_or_gdp(api_client):
    # OWID doesn't compute year-over-year growth or per-GDP for methane -- must be None,
    # not a fabricated or silently-CO2 value.
    body = await get_historical_emissions(countries=["China"], gas="methane")
    series = body["series"][0]
    assert series["per_capita"] == [0.20, 0.21, 0.22, 0.23, 0.24]
    assert series["yoy_pct_change"] == [None, None, None, None, None]
    assert series["per_gdp"] == [None, None, None, None, None]


async def test_get_historical_emissions_omitted_countries_trims_over_cap(bare_api_client, data_dir):
    # 12 sovereign countries with real 2024 magnitude separation -- Vietnam/Poland are the
    # two lowest and must be excluded by the top-10 cap; China is highest and must lead.
    owid_raw_headline_df().to_csv(data_dir / "owid-co2-data.csv", index=False)
    body = await get_historical_emissions(scope="sovereign")
    names = [s["name"] for s in body["series"]]
    assert len(names) == 10
    assert names[0] == "China"
    assert "Vietnam" not in names
    assert "Poland" not in names
    assert "scope_note" in body
    assert "10 of 12" in body["scope_note"]


async def test_get_gas_composition_by_decade_omitted_countries_respects_scope(api_client):
    resp_expanded = await get_gas_composition_by_decade()
    resp_sovereign = await get_gas_composition_by_decade(scope="sovereign")
    assert resp_expanded != resp_sovereign


async def test_get_gas_composition_by_decade_explicit_countries_resolved(api_client):
    # DecadeGasShare carries no country field (it's an aggregate across the given
    # countries, not a per-country breakdown), so resolution is proven by equivalence with
    # the exact-name call rather than by inspecting a name in the response.
    typo_body = await get_gas_composition_by_decade(countries=["Chinaa"], scope="sovereign")
    exact_body = await get_gas_composition_by_decade(countries=["China"], scope="sovereign")
    assert typo_body == exact_body
