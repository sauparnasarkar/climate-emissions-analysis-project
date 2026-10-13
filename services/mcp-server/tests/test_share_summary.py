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
    assert s["counted_from"] == 1750 and "since_year=1990" in s["window_note"] and "1750" in s["window_note"] and "EMITTED" in s["window_note"]
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
    assert out["summary"]["counted_from"] == out["cumulative_from"] and "since_year=1950" in out["summary"]["window_note"]
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


# --- "since YYYY": emissions in a period (Release 24.7, D7) ----------------------------------------------------------------------------------------------------------


import pytest  # noqa: E402

from mcp_server.climate import SHARE_FIRST_PUBLISHED_YEAR, check_since_year, period_rows, since_ranking_summary, since_series_block, world_total_mt  # noqa: E402


def test_since_year_must_leave_a_published_base_year():
    assert SHARE_FIRST_PUBLISHED_YEAR == 1850
    check_since_year(1851, 2024)
    check_since_year(2024, 2024)  # the latest year alone is a valid period
    for bad in (1850, 1800, 2025):
        with pytest.raises(ValueError, match="between 1851 and 2024"):
            check_since_year(bad, 2024)


def ranking(year, rows, world=None, total=None):
    out = {"year": year, "rows": [{"country": c, "name": n, "cumulative_mt": mt, "in_expanded_scope": True} for c, n, mt in rows], "total_cumulative_mt": total, "remainder": None}
    if world is not None:
        out["remainder"] = {"world_cumulative_mt": world}
    return out


def test_period_rows_are_the_end_total_minus_the_base_total_ranked_and_a_new_country_starts_from_zero():
    end = ranking(2024, [("USA", "United States", 434_866.0), ("CHN", "China", 285_087.0), ("NEW", "Newland", 50.0)], world=1_849_000.0)
    base = ranking(1969, [("USA", "United States", 150_000.0), ("CHN", "China", 10_000.0)], world=900_000.0)  # Newland had no row in 1969
    rows, world = period_rows(end, base)
    assert world == 949_000.0
    assert [(r["country"], r["rank"], r["emitted_mt"]) for r in rows] == [("USA", 1, 284_866.0), ("CHN", 2, 275_087.0), ("NEW", 3, 50.0)]  # Newland: base 0
    assert rows[0]["emitted_text"] == "284.9 GtCO₂" and rows[0]["share_of_period_pct"] == round(284_866 / 949_000 * 100, 2)


def test_a_country_whose_record_ended_emitted_nothing_in_a_later_period_and_never_negative():
    end = ranking(2024, [("DDD", "Dland", 262.0)], total=262.0)
    base = ranking(1979, [("DDD", "Dland", 262.0)], total=262.0)
    rows, world = period_rows(end, base)
    assert rows[0]["emitted_mt"] == 0.0 and world == 0.0 and rows[0]["share_of_period_pct"] is None  # no World emissions in the period: no share, not a division error


def test_the_world_total_is_the_remainders_for_owid_and_the_sum_of_countries_for_primap():
    assert world_total_mt(ranking(2024, [], world=1_849_000.0, total=1_803_000.0)) == 1_849_000.0
    assert world_total_mt(ranking(2024, [], total=1_803_000.0)) == 1_803_000.0


def test_the_series_block_has_the_period_the_rest_of_world_and_the_widgets_base_values():
    end = ranking(2024, [("USA", "United States", 434_866.0), ("CHN", "China", 285_087.0)], world=1_849_000.0)
    base = ranking(1969, [("USA", "United States", 150_000.0), ("CHN", "China", 10_000.0)], world=900_000.0)
    rows, world = period_rows(end, base)
    b = since_series_block(rows, world, ["CHN"], 1970, 2024, True, world_total_mt(base))
    assert b["period"] == "1970–2024" and b["rank_of"] == 2 and b["world_emitted_text"] == "949.0 GtCO₂" and b["world_base_cumulative_mt"] == 900_000.0
    assert b["countries"] == [{"country": "CHN", "name": "China", "emitted_mt": 275_087.0, "emitted_gt": 275.1, "emitted_text": "275.1 GtCO₂", "share_of_period_pct": 28.99, "rank": 2, "base_cumulative_mt": 10_000.0}]
    assert b["rest_of_world"]["emitted_text"] == "673.9 GtCO₂" and "international aviation and shipping" in b["basis"]
    assert "rest_of_world" not in since_series_block(rows, world, ["CHN"], 1970, 2024, False, 0.0) and "source's own total" in since_series_block(rows, world, ["CHN"], 1970, 2024, False, 0.0)["basis"]


def test_the_ranking_summary_names_the_period_and_what_the_rows_shown_leave():
    end = ranking(2024, [("USA", "United States", 434_866.0), ("CHN", "China", 285_087.0)], world=1_849_000.0)
    base = ranking(1969, [("USA", "United States", 150_000.0), ("CHN", "China", 10_000.0)], world=900_000.0)
    rows, world = period_rows(end, base)
    s = since_ranking_summary(rows, rows[:1], world, 1970, 2024, True)
    assert s["since"]["period"] == "1970–2024" and s["top"][0]["emitted_text"] == "284.9 GtCO₂" and s["n_rows"] == 1
    assert s["shown_share_of_period_pct_total"] == 30.02 and s["not_shown_share_of_period_pct"] == 69.98  # 284.9 of the World's 949.0 Gt; the rest includes the other country and international transport


# the stub data: AAA 10/yr from 1840, BBB 5/yr from 1900, CCC 1/yr (1950-52 missing), DDD 2/yr until 1970; the World adds 3/yr of international transport


async def test_since_a_year_is_the_period_total_and_equals_the_sum_of_the_annual_values(climate_client):
    out = await get_country_cumulative_share(countries=["AAA"], since_year=1950)
    c = out["summary"]["since"]["countries"][0]
    assert c["emitted_mt"] == 510.0 == 10.0 * (2000 - 1950 + 1)  # the cumulative at 2000 minus the cumulative at 1949
    assert c["emitted_mt"] == pytest.approx(sum(p["annual_mt"] for p in out["series"][0]["points"]))  # the identity, on the points the tool returned
    assert out["series"][0]["points"][0]["year"] == 1950 and out["summary"]["since"]["period"] == "1950–2000"
    assert "window_note" not in out["summary"]  # since_year is not a start_year: the window note (which points a start_year caller to since_year) does not apply


async def test_a_country_that_started_after_the_base_year_has_a_zero_base_and_emitted_all_it_has(climate_client):
    s = (await get_country_cumulative_share(countries=["BBB"], since_year=1890))["summary"]["since"]["countries"][0]  # BBB's record starts in 1900
    assert s["base_cumulative_mt"] == 0.0 and s["emitted_mt"] == 5.0 * (2000 - 1900 + 1)


async def test_a_record_that_ended_before_the_period_emitted_nothing_in_it(climate_client):
    s = (await get_country_cumulative_share(countries=["DDD"], since_year=1980))["summary"]["since"]["countries"][0]  # DDD stopped reporting in 1970
    assert s["emitted_mt"] == 0.0 and s["share_of_period_pct"] == 0.0


async def test_the_period_can_end_early_and_the_world_total_includes_international_transport(climate_client):
    out = await get_country_cumulative_share(countries=["AAA"], since_year=1950, end_year=1960)
    since = out["summary"]["since"]
    assert since["period"] == "1950–1960" and since["countries"][0]["emitted_mt"] == 10.0 * 11
    countries_1950_60 = sum(10 + (5 if y >= 1900 else 0) + (0 if 1950 <= y <= 1952 else 1) + 2 for y in range(1950, 1961))
    assert since["world_emitted_gt"] == round((countries_1950_60 + 3.0 * 11) / 1000, 1)  # the World = the countries + 3 Mt/yr of international transport
    assert since["rest_of_world"]["emitted_gt"] == round((countries_1950_60 + 3.0 * 11 - 110) / 1000, 1)


async def test_a_ranking_since_a_year_is_ranked_by_emissions_in_the_period_not_by_the_cumulative_total(climate_client):
    out = await get_country_cumulative_share(since_year=1950, limit=3)
    # emitted 1950-2000: AAA 10 x 51 = 510, BBB 5 x 51 = 255, CCC 1 x (51 - 3 missing years) = 48, DDD 2 x 21 (its record ends in 1970) = 42
    assert out["rows"] == [] and [(r["country"], r["emitted_mt"]) for r in out["since_rows"]] == [("AAA", 510.0), ("BBB", 255.0), ("CCC", 48.0)] and out["since_year"] == 1950
    s = out["summary"]
    assert s["mode"] == "ranking" and s["since"]["period"] == "1950–2000" and s["top"][0]["emitted_text"] == "0.5 GtCO₂" and "cumulative_gt" not in s["top"][0]
    assert s["shown_share_of_period_pct_total"] + s["not_shown_share_of_period_pct"] == pytest.approx(100.0, abs=0.05)


async def test_since_year_boundaries_and_misuse_name_what_to_pass(climate_client):
    for bad in (1850, 2001):
        with pytest.raises(ValueError, match="between 1851 and 2000"):
            await get_country_cumulative_share(countries=["AAA"], since_year=bad)
    await get_country_cumulative_share(countries=["AAA"], since_year=1851)
    await get_country_cumulative_share(countries=["AAA"], since_year=2000)
    with pytest.raises(ValueError, match="omit `start_year`"):
        await get_country_cumulative_share(countries=["AAA"], since_year=1950, start_year=1960)
    await get_country_cumulative_share(countries=["AAA"], since_year=1950, start_year=1950)  # the same year is fine
    with pytest.raises(ValueError, match="since_year"):
        await get_country_cumulative_share(start_year=1970)  # a ranking cannot take start_year: the message says what to pass instead
    with pytest.raises(ValueError, match="end between 1950 and 2000"):
        await get_country_cumulative_share(countries=["AAA"], since_year=1950, end_year=1940)


async def test_primap_since_is_a_share_of_the_sources_own_total_without_a_rest_of_world(climate_client):
    out = await get_country_cumulative_share(countries=["AAA"], since_year=1950, source="primap_hist")
    since = out["summary"]["since"]
    assert "source's own total" in since["basis"] and "rest_of_world" not in since and since["countries"][0]["emitted_mt"] == 510.0
