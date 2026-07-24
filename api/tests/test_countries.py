from api.constants import FEATURED_COUNTRIES

from .conftest import write_selected_countries_json


def test_list_countries_falls_back_when_no_selection_persisted(client):
    """No selected_countries.json fixture is written by `client` — expanded should fall
    back to FEATURED_COUNTRIES, matching load_expanded_countries()'s own fallback."""
    resp = client.get("/api/countries")
    assert resp.status_code == 200
    body = resp.json()
    assert body["featured"] == FEATURED_COUNTRIES
    assert body["expanded"] == FEATURED_COUNTRIES


def test_list_countries_reflects_persisted_selection(full_data):
    from fastapi.testclient import TestClient

    from api.main import app

    write_selected_countries_json(full_data)
    resp = TestClient(app).get("/api/countries")
    assert resp.status_code == 200
    body = resp.json()

    assert body["featured"] == FEATURED_COUNTRIES
    assert "France" in body["expanded"]
    assert set(body["expanded"]) == {"China", "United States", "Germany", "France"}
