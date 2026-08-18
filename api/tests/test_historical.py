import json

import pytest


def test_timeseries_no_scope_matches_explicit_expanded_scope(client):
    # Backward compatibility: every existing caller (the dashboard included -- confirmed by
    # inspection of climate-dashboard-react/src/api/client.ts) never sends `scope`. The new
    # parameter's default must reproduce the old unparameterized behavior exactly.
    resp_default = client.get("/api/historical/timeseries", params={"countries": ["China"]})
    resp_explicit = client.get(
        "/api/historical/timeseries", params={"countries": ["China"], "scope": "expanded"}
    )
    assert resp_default.json() == resp_explicit.json()


def test_timeseries_scope_sovereign_reaches_countries_outside_expanded(client):
    # Canada (owid_raw_df fixture: iso_code=CAN, single 1995 row, co2=999.0) has a real
    # iso_code but isn't in FEATURED_COUNTRIES and isn't opted into `expanded` by any fixture
    # here -- unreachable under featured/expanded scope, only under sovereign.
    resp_expanded = client.get("/api/historical/timeseries", params={"countries": ["Canada"]})
    assert resp_expanded.json()["series"] == []

    resp_sovereign = client.get(
        "/api/historical/timeseries", params={"countries": ["Canada"], "scope": "sovereign"}
    )
    canada = next(s for s in resp_sovereign.json()["series"] if s["name"] == "Canada")
    assert canada["years"] == [1995]
    assert canada["values"] == [999.0]


def test_timeseries_scope_featured_excludes_expanded_only_country(client, full_data):
    # A custom expanded set (Canada opted in, unlike the shared write_selected_countries_json
    # helper which opts in France instead -- France isn't in the owid-co2-data.csv fixture at
    # all, so it can't discriminate featured from expanded for *this* endpoint's data pool).
    import api.data_loaders as data_loaders

    with open(full_data / "selected_countries.json", "w") as f:
        json.dump(
            {
                "generated": "2026-01-01",
                "source_year": 2023,
                "coverage_threshold_pct": 90,
                "mt_floor": 100,
                "expanded": ["China", "United States", "Germany", "Canada"],
                "expanded_count": 4,
                "expanded_global_share_pct": 92.2,
            },
            f,
        )
    data_loaders.load_expanded_countries.cache_clear()

    resp_expanded = client.get(
        "/api/historical/timeseries", params={"countries": ["Canada"], "scope": "expanded"}
    )
    assert resp_expanded.json()["series"] != []

    resp_featured = client.get(
        "/api/historical/timeseries", params={"countries": ["Canada"], "scope": "featured"}
    )
    assert resp_featured.json()["series"] == []


def test_timeseries_default_params(client):
    resp = client.get("/api/historical/timeseries")
    assert resp.status_code == 200
    body = resp.json()
    assert body["gas"] == "co2"
    assert body["gas_label"] == "CO₂"
    # Default selects the full FEATURED_COUNTRIES (10 countries); only China, United States,
    # and Germany are present in the fixture, so only they should appear — no empty series
    # for countries missing from the raw data.
    names = {s["name"] for s in body["series"]}
    assert names == {"China", "United States", "Germany"}
    for s in body["series"]:
        # owid_raw_df() (conftest) gives every fixture country 5 years: 1990/1995/2000/2005/2010.
        assert len(s["years"]) == len(s["values"]) == len(s["per_capita"]) == 5
        assert len(s["yoy_pct_change"]) == len(s["per_gdp"]) == 5


def test_timeseries_co2_new_fields_populated_with_deliberate_null(client):
    resp = client.get("/api/historical/timeseries", params={"countries": ["China"], "gas": "co2"})
    china = next(s for s in resp.json()["series"] if s["name"] == "China")

    assert china["years"] == [1990, 1995, 2000, 2005, 2010]
    assert china["per_capita"] == pytest.approx([7.0, 7.5, 8.0, 8.5, 9.0])
    # co2_growth_prct is null on a country's first data year (owid_raw_df fixture, mirrors
    # real OWID behavior -- no prior-year baseline) -- proves the pd.isna() -> None conversion
    # path, not just that the field is present.
    assert china["yoy_pct_change"][0] is None
    assert china["yoy_pct_change"][1:] == pytest.approx([2.1, 2.2, 2.3, 2.4])
    assert china["per_gdp"] == pytest.approx([0.40, 0.42, 0.44, 0.46, 0.48])


def test_timeseries_non_co2_gas_nulls_growth_and_per_gdp_but_keeps_per_capita(client):
    resp = client.get("/api/historical/timeseries", params={"countries": ["China"], "gas": "methane"})
    china = next(s for s in resp.json()["series"] if s["name"] == "China")

    # co2_growth_prct/co2_per_gdp have no methane equivalent in OWID -- None-filled to the
    # same length as years, not omitted or an empty list.
    assert china["yoy_pct_change"] == [None, None, None, None, None]
    assert china["per_gdp"] == [None, None, None, None, None]
    # per_capita IS populated for every gas (methane_per_capita is a real OWID column) --
    # varying per-year values prove the {gas}_per_capita column lookup, not a flat
    # placeholder that could pass by accident.
    assert china["per_capita"] == pytest.approx([0.20, 0.21, 0.22, 0.23, 0.24])


def test_timeseries_default_countries_ignores_scope(client):
    # No `countries` given -> the default is always the full FEATURED_COUNTRIES list
    # regardless of `scope`. Canada (owid_raw_df fixture: iso_code=CAN, reachable via
    # sovereign scope per test_timeseries_scope_sovereign_reaches_countries_outside_expanded
    # above) isn't in FEATURED_COUNTRIES, so even scope="sovereign" can't surface it without
    # an explicit `countries` list -- `scope` has no observable effect on this endpoint's
    # default path, unlike get_decade_composition's (see that endpoint's sovereign-scope test).
    resp_expanded = client.get("/api/historical/timeseries")
    resp_sovereign = client.get("/api/historical/timeseries", params={"scope": "sovereign"})
    assert resp_expanded.json() == resp_sovereign.json()
    names = {s["name"] for s in resp_sovereign.json()["series"]}
    assert "Canada" not in names


def test_timeseries_explicit_countries_and_gas(client):
    resp = client.get("/api/historical/timeseries", params={"countries": ["China", "Germany"], "gas": "methane"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["gas"] == "methane"
    names = {s["name"] for s in body["series"]}
    assert names == {"China", "Germany"}


def test_timeseries_invalid_gas_is_422(client):
    resp = client.get("/api/historical/timeseries", params={"gas": "co3"})
    assert resp.status_code == 422


def test_timeseries_excludes_pre_1990_and_out_of_scope(client):
    resp = client.get("/api/historical/timeseries", params={"countries": ["China"], "gas": "co2"})
    china = next(s for s in resp.json()["series"] if s["name"] == "China")
    assert min(china["years"]) == 1990  # the fixture's 1985 row must be filtered out
    assert 1985 not in china["years"]


def test_decade_composition_shares_sum_to_100(client):
    resp = client.get("/api/historical/decade-composition")
    assert resp.status_code == 200
    body = resp.json()
    assert body["decades"] == [1990, 2000, 2010]

    by_gas = {s["gas"]: s["share"] for s in body["series"]}
    n_decades = len(body["decades"])
    for i in range(n_decades):
        total = sum(by_gas[gas][i] for gas in by_gas)
        assert round(total, 6) == 100.0


def test_decade_composition_filtered_to_countries_still_sums_to_100(client):
    resp = client.get("/api/historical/decade-composition", params={"countries": ["China"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["decades"] == [1990, 2000, 2010]

    by_gas = {s["gas"]: s["share"] for s in body["series"]}
    for i in range(len(body["decades"])):
        total = sum(by_gas[gas][i] for gas in by_gas)
        assert round(total, 6) == 100.0


def test_decade_composition_no_scope_matches_explicit_expanded_scope(client):
    resp_default = client.get("/api/historical/decade-composition")
    resp_explicit = client.get("/api/historical/decade-composition", params={"scope": "expanded"})
    assert resp_default.json() == resp_explicit.json()


def test_decade_composition_scope_sovereign_widens_the_default_pool(client):
    # No `countries` given -> decade-composition aggregates the *whole* selected-scope pool
    # (unlike get_timeseries, whose no-countries default is always FEATURED_COUNTRIES[:5]
    # regardless of scope). Canada's single 1995 row (decade 1990, co2=999.0) is invisible
    # under expanded scope but pulled into the sovereign-scope aggregate, so the 1990-decade
    # shares must differ between the two.
    resp_expanded = client.get("/api/historical/decade-composition")
    resp_sovereign = client.get("/api/historical/decade-composition", params={"scope": "sovereign"})
    assert resp_expanded.json()["decades"] == resp_sovereign.json()["decades"] == [1990, 2000, 2010]

    by_gas_expanded = {s["gas"]: s["share"][0] for s in resp_expanded.json()["series"]}
    by_gas_sovereign = {s["gas"]: s["share"][0] for s in resp_sovereign.json()["series"]}
    assert by_gas_expanded != by_gas_sovereign


def test_decade_composition_filtered_to_unknown_country_is_empty(client):
    # Proves `countries` actually restricts the frame (rather than being accepted and
    # ignored) -- an unmatched filter leaves no rows to group by decade at all.
    resp = client.get("/api/historical/decade-composition", params={"countries": ["Nonexistent"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["decades"] == []


@pytest.mark.parametrize(
    "endpoint", ["/api/historical/timeseries", "/api/historical/decade-composition", "/api/historical/change-summary"]
)
def test_503_when_raw_data_missing(data_dir, endpoint):
    from fastapi.testclient import TestClient

    from api.main import app

    resp = TestClient(app).get(endpoint)
    assert resp.status_code == 503
    assert "owid-co2-data.csv" in resp.json()["detail"]


def _change_summary_client(data_dir):
    from fastapi.testclient import TestClient

    from api.main import app

    from .conftest import owid_raw_change_summary_df

    owid_raw_change_summary_df().to_csv(data_dir / "owid-co2-data.csv", index=False)
    return TestClient(app)


def test_change_summary_happy_path_counts_and_ranking(data_dir):
    client = _change_summary_client(data_dir)
    resp = client.get("/api/historical/change-summary", params={"scope": "sovereign"})
    assert resp.status_code == 200
    body = resp.json()

    assert body["scope"] == "sovereign"
    assert body["baseline_year"] == 1990
    assert body["latest_year"] == 2024
    # 7 countries in the fixture; Latvia has no 1990 row, so countries_with_data is 6.
    assert body["country_pool_size"] == 7
    assert body["countries_with_data"] == 6
    # China, India, Zeroland increase (Zeroland's absolute_change is still a well-defined +50
    # despite its undefined pct_change -- see the inf-guard test below); Ukraine, United
    # Kingdom decrease; Norway unchanged.
    assert body["increased_count"] == 3
    assert body["decreased_count"] == 2
    assert body["unchanged_count"] == 1
    assert body["increased_count"] + body["decreased_count"] + body["unchanged_count"] == 6

    # Ranked by absolute_change, biggest mover first in each direction.
    assert [r["country"] for r in body["top_increases"]] == ["China", "India", "Zeroland"]
    assert [r["country"] for r in body["top_decreases"]] == ["Ukraine", "United Kingdom"]
    assert body["top_increases"][0]["absolute_change"] == pytest.approx(9600.0)
    assert body["top_decreases"][0]["absolute_change"] == pytest.approx(-560.0)


def test_change_summary_zero_baseline_country_keeps_absolute_change_nulls_pct(data_dir):
    # Regression test for the inf guard: Zeroland's co2_1990 == 0.0 makes pct_change +inf,
    # which plain dropna() does not remove and json.dumps can't serialize. No real sovereign
    # country has co2 == 0 at 1990 today, but this must not crash -- and since
    # absolute_change (0 -> 50 Mt) is still a real, well-defined increase, Zeroland must stay
    # counted as increased with only its pct_change nulled, not dropped from the response
    # entirely.
    client = _change_summary_client(data_dir)
    resp = client.get("/api/historical/change-summary", params={"scope": "sovereign"})
    assert resp.status_code == 200
    body = resp.json()
    zeroland = next(r for r in body["top_increases"] if r["country"] == "Zeroland")
    assert zeroland["absolute_change"] == pytest.approx(50.0)
    assert zeroland["pct_change"] is None


def test_change_summary_missing_baseline_row_excluded_not_crashed(data_dir):
    # Latvia has only a 2024 row (no 1990) -- must be excluded from countries_with_data
    # without a 500, mirroring overview.py's own top_movers empty-pair handling.
    client = _change_summary_client(data_dir)
    resp = client.get("/api/historical/change-summary", params={"scope": "sovereign"})
    assert resp.status_code == 200
    all_countries = {r["country"] for r in resp.json()["top_increases"] + resp.json()["top_decreases"]}
    assert "Latvia" not in all_countries


def test_change_summary_top_n_bounds(data_dir):
    client = _change_summary_client(data_dir)
    assert client.get("/api/historical/change-summary", params={"top_n": 0}).status_code == 422
    assert client.get("/api/historical/change-summary", params={"top_n": 26}).status_code == 422
    assert client.get("/api/historical/change-summary", params={"top_n": 1}).status_code == 200


def test_change_summary_top_n_caps_each_direction(data_dir):
    client = _change_summary_client(data_dir)
    resp = client.get("/api/historical/change-summary", params={"scope": "sovereign", "top_n": 1})
    body = resp.json()
    assert len(body["top_increases"]) == 1
    assert len(body["top_decreases"]) == 1
    # Counts stay the true totals even though the lists are trimmed to top_n.
    assert body["increased_count"] == 3
    assert body["decreased_count"] == 2


def test_change_summary_scope_changes_pool_size(data_dir):
    # No selected_countries.json written -> load_expanded_countries() falls back to
    # FEATURED_COUNTRIES, so "featured" and "expanded" coincide here; the real assertion is
    # that `scope` is actually threaded into _scoped_pool at all (sovereign reaches everyone).
    client = _change_summary_client(data_dir)
    featured = client.get("/api/historical/change-summary", params={"scope": "featured"}).json()
    sovereign = client.get("/api/historical/change-summary", params={"scope": "sovereign"}).json()
    # FEATURED_COUNTRIES ∩ fixture = China, India, United Kingdom.
    assert featured["country_pool_size"] == 3
    assert sovereign["country_pool_size"] == 7
    assert featured["country_pool_size"] != sovereign["country_pool_size"]
