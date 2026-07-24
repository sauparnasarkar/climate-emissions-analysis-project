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
    # France is present in the fixture CSV but not in the real FEATURED_COUNTRIES fallback
    # load_expanded_countries() uses when no selected_countries.json fixture is present.
    resp = client.get("/api/countries/France/profile")
    assert resp.status_code == 404


def test_country_profile_expanded_but_not_featured_country_succeeds(full_data):
    from fastapi.testclient import TestClient

    from api.main import app

    from .conftest import write_selected_countries_json

    write_selected_countries_json(full_data)  # expanded = FIXTURE_COUNTRIES + France
    resp = TestClient(app).get("/api/countries/France/profile")
    assert resp.status_code == 200
    assert resp.json()["country"] == "France"


def test_country_profile_outside_expanded_set_still_404s(full_data):
    from fastapi.testclient import TestClient

    from api.main import app

    from .conftest import write_selected_countries_json

    write_selected_countries_json(full_data)  # expanded = FIXTURE_COUNTRIES + France, not Atlantis
    resp = TestClient(app).get("/api/countries/Atlantis/profile")
    assert resp.status_code == 404


def test_country_profile_503_when_features_missing(data_dir):
    from fastapi.testclient import TestClient

    from api.main import app

    resp = TestClient(app).get("/api/countries/China/profile")
    assert resp.status_code == 503
    assert "ghg_features.csv" in resp.json()["detail"]
