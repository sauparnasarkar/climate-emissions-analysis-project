import json
import os

import numpy as np
import pandas as pd
import pytest

from pipeline import country_share as S

LAST = 2000
YEARS = list(range(1840, LAST + 1))


def annual(country, y):
    """A: 10/yr from 1840. B: 5/yr from 1900. C: 1/yr from 1840 with 1950-1952 missing. D: 2/yr from 1840 but its record ends in 1970."""
    if country == "AAA":
        return 10.0
    if country == "BBB":
        return 5.0 if y >= 1900 else None
    if country == "CCC":
        return None if 1950 <= y <= 1952 else 1.0
    if country == "DDD":
        return 2.0 if y <= 1970 else None
    raise KeyError(country)


COUNTRIES = ["AAA", "BBB", "CCC", "DDD"]


def write(tmp_path, owid_edit=None, primap_edit=None, world_edit=None, glob_edit=None, crosswalk=True, with_owid=True, with_primap=True):
    rows = []
    for c in COUNTRIES:
        for y in YEARS:
            rows.append((c, y, c, annual(c, y)))
    for y in YEARS:  # entities that must never enter the denominator
        rows.append(("Europe", y, np.nan, 100.0))
        rows.append(("International aviation", y, np.nan, 3.0))
    raw = pd.DataFrame(rows, columns=["country", "year", "iso_code", "co2"])
    if owid_edit:
        raw = owid_edit(raw)
    if with_owid:
        raw.to_csv(tmp_path / "owid-co2-data.csv", index=False)
    national = [sum((annual(c, y) or 0.0) for c in COUNTRIES) for y in YEARS]
    nat = pd.DataFrame({"year": YEARS, "national_sum_mt": national, "co2_mt": [v + 3.0 for v in national]})  # World includes international transport
    if world_edit:
        nat = world_edit(nat)
    nat.to_csv(tmp_path / "owid_world_co2_annual.csv", index=False)
    prim = pd.DataFrame([(c, y, annual(c, y), (annual(c, y) or np.nan) * 2 if annual(c, y) is not None else np.nan, "country") for c in COUNTRIES for y in YEARS],
                        columns=["iso3", "year", "co2_mt", "total_ghg_mtco2e", "entity_type"])
    g = prim.groupby("year")[["co2_mt", "total_ghg_mtco2e"]].sum(min_count=1).reset_index()  # the global series comes from the unedited data, as in the real source
    if primap_edit:
        prim = primap_edit(prim)
    if with_primap:
        prim.to_csv(tmp_path / "primap_country_annual.csv", index=False)
    if glob_edit:
        g = glob_edit(g)
    g.to_csv(tmp_path / "primap_global_composition_annual.csv", index=False)
    if crosswalk:
        pd.DataFrame({"iso3": COUNTRIES, "primap_name": ["Aland", "Bland", "Cland", "Dland"], "owid_name": ["Aland", "Bland", "Cland", "Dland"],
                      "expanded": [True, False, False, False]}).to_csv(tmp_path / "country_crosswalk.csv", index=False)
    (tmp_path / "provenance.json").write_text(json.dumps({
        "owid_world_co2_annual": {"source": "OWID", "license": "CC BY 4.0", "citations": ["OWID", "GCP"]},
        "primap_country_annual": {"source": "PRIMAP-hist", "license": "CC BY-NC-SA 4.0", "citations": ["Gütschow & Pflüger"], "source_release": {"version": "v2.8"}}}))


def go(tmp_path, **kw):
    write(tmp_path, **kw)
    rep = S.run(str(tmp_path), owid_path=str(tmp_path / "owid-co2-data.csv"))
    return rep, json.loads((tmp_path / "correlation_country_share.json").read_text()), pd.read_csv(tmp_path / "correlation_country_share.csv")


def combo(meta, source, scope):
    return [c for c in meta["combinations"] if c["source"] == source and c["gas_scope"] == scope][0]


def cum_expected(country, upto):
    return sum((annual(country, y) or 0.0) for y in range(1840, upto + 1))


def row(long, source, scope, country, year):
    r = long[(long.source == source) & (long.gas_scope == scope) & (long.country == country) & (long.year == year)]
    return r.iloc[0] if len(r) else None


# ---------------------------------------------------------------- the numbers


def test_cumulative_and_share_match_hand_calculation(tmp_path):
    rep, meta, long = go(tmp_path)
    assert rep.deviations == []
    for year in (1900, 1953, 2000):
        total = sum(cum_expected(c, year) for c in COUNTRIES)
        for c in COUNTRIES:
            r = row(long, "owid_co2", "co2", c, year)
            assert r.cumulative_mt == pytest.approx(cum_expected(c, year), abs=1e-6) and r.share_pct == pytest.approx(cum_expected(c, year) / total * 100, abs=1e-8)
    assert row(long, "owid_co2", "co2", "AAA", 2000).cumulative_mt == 1610.0 and row(long, "owid_co2", "co2", "BBB", 2000).cumulative_mt == 505.0


def test_cumulative_runs_from_the_first_year_but_rows_are_published_from_1850(tmp_path):
    _, meta, long = go(tmp_path)
    a = long[(long.source == "owid_co2") & (long.country == "AAA")]
    assert a.year.min() == 1850 and row(long, "owid_co2", "co2", "AAA", 1850).cumulative_mt == 10.0 * 11  # 1840-1850 inclusive: pre-1850 emissions count
    assert combo(meta, "owid_co2", "co2")["cumulative_from"] == 1840 and combo(meta, "owid_co2", "co2")["coverage"] == [1850, 2000] and meta["published_from"] == 1850


def test_a_country_has_rows_only_from_its_first_observation(tmp_path):
    _, _, long = go(tmp_path)
    b = long[(long.source == "owid_co2") & (long.country == "BBB")]
    assert b.year.min() == 1900 and b.year.max() == 2000 and len(b) == 101 and row(long, "owid_co2", "co2", "BBB", 1899) is None  # absent = no emissions recorded yet


def test_shares_sum_to_100_every_year_including_the_published_rounded_values(tmp_path):
    _, _, long = go(tmp_path)
    sums = long.groupby(["source", "gas_scope", "year"]).share_pct.sum()
    assert (sums - 100).abs().max() < 1e-6 and len(sums) == 3 * 151


def test_non_iso_entities_and_international_transport_never_enter_the_denominator(tmp_path):
    _, meta, long = go(tmp_path)
    c = combo(meta, "owid_co2", "co2")
    expected = sum(cum_expected(x, 2000) for x in COUNTRIES)
    assert c["latest"]["total_cumulative_mt"] == pytest.approx(expected) and set(long.country) == set(COUNTRIES)  # no 'Europe', no aviation
    world = sum(annual_total + 3.0 for annual_total in [sum((annual(x, y) or 0.0) for x in COUNTRIES) for y in YEARS])
    assert c["denominator"]["world_cumulative_mt"] == pytest.approx(world) and c["denominator"]["difference_from_world_pct"] == pytest.approx((expected / world - 1) * 100)
    assert c["denominator"]["difference_from_world_pct"] < 0  # the national sum is below the World series, by design


def test_missing_years_count_as_zero_and_are_listed_not_interpolated(tmp_path):
    _, meta, long = go(tmp_path)
    c = combo(meta, "owid_co2", "co2")
    assert c["gaps"] == [{"country": "CCC", "n_years": 3, "first": 1950, "last": 1952}]
    assert row(long, "owid_co2", "co2", "CCC", 1952).cumulative_mt == cum_expected("CCC", 1949)  # flat through the gap
    assert row(long, "owid_co2", "co2", "CCC", 2000).cumulative_mt == 161 - 3  # three years short, not filled in
    assert any("counted as zero and listed under `gaps`" in x for x in meta["caveats"])


def test_a_series_that_ends_early_stops_growing_and_is_listed(tmp_path):
    _, meta, long = go(tmp_path)
    c = combo(meta, "owid_co2", "co2")
    assert c["ended_before_last_year"] == [{"country": "DDD", "last_observation": 1970}]
    assert row(long, "owid_co2", "co2", "DDD", 1970).cumulative_mt == row(long, "owid_co2", "co2", "DDD", 2000).cumulative_mt == 2.0 * 131
    assert row(long, "owid_co2", "co2", "DDD", 2000).share_pct < row(long, "owid_co2", "co2", "DDD", 1970).share_pct


def test_latest_top_emitters_are_ordered_and_consistent_with_the_file(tmp_path):
    _, meta, long = go(tmp_path)
    top = combo(meta, "owid_co2", "co2")["latest"]["top"]
    assert [t["country"] for t in top] == ["AAA", "BBB", "DDD", "CCC"]  # 1610 / 505 / 262 / 158
    assert all(t["share_pct"] == pytest.approx(row(long, "owid_co2", "co2", t["country"], 2000).share_pct, abs=1e-8) for t in top)
    assert [t["share_pct"] for t in top] == sorted((t["share_pct"] for t in top), reverse=True)


def test_primap_scopes_use_their_own_columns(tmp_path):
    def uneven(p):
        return p.assign(total_ghg_mtco2e=np.where(p.iso3 == "AAA", p.total_ghg_mtco2e * 10, p.total_ghg_mtco2e))

    _, meta, long = go(tmp_path, primap_edit=uneven, glob_edit=lambda g: g.assign(total_ghg_mtco2e=g.co2_mt * 0))  # the global file is edited below to match
    # co2 uses co2_mt, total_ghg uses total_ghg_mtco2e: AAA's total_ghg share must differ from its co2 share
    assert row(long, "primap_hist", "co2", "AAA", 2000).share_pct == pytest.approx(row(long, "owid_co2", "co2", "AAA", 2000).share_pct, abs=1e-8)  # same underlying co2
    assert row(long, "primap_hist", "total_ghg", "AAA", 2000).share_pct > row(long, "primap_hist", "co2", "AAA", 2000).share_pct + 5


def test_cumulate_matches_an_independent_pandas_calculation_on_random_data():
    rng = np.random.default_rng(4)
    rows = [(f"C{i:02d}", y, float(rng.uniform(0, 50)) if rng.random() > 0.05 else np.nan) for i in range(30) for y in range(1900, 1950)]
    df = pd.DataFrame(rows, columns=["iso", "year", "v"])
    c = S.cumulate(df, "iso", "v", 1949)
    expected = df.assign(v=df.v.fillna(0.0)).sort_values(["iso", "year"]).groupby("iso").v.cumsum().to_numpy().reshape(30, 50).T  # independent: pandas cumsum
    assert np.allclose(c["cum"], expected, rtol=1e-12, atol=1e-9) and c["years"][0] == 1900 and c["ids"] == sorted(df.iso.unique())


# ---------------------------------------------------------------- reconciliation and integrity


def test_the_sums_reconcile_to_the_published_artifacts(tmp_path):
    rep, meta, _ = go(tmp_path)
    o, p = combo(meta, "owid_co2", "co2")["reconciliation"], combo(meta, "primap_hist", "total_ghg")["reconciliation"]
    assert o["against"] == "owid_world_co2_annual.national_sum_mt" and o["max_relative_difference"] < 1e-12 and o["years_compared"] == [1840, 2000]
    assert p["against"] == "primap_global_composition_annual.total_ghg_mtco2e" and p["max_relative_difference"] < 1e-12 and rep.deviations == []


def test_a_mismatch_with_the_published_national_sum_is_a_deviation(tmp_path):
    rep, meta, _ = go(tmp_path, world_edit=lambda w: w.assign(national_sum_mt=w.national_sum_mt * 1.01))
    assert any("owid_world_co2_annual.national_sum_mt" in d and "differs from the published series" in d for d in rep.deviations)
    assert combo(meta, "owid_co2", "co2")["reconciliation"]["max_relative_difference"] > 1e-3


def test_a_mismatch_with_the_global_composition_is_a_deviation(tmp_path):
    rep, _, _ = go(tmp_path, glob_edit=lambda g: g.assign(co2_mt=g.co2_mt * 1.5))
    assert any("primap_global_composition_annual.co2_mt" in d for d in rep.deviations) and not any("total_ghg_mtco2e" in d for d in rep.deviations)


def test_negative_annual_emissions_are_a_deviation(tmp_path):
    rep, _, _ = go(tmp_path, owid_edit=lambda r: r.assign(co2=np.where((r.iso_code == "BBB") & (r.year == 1950), -4.0, r.co2)))
    assert any("owid_co2/co2: negative annual emissions" in d for d in rep.deviations)


# ---------------------------------------------------------------- failure behaviour


def test_each_source_fails_independently_with_an_explicit_reason(tmp_path):
    rep, meta, long = go(tmp_path, with_owid=False)
    o = combo(meta, "owid_co2", "co2")
    assert o["available"] is False and "FileNotFoundError" in o["unavailable_reason"] and set(long.source) == {"primap_hist"}
    assert combo(meta, "primap_hist", "co2")["available"] and combo(meta, "primap_hist", "total_ghg")["available"]
    assert any("owid_co2/co2 country shares unavailable" in d for d in rep.deviations)


def test_primap_failure_leaves_owid_and_makes_both_primap_combinations_unavailable(tmp_path):
    rep, meta, long = go(tmp_path, with_primap=False)
    assert combo(meta, "owid_co2", "co2")["available"] and set(long.source) == {"owid_co2"}
    assert [combo(meta, "primap_hist", s)["available"] for s in ("co2", "total_ghg")] == [False, False] and len([d for d in rep.deviations if "unavailable" in d]) == 2


def test_a_failure_overwrites_the_previous_outputs_instead_of_leaving_them(tmp_path):
    _, _, long = go(tmp_path)
    assert (long.source == "owid_co2").any()
    os.remove(tmp_path / "owid-co2-data.csv")
    S.run(str(tmp_path), owid_path=str(tmp_path / "owid-co2-data.csv"))
    after = pd.read_csv(tmp_path / "correlation_country_share.csv")
    assert not (after.source == "owid_co2").any() and (after.source == "primap_hist").any()  # no stale OWID rows survive


def test_duplicate_rows_or_a_zero_total_make_only_that_combination_unavailable(tmp_path):
    _, meta, _ = go(tmp_path, owid_edit=lambda r: pd.concat([r, r[r.iso_code == "AAA"].head(1)]))
    assert "duplicate iso_code/year rows" in combo(meta, "owid_co2", "co2")["unavailable_reason"] and combo(meta, "primap_hist", "co2")["available"]
    _, meta2, _ = go(tmp_path / "z" if (tmp_path / "z").mkdir() is None else tmp_path, primap_edit=lambda p: p.assign(total_ghg_mtco2e=np.where(p.year < 1900, 0.0, p.total_ghg_mtco2e)))
    assert "a published year has a zero total" in combo(meta2, "primap_hist", "total_ghg")["unavailable_reason"] and combo(meta2, "primap_hist", "co2")["available"]


def test_a_missing_required_column_is_a_reason_not_a_crash(tmp_path):
    _, meta, _ = go(tmp_path, primap_edit=lambda p: p.drop(columns=["total_ghg_mtco2e"]))
    assert "required column missing: total_ghg_mtco2e" in combo(meta, "primap_hist", "co2")["unavailable_reason"] and combo(meta, "owid_co2", "co2")["available"]


def test_malformed_provenance_and_missing_crosswalk_do_not_stop_the_outputs(tmp_path):
    write(tmp_path, crosswalk=False)
    (tmp_path / "provenance.json").write_text("{not json")
    rep = S.run(str(tmp_path), owid_path=str(tmp_path / "owid-co2-data.csv"))
    meta = json.loads((tmp_path / "correlation_country_share.json").read_text())
    assert meta["attribution"] == {} and [c["iso3"] for c in meta["countries"]] == COUNTRIES and all(c["name"] == c["iso3"] for c in meta["countries"])
    assert all(c["available"] for c in meta["combinations"]) and meta["caveats"]


# ---------------------------------------------------------------- metadata


def test_no_attribution_denominator_territorial_and_licence_caveats_travel_with_the_numbers(tmp_path):
    _, meta, _ = go(tmp_path)
    c = " ".join(meta["caveats"])
    assert "not a measure of responsibility for warming or a causal attribution" in c and "no country's emissions are regressed against the global temperature series" in c
    assert "differs by design from the World series" in c and "territorial" in c and "not adjusted for trade" in c and "PRIMAP-hist licence: CC BY-NC-SA 4.0" in c
    assert meta["note"] == S.NO_ATTRIBUTION and meta["attribution"]["owid"]["license"] == "CC BY 4.0" and meta["attribution"]["primap_hist"]["citations"] == ["Gütschow & Pflüger"]


def test_country_names_and_the_expanded_flag_come_from_the_crosswalk(tmp_path):
    _, meta, _ = go(tmp_path)
    assert meta["countries"][0] == {"iso3": "AAA", "name": "Aland", "expanded": True} and [c["expanded"] for c in meta["countries"]] == [True, False, False, False]


def test_the_outputs_are_deterministic_and_the_stage_is_registered_and_gated(tmp_path):
    from pipeline import run

    _, a, la = go(tmp_path)
    S.run(str(tmp_path), owid_path=str(tmp_path / "owid-co2-data.csv"))
    b = json.loads((tmp_path / "correlation_country_share.json").read_text())
    lb = pd.read_csv(tmp_path / "correlation_country_share.csv")
    for d in (a, b):
        d.pop("generated_at")
    assert a == b and la.equals(lb)
    assert "country_share" in run.DERIVED_SOURCES and "country_share" not in run.ACTIVE_SOURCES and run.DEPENDS_ON["country_share"] == ("owid", "primap_hist")


def test_a_share_sum_violation_makes_the_combination_unavailable_instead_of_publishing_bad_shares(tmp_path, monkeypatch):
    """Shares sum to 100 by construction, so the guard is a defensive invariant; this forces it to fire and checks the wiring."""
    monkeypatch.setattr(S, "SHARE_SUM_TOL", -1.0)
    rep, meta, long = go(tmp_path)
    assert all(not c["available"] and "shares sum to" in c["unavailable_reason"] for c in meta["combinations"]) and len(long) == 0
    assert len([d for d in rep.deviations if "country shares unavailable" in d]) == 3


# ---------------------------------------------------------------- annual values (decision 60)


def annual_expected(country, y):
    return annual(country, y) or 0.0


def test_annual_columns_match_hand_calculation(tmp_path):
    _, _, long = go(tmp_path)
    assert {"annual_mt", "annual_share_pct"} <= set(long.columns)
    for year in (1900, 1951, 1953, 2000):  # 1951 is inside CCC's missing run (counted as zero); 2000 is after DDD's record ends
        total = sum(annual_expected(c, year) for c in COUNTRIES)
        for c in COUNTRIES:
            r = row(long, "owid_co2", "co2", c, year)
            assert r.annual_mt == pytest.approx(annual_expected(c, year), abs=1e-6)
            assert r.annual_share_pct == pytest.approx(annual_expected(c, year) / total * 100, abs=1e-8)


def test_annual_shares_sum_to_100_per_year_and_annual_sum_reconciles_to_the_national_series(tmp_path):
    _, _, long = go(tmp_path)
    for (source, scope), g in long.groupby(["source", "gas_scope"]):
        assert (g.groupby("year")["annual_share_pct"].sum() - 100).abs().max() < 1e-6
    owid = long[(long.source == "owid_co2")].groupby("year")["annual_mt"].sum()
    national = pd.read_csv(tmp_path / "owid_world_co2_annual.csv").set_index("year")["national_sum_mt"]
    common = owid.index.intersection(national.index)
    assert np.allclose(owid.loc[common].to_numpy(), national.loc[common].to_numpy(), atol=1e-6)


def test_primap_total_ghg_annual_uses_its_own_column(tmp_path):
    _, _, long = go(tmp_path)
    r = row(long, "primap_hist", "total_ghg", "AAA", 1990)
    assert r.annual_mt == pytest.approx(2 * annual_expected("AAA", 1990), abs=1e-6)


def test_a_year_with_a_zero_annual_total_makes_the_combination_unavailable_not_a_division_error(tmp_path):
    # every country reports 0 in 1990: cumulative totals stay positive (earlier years), annual shares are undefined
    rep, meta, long = go(tmp_path, owid_edit=lambda raw: raw.assign(co2=np.where(raw["year"] == 1990, 0.0, raw["co2"])))
    assert not combo(meta, "owid_co2", "co2")["available"]
    assert any("zero annual total" in m for m in rep.deviations)
    assert len(long[long.source == "owid_co2"]) == 0
