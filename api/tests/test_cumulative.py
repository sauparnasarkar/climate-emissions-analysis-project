"""/historical/cumulative and /countries/{country}/cumulative (SPEC.md §5.28)."""

import pytest
from fastapi.testclient import TestClient

from api.tests.conftest import write_cumulative_fixture


@pytest.fixture
def cclient(data_dir):
    write_cumulative_fixture(data_dir)
    from api.main import app

    return TestClient(app)


def test_historical_cumulative_window_and_alignment(cclient):
    body = cclient.get("/api/historical/cumulative", params={"countries": ["China", "United States"]}).json()
    # The 1965 rows are cut by the 1970 window; years come from the World aggregate.
    assert body["years"] == [1970, 2022, 2023]
    assert body["world_cumulative_co2"] == [1000.0, 2000.0, 2100.0]
    china, us = body["series"]
    assert china["name"] == "China" and us["name"] == "United States"
    assert china["cumulative_co2"] == [50.0, 400.0, 450.0]
    assert china["share_of_world_cumulative"] == [5.0, 20.0, 21.4]
    assert china["share_of_world_annual"] == [4.0, 30.0, 31.0]
    for s in body["series"]:
        assert len(s["cumulative_co2"]) == len(body["years"])


def test_historical_cumulative_rest_of_world_is_never_negative(cclient):
    body = cclient.get(
        "/api/historical/cumulative", params={"countries": ["China", "United States", "Germany"]}
    ).json()
    for i in range(len(body["years"])):
        shown = sum(s["cumulative_co2"][i] for s in body["series"])
        assert body["world_cumulative_co2"][i] - shown >= 0


def test_historical_cumulative_null_becomes_none(cclient):
    body = cclient.get(
        "/api/historical/cumulative", params={"countries": ["Ruritania"], "scope": "sovereign"}
    ).json()
    s = body["series"][0]
    assert s["cumulative_co2"] == [10.0, None, 11.0]
    assert s["share_of_world_cumulative"][1] is None and s["share_of_world_annual"][1] is None


def test_historical_cumulative_default_is_featured_countries(cclient):
    # No `countries`: the featured ten, like /historical/timeseries. Only three are in the fixture, so the rest 404.
    resp = cclient.get("/api/historical/cumulative")
    assert resp.status_code == 404
    assert "Brazil" in resp.json()["detail"]


def test_historical_cumulative_scope(cclient):
    # Canada is sovereign but outside featured/expanded; the aggregate "Asia" is never sovereign.
    assert cclient.get("/api/historical/cumulative", params={"countries": ["Canada"]}).status_code == 404
    ok = cclient.get("/api/historical/cumulative", params={"countries": ["Canada"], "scope": "sovereign"})
    assert ok.status_code == 200 and ok.json()["series"][0]["name"] == "Canada"
    assert cclient.get(
        "/api/historical/cumulative", params={"countries": ["Asia"], "scope": "sovereign"}
    ).status_code == 404


def test_historical_cumulative_unknown_country_is_404(cclient):
    resp = cclient.get("/api/historical/cumulative", params={"countries": ["Atlantis"]})
    assert resp.status_code == 404
    assert "Atlantis" in resp.json()["detail"]


def test_historical_cumulative_more_than_ten_countries_is_422(cclient):
    resp = cclient.get("/api/historical/cumulative", params={"countries": [f"C{i}" for i in range(11)]})
    assert resp.status_code == 422


def test_historical_cumulative_duplicate_countries_collapse(cclient):
    body = cclient.get("/api/historical/cumulative", params={"countries": ["China", "China"]}).json()
    assert [s["name"] for s in body["series"]] == ["China"]


def test_historical_cumulative_missing_file_is_503(data_dir):
    from api.main import app

    assert TestClient(app).get("/api/historical/cumulative", params={"countries": ["China"]}).status_code == 503


def test_historical_cumulative_file_without_columns_is_503(data_dir):
    # An older owid-co2-data.csv lacking the cumulative columns degrades to 503 rather than a 500.
    (data_dir / "owid-co2-data.csv").write_text("country,year,iso_code\nChina,2000,CHN\n")
    from api.main import app

    assert TestClient(app).get("/api/historical/cumulative", params={"countries": ["China"]}).status_code == 503


def test_country_cumulative_series_and_latest(cclient):
    body = cclient.get("/api/countries/China/cumulative").json()
    assert body["years"] == [1970, 2022, 2023]
    assert body["cumulative_co2"] == [50.0, 400.0, 450.0]
    assert body["share_of_world_annual"] == [4.0, 30.0, 31.0]
    # 2023: United States 720 and China 450 lead Germany 152, Canada 82, Ruritania 11; Asia is an aggregate.
    assert body["latest"] == {
        "year": 2023, "cumulative_co2": 450.0, "share_of_world_cumulative": 21.4, "rank": 2, "rank_of": 5,
    }


def test_country_cumulative_rank_ignores_aggregates(cclient):
    # Asia (650) would outrank China (450) if aggregates counted; China must be #2 behind the US only.
    assert cclient.get("/api/countries/China/cumulative").json()["latest"]["rank"] == 2
    assert cclient.get("/api/countries/United States/cumulative").json()["latest"]["rank"] == 1


def test_country_cumulative_latest_skips_null_years(data_dir):
    # A country whose newest row is null reports its last real year.
    from api.tests.conftest import owid_cumulative_df

    df = owid_cumulative_df()
    df.loc[(df["country"] == "China") & (df["year"] == 2023), ["cumulative_co2", "share_global_cumulative_co2"]] = float("nan")
    df.to_csv(data_dir / "owid-co2-data.csv", index=False)
    from api.main import app

    body = TestClient(app).get("/api/countries/China/cumulative").json()
    assert body["cumulative_co2"][-1] is None
    assert body["latest"]["year"] == 2022 and body["latest"]["cumulative_co2"] == 400.0


def test_country_cumulative_unknown_and_out_of_scope_are_404(cclient):
    assert cclient.get("/api/countries/Atlantis/cumulative").status_code == 404
    # Canada is in the file but not in the (fallback) expanded list, like /profile.
    assert cclient.get("/api/countries/Canada/cumulative").status_code == 404


def test_country_cumulative_missing_file_is_503(data_dir):
    from api.main import app

    assert TestClient(app).get("/api/countries/China/cumulative").status_code == 503


def test_country_profile_is_unchanged(full_data):
    from api.main import app

    body = TestClient(app).get("/api/countries/China/profile").json()
    assert "cumulative_co2" not in body and body["years"] == [1990, 2020, 2023]
