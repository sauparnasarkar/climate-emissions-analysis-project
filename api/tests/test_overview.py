from .conftest import write_fixture, write_selected_countries_json


def test_overview_happy_path(client):
    resp = client.get("/api/overview")
    assert resp.status_code == 200
    body = resp.json()

    assert body["latest_year"] == 2023
    # China 11000 + United States 4700 + Germany 600 — France's 300 must be excluded.
    assert body["latest_co2_total"] == 16300
    assert body["co2_1990_total"] == 8400
    assert round(body["pct_change_since_1990"], 2) == round((16300 - 8400) / 8400 * 100, 2)


def test_overview_bar_is_filtered_by_scope(client):
    """latest_year_bar is now filtered consistently with latest_co2_total/co2_1990_total/
    top_movers just above it — France (present in ghg_features.csv but outside the real
    FEATURED_COUNTRIES fallback) must not appear in the default (scope=featured) bar."""
    resp = client.get("/api/overview")
    countries_in_bar = {row["country"] for row in resp.json()["latest_year_bar"]}
    assert countries_in_bar == {"China", "United States", "Germany"}
    assert "France" not in countries_in_bar


def test_overview_scope_expanded_includes_out_of_scope_country(full_data):
    from fastapi.testclient import TestClient

    from api.main import app

    write_selected_countries_json(full_data)  # expanded = FIXTURE_COUNTRIES + France
    resp = TestClient(app).get("/api/overview", params={"scope": "expanded"})
    assert resp.status_code == 200
    body = resp.json()

    countries_in_bar = {row["country"] for row in body["latest_year_bar"]}
    assert "France" in countries_in_bar
    assert body["countries_count"] == 4
    assert body["total_countries_analyzed"] == 4  # same expanded set in this fixture


def test_overview_total_countries_analyzed_independent_of_scope(full_data):
    """total_countries_analyzed always reflects the full expanded set, regardless of which
    scope's data the rest of the response is scoped to."""
    from fastapi.testclient import TestClient

    from api.main import app

    write_selected_countries_json(full_data)  # expanded_count = 4
    client = TestClient(app)

    featured_resp = client.get("/api/overview", params={"scope": "featured"})
    expanded_resp = client.get("/api/overview", params={"scope": "expanded"})

    assert featured_resp.json()["total_countries_analyzed"] == 4
    assert expanded_resp.json()["total_countries_analyzed"] == 4
    assert featured_resp.json()["countries_count"] != expanded_resp.json()["countries_count"]


def test_overview_top_movers_ordering(client):
    body = client.get("/api/overview").json()
    movers_by_country = {m["country"]: m["pct_change"] for m in body["top_movers"]}

    # China grew ~358%, United States shrank ~6%, Germany shrank ~40%.
    assert body["fastest_growth"]["country"] == "China"
    assert body["largest_reduction"]["country"] == "Germany"
    pct_values = [m["pct_change"] for m in body["top_movers"]]
    assert pct_values == sorted(pct_values, reverse=True)
    assert round(movers_by_country["China"], 1) == round((11000 - 2400) / 2400 * 100, 1)


def test_overview_503_when_features_missing(data_dir):
    from fastapi.testclient import TestClient

    from api.main import app

    resp = TestClient(app).get("/api/overview")
    assert resp.status_code == 503
    assert "ghg_features.csv" in resp.json()["detail"]


def test_overview_503_message_mentions_week2(data_dir):
    write_fixture(data_dir, "ets_forecasts.csv")  # unrelated file present, features still missing
    from fastapi.testclient import TestClient

    from api.main import app

    resp = TestClient(app).get("/api/overview")
    assert resp.status_code == 503
    assert "Week 2" in resp.json()["detail"]
