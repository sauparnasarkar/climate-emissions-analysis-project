import json
import os
from datetime import date, datetime, timezone

import numpy as np
import pandas as pd
import pytest

from pipeline import owid

TODAY = date(2025, 10, 2)  # the synthetic data ends in 2024, so 'today' is a year later (lag within limits)


def make_df(years=range(1990, 2025), partial_last=False, jump_last=False, drop_bbb_before=None, no_cum=False, luc=True, luc_end=None, luc_gap=None, luc_start=None):
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
            rows.append((name, y, iso, v, np.nan, 1.0, 1.0, np.nan))
        rows.append(("International aviation", y, np.nan, air, np.nan, np.nan, np.nan, np.nan))
        rows.append(("International shipping", y, np.nan, ship, np.nan, np.nan, np.nan, np.nan))
        luc_v = 400.0 + 2 * (y - 1990)  # land-use CO2 (Mt): a separate World column, not part of `co2`
        if not luc or (luc_end and y > luc_end) or (luc_gap and y == luc_gap) or (luc_start and y < luc_start):
            luc_v = np.nan
        rows.append(("World", y, np.nan, world, np.nan if no_cum else cum, 1.0, 1.0, luc_v))
        rows.append(("Europe", y, np.nan, 5.0, np.nan, np.nan, np.nan, np.nan))  # an aggregate without iso: must be ignored for countries
    return pd.DataFrame(rows, columns=["country", "year", "iso_code", "co2", "cumulative_co2", "methane", "nitrous_oxide", "land_use_change_co2"])


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
    assert w["coverage"] == [1990, 2024] and "CC BY 4.0" in w["license"] and len(w["citations"]) == 3 and w["published"] is True
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


def test_year_with_no_country_observations_at_all_is_not_published(tmp_path):
    # 2024 has a World row (and transport) but not a single ISO-coded country row: the pivot drops the year entirely
    df = make_df()
    df = df[~((df.year == 2024) & df.country.isin(["Aland", "Bland", "Cland"]))]
    rep = run(tmp_path, write(tmp_path, df))
    s = pd.read_csv(tmp_path / "out" / "owid_world_co2_annual.csv")
    assert s["year"].max() == 2023
    assert any("excluded incomplete year 2024: no country observations" in n for n in rep.notes)


# ---------------------------------------------------------------- land-use CO2 and total anthropogenic CO2 (decision 40)


def test_land_use_and_total_columns_are_published_and_add_up(tmp_path):
    rep = run(tmp_path, write(tmp_path, make_df()))
    assert rep.deviations == []
    s = pd.read_csv(tmp_path / "out" / "owid_world_co2_annual.csv").set_index("year")
    assert s.loc[1990, "land_use_change_co2_mt"] == pytest.approx(400.0) and s.loc[2024, "land_use_change_co2_mt"] == pytest.approx(400.0 + 2 * 34)
    assert (s["total_co2_incl_luc_mt"] - (s["co2_mt"] + s["land_use_change_co2_mt"])).abs().max() < 1e-3
    assert any("World land-use CO2 1990-2024" in n for n in rep.notes)


def test_land_use_licence_note_and_citation_are_in_provenance_verbatim(tmp_path):
    run(tmp_path, write(tmp_path, make_df()))
    w = json.loads((tmp_path / "p.json").read_text())["owid_world_co2_annual"]
    assert w["land_use_license_note"] == owid.LAND_USE_LICENSE_NOTE
    for phrase in ("originates from the Global Carbon Project via OWID", "No formal license (e.g., CC BY) is stated", "use is conditional on citing the original source",
                   "No non-commercial, no-derivatives, or share-alike restrictions were found"):
        assert phrase in w["land_use_license_note"]
    assert "licensed under" not in w["land_use_license_note"].lower() and "is cc by" not in w["land_use_license_note"].lower()  # never defaulted to a claimed CC BY licence
    assert w["attribution_required"] is True and "doi.org/10.18160/gcp-" in w["required_citation_format"]
    assert any("Supplemental data of Global Carbon Budget" in c for c in w["citations"])
    assert any("separate column" in c for c in w["caveats"]) and any("+/-0.7 GtC/yr" in c for c in w["caveats"])
    assert "Global Carbon Project" in w["columns"]["land_use_change_co2_mt"]


def test_missing_land_use_column_is_a_deviation_but_the_fossil_series_survives(tmp_path):
    df = make_df().drop(columns=["land_use_change_co2"])
    rep = run(tmp_path, write(tmp_path, df))
    assert any("land_use_change_co2" in d and "unavailable" in d for d in rep.deviations)
    s = pd.read_csv(tmp_path / "out" / "owid_world_co2_annual.csv")
    assert s["co2_mt"].notna().all() and s["land_use_change_co2_mt"].isna().all() and s["total_co2_incl_luc_mt"].isna().all()


def test_land_use_series_ending_before_the_last_year_and_interior_gaps_are_deviations(tmp_path):
    rep = run(tmp_path, write(tmp_path, make_df(luc_end=2022)))
    assert any("ends in 2022" in d and "2023-2024" in d for d in rep.deviations)
    s = pd.read_csv(tmp_path / "out" / "owid_world_co2_annual.csv").set_index("year")
    assert s.loc[2022, "total_co2_incl_luc_mt"] > 0 and pd.isna(s.loc[2023, "total_co2_incl_luc_mt"])  # no total where a component is absent
    rep2 = run(tmp_path, write(tmp_path, make_df(luc_gap=2005, ), name="g.csv"))
    assert any("interior gap" in d and "2005" in d for d in rep2.deviations)


def test_land_use_series_starting_late_is_a_deviation_not_a_silently_shorter_period(tmp_path):
    rep = run(tmp_path, write(tmp_path, make_df(luc_start=2000)))
    assert any("land-use CO2 starts in 2000, after 1990" in d and "silently start later" in d for d in rep.deviations)
    rep_ok = run(tmp_path, write(tmp_path, make_df(), name="ok.csv"))  # starting with the CO2 series (or 1850, whichever is later) is fine
    assert not any("starts in" in d for d in rep_ok.deviations)


def test_land_use_observations_before_the_start_year_are_ignored_not_accumulated(tmp_path, monkeypatch):
    monkeypatch.setattr(owid, "LAND_USE_START", 2000)  # the synthetic data has land-use from 1990: 1990-1999 are 'before the start'
    rep = run(tmp_path, write(tmp_path, make_df()))
    s = pd.read_csv(tmp_path / "out" / "owid_world_co2_annual.csv").set_index("year")
    assert s.loc[:1999, "land_use_change_co2_mt"].isna().all() and s.loc[:1999, "total_co2_incl_luc_mt"].isna().all()
    assert s.loc[2000, "land_use_change_co2_mt"] == pytest.approx(400.0 + 2 * 10) and s.loc[2000:, "total_co2_incl_luc_mt"].notna().all()
    assert any("10 observation(s) before 2000 (1990-1999); ignored" in n for n in rep.notes)
    assert not any("land-use" in d.lower() for d in rep.deviations)  # trimmed, so no late-start or gap deviation either
    assert s["co2_mt"].notna().all()  # the fossil series is untouched
