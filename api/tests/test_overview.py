from .conftest import write_fixture


def test_overview_happy_path(client):
    resp = client.get("/api/overview")
    assert resp.status_code == 200
    body = resp.json()

    assert body["latest_year"] == 2023
    # China 11000 + United States 4700 + Germany 600 — France's 300 must be excluded.
    assert body["latest_co2_total"] == 16300
    assert body["co2_1990_total"] == 8400
    assert round(body["pct_change_since_1990"], 2) == round((16300 - 8400) / 8400 * 100, 2)


def test_overview_bar_is_not_filtered_by_focus_countries(client):
    """Documents current behavior: unlike latest_co2_total/co2_1990_total/top_movers just
    above it (which all explicitly filter to COUNTRIES), latest_year_bar has no such filter
    — any country present in ghg_features.csv at the latest year appears in the bar, even one
    outside the 10 focus countries. In production this can't surface as long as the notebook
    only ever writes focus-country rows to ghg_features.csv; this test exists so a future
    change to that filtering isn't silent either way."""
    resp = client.get("/api/overview")
    countries_in_bar = {row["country"] for row in resp.json()["latest_year_bar"]}
    assert countries_in_bar == {"China", "United States", "Germany", "France"}


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
