import pytest

from api.tests.conftest import owid_raw_change_summary_df, owid_raw_world_map_series_df
from mcp_server.resolution import CountryResolutionError
from mcp_server.tools.composed import (
    get_emissions_change_summary,
    get_forecast_comparison,
    get_methodology_notes,
    get_top_emitters,
)


async def test_get_top_emitters_ranks_descending_and_excludes_none(bare_api_client, data_dir):
    owid_raw_world_map_series_df().to_csv(data_dir / "owid-co2-data.csv", index=False)
    body = await get_top_emitters(year=2000, n=10)
    assert body["year"] == 2000
    countries = [row["country"] for row in body["emitters"]]
    # Monaco is present every year with co2=None -- must be excluded, not ranked as 0.
    assert "Monaco" not in countries
    # China's synthetic series grows well above the US's declining one by 2000.
    assert countries[0] == "China"
    co2_values = [row["co2"] for row in body["emitters"]]
    assert co2_values == sorted(co2_values, reverse=True)


async def test_get_top_emitters_respects_n(bare_api_client, data_dir):
    owid_raw_world_map_series_df().to_csv(data_dir / "owid-co2-data.csv", index=False)
    body = await get_top_emitters(year=2000, n=1)
    assert len(body["emitters"]) == 1
    assert body["emitters"][0]["country"] == "China"


async def test_get_top_emitters_unknown_year_raises(bare_api_client, data_dir):
    owid_raw_world_map_series_df().to_csv(data_dir / "owid-co2-data.csv", index=False)
    with pytest.raises(ValueError, match="No data for year 1899"):
        await get_top_emitters(year=1899)


async def test_get_forecast_comparison_explicit_countries_returns_all_uncapped(api_client):
    body = await get_forecast_comparison(countries=["China", "United States", "Germany"])
    names = {f["country"] for f in body["forecasts"]}
    assert names == {"China", "United States", "Germany"}
    assert "scope_note" not in body


async def test_get_forecast_comparison_typo_in_explicit_list_resolves(api_client):
    body = await get_forecast_comparison(countries=["Chinaa"])
    assert body["forecasts"][0]["country"] == "China"


async def test_get_forecast_comparison_omitted_countries_no_scope_note_when_under_cap(api_client):
    # Fixture data only has 3 countries with forecasts -- well under the trim cap; also
    # proves the omitted-countries path resolves and fetches the scope pool concurrently
    # rather than erroring, since every fixture country actually has forecast data.
    body = await get_forecast_comparison(scope="featured")
    assert "scope_note" not in body
    assert len(body["forecasts"]) >= 1


async def test_get_forecast_comparison_out_of_scope_explicit_country_raises(api_client):
    with pytest.raises(CountryResolutionError, match="outside 'expanded' scope"):
        await get_forecast_comparison(countries=["Canada"])


async def test_get_forecast_comparison_rejects_sovereign_scope(api_client):
    with pytest.raises(ValueError, match="scope must be 'featured' or 'expanded'"):
        await get_forecast_comparison(scope="sovereign")


async def test_get_emissions_change_summary_passes_scope_and_top_n_through(bare_api_client, data_dir):
    owid_raw_change_summary_df().to_csv(data_dir / "owid-co2-data.csv", index=False)
    body = await get_emissions_change_summary(scope="sovereign", top_n=1)
    assert body["scope"] == "sovereign"
    assert len(body["top_increases"]) == 1
    assert len(body["top_decreases"]) == 1
    # Counts stay the true totals even though the movers lists are trimmed to top_n=1 --
    # proves this tool is a thin pass-through of the endpoint's own response, not
    # re-deriving counts client-side from the (already top_n-capped) movers lists.
    assert body["increased_count"] > 1
    assert body["decreased_count"] > 1


async def test_get_emissions_change_summary_default_scope_is_sovereign(bare_api_client, data_dir):
    owid_raw_change_summary_df().to_csv(data_dir / "owid-co2-data.csv", index=False)
    body = await get_emissions_change_summary()
    assert body["scope"] == "sovereign"
    # 7 countries in the fixture; sovereign scope reaches all of them (see
    # api/tests/test_historical.py's own test_change_summary_scope_changes_pool_size for
    # the featured-vs-sovereign contrast this tool's default is meant to preserve).
    assert body["country_pool_size"] == 7


async def test_get_emissions_change_summary_invalid_scope_raises_before_any_http_call():
    # No api_client/bare_api_client fixture -- the validation must happen before get_client()
    # is ever called, matching get_forecast_comparison's own scope-validation test.
    with pytest.raises(ValueError, match="scope must be 'featured', 'expanded', or 'sovereign'"):
        await get_emissions_change_summary(scope="global")


async def test_get_methodology_notes_returns_canonical_sections():
    body = await get_methodology_notes()
    assert set(body.keys()) == {
        "forecasting_methodology",
        "model_comparison",
        "data_provenance",
        "scope_criteria",
    }
    assert "ETS(A,Ad,N)" in body["forecasting_methodology"]
