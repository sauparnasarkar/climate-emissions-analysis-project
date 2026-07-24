from .conftest import write_fixture, write_selected_countries_json


def test_overview_happy_path_defaults_to_featured(client):
    resp = client.get("/api/overview")
    assert resp.status_code == 200
    body = resp.json()

    # China 11000 + United States 4700 + Germany 600 -- France's 300 must be excluded
    # (France is outside the real FEATURED_COUNTRIES fallback used when no selected_countries.json
    # is written, and outside the "countries" param default too).
    assert body["selected"]["label"] == "Selected"
    assert body["selected"]["latest_co2_total"] == 16300
    assert body["selected"]["co2_1990_total"] == 8400
    assert round(body["selected"]["pct_change_since_1990"], 2) == round((16300 - 8400) / 8400 * 100, 2)


def test_overview_selected_country_list_defaults_to_featured_countries(client):
    from api.constants import FEATURED_COUNTRIES

    resp = client.get("/api/overview")
    assert resp.json()["selected_country_list"] == FEATURED_COUNTRIES


def test_overview_all_countries_tier_excludes_non_sovereign_aggregates(client):
    """all_countries reflects the full NON_SOVEREIGN-excluded raw universe -- the fixture's
    injected "World" row (9999.0 at year 2010) must not leak into the total, and Canada
    (present only via a one-off fixture row) must be counted since it's a real sovereign."""
    body = client.get("/api/overview").json()
    tier = body["all_countries"]

    assert tier["label"] == "All Countries"
    assert tier["countries_count"] == 4  # China, United States, Germany, Canada
    assert tier["latest_year"] == 2010  # owid_raw_df()'s own latest year, independent of ghg_features.csv's
    assert tier["latest_co2_total"] == 312.0  # China+US+Germany at year 2010, 104.0 each -- World's 9999.0 excluded
    assert tier["co2_1990_total"] == 300.0  # China+US+Germany at year 1990, 100.0 each
    assert round(tier["pct_change_since_1990"], 2) == round((312.0 - 300.0) / 300.0 * 100, 2)


def test_overview_expanded_tier_differs_from_selected_with_custom_expanded_set(full_data):
    from fastapi.testclient import TestClient

    from api.main import app

    write_selected_countries_json(full_data)  # expanded = China, United States, Germany, France
    resp = TestClient(app).get("/api/overview")
    body = resp.json()

    # expanded includes France (16600 = 11000+4700+600+300); selected still defaults to the
    # real FEATURED_COUNTRIES fallback, which excludes France (16300).
    assert body["expanded_countries"]["countries_count"] == 4
    assert body["expanded_countries"]["latest_co2_total"] == 16600
    assert body["selected"]["latest_co2_total"] == 16300


def test_overview_countries_param_scopes_selected_tier_only(full_data):
    from fastapi.testclient import TestClient

    from api.main import app

    write_selected_countries_json(full_data)  # France is in the expanded set, so it's a valid "countries" value
    client = TestClient(app)

    resp_china = client.get("/api/overview", params={"countries": "China"})
    resp_france = client.get("/api/overview", params={"countries": "France"})

    body_china = resp_china.json()
    body_france = resp_france.json()

    assert body_china["selected"]["latest_co2_total"] == 11000
    assert body_china["selected_country_list"] == ["China"]
    assert body_france["selected"]["latest_co2_total"] == 300
    assert body_france["selected_country_list"] == ["France"]

    # all_countries/expanded_countries are independent of the countries param -- identical
    # across both responses even though `selected` differs.
    assert body_china["all_countries"] == body_france["all_countries"]
    assert body_china["expanded_countries"] == body_france["expanded_countries"]


def test_overview_422_over_max_selected_countries(client):
    resp = client.get("/api/overview", params={"countries": [f"Country{i}" for i in range(11)]})
    assert resp.status_code == 422


def test_overview_404_on_unknown_country(client):
    resp = client.get("/api/overview", params={"countries": "France"})  # not in the real FEATURED_COUNTRIES fallback
    assert resp.status_code == 404


def test_overview_top_movers_falls_back_to_na_when_selection_has_no_complete_pair(full_data):
    """Ruritania (conftest fixture) has only a 2023 row, no 1990 -- selecting it alone
    empties top_movers after dropna(). fastest_growth/largest_reduction must fall back to
    an "N/A" placeholder instead of crashing with an IndexError."""
    import json

    from fastapi.testclient import TestClient

    from api.main import app

    with open(full_data / "selected_countries.json", "w") as f:
        json.dump({"expanded": ["China", "United States", "Germany", "Ruritania"]}, f)

    resp = TestClient(app).get("/api/overview", params={"countries": "Ruritania"})
    assert resp.status_code == 200
    body = resp.json()

    assert body["top_movers"] == []
    assert body["fastest_growth"]["country"] == "N/A"
    assert body["fastest_growth"]["pct_change"] is None
    assert body["largest_reduction"]["country"] == "N/A"


def test_overview_top_movers_ordering(client):
    body = client.get("/api/overview").json()
    movers_by_country = {m["country"]: m["pct_change"] for m in body["top_movers"]}

    # China grew ~358%, United States shrank ~6%, Germany shrank ~40%.
    assert body["fastest_growth"]["country"] == "China"
    assert body["largest_reduction"]["country"] == "Germany"
    pct_values = [m["pct_change"] for m in body["top_movers"]]
    assert pct_values == sorted(pct_values, reverse=True)
    assert round(movers_by_country["China"], 1) == round((11000 - 2400) / 2400 * 100, 1)


def test_overview_latest_year_bar_scoped_to_selected(full_data):
    from fastapi.testclient import TestClient

    from api.main import app

    write_selected_countries_json(full_data)
    resp = TestClient(app).get("/api/overview", params={"countries": "France"})
    countries_in_bar = {row["country"] for row in resp.json()["latest_year_bar"]}
    assert countries_in_bar == {"France"}


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


def test_overview_503_when_raw_owid_data_missing(data_dir):
    """ghg_features.csv present (so the Expanded/Selected tiers' prerequisite is satisfied),
    but owid-co2-data.csv absent -- the new All Countries tier's own prerequisite."""
    write_fixture(data_dir, "ghg_features.csv")
    from fastapi.testclient import TestClient

    from api.main import app

    resp = TestClient(app).get("/api/overview")
    assert resp.status_code == 503
    assert "owid-co2-data.csv" in resp.json()["detail"]
