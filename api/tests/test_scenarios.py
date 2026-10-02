from fastapi.testclient import TestClient

from api.main import app

from .conftest import write_fixture


def test_scenario_timeseries_single_view_happy_path(client):
    resp = client.get("/api/scenarios/timeseries", params={"view": "single", "country": "China"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["title_suffix"] == "China"
    assert body["level_1990"] == 2400
    assert body["historical"]["years"] == [1990, 2020, 2023]
    assert body["historical"]["values"] == [2400, 10000, 11000]

    series_by_name = {s["name"]: s for s in body["scenarios"]}
    # All three lines come from scenario_projections.csv, from 2025: BAU is the baseline the other two derive from.
    assert series_by_name["BAU"]["years"] == [2025, 2040] and series_by_name["BAU"]["values"] == [10800, 12500]
    assert series_by_name["Moderate"]["years"] == [2025, 2040] and series_by_name["Moderate"]["values"] == [10500, 9000]
    assert series_by_name["Aggressive"]["years"] == [2025, 2040] and series_by_name["Aggressive"]["values"] == [10200, 7000]


def test_scenario_timeseries_single_requires_country(client):
    resp = client.get("/api/scenarios/timeseries", params={"view": "single"})
    assert resp.status_code == 400


def test_scenario_timeseries_single_rejects_unknown_country(client):
    resp = client.get("/api/scenarios/timeseries", params={"view": "single", "country": "Atlantis"})
    assert resp.status_code == 400


def test_scenario_timeseries_global_view(client):
    resp = client.get("/api/scenarios/timeseries", params={"view": "global"})
    assert resp.status_code == 200
    # scope defaults to "featured"; with no selected_countries.json fixture,
    # load_expanded_countries() falls back to the real 10 FEATURED_COUNTRIES either way.
    assert resp.json()["title_suffix"] == "All 10 Countries"


def test_scenario_timeseries_global_view_scope_expanded(full_data):
    from .conftest import write_selected_countries_json

    write_selected_countries_json(full_data)  # expanded = FIXTURE_COUNTRIES + France, 4 total
    resp = TestClient(app).get("/api/scenarios/timeseries", params={"view": "global", "scope": "expanded"})
    assert resp.status_code == 200
    assert resp.json()["title_suffix"] == "All 4 Countries"


def test_scenario_timeseries_single_view_expanded_but_not_featured_succeeds(full_data):
    from .conftest import write_selected_countries_json

    write_selected_countries_json(full_data)  # expanded = FIXTURE_COUNTRIES + France
    resp = TestClient(app).get("/api/scenarios/timeseries", params={"view": "single", "country": "France"})
    assert resp.status_code == 200
    assert resp.json()["title_suffix"] == "France"


def test_scenario_timeseries_invalid_view_is_422(client):
    resp = client.get("/api/scenarios/timeseries", params={"view": "both"})
    assert resp.status_code == 422


def test_scenario_timeseries_tolerates_missing_optional_data(data_dir):
    """Only scenario_projections.csv is required; missing ghg_features.csv degrades gracefully (historical=None)
    rather than 503, and BAU is still present because it comes from the scenario file."""
    write_fixture(data_dir, "scenario_projections.csv")
    resp = TestClient(app).get("/api/scenarios/timeseries", params={"view": "single", "country": "China"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["historical"] is None
    assert body["level_1990"] is None
    series_by_name = {s["name"]: s for s in body["scenarios"]}
    assert series_by_name["BAU"]["years"] == [2025, 2040]
    assert series_by_name["Moderate"]["years"] == [2025, 2040]


def test_scenario_timeseries_503_when_scenarios_missing(data_dir):
    write_fixture(data_dir, "ets_forecasts.csv")
    write_fixture(data_dir, "ghg_features.csv")
    resp = TestClient(app).get("/api/scenarios/timeseries", params={"view": "single", "country": "China"})
    assert resp.status_code == 503
    assert "scenario_projections.csv" in resp.json()["detail"]


def test_scenario_cumulative_default_sort(client):
    resp = client.get("/api/scenarios/cumulative")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sort_by"] == "BAU"
    assert body["order"] == ["China", "United States", "Germany"]

    rows_by_country = {r["country"]: r["values"] for r in body["rows"]}
    assert rows_by_country["China"]["BAU"] == 23300
    assert rows_by_country["Germany"]["Moderate"] == 1000

    rows_by_country_full = {r["country"]: r for r in body["rows"]}
    # Single-year 2040 value per scenario, alongside the cumulative sum above.
    assert rows_by_country_full["China"]["year_2040"] == {"BAU": 12500, "Moderate": 9000, "Aggressive": 7000}
    assert rows_by_country_full["Germany"]["year_2040"] == {"BAU": 550, "Moderate": 400, "Aggressive": 9000}
    # Current/latest actual level, from ghg_features.csv's own latest year (2023 in the fixture).
    assert rows_by_country_full["China"]["current_level"] == 11000
    assert rows_by_country_full["United States"]["current_level"] == 4700
    assert rows_by_country_full["Germany"]["current_level"] == 600


def test_scenario_cumulative_tolerates_missing_features(data_dir):
    """current_level should be None (not a 503) when ghg_features.csv is missing --
    year_2040/cumulative totals still come from scenario_projections.csv alone."""
    write_fixture(data_dir, "scenario_projections.csv")
    resp = TestClient(app).get("/api/scenarios/cumulative")
    assert resp.status_code == 200
    rows_by_country = {r["country"]: r for r in resp.json()["rows"]}
    assert rows_by_country["China"]["current_level"] is None
    assert rows_by_country["China"]["year_2040"]["BAU"] == 12500


def test_scenario_cumulative_sort_by_changes_order(client):
    resp = client.get("/api/scenarios/cumulative", params={"sort_by": "Aggressive"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["sort_by"] == "Aggressive"
    # Germany's Aggressive total (17000) beats United States' (7400), unlike the BAU order.
    assert body["order"] == ["China", "Germany", "United States"]


def test_scenario_cumulative_invalid_sort_by_is_422(client):
    resp = client.get("/api/scenarios/cumulative", params={"sort_by": "Whatever"})
    assert resp.status_code == 422


def test_scenario_cumulative_503_when_missing(data_dir):
    resp = TestClient(app).get("/api/scenarios/cumulative")
    assert resp.status_code == 503
    assert "scenario_projections.csv" in resp.json()["detail"]


def test_scenario_compare_happy_path_not_summed(client):
    resp = client.get("/api/scenarios/compare", params={"countries": ["China", "United States"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["countries"] == ["China", "United States"]

    bau_by_country = {s["name"]: s for s in body["scenarios"]["BAU"]}
    # observed history up to the year before the scenarios begin, then the BAU projection from scenario_projections.csv
    assert bau_by_country["China"]["years"] == [1990, 2020, 2023, 2025, 2040]
    assert bau_by_country["China"]["values"] == [2400, 10000, 11000, 10800, 12500]
    assert bau_by_country["United States"]["years"] == [1990, 2020, 2023, 2025, 2040]
    assert bau_by_country["United States"]["values"] == [5000, 4800, 4700, 4700, 4200]
    # Proves each country keeps its own values rather than being summed, unlike
    # /scenarios/cumulative and the view=global /scenarios/timeseries.
    assert bau_by_country["China"]["values"] != bau_by_country["United States"]["values"]


def test_scenario_compare_each_scenario_is_observed_history_then_its_own_projection(client):
    resp = client.get("/api/scenarios/compare", params={"countries": ["China"]})
    body = resp.json()
    moderate = body["scenarios"]["Moderate"][0]
    # observed history (1990, 2020, 2023), then Moderate's own 2025/2040 rows: no forecast segment in between
    assert moderate["years"] == [1990, 2020, 2023, 2025, 2040]
    assert moderate["values"] == [2400, 10000, 11000, 10500, 9000]


def test_scenario_compare_rejects_unknown_country(client):
    resp = client.get("/api/scenarios/compare", params={"countries": ["Atlantis"]})
    assert resp.status_code == 400


def test_scenario_compare_requires_countries_param(client):
    resp = client.get("/api/scenarios/compare")
    assert resp.status_code == 422


def test_scenario_compare_tolerates_missing_optional_data(data_dir):
    """Only scenario_projections.csv is required; missing ghg_features.csv degrades gracefully (no history)
    rather than 503, and BAU is still present because it comes from the scenario file."""
    write_fixture(data_dir, "scenario_projections.csv")
    resp = TestClient(app).get("/api/scenarios/compare", params={"countries": ["China"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scenarios"]["BAU"][0]["years"] == [2025, 2040]
    assert body["scenarios"]["Moderate"][0]["years"] == [2025, 2040]


def test_scenario_compare_503_when_scenarios_missing(data_dir):
    write_fixture(data_dir, "ets_forecasts.csv")
    write_fixture(data_dir, "ghg_features.csv")
    resp = TestClient(app).get("/api/scenarios/compare", params={"countries": ["China"]})
    assert resp.status_code == 503
    assert "scenario_projections.csv" in resp.json()["detail"]


# ---------------------------------------------------------------- BAU comes from the scenario file, never from ets_forecasts.csv (Backlog B2)


def test_the_bau_line_is_the_scenario_files_bau_even_when_a_different_forecast_file_is_present(client):
    """The `client` fixture also has ets_forecasts.csv (the Week 4 fit stopped at 2018: China 2030 = 13000). The BAU line must be the scenario file's, so that BAU,
    Moderate and Aggressive share one baseline; mixing the two made mitigation appear as a step in 2025."""
    body = client.get("/api/scenarios/timeseries", params={"view": "single", "country": "China"}).json()
    bau = {s["name"]: s for s in body["scenarios"]}["BAU"]
    assert bau["years"] == [2025, 2040] and bau["values"] == [10800, 12500]
    assert 13000 not in bau["values"] and 10500 not in bau["values"] and 16000 not in bau["values"]  # none of the forecast file's values


def test_scenarios_do_not_need_the_forecast_file_at_all(data_dir):
    write_fixture(data_dir, "scenario_projections.csv")
    write_fixture(data_dir, "ghg_features.csv")  # but no ets_forecasts.csv
    ts = TestClient(app).get("/api/scenarios/timeseries", params={"view": "single", "country": "China"})
    cmp_ = TestClient(app).get("/api/scenarios/compare", params={"countries": ["China"]})
    assert ts.status_code == 200 and cmp_.status_code == 200
    assert {s["name"]: s["years"] for s in ts.json()["scenarios"]} == {"BAU": [2025, 2040], "Moderate": [2025, 2040], "Aggressive": [2025, 2040]}


def test_no_scenario_line_starts_before_the_first_scenario_year_and_all_three_share_that_start(client):
    ts = client.get("/api/scenarios/timeseries", params={"view": "single", "country": "China"}).json()
    firsts = {s["name"]: s["years"][0] for s in ts["scenarios"]}
    assert set(firsts.values()) == {2025}
    for s in ts["scenarios"]:
        assert s["years"] == sorted(set(s["years"]))  # increasing, no duplicate years (no overlapping segment)


def test_the_three_scenarios_start_from_the_same_year_for_every_country_in_compare(client):
    body = client.get("/api/scenarios/compare", params={"countries": ["China", "United States", "Germany"]}).json()
    for scenario, series in body["scenarios"].items():
        for s in series:
            first_projected = [y for y in s["years"] if y >= 2025][0]
            assert first_projected == 2025 and s["years"] == sorted(set(s["years"])), (scenario, s["name"])  # one continuous, non-overlapping line
            assert s["years"].index(2025) == len([y for y in s["years"] if y < 2025])  # history then projection, nothing in between


def test_compare_history_stops_the_year_before_the_scenarios_begin(client):
    s = {x["name"]: x for x in client.get("/api/scenarios/compare", params={"countries": ["China"]}).json()["scenarios"]["BAU"]}["China"]
    history = [y for y in s["years"] if y < 2025]
    assert history == [1990, 2020, 2023] and max(history) < min(y for y in s["years"] if y >= 2025)
