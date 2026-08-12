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
        assert len(s["years"]) == len(s["values"]) == 5


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


@pytest.mark.parametrize("endpoint", ["/api/historical/timeseries", "/api/historical/decade-composition"])
def test_503_when_raw_data_missing(data_dir, endpoint):
    from fastapi.testclient import TestClient

    from api.main import app

    resp = TestClient(app).get(endpoint)
    assert resp.status_code == 503
    assert "owid-co2-data.csv" in resp.json()["detail"]
