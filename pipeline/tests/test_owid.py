import json
import os
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from pipeline import owid

TODAY = date(2025, 10, 2)  # the synthetic data ends in 2024, so 'today' is a year later (lag within limits)


def make_df(years=range(1990, 2025), partial_last=False, jump_last=False, drop_bbb_before=None, no_cum=False):
    rows = []
    cum = 0.0
    for y in years:
        g = 1.01 ** (y - 1990)
        a, b, c = 1000 * g, 2000 * g, 500 * g
        air, ship = 80 * g, 120 * g
        world = a + b + c + air + ship
        if jump_last and y == max(years):
            world *= 1.4
        cum += world
        if partial_last and y == max(years):
            b = c = np.nan  # only one country reports; World is also incomplete
            world = a + air + ship
        for name, iso, v in [("Aland", "AAA", a), ("Bland", "BBB", b), ("Cland", "CCC", c)]:
            if drop_bbb_before and name == "Bland" and y < drop_bbb_before:
                continue
            rows.append((name, y, iso, v, np.nan, 1.0, 1.0))
        rows.append(("International aviation", y, np.nan, air, np.nan, np.nan, np.nan))
        rows.append(("International shipping", y, np.nan, ship, np.nan, np.nan, np.nan))
        rows.append(("World", y, np.nan, world, np.nan if no_cum else cum, 1.0, 1.0))
        rows.append(("Europe", y, np.nan, 5.0, np.nan, np.nan, np.nan))  # an aggregate without iso: must be ignored for countries
    return pd.DataFrame(rows, columns=["country", "year", "iso_code", "co2", "cumulative_co2", "methane", "nitrous_oxide"])


def write(tmp_path, df, name="owid.csv", age_days=1):
    p = tmp_path / name
    df.to_csv(p, index=False)
    t = datetime(TODAY.year, TODAY.month, TODAY.day, tzinfo=timezone.utc).timestamp() - age_days * 86400  # relative to TODAY, not the real clock
    os.utime(p, (t, t))
    return str(p)


def run(tmp_path, path, **kw):
    return owid.run(path, out_dir=str(tmp_path / "out"), provenance_path=str(tmp_path / "p.json"), today=kw.pop("today", TODAY), **kw)


def test_run_publishes_world_series_and_provenance(tmp_path):
    path = write(tmp_path, make_df())
    rep = run(tmp_path, path)
    assert rep.deviations == []
    s = pd.read_csv(tmp_path / "out" / "owid_world_co2_annual.csv").set_index("year")
    assert s.index.min() == 1990 and s.index.max() == 2024
    r = s.loc[1990]
    assert r["co2_mt"] == pytest.approx(3700.0) and r["national_sum_mt"] == pytest.approx(3500.0)
    assert r["international_transport_mt"] == pytest.approx(200.0) and r["countries_reporting"] == 3
    assert s["cumulative_co2_mt"].is_monotonic_increasing
    assert any("reconciles to national sum + international transport" in n for n in rep.notes)
    p = json.loads((tmp_path / "p.json").read_text())
    w, c = p["owid_world_co2_annual"], p["owid_country_co2"]
    assert w["coverage"] == [1990, 2024] and "CC BY 4.0" in w["license"] and len(w["citations"]) == 2 and w["published"] is True
    assert c["rows_in_source"] == len(make_df()) and len(c["raw_sha256"]["owid-co2-data.csv"]) == 64
    assert "does not download" in w["retrieved_at_basis"] or "not download" in w["retrieved_at_basis"]


def test_required_column_missing_and_missing_file_fail_loudly(tmp_path):
    with pytest.raises(FileNotFoundError, match="refresh job downloads it"):
        run(tmp_path, str(tmp_path / "nope.csv"))
    with pytest.raises(ValueError, match="required column.*methane"):
        run(tmp_path, write(tmp_path, make_df().drop(columns=["methane"])))


def test_world_gap_in_years_raises(tmp_path):
    df = make_df()
    df = df[~((df.country == "World") & (df.year == 2005))]
    with pytest.raises(ValueError, match="OWID World CO2: 1 missing year"):
        run(tmp_path, write(tmp_path, df))


def test_partial_latest_year_is_trimmed_not_published(tmp_path):
    rep = run(tmp_path, write(tmp_path, make_df(partial_last=True)))
    s = pd.read_csv(tmp_path / "out" / "owid_world_co2_annual.csv")
    assert s["year"].max() == 2023
    assert any("excluded incomplete year 2024" in n and "country coverage" in n for n in rep.notes) and rep.deviations == []
    assert json.loads((tmp_path / "p.json").read_text())["owid_world_co2_annual"]["excluded_incomplete_years"][0]["year"] == 2024


def test_world_jump_beyond_limit_is_trimmed(tmp_path):
    rep = run(tmp_path, write(tmp_path, make_df(jump_last=True)))
    assert pd.read_csv(tmp_path / "out" / "owid_world_co2_annual.csv")["year"].max() == 2023
    assert any("vs prior year" in n for n in rep.notes)


def _partial(df, years):
    for y in years:
        df.loc[(df.year == y) & df.country.isin(["Bland", "Cland"]), "co2"] = np.nan
        df.loc[(df.year == y) & (df.country == "World"), "co2"] = 1500.0 + 10 * (y - years[0])
    return df


def test_cascading_partial_years_are_trimmed_from_the_first_failure(tmp_path):
    # 2023 is partial; 2024 is equally partial so it looks complete *relative to 2023* -- but 2023 must not be published
    rep = run(tmp_path, write(tmp_path, _partial(make_df(), [2023, 2024])))
    s = pd.read_csv(tmp_path / "out" / "owid_world_co2_annual.csv")
    assert s["year"].max() == 2022
    ex = json.loads((tmp_path / "p.json").read_text())["owid_world_co2_annual"]["excluded_incomplete_years"]
    assert [e["year"] for e in ex] == [2024, 2023] and "measured against partial data" in ex[0]["reasons"]
    assert any("2 trailing OWID years excluded" in d for d in rep.deviations)


def test_more_than_two_incomplete_years_raise(tmp_path):
    with pytest.raises(ValueError, match="3 trailing years fail the completeness test.*more than 2"):
        run(tmp_path, write(tmp_path, _partial(make_df(), [2022, 2023, 2024])))


def test_stale_file_flags_refresh_job_not_running(tmp_path):
    rep = run(tmp_path, write(tmp_path, make_df(), age_days=75))
    assert any("75 days ago" in d and "may have stopped running" in d for d in rep.deviations)


def test_row_drop_since_previous_run_deviates(tmp_path):
    run(tmp_path, write(tmp_path, make_df()))
    rep = run(tmp_path, write(tmp_path, make_df(drop_bbb_before=2010, ), "owid2.csv"))  # drops 20 rows of ~140
    assert any("row count fell" in d for d in rep.deviations) or any("rows" in n and "-" in n for n in rep.notes)
    rep2 = run(tmp_path, write(tmp_path, make_df(), "owid3.csv"))
    assert any("vs previous run" in n for n in rep2.notes)


def test_world_not_reconciling_to_national_plus_transport_deviates(tmp_path):
    df = make_df()
    df.loc[(df.country == "World") & (df.year == 2024), "co2"] *= 1.06
    rep = run(tmp_path, write(tmp_path, df))
    assert any("differs from national sum + international transport" in d for d in rep.deviations)


def test_missing_cumulative_deviates(tmp_path):
    rep = run(tmp_path, write(tmp_path, make_df(no_cum=True)))
    assert any("cumulative_co2 is missing" in d for d in rep.deviations)


def test_owid_url_comes_from_constants(tmp_path):
    (tmp_path / "notebook").mkdir()
    (tmp_path / "notebook" / "constants.py").write_text('# c\nOWID_URL = "https://example.test/owid.csv"\nX = 1\n')
    assert owid.owid_url(str(tmp_path)) == "https://example.test/owid.csv"
    (tmp_path / "notebook" / "constants.py").write_text("X = 1\n")
    with pytest.raises(ValueError, match="OWID_URL not found"):
        owid.owid_url(str(tmp_path))
    assert owid.owid_url().startswith("https://")  # the real constants file
