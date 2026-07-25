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
    assert series_by_name["BAU"]["years"] == [2020, 2030, 2035, 2040]
    assert series_by_name["BAU"]["values"] == [10500, 13000, 14500, 16000]
    # Moderate/Aggressive stitch the 2020 BAU point onto their own 2025/2040 rows.
    assert series_by_name["Moderate"]["years"] == [2020, 2025, 2040]
    assert series_by_name["Aggressive"]["values"][0] == 10500  # the stitched BAU 2020 value


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
    """Only scenario_projections.csv is required; missing ets_forecasts.csv/ghg_features.csv
    should degrade gracefully (historical=None, empty BAU) rather than 503."""
    write_fixture(data_dir, "scenario_projections.csv")
    resp = TestClient(app).get("/api/scenarios/timeseries", params={"view": "single", "country": "China"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["historical"] is None
    assert body["level_1990"] is None
    series_by_name = {s["name"]: s for s in body["scenarios"]}
    assert series_by_name["BAU"]["years"] == []
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
    assert bau_by_country["China"]["years"] == [1990, 2020, 2030, 2035, 2040]
    assert bau_by_country["China"]["values"] == [2400, 10500, 13000, 14500, 16000]
    assert bau_by_country["United States"]["years"] == [1990, 2020, 2030, 2035, 2040]
    assert bau_by_country["United States"]["values"] == [5000, 4900, 4400, 4100, 3800]
    # Proves each country keeps its own values rather than being summed, unlike
    # /scenarios/cumulative and the view=global /scenarios/timeseries.
    assert bau_by_country["China"]["values"] != bau_by_country["United States"]["values"]


def test_scenario_compare_moderate_stitches_bau_then_diverges(client):
    resp = client.get("/api/scenarios/compare", params={"countries": ["China"]})
    body = resp.json()
    moderate = body["scenarios"]["Moderate"][0]
    # 1990 historical, 2020 BAU-derived (scenarios only diverge from 2025), then Moderate's
    # own 2025/2040 rows.
    assert moderate["years"] == [1990, 2020, 2025, 2040]
    assert moderate["values"] == [2400, 10500, 10500, 9000]


def test_scenario_compare_rejects_unknown_country(client):
    resp = client.get("/api/scenarios/compare", params={"countries": ["Atlantis"]})
    assert resp.status_code == 400


def test_scenario_compare_requires_countries_param(client):
    resp = client.get("/api/scenarios/compare")
    assert resp.status_code == 422


def test_scenario_compare_tolerates_missing_optional_data(data_dir):
    """Only scenario_projections.csv is required; missing ets_forecasts.csv/ghg_features.csv
    should degrade gracefully (empty historical/BAU) rather than 503."""
    write_fixture(data_dir, "scenario_projections.csv")
    resp = TestClient(app).get("/api/scenarios/compare", params={"countries": ["China"]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scenarios"]["BAU"][0]["years"] == []
    assert body["scenarios"]["Moderate"][0]["years"] == [2025, 2040]


def test_scenario_compare_503_when_scenarios_missing(data_dir):
    write_fixture(data_dir, "ets_forecasts.csv")
    write_fixture(data_dir, "ghg_features.csv")
    resp = TestClient(app).get("/api/scenarios/compare", params={"countries": ["China"]})
    assert resp.status_code == 503
    assert "scenario_projections.csv" in resp.json()["detail"]
