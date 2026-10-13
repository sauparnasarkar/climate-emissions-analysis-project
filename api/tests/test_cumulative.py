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


# --- counting from a year: `from_year` (Release 24.8, D7) -------------------------------------------------------------------------------------------------------
# Fixture totals: World 950 (1969) / 1000 (1970) / 2000 (2022) / 2100 (2023); China 20 / 50 / 400 / 450; United States 280 / 300 / 700 / 720; Germany 95 / 100 / 150 / 152;
# Canada (no 1969 row: base 0) 40 / 80 / 82; Ruritania (no 1969 row) 10 / NaN / 11.


def test_the_default_still_counts_from_the_first_record_and_never_shows_the_1969_base_year(cclient):
    body = cclient.get("/api/historical/cumulative", params={"countries": ["China"]}).json()
    assert body["years"] == [1970, 2022, 2023] and body["from_year"] is None and body["latest_year"] == 2023
    assert body["series"][0]["cumulative_co2"] == [50.0, 400.0, 450.0] and body["world_cumulative_co2"] == [1000.0, 2000.0, 2100.0]


def test_from_1970_subtracts_the_1969_total_from_every_running_total_and_the_worlds(cclient):
    body = cclient.get("/api/historical/cumulative", params={"countries": ["China", "Canada"], "from_year": 1970, "scope": "sovereign"}).json()
    assert body["years"] == [1970, 2022, 2023] and body["from_year"] == 1970
    assert body["world_cumulative_co2"] == [50.0, 1050.0, 1150.0]  # the World's emissions in the period, from zero at the base
    china, canada = body["series"]
    assert china["cumulative_co2"] == [30.0, 380.0, 430.0]  # minus its 1969 total of 20
    assert canada["cumulative_co2"] == [40.0, 80.0, 82.0]  # no 1969 row: it had emitted nothing before, so its base is 0
    assert china["share_of_world_cumulative"] == [60.0, pytest.approx(380 / 1050 * 100), pytest.approx(430 / 1150 * 100)]  # a share of the PERIOD's emissions
    assert china["share_of_world_annual"] == [4.0, 30.0, 31.0]  # the year's own share is unchanged


def test_from_a_later_year_starts_the_years_there_and_uses_the_year_before_as_the_base(cclient):
    body = cclient.get("/api/historical/cumulative", params={"countries": ["China"], "from_year": 1971}).json()
    assert body["years"] == [2022, 2023]  # the fixture has no 1971..2021 rows; the base is the 1970 total (50)
    assert body["series"][0]["cumulative_co2"] == [350.0, 400.0] and body["world_cumulative_co2"] == [1000.0, 1100.0]


def test_from_year_outside_1970_to_the_latest_year_is_a_422_naming_the_range(cclient):
    for bad in (1969, 1800, 2024):
        r = cclient.get("/api/historical/cumulative", params={"countries": ["China"], "from_year": bad})
        assert r.status_code == 422 and "between 1970 and 2023" in r.json()["detail"], bad
        assert cclient.get("/api/countries/China/cumulative", params={"from_year": bad}).status_code == 422
    assert cclient.get("/api/historical/cumulative", params={"countries": ["China"], "from_year": 2023}).status_code == 200


def test_the_country_profile_counting_from_a_year_has_the_periods_total_share_and_rank(cclient):
    body = cclient.get("/api/countries/China/cumulative", params={"from_year": 1970}).json()
    assert body["from_year"] == 1970 and body["years"] == [1970, 2022, 2023] and body["cumulative_co2"] == [30.0, 380.0, 430.0]
    latest = body["latest"]
    assert latest["year"] == 2023 and latest["cumulative_co2"] == 430.0 and latest["share_of_world_cumulative"] == pytest.approx(430 / 1150 * 100)
    # emissions 1970-2023 among sovereign countries: USA 440, China 430, Canada 82, Germany 57, Ruritania 11 -> China is 2nd of 5
    assert (latest["rank"], latest["rank_of"]) == (2, 5)
    default = cclient.get("/api/countries/China/cumulative").json()["latest"]
    assert default["cumulative_co2"] == 450.0 and default["rank"] == 2 and body["latest"]["cumulative_co2"] < default["cumulative_co2"]  # a smaller figure than since records began


def test_a_late_starter_with_no_value_at_the_base_year_has_a_zero_base_and_a_missing_value_stays_missing(cclient):
    body = cclient.get("/api/historical/cumulative", params={"countries": ["Ruritania"], "from_year": 1970, "scope": "sovereign"}).json()
    assert body["series"][0]["cumulative_co2"] == [10.0, None, 11.0]  # no 1969 row: base 0; the null 2022 value stays None, not a number
