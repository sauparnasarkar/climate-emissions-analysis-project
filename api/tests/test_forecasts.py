from fastapi.testclient import TestClient

from api.main import app

from .conftest import write_fixture


def test_forecast_summary_happy_path_and_ordering(client):
    resp = client.get("/api/forecasts/summary")
    assert resp.status_code == 200
    rows = {r["country"]: r for r in resp.json()["rows"]}

    china = rows["China"]
    assert china["forecast_2040"] == 16000
    assert china["actual_2020"] == 10000
    assert china["pct_change_2020_2040"] == 60.0

    us = rows["United States"]
    assert us["forecast_2040"] == 3800
    assert round(us["pct_change_2020_2040"], 1) == -20.8

    germany = rows["Germany"]
    # Germany's fixture has no 2040 forecast row.
    assert germany["forecast_2040"] is None
    assert germany["pct_change_2020_2040"] is None

    # Descending by forecast_2040, missing values sorted last.
    order = [r["country"] for r in resp.json()["rows"]]
    assert order == ["China", "United States", "Germany"]


def test_model_comparison_snake_cases_columns(client):
    resp = client.get("/api/forecasts/model-comparison")
    assert resp.status_code == 200
    body = resp.json()
    assert body["columns"] == ["country", "model", "mae", "rmse"]
    assert any(r["country"] == "China" and r["model"] == "RF Pooled" for r in body["rows"])


def test_ets_parameters(client):
    resp = client.get("/api/forecasts/ets-parameters")
    assert resp.status_code == 200
    rows = {r["country"]: r for r in resp.json()["rows"]}
    assert rows["China"]["alpha"] == 0.8
    assert rows["Germany"]["phi"] == 0.88


def test_feature_importance_sorted_ascending(client):
    resp = client.get("/api/forecasts/feature-importance")
    assert resp.status_code == 200
    features = [r["feature"] for r in resp.json()["rows"]]
    assert features == ["population", "coal_share", "gdp", "energy_intensity"]


def test_forecast_by_country_happy_path(client):
    resp = client.get("/api/forecasts/China")
    assert resp.status_code == 200
    body = resp.json()
    assert body["hist_years"] == [1990]
    assert body["hist_co2"] == [2400]
    assert body["holdout_years"] == [2020, 2023]
    assert body["holdout_co2"] == [10000, 11000]
    assert body["forecast_years"] == [2020, 2030, 2035, 2040]
    assert body["forecast_mean"] == [10500, 13000, 14500, 16000]


def test_forecast_by_country_unknown_is_404(client):
    resp = client.get("/api/forecasts/Atlantis")
    assert resp.status_code == 404


def test_forecast_by_country_expanded_but_not_featured_succeeds(full_data):
    from .conftest import write_selected_countries_json

    write_selected_countries_json(full_data)  # expanded = FIXTURE_COUNTRIES + France
    resp = TestClient(app).get("/api/forecasts/France")
    assert resp.status_code == 200
    assert resp.json()["country"] == "France"


def test_forecast_summary_scope_expanded_matches_featured_without_persisted_selection(client):
    """Without a selected_countries.json fixture, load_expanded_countries() falls back to
    the real FEATURED_COUNTRIES -- scope=expanded and scope=featured must produce identical
    results in that case, since they resolve to the same country list."""
    featured_resp = client.get("/api/forecasts/summary", params={"scope": "featured"})
    expanded_resp = client.get("/api/forecasts/summary", params={"scope": "expanded"})
    assert featured_resp.json() == expanded_resp.json()


def test_static_routes_are_not_shadowed_by_dynamic_country_route(client):
    """Regression test for the route-ordering comment in forecasts.py: the static routes
    must be declared before /forecasts/{country}, or Starlette would match e.g. "summary" as
    a country path param and this would 404 with "Unknown country: summary" instead."""
    for path in [
        "/api/forecasts/summary",
        "/api/forecasts/model-comparison",
        "/api/forecasts/ets-parameters",
        "/api/forecasts/feature-importance",
    ]:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} was shadowed by the dynamic /forecasts/{{country}} route"


def test_summary_503_when_forecasts_missing(data_dir):
    write_fixture(data_dir, "ghg_features.csv")
    resp = TestClient(app).get("/api/forecasts/summary")
    assert resp.status_code == 503
    assert "ets_forecasts.csv" in resp.json()["detail"]


def test_summary_503_when_features_missing(data_dir):
    write_fixture(data_dir, "ets_forecasts.csv")
    resp = TestClient(app).get("/api/forecasts/summary")
    assert resp.status_code == 503
    assert "ghg_features.csv" in resp.json()["detail"]


def test_by_country_503_when_forecasts_missing(data_dir):
    write_fixture(data_dir, "ghg_features.csv")
    resp = TestClient(app).get("/api/forecasts/China")
    assert resp.status_code == 503


def test_model_comparison_503_when_missing(data_dir):
    resp = TestClient(app).get("/api/forecasts/model-comparison")
    assert resp.status_code == 503
    assert "model_comparison.csv" in resp.json()["detail"]


def test_ets_parameters_503_when_missing(data_dir):
    resp = TestClient(app).get("/api/forecasts/ets-parameters")
    assert resp.status_code == 503
    assert "ets_parameters.csv" in resp.json()["detail"]


def test_feature_importance_503_when_missing(data_dir):
    resp = TestClient(app).get("/api/forecasts/feature-importance")
    assert resp.status_code == 503
    assert "feature_importance.csv" in resp.json()["detail"]
