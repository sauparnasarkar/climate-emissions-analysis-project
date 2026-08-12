import pytest

from mcp_server.resolution import CountryResolutionError
from mcp_server.tools.forecasts import get_forecast, get_forecast_summary, get_model_comparison


async def test_get_forecast_returns_series_for_a_known_country(api_client):
    body = await get_forecast("China")
    assert body["country"] == "China"
    assert body["forecast_years"]


async def test_get_forecast_out_of_scope_country_raises(api_client):
    with pytest.raises(CountryResolutionError, match="outside 'expanded' scope"):
        await get_forecast("Canada")


async def test_get_forecast_summary_returns_rows(api_client):
    body = await get_forecast_summary(scope="featured")
    assert isinstance(body["rows"], list)


async def test_get_model_comparison_returns_columns_and_rows(api_client):
    body = await get_model_comparison()
    assert "columns" in body
    assert "rows" in body
