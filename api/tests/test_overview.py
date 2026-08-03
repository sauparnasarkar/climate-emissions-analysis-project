from .conftest import owid_raw_world_map_series_df, write_fixture, write_selected_countries_json


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
    """all_countries reflects the full iso_code.notna()-filtered raw universe (SPEC.md §6.1)
    -- the fixture's injected "World" row (9999.0 at year 2010, iso_code=None) must not leak
    into the total, and Canada (present only via a one-off fixture row) must be counted since
    it's a real sovereign."""
    body = client.get("/api/overview").json()
    tier = body["all_countries"]

    assert tier["label"] == "All Countries"
    assert tier["countries_count"] == 4  # China, United States, Germany, Canada
    assert tier["latest_year"] == 2010  # owid_raw_df()'s own latest year, independent of ghg_features.csv's
    assert tier["latest_co2_total"] == 312.0  # China+US+Germany at year 2010, 104.0 each -- World's 9999.0 excluded
    assert tier["co2_1990_total"] == 300.0  # China+US+Germany at year 1990, 100.0 each
    assert round(tier["pct_change_since_1990"], 2) == round((312.0 - 300.0) / 300.0 * 100, 2)


def test_overview_world_map_is_unfiltered_latest_year_with_iso_codes(client):
    """world_map is always every sovereign country's own latest year -- independent of
    `countries`/Selected, matching all_countries. Canada has no row at the fixture's latest
    year (2010, only a 1995 row), so it's absent from world_map despite counting toward
    all_countries' countries_count; World is excluded (null iso_code, SPEC.md §6.1)."""
    body = client.get("/api/overview").json()
    points_by_country = {p["country"]: p for p in body["world_map"]}

    assert set(points_by_country) == {"China", "United States", "Germany"}
    assert points_by_country["China"]["iso_code"] == "CHN"
    assert points_by_country["China"]["value"] == 104.0
    assert points_by_country["United States"]["iso_code"] == "USA"


def test_overview_world_map_unaffected_by_countries_param(client):
    """world_map doesn't change when a narrower `countries` selection is requested --
    it's always the full sovereign universe, same as all_countries."""
    default_map = client.get("/api/overview").json()["world_map"]
    scoped_map = client.get("/api/overview", params={"countries": ["China"]}).json()["world_map"]
    assert default_map == scoped_map


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


def test_overview_co2_by_year_present_for_all_and_expanded_empty_for_selected(client):
    """SPEC.md §5.17.5 -- co2_by_year backs the animated choropleth's synced KPI numbers for
    All Countries/Expanded; Selected is summed client-side instead, so the API never computes
    it (empty list, not omitted/null, per the schema's `= []` default)."""
    resp = client.get("/api/overview")
    body = resp.json()

    assert len(body["all_countries"]["co2_by_year"]) == 35  # WORLD_MAP_YEAR_START..END inclusive
    assert len(body["expanded_countries"]["co2_by_year"]) == 35
    assert body["selected"]["co2_by_year"] == []

    # owid_raw_df's fixture has China/US/Germany at co2=100.0 each for year 1990 (load_raw_sovereign
    # includes every sovereign country, not just FEATURED_COUNTRIES, but Canada's only fixture row
    # is 1995) -- All Countries' 1990 total is exactly their sum.
    assert body["all_countries"]["co2_by_year"][0] == 300.0
    # A year with no fixture rows at all reindexes to 0.0, not null/omitted.
    assert body["all_countries"]["co2_by_year"][1] == 0.0  # 1991


def test_world_map_series_shape_ordering_and_value_range(data_dir):
    owid_raw_world_map_series_df().to_csv(data_dir / "owid-co2-data.csv", index=False)
    from fastapi.testclient import TestClient

    from api.main import app

    resp = TestClient(app).get("/api/overview/world-map-series")
    assert resp.status_code == 200
    body = resp.json()

    assert body["years"] == list(range(1990, 2025))
    # Deterministic order: sorted by iso_code, not fixture insertion order (China/US/Kiribati/Monaco).
    assert body["iso_codes"] == sorted(["CHN", "USA", "KIR", "MCO"])
    assert body["countries"][body["iso_codes"].index("CHN")] == "China"
    assert len(body["values"]) == 35
    assert all(len(row) == 4 for row in body["values"])

    # value_range spans every year, not just one -- max is China's 2024 value (8000 + 34*150),
    # min is Kiribati's constant 50.0 (lower than any US value, which ranges 5000 down to 4650.0).
    assert body["value_range"] == [50.0, 8000.0 + 34 * 150.0]


def test_world_map_series_no_data_gaps(data_dir):
    """Kiribati (mirrors the real CXR/ERI/FSM/MHL/NAM/TLS pattern) has no data until 1995, then
    is complete; Monaco (mirrors the real MCO/SMR/VAT pattern) has no data in any year."""
    owid_raw_world_map_series_df().to_csv(data_dir / "owid-co2-data.csv", index=False)
    from fastapi.testclient import TestClient

    from api.main import app

    resp = TestClient(app).get("/api/overview/world-map-series")
    body = resp.json()
    kir_idx = body["iso_codes"].index("KIR")
    mco_idx = body["iso_codes"].index("MCO")
    year_1990_idx = body["years"].index(1990)
    year_1995_idx = body["years"].index(1995)

    assert body["values"][year_1990_idx][kir_idx] is None
    assert body["values"][year_1995_idx][kir_idx] == 50.0
    assert all(body["values"][y][mco_idx] is None for y in range(len(body["years"])))


def test_world_map_series_503_when_raw_owid_data_missing(data_dir):
    from fastapi.testclient import TestClient

    from api.main import app

    resp = TestClient(app).get("/api/overview/world-map-series")
    assert resp.status_code == 503
    assert "owid-co2-data.csv" in resp.json()["detail"]


def test_world_map_series_value_range_excludes_literal_zero(data_dir):
    """A real entity (Antarctica, confirmed against the actual OWID data) reports literal 0.0
    co2 in some years -- genuinely zero, not missing. log10(0) is undefined, so value_range's
    floor must be the smallest *positive* value, not 0.0, or a zLog consumer's colorRange would
    compute a null zmin."""
    import pandas as pd

    rows = [
        ("Antarctica", 1990, 0.0, "ATA"),
        ("Antarctica", 2024, 0.0, "ATA"),
        ("China", 1990, 0.004, "CHN"),  # smallest genuinely positive value in this fixture
        ("China", 2024, 8000.0, "CHN"),
    ]
    pd.DataFrame(rows, columns=["country", "year", "co2", "iso_code"]).to_csv(data_dir / "owid-co2-data.csv", index=False)
    from fastapi.testclient import TestClient

    from api.main import app

    resp = TestClient(app).get("/api/overview/world-map-series")
    body = resp.json()
    assert body["value_range"] == [0.004, 8000.0]
