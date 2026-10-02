import json
import os

import numpy as np
import pandas as pd
import pytest

from pipeline import composition as K

CO2, CH4, N2O, FG = 70.0, 20.0, 8.0, 2.0  # a synthetic composition in percent: exactly 100


def write(tmp_path, years=range(1990, 2025), fgas_null_before=None, drop_col=None, edit=None, prov_extra=None, total_scale=1.0):
    y = np.array(list(years))
    g = (y - 1989).astype(float)
    df = pd.DataFrame({"year": y, "co2_mt": CO2 * g, "ch4_mtco2e": CH4 * g, "n2o_mtco2e": N2O * g, "fgas_mtco2e": FG * g})
    df["total_ghg_mtco2e"] = (df[["co2_mt", "ch4_mtco2e", "n2o_mtco2e", "fgas_mtco2e"]].sum(axis=1)) * total_scale
    if fgas_null_before:
        df.loc[df.year < fgas_null_before, "fgas_mtco2e"] = np.nan
    if edit:
        df = edit(df)
    if drop_col:
        df = df.drop(columns=[drop_col])
    df.to_csv(tmp_path / "primap_global_composition_annual.csv", index=False)
    prov = {"primap_global_composition_annual": {"source": "PRIMAP-hist", "license": "CC BY-NC-SA 4.0", "citations": ["Gütschow & Pflüger (2026)"], "coverage": [int(y.min()), int(y.max())],
                                                 "source_release": {"version": "v2.8"}, "caveats": ["PRIMAP-hist is a composite of country-reported and third-party data."],
                                                 "excluded_incomplete_years": [{"year": 2025, "reasons": "ch4 coverage 2.0% < 98%"}], **(prov_extra or {})}}
    (tmp_path / "provenance.json").write_text(json.dumps(prov))


def go(tmp_path, **kw):
    write(tmp_path, **kw)
    rep = K.run(str(tmp_path))
    return rep, json.loads((tmp_path / "correlation_composition.json").read_text()), pd.read_csv(tmp_path / "correlation_composition_annual.csv")


def test_shares_are_exact_and_sum_to_100_every_year(tmp_path):
    rep, meta, long = go(tmp_path)
    assert rep.deviations == [] and meta["coverage"] == [1990, 2024] and meta["n_years"] == 35 and len(long) == 35 * 4
    r = long[(long.year == 2000) & (long.gas == "ch4")].iloc[0]
    assert r.share_pct == pytest.approx(20.0, abs=1e-8) and r.mtco2e == pytest.approx(20.0 * 11, abs=1e-6)  # 2000 is year 11 of the synthetic series
    assert (long.groupby("year").share_pct.sum() - 100).abs().max() < 1e-6  # the PUBLISHED (rounded) shares satisfy the tolerance too
    assert list(long.columns) == ["year", "gas", "gas_name", "mtco2e", "share_pct"] and set(long.gas) == {"co2", "ch4", "n2o", "fgas"}
    assert set(long.gas_name) == {"CO₂", "CH₄", "N₂O", "Fluorinated gases"} and (long.groupby("year").gas.count() == 4).all()


def test_shares_of_a_year_with_known_unequal_values_match_hand_calculation(tmp_path):
    def edit(df):
        df.loc[df.year == 2010, ["co2_mt", "ch4_mtco2e", "n2o_mtco2e", "fgas_mtco2e"]] = [600.0, 250.0, 100.0, 50.0]
        df.loc[df.year == 2010, "total_ghg_mtco2e"] = 1000.0
        return df

    _, meta, long = go(tmp_path, edit=edit)
    s = long[long.year == 2010].set_index("gas").share_pct
    assert s.to_dict() == {"co2": pytest.approx(60.0), "ch4": pytest.approx(25.0), "n2o": pytest.approx(10.0), "fgas": pytest.approx(5.0)}
    y = [y for y in meta["years"] if y["year"] == 2010][0]
    assert y["components_total_mtco2e"] == 1000.0 and y["national_total_mtco2e"] == 1000.0 and y["residual_pct"] == pytest.approx(0.0, abs=1e-12)


def test_a_real_zero_stays_a_zero_and_is_not_turned_into_a_null(tmp_path):
    """PRIMAP-hist reports F-gases as 0.0 in 1750: that is a value."""
    def edit(df):
        df.loc[df.year < 1995, "fgas_mtco2e"] = 0.0
        df["total_ghg_mtco2e"] = df[["co2_mt", "ch4_mtco2e", "n2o_mtco2e", "fgas_mtco2e"]].sum(axis=1)
        return df

    rep, meta, long = go(tmp_path, edit=edit)
    r = long[(long.year == 1991) & (long.gas == "fgas")].iloc[0]
    assert r.mtco2e == 0.0 and r.share_pct == 0.0 and [y for y in meta["years"] if y["year"] == 1991][0]["gases_included"] == ["co2", "ch4", "n2o", "fgas"]


def test_a_gas_with_no_value_is_an_explicit_null_not_a_zero_and_shares_are_over_the_included_gases(tmp_path):
    rep, meta, long = go(tmp_path, fgas_null_before=2000, edit=lambda df: df.assign(total_ghg_mtco2e=df[["co2_mt", "ch4_mtco2e", "n2o_mtco2e"]].sum(axis=1) + df.fgas_mtco2e.fillna(0)))
    row = long[(long.year == 1995) & (long.gas == "fgas")].iloc[0]
    assert pd.isna(row.mtco2e) and pd.isna(row.share_pct)  # empty in the file, not 0
    y = [y for y in meta["years"] if y["year"] == 1995][0]
    assert y["gases_included"] == ["co2", "ch4", "n2o"]
    others = long[(long.year == 1995) & (long.gas != "fgas")].share_pct
    assert others.sum() == pytest.approx(100.0, abs=1e-6) and long[(long.year == 1995) & (long.gas == "co2")].share_pct.iloc[0] == pytest.approx(CO2 / (CO2 + CH4 + N2O) * 100, abs=1e-6)
    assert rep.deviations == [] and any("F-gases have no value for 10 year(s) (1990-1999)" in n for n in rep.notes)  # a note, not a deviation
    assert "fgas" in [y for y in meta["years"] if y["year"] == 2005][0]["gases_included"]


@pytest.mark.parametrize("gas_col,gas", [("co2_mt", "co2"), ("ch4_mtco2e", "ch4"), ("n2o_mtco2e", "n2o")])
def test_a_missing_core_gas_is_a_deviation_and_never_silently_renormalised(tmp_path, gas_col, gas):
    def edit(df):
        df.loc[df.year == 2005, gas_col] = np.nan
        return df.assign(total_ghg_mtco2e=df[["co2_mt", "ch4_mtco2e", "n2o_mtco2e", "fgas_mtco2e"]].sum(axis=1))

    rep, meta, long = go(tmp_path, edit=edit)
    assert any(d.startswith(f"2005: no value for {gas};") and "computed over the remaining gases" in d for d in rep.deviations)
    assert gas not in [y for y in meta["years"] if y["year"] == 2005][0]["gases_included"] and pd.isna(long[(long.year == 2005) & (long.gas == gas)].share_pct.iloc[0])


def test_the_reconciliation_to_the_national_total_is_published_and_checked(tmp_path):
    rep, meta, _ = go(tmp_path)
    assert meta["reconciliation"]["max_abs_residual_pct"] == pytest.approx(0.0, abs=1e-9) and meta["reconciliation"]["tolerance_pct"] == 1.0
    rep2, meta2, _ = go(tmp_path / "off" if (tmp_path / "off").mkdir() is None else tmp_path, total_scale=1.03)  # the national total is 3% above the components
    assert any("from PRIMAP-hist's national total (tolerance ±1.0%)" in d for d in rep2.deviations) and meta2["reconciliation"]["max_abs_residual_pct"] == pytest.approx(2.913, abs=0.01)
    assert [y for y in meta2["years"] if y["year"] == 2000][0]["residual_pct"] == pytest.approx(-2.913, abs=0.01)


def test_years_beyond_the_completeness_tested_coverage_are_a_deviation(tmp_path):
    rep, _, _ = go(tmp_path, years=range(1990, 2026), prov_extra={"coverage": [1990, 2024]})  # 2025 slipped in
    assert any("beyond the completeness-tested coverage [1990, 2024]: [2025]" in d for d in rep.deviations)


def test_a_gap_in_the_years_is_refused_and_the_output_becomes_explicit_nulls(tmp_path):
    rep, meta, long = go(tmp_path, edit=lambda df: df[df.year != 2003])
    assert meta["years"] == [] and meta["coverage"] is None and "missing year" in meta["unavailable_reason"] and len(long) == 0
    assert any("composition unavailable" in d for d in rep.deviations)


def test_early_period_caveat_is_generated_only_when_methane_dominates_the_first_year(tmp_path):
    def methane_first(df):
        df.loc[df.year == 1990, ["co2_mt", "ch4_mtco2e", "n2o_mtco2e", "fgas_mtco2e"]] = [10.0, 950.0, 35.0, 5.0]
        df.loc[df.year == 1990, "total_ghg_mtco2e"] = 1000.0
        return df

    _, meta, _ = go(tmp_path, edit=methane_first)
    text = [c for c in meta["caveats"] if c.startswith("In 1990 ")]
    assert len(text) == 1 and "CH₄ is 95% of the CO2-equivalent total and CO2 only 1%" in text[0] and "reconstruction dominated by methane" in text[0] and "land-use change" in text[0]
    _, meta2, _ = go(tmp_path / "x" if (tmp_path / "x").mkdir() is None else tmp_path)
    assert not any(c.startswith("In 1990 ") for c in meta2["caveats"])  # CO2 is the largest share: nothing to warn about


def test_basis_scope_licence_and_provenance_caveats_travel_with_the_numbers(tmp_path):
    _, meta, _ = go(tmp_path)
    c = " ".join(meta["caveats"])
    assert "IPCC AR5 100-year global-warming potentials" in meta["basis"] and "CH4 28, N2O 265" in meta["basis"] and meta["units"] == "MtCO2e (CO2 in Mt CO2)"
    assert "Excludes international aviation and shipping and land-use change" in c and "PRIMAP-hist is a composite of country-reported and third-party data." in c
    assert "PRIMAP-hist licence: CC BY-NC-SA 4.0" in c and meta["attribution"]["citations"] == ["Gütschow & Pflüger (2026)"] and meta["excluded_incomplete_years"] == [2025]
    assert [g["id"] for g in meta["gases"]] == ["co2", "ch4", "n2o", "fgas"]


def test_a_missing_input_overwrites_the_previous_outputs_with_explicit_nulls_and_keeps_the_metadata(tmp_path):
    go(tmp_path)
    assert len(pd.read_csv(tmp_path / "correlation_composition_annual.csv")) == 140
    os.remove(tmp_path / "primap_global_composition_annual.csv")
    rep = K.run(str(tmp_path))  # must not raise
    meta = json.loads((tmp_path / "correlation_composition.json").read_text())
    long = pd.read_csv(tmp_path / "correlation_composition_annual.csv")
    assert len(long) == 0 and list(long.columns) == K.CSV_COLUMNS and meta["years"] == [] and "FileNotFoundError" in meta["unavailable_reason"]
    assert meta["attribution"]["license"] == "CC BY-NC-SA 4.0" and any("PRIMAP-hist licence" in c for c in meta["caveats"]) and meta["basis"] and meta["gases"]
    assert any("composition unavailable" in d for d in rep.deviations)


def test_a_malformed_table_and_malformed_provenance_are_handled_not_raised(tmp_path):
    rep, meta, long = go(tmp_path, drop_col="ch4_mtco2e")
    assert "required column(s) missing: ch4_mtco2e" in meta["unavailable_reason"] and len(long) == 0
    write(tmp_path)
    (tmp_path / "provenance.json").write_text("{not json")
    rep2 = K.run(str(tmp_path))
    meta2 = json.loads((tmp_path / "correlation_composition.json").read_text())
    assert meta2["years"] == [] and meta2["caveats"] and any("composition unavailable" in d for d in rep2.deviations)


def test_the_output_is_deterministic_and_the_stage_is_registered(tmp_path):
    from pipeline import run

    _, a, la = go(tmp_path)
    K.run(str(tmp_path))
    b = json.loads((tmp_path / "correlation_composition.json").read_text())
    lb = pd.read_csv(tmp_path / "correlation_composition_annual.csv")
    for d in (a, b):
        d.pop("generated_at")
    assert a == b and la.equals(lb)
    assert "composition" in run.DERIVED_SOURCES and "composition" not in run.ACTIVE_SOURCES and "composition" not in run.DEPENDS_ON


def test_a_share_sum_violation_makes_the_output_unavailable_instead_of_publishing_bad_shares(tmp_path, monkeypatch):
    """Shares sum to 100 by construction, so the guard is a defensive invariant; this forces it to fire and checks the wiring."""
    monkeypatch.setattr(K, "SHARE_SUM_TOL", -1.0)
    rep, meta, long = go(tmp_path)
    assert meta["years"] == [] and "shares sum to" in meta["unavailable_reason"] and len(long) == 0
    assert any("composition unavailable" in d and "shares sum to" in d for d in rep.deviations)
