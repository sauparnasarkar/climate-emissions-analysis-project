"""Release 24: one country, one number. The Release 23 views (`/countries/{c}/cumulative`) and the Correlation share endpoint (what the agent's
`get_country_cumulative_share` returns) must give the same cumulative total, share, rank and `rank_of` for the same country and year.

Runs on the real (gitignored) data and is skipped where it is absent: the stub fixtures cannot show a disagreement between two computations of OWID's
own numbers."""

import os

import pytest
from fastapi.testclient import TestClient

from api import data_loaders
from api.main import app

REAL = os.path.join(data_loaders.DATA_DIR, "owid-co2-data.csv")
REAL_CLIMATE = os.path.join(data_loaders.DATA_DIR, "climate", "correlation_country_share.csv")

pytestmark = pytest.mark.skipif(not (os.path.exists(REAL) and os.path.exists(REAL_CLIMATE)), reason="needs the real (gitignored) OWID and Area 2 data")

COUNTRIES = [("China", "CHN"), ("United States", "USA"), ("India", "IND"), ("Germany", "DEU"), ("United Kingdom", "GBR")]


def test_share_tool_numbers_equal_the_release_23_numbers():
    c = TestClient(app)
    ranking = {r["country"]: r for r in c.get("/api/correlation/country-share?all_countries=true").json()["rows"]}
    year = c.get("/api/correlation/country-share?limit=1").json()["year"]
    for name, iso in COUNTRIES:
        latest = c.get(f"/api/countries/{name}/cumulative").json()["latest"]
        row = ranking[iso]
        assert latest["year"] == year, name
        assert row["cumulative_mt"] == pytest.approx(latest["cumulative_co2"], rel=1e-6, abs=0.01), name
        assert row["share_pct"] == pytest.approx(latest["share_of_world_cumulative"], abs=0.002), name  # OWID rounds its own shares to three decimals
        assert row["rank"] == latest["rank"], name
    assert len(ranking) == c.get("/api/countries/China/cumulative").json()["latest"]["rank_of"]


def test_emissions_since_a_year_are_the_difference_of_cumulatives_and_equal_the_sum_of_the_annual_values():
    """Release 24.7 ("since YYYY"): emitted since X = the cumulative total at the end year minus the total at X-1, which must equal the sum of the annual values
    of X..end. Checked for China and the World, and the since-1970 ranking's top five pinned (US, China, Russia, India, Japan)."""
    c = TestClient(app)
    j = c.get("/api/correlation/country-share?countries=CHN&start_year=1989").json()
    pts = {p["year"]: p for p in j["series"][0]["points"]}
    last = max(pts)
    since = pts[last]["cumulative_mt"] - pts[1989]["cumulative_mt"]
    assert since == pytest.approx(sum(p["annual_mt"] for y, p in pts.items() if y >= 1990), rel=1e-9)
    rem = {r["year"]: r for r in j["remainder_series"]}
    world = rem[last]["world_cumulative_mt"] - rem[1989]["world_cumulative_mt"]
    assert 0 < since / world < 0.5  # a share of the period's emissions (China 1990-2024: about 23%)
    end = {r["country"]: r["cumulative_mt"] for r in c.get("/api/correlation/country-share?all_countries=true").json()["rows"]}
    base = {r["country"]: r["cumulative_mt"] for r in c.get("/api/correlation/country-share?all_countries=true&year=1969").json()["rows"]}
    emitted = sorted(((end[k] - base.get(k, 0.0), k) for k in end), reverse=True)
    assert [k for _, k in emitted[:5]] == ["USA", "CHN", "RUS", "IND", "JPN"]
