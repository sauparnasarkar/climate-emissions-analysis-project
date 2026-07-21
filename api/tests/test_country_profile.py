def test_country_profile_happy_path(client):
    resp = client.get("/api/countries/China/profile")
    assert resp.status_code == 200
    body = resp.json()
    assert body["country"] == "China"
    assert body["years"] == [1990, 2020, 2023]
    assert body["co2"] == [2400, 10000, 11000]


def test_country_profile_first_year_nan_becomes_none(client):
    body = client.get("/api/countries/China/profile").json()
    first_row = body["table"][0]
    assert first_row["year"] == 1990
    assert first_row["co2_yoy_pct_change"] is None

    # yoy_years/yoy_values should only include rows where the value wasn't NaN.
    assert 1990 not in body["yoy_years"]
    assert len(body["yoy_years"]) == len(body["yoy_values"]) == 2


def test_country_profile_unknown_country_is_404(client):
    resp = client.get("/api/countries/Atlantis/profile")
    assert resp.status_code == 404
    assert "Atlantis" in resp.json()["detail"]


def test_country_profile_out_of_scope_country_is_404(client):
    # France is present in the fixture CSV but not in api.constants.COUNTRIES.
    resp = client.get("/api/countries/France/profile")
    assert resp.status_code == 404


def test_country_profile_503_when_features_missing(data_dir):
    from fastapi.testclient import TestClient

    from api.main import app

    resp = TestClient(app).get("/api/countries/China/profile")
    assert resp.status_code == 503
    assert "ghg_features.csv" in resp.json()["detail"]
