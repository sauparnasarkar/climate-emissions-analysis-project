from mcp_server.resolution import CountryLists, fetch_country_lists
from mcp_server.server import list_countries


async def test_list_countries_tool_returns_the_three_scopes(api_client):
    body = await list_countries()
    assert set(body.keys()) == {"featured", "expanded", "sovereign"}
    assert isinstance(body["sovereign"], list)


async def test_fetch_country_lists_wraps_the_same_data(api_client):
    lists = await fetch_country_lists()
    assert isinstance(lists, CountryLists)
    assert lists.featured
    assert lists.sovereign
