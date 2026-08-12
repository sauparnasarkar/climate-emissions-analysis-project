import pytest

from mcp_server.resolution import CountryResolutionError
from mcp_server.tools.countries import get_country_profile


async def test_get_country_profile_exact_match(api_client):
    body = await get_country_profile("China")
    assert body["country"] == "China"
    assert body["years"]


async def test_get_country_profile_fuzzy_typo_resolves(api_client):
    body = await get_country_profile("Chinaa")
    assert body["country"] == "China"


async def test_get_country_profile_out_of_scope_country_raises(api_client):
    # Canada is present in the owid-co2-data.csv fixture (real ISO code, so it appears in
    # /countries' sovereign list) but is not part of the real FEATURED_COUNTRIES constant
    # that load_expanded_countries() falls back to when selected_countries.json is absent
    # (the case here, per full_data) -- a known country outside this tool's fixed scope.
    with pytest.raises(CountryResolutionError, match="outside 'expanded' scope"):
        await get_country_profile("Canada")
