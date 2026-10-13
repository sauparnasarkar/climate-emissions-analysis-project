"""Release 24.3: the country-share tool's summary (rank, share change and trend, Gt, rest of world), computed by the tool so the model quotes it."""

import pytest

from mcp_server.climate import SHARE_TREND_TOLERANCE_PP, share_ranking_summary, share_series_summary, share_trend
from mcp_server.tools.climate import get_country_cumulative_share

# --- the trend rule (ENHANCEMENTS.md D6: steady below 0.5 percentage points) ----------------------------------------


@pytest.mark.parametrize(
    "change,expected",
    [(None, None), (0.0, "steady"), (0.5, "steady"), (-0.5, "steady"), (0.51, "rising"), (-0.51, "falling"), (12.0, "rising"), (-3.2, "falling")],
)
def test_share_trend_edges_are_inclusive_of_the_tolerance(change, expected):
    assert SHARE_TREND_TOLERANCE_PP == 0.5
    assert share_trend(change) == expected


# --- series ---------------------------------------------------------------------------------------------------------


def pt(year, cum, share, annual_share=None, annual=None):
    return {"year": year, "cumulative_mt": cum, "share_pct": share, "annual_mt": annual, "annual_share_pct": annual_share}


def body(series, remainder_series=None, cumulative_from=1750):
    return {"series": series, "remainder_series": remainder_series or [], "cumulative_from": cumulative_from, "unit": "Mt CO2", "label": "x"}


ROSTER = {"year": 2024, "rows": [{"country": "USA", "rank": 1}, {"country": "CHN", "rank": 2}, {"country": "IND", "rank": 9}]}


def test_series_summary_gives_change_trend_gt_annual_share_and_rank():
    b = body([
        {"country": "CHN", "name": "China", "in_expanded_scope": True, "points": [pt(1970, 4000.0, 3.0, 5.0, 800.0), pt(2024, 285087.04, 15.42, 31.84, 12289.0)]},
        {"country": "USA", "name": "United States", "in_expanded_scope": True, "points": [pt(1970, 190000.0, 30.0, 28.0, 4000.0), pt(2024, 434866.56, 23.52, 12.71, 4904.0)]},
    ])
    s = share_series_summary(b, ROSTER, start_year=1970)
    china, us = s["countries"]
    assert (china["share_change_pp"], china["share_trend"], china["last_cumulative_gt"], china["last_annual_share_pct"]) == (12.42, "rising", 285.1, 31.84)
    assert (us["share_change_pp"], us["share_trend"], us["last_cumulative_gt"]) == (-6.48, "falling", 434.9)
    assert (china["rank"], china["rank_of"], us["rank"]) == (2, 3, 1) and s["trend_window"] == [1970, 2024] and s["rank_year"] == 2024
    assert s["trend_tolerance_pp"] == 0.5 and china["in_expanded_scope"] is True


def test_a_rank_is_given_only_when_the_series_ends_in_the_rankings_year():
    b = body([{"country": "CHN", "name": "China", "points": [pt(1970, 1.0, 3.0), pt(2000, 2.0, 7.0)]}])
    c = share_series_summary(b, ROSTER, start_year=None)["countries"][0]
    assert c["rank"] is None and c["rank_of"] is None  # 2000 is not the roster's 2024: never a latest-year rank beside an earlier window
    assert c["share_trend"] == "rising"


def test_a_country_missing_from_the_roster_has_no_rank_and_a_single_point_has_no_change():
    b = body([{"country": "ZZZ", "name": "Zed", "points": [pt(2024, 1.0, 0.1)]}])
    c = share_series_summary(b, ROSTER, start_year=None)["countries"][0]
    assert c["rank"] is None and c["share_change_pp"] is None and c["share_trend"] is None


def test_an_empty_series_is_all_nulls_not_an_error():
    s = share_series_summary(body([{"country": "ZZZ", "name": "Zed", "points": []}]), ROSTER, start_year=None)
    assert s["countries"][0]["last_year"] is None and s["trend_window"] is None and "rest_of_world" not in s


def test_rest_of_world_is_the_world_total_minus_the_countries_shown_and_only_for_a_world_denominator():
    series = [
        {"country": "CHN", "name": "China", "points": [pt(2023, 270000.0, 15.0), pt(2024, 285000.0, 15.4)]},
        {"country": "USA", "name": "United States", "points": [pt(2023, 430000.0, 23.6), pt(2024, 435000.0, 23.5)]},
    ]
    rem = [{"year": 2024, "world_cumulative_mt": 1_850_000.0, "world_annual_mt": 38600.0}, {"year": 2023, "world_cumulative_mt": 1_810_000.0, "world_annual_mt": 38000.0}]
    s = share_series_summary(body(series, rem), ROSTER, start_year=None)
    row = s["rest_of_world"]
    assert row["year"] == 2024 and row["cumulative_mt"] == 1_130_000.0 and row["cumulative_gt"] == 1130.0 and row["share_pct"] == round(100 - 15.4 - 23.5, 2)
    assert s["world_cumulative_gt"] == 1850.0 and "international aviation and shipping" in row["includes"]
    assert "rest_of_world" not in share_series_summary(body(series, None), ROSTER, None)  # PRIMAP-hist: no remainder, no World total to subtract from


def test_a_start_year_after_the_first_record_is_explained_not_applied():
    b = body([{"country": "CHN", "name": "China", "points": [pt(1990, 1.0, 5.0)]}], cumulative_from=1750)
    s = share_series_summary(b, ROSTER, start_year=1990)
    assert s["counted_from"] == 1750 and "never restarted" in s["window_note"] and "1750" in s["window_note"]
    assert "window_note" not in share_series_summary(b, ROSTER, start_year=None) and "window_note" not in share_series_summary(b, ROSTER, start_year=1750)


# --- ranking --------------------------------------------------------------------------------------------------------


def row(rank, name, share, mt):
    return {"rank": rank, "name": name, "share_pct": share, "cumulative_mt": mt, "in_expanded_scope": rank < 3}


def test_ranking_summary_reports_the_remainder_and_what_a_limit_leaves_out():
    b = {"year": 2024, "rows": [row(1, "United States", 23.52, 434866.56), row(2, "China", 15.42, 285087.04)], "total_cumulative_mt": 1_849_000.0,
         "remainder": {"share_pct": 2.49}}
    s = share_ranking_summary(b)
    assert s["top"][0] == {"rank": 1, "name": "United States", "share_pct": 23.52, "cumulative_gt": 434.9, "cumulative_text": "434.9 GtCO₂", "in_expanded_scope": True}
    assert s["shown_share_pct_total"] == 38.94 and s["remainder_share_pct"] == 2.49 and s["world_cumulative_gt"] == 1849.0
    assert s["not_shown_share_pct"] == round(100 - 38.94 - 2.49, 2)  # held by the countries the limit left out: rows + remainder are not 100


def test_ranking_without_a_remainder_has_no_remainder_fields_and_an_empty_one_is_unavailable():
    s = share_ranking_summary({"year": 2024, "rows": [row(1, "A", 60.0, 1.0)], "total_cumulative_mt": 1.0, "remainder": None})
    assert "remainder_share_pct" not in s and "not_shown_share_pct" not in s
    empty = share_ranking_summary({"year": 1700, "rows": [], "total_cumulative_mt": None, "remainder": None})
    assert empty["shown_share_pct_total"] is None and "No ranking rows" in empty["unavailable"]


# --- the tool, end to end on the stub data ----------------------------------------------------------------------------


async def test_the_tool_summary_carries_the_new_fields_for_a_series(climate_client):
    full = await get_country_cumulative_share(limit=50)
    codes = [r["country"] for r in full["rows"]][:2]
    out = await get_country_cumulative_share(countries=codes)
    s = out["summary"]
    assert s["mode"] == "series" and len(s["countries"]) == 2 and s["trend_window"][0] <= s["trend_window"][1]
    for c, r in zip(s["countries"], full["rows"][:2]):
        assert c["rank"] == r["rank"] and c["rank_of"] == len(full["rows"]) and c["share_trend"] in ("rising", "falling", "steady")
        assert c["last_cumulative_gt"] == round(c["last_cumulative_mt"] / 1000, 1)
        assert c["in_expanded_scope"] in (True, False)
    # rest of world = World minus what is shown, and shown + rest = 100 (OWID shares are of the World total)
    row = s["rest_of_world"]
    assert row["share_pct"] == pytest.approx(100 - sum(c["last_share_pct"] for c in s["countries"]), abs=0.02)
    assert row["cumulative_mt"] == pytest.approx(out["remainder_series"][-1]["world_cumulative_mt"] - sum(c["last_cumulative_mt"] for c in s["countries"]), abs=0.2)


async def test_the_tool_explains_a_start_year_instead_of_restarting_the_total(climate_client):
    code = (await get_country_cumulative_share())["rows"][0]["country"]
    out = await get_country_cumulative_share(countries=[code], start_year=1950)
    assert out["summary"]["counted_from"] == out["cumulative_from"] and "never restarted" in out["summary"]["window_note"]
    assert out["series"][0]["points"][0]["year"] == 1950  # the years shown start there; the total did not


async def test_primap_series_has_no_rest_of_world_because_it_has_no_world_total(climate_client):
    code = (await get_country_cumulative_share(source="primap_hist"))["rows"][0]["country"]
    out = await get_country_cumulative_share(countries=[code], source="primap_hist")
    assert "rest_of_world" not in out["summary"] and out["remainder_series"] == []


async def test_the_ranking_summary_carries_the_remainder_and_not_shown_share(climate_client):
    out = await get_country_cumulative_share(limit=2)
    s = out["summary"]
    assert s["remainder_share_pct"] == pytest.approx(out["remainder"]["share_pct"], abs=0.01)
    assert s["shown_share_pct_total"] + s["remainder_share_pct"] + s["not_shown_share_pct"] == pytest.approx(100.0, abs=0.03)


# --- units: a live answer wrote "434.9 Mt" for the United States' 434.9 Gt ----------------------------------------------------------------------------------


def test_the_summary_does_not_carry_the_bodys_mt_unit_beside_gt_fields_and_says_what_each_suffix_means():
    from mcp_server.climate import SHARE_SUMMARY_UNITS

    assert set(SHARE_SUMMARY_UNITS) == {"_mt", "_gt", "_pct", "_pp", "_text"}
    assert "GtCO₂" in SHARE_SUMMARY_UNITS["_gt"] and "MtCO₂" in SHARE_SUMMARY_UNITS["_mt"] and "1,000" in SHARE_SUMMARY_UNITS["_gt"]


def test_cumulative_values_come_with_a_ready_to_quote_text_that_carries_the_unit():
    from mcp_server.climate import gt_text

    assert gt_text(434_866.56) == "434.9 GtCO₂" and gt_text(1_849_100.0) == "1,849.1 GtCO₂" and gt_text(None) is None
    b = {"series": [{"country": "USA", "name": "United States", "points": [pt(2023, 430000.0, 23.6), pt(2024, 434866.56, 23.52)]}], "cumulative_from": 1750,
         "remainder_series": [{"year": 2024, "world_cumulative_mt": 1_849_100.0, "world_annual_mt": 38600.0}]}
    s = share_series_summary(b, {"year": 2024, "rows": [{"country": "USA", "rank": 1}]}, None)
    assert s["countries"][0]["last_cumulative_text"] == "434.9 GtCO₂" and s["world_cumulative_text"] == "1,849.1 GtCO₂" and s["rest_of_world"]["cumulative_text"] == "1,414.2 GtCO₂"
    r = share_ranking_summary({"year": 2024, "rows": [row(1, "United States", 23.52, 434866.56)], "total_cumulative_mt": 1_849_100.0, "remainder": {"share_pct": 2.49}})
    assert r["top"][0]["cumulative_text"] == "434.9 GtCO₂" and r["world_cumulative_text"] == "1,849.1 GtCO₂"


async def test_the_tool_summary_has_a_units_map_and_no_single_unit(climate_client):
    for out in (await get_country_cumulative_share(limit=3), await get_country_cumulative_share(countries=["AAA"])):
        assert "unit" not in out["summary"] and out["summary"]["units"]["_gt"].startswith("GtCO₂")
        assert out["unit"] == "Mt CO₂"  # the body is unchanged (its raw values really are Mt; the server's typography pass writes the subscript)
