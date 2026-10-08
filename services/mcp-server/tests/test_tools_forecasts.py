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


async def test_get_forecast_summary_no_scope_note_when_at_or_under_cap(api_client):
    # Fixture data only has 3 countries with forecasts -- well under the trim cap.
    body = await get_forecast_summary(scope="featured")
    assert "scope_note" not in body


async def test_get_model_comparison_returns_columns_and_rows(api_client):
    body = await get_model_comparison()
    assert "columns" in body
    assert "rows" in body


class _FakeSummaryClient:
    """12 expanded-scope rows where the 2040 order differs from the 2020 order, so the cap column matters."""

    async def get(self, path, params=None):
        assert path == "/forecasts/summary"
        rows = [
            {"country": f"C{i}", "actual_2020": 100.0 - i, "forecast_2030": 0.0, "forecast_2035": 0.0,
             "forecast_2040": 10.0 * i, "pct_change_2020_2040": float(i)}
            for i in range(12)
        ]
        return {"rows": rows}


async def test_get_forecast_summary_rank_by_changes_the_cap_column(monkeypatch):
    from mcp_server.tools import forecasts

    monkeypatch.setattr(forecasts, "get_client", lambda: _FakeSummaryClient())
    by_2020 = await get_forecast_summary(scope="expanded")
    by_2040 = await get_forecast_summary(scope="expanded", rank_by="forecast_2040")
    assert by_2020["ranked_by"] == "actual_2020" and by_2020["rows"][0]["country"] == "C0"
    # C11 has the highest 2040 forecast but the lowest 2020 actual: only ranking by 2040 keeps it.
    assert by_2040["ranked_by"] == "forecast_2040"
    assert [r["country"] for r in by_2040["rows"]][:3] == ["C11", "C10", "C9"]
    assert "forecast_2040 descending" in by_2040["scope_note"]
    assert "C11" not in {r["country"] for r in by_2020["rows"]}


async def test_get_forecast_summary_rejects_an_unknown_rank_column(api_client):
    with pytest.raises(ValueError, match="rank_by must be one of"):
        await get_forecast_summary(scope="featured", rank_by="forecast_2099")
