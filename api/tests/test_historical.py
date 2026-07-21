import pytest


def test_timeseries_default_params(client):
    resp = client.get("/api/historical/timeseries")
    assert resp.status_code == 200
    body = resp.json()
    assert body["gas"] == "co2"
    assert body["gas_label"] == "CO₂"
    # Default selects COUNTRIES[:5] (China, United States, India, Russia, Japan); only the
    # first two are present in the fixture, so only they should appear — no empty series for
    # countries missing from the raw data.
    names = {s["name"] for s in body["series"]}
    assert names == {"China", "United States"}
    for s in body["series"]:
        assert len(s["years"]) == len(s["values"]) == 5


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


@pytest.mark.parametrize("endpoint", ["/api/historical/timeseries", "/api/historical/decade-composition"])
def test_503_when_raw_data_missing(data_dir, endpoint):
    from fastapi.testclient import TestClient

    from api.main import app

    resp = TestClient(app).get(endpoint)
    assert resp.status_code == 503
    assert "owid-co2-data.csv" in resp.json()["detail"]
