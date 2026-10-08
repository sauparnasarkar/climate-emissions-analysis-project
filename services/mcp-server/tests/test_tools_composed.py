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

async def test_get_forecast_comparison_rejects_an_explicit_empty_countries_list(api_client):
    with pytest.raises(CountryResolutionError, match="empty list"):
        await get_forecast_comparison(countries=[])


async def test_get_top_emitters_defaults_to_the_latest_year_with_data(bare_api_client, data_dir):
    # Reported in the Ask-page design review: the agent ranked 2020 because `year` was required and
    # the model had to guess one. Omitting it must use the latest populated year, and say which.
    owid_raw_world_map_series_df().to_csv(data_dir / "owid-co2-data.csv", index=False)
    explicit_latest = await get_top_emitters(year=2024, n=3)
    default = await get_top_emitters(n=3)
    assert default["year"] == 2024 and default == explicit_latest


async def test_get_top_emitters_explicit_year_is_unchanged(bare_api_client, data_dir):
    owid_raw_world_map_series_df().to_csv(data_dir / "owid-co2-data.csv", index=False)
    assert (await get_top_emitters(year=2000, n=1))["year"] == 2000


async def test_get_top_emitters_default_skips_a_trailing_all_null_year():
    import mcp_server.client as mcp_client

    class FakeClient:
        async def get(self, path, params=None):
            return {
                "years": [2022, 2023, 2024],
                "countries": ["A", "B"],
                "iso_codes": ["AAA", "BBB"],
                "values": [[5.0, 9.0], [6.0, 8.0], [None, None]],  # 2024 column exists but is empty
            }

    mcp_client.set_client(FakeClient())
    try:
        body = await get_top_emitters(n=2)
    finally:
        mcp_client.set_client(None)
    assert body["year"] == 2023 and [r["country"] for r in body["emitters"]] == ["B", "A"]


async def test_get_top_emitters_reports_the_ranked_count_total_and_top_n_share(bare_api_client, data_dir):
    owid_raw_world_map_series_df().to_csv(data_dir / "owid-co2-data.csv", index=False)
    full = await get_top_emitters(year=2000, n=100)
    top1 = await get_top_emitters(year=2000, n=1)
    assert full["n_ranked"] == len(full["emitters"]) and full["top_n_share_pct"] == 100.0
    assert top1["n_ranked"] == full["n_ranked"] and top1["total_mt"] == full["total_mt"]
    assert top1["total_mt"] == round(sum(r["co2"] for r in full["emitters"]), 3)
    assert top1["top_n_share_pct"] == round(top1["emitters"][0]["co2"] / top1["total_mt"] * 100, 1)
    assert 0 < top1["top_n_share_pct"] < 100


async def test_get_top_emitters_share_is_none_when_the_total_is_zero():
    import mcp_server.client as mcp_client

    class FakeClient:
        async def get(self, path, params=None):
            return {"years": [2024], "countries": ["A"], "iso_codes": ["AAA"], "values": [[0.0]]}

    mcp_client.set_client(FakeClient())
    try:
        body = await get_top_emitters()
    finally:
        mcp_client.set_client(None)
    assert body["total_mt"] == 0 and body["top_n_share_pct"] is None


def test_returned_methodology_text_uses_co2_subscript_degree_sign_and_en_dashes():
    # Ask-page design review: these strings reach users (through the agent's answers and alerts), so
    # plain "CO2", "degC" and a "--" stand-in for a dash must not appear. File names and identifiers
    # (owid-co2-data.csv, `owid_co2`) are not text and stay as they are.
    import re

    from mcp_server.methodology import (
        CLIMATE_METHODOLOGY,
        HEADLINE_DERIVATION_OUTLINE,
        SCOPE_LABELS,
        methodology_notes,
    )

    texts = [*CLIMATE_METHODOLOGY.values(), *HEADLINE_DERIVATION_OUTLINE, *SCOPE_LABELS.values(), *methodology_notes().values()]
    assert len(texts) > 15
    for t in texts:
        assert not re.search(r"\bCO2e?\b|GtCO2|non-CO2|degC", t), t
        assert " -- " not in t, t
    assert "owid-co2-data.csv" in methodology_notes()["data_provenance"]  # the file name is untouched


async def test_relationship_labels_use_the_co2_subscript(climate_client):
    from mcp_server.tools.climate import get_emissions_temperature_relationship

    for kwargs in ({}, {"variant": "fossil", "baseline": "1970"}, {"baseline": "1990"}):
        label = (await get_emissions_temperature_relationship(**kwargs))["summary"]["relationship"]
        assert "CO2" not in label, label
