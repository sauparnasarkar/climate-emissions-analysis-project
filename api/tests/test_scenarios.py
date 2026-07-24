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
