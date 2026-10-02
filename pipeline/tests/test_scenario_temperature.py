import hashlib
import json
import os

import numpy as np
import pandas as pd
import pytest

from pipeline import scenario_temperature as T

T0 = 2000
SLOPE_H, CI_H = 0.5, [0.4, 0.6]  # headline: total anthropogenic CO2
SLOPE_F, CI_F = 0.8, [0.7, 0.9]  # secondary: fossil + cement only
COUNTRIES = {"Aland": 600_000.0, "Bland": 400_000.0}  # last-observed (T0) Mt: covered = 1,000,000
WORLD_T0 = 1_250_000.0  # so the rest-of-world share is 0.2
LUC = 100_000.0  # Mt/yr of land-use CO2 in each of the last five years
ANOM = {1996: 1.00, 1997: 1.10, 1998: 1.20, 1999: 1.30, 2000: 1.90}  # the anchor is the 5-year mean (1.30), not the last year (1.90)
FIRST = T0 + 1
# the stage requires exactly BAU, Moderate and Aggressive. The default pathways are HEALTHY data: their first-year covered totals are 1,010,000 (+1.0%), 1,005,000 (+0.5%) and
# 995,000 (-0.5%) against 1,000,000 observed, inside the +/-2% aggregate and +/-5% per-country thresholds. Tests that need a large step create it with `with_steps`.
PATH = {"BAU": {"Aland": [606_000, 650_000, 700_000], "Bland": [404_000, 430_000, 460_000]},
        "Moderate": {"Aland": [603_000, 590_000, 580_000], "Bland": [402_000, 395_000, 388_000]},
        "Aggressive": {"Aland": [597_000, 560_000, 520_000], "Bland": [398_000, 380_000, 360_000]}}


def with_steps(**pct):
    """A scenario_edit that moves each named scenario's first-year values to `pct` percent from the last observed value, for every country."""
    def edit(p):
        cols = {c: p.reset_index(drop=True)[c].to_numpy().copy() for c in p.columns}
        vals = cols["co2_projected"].astype(float)
        for sc, s in pct.items():
            mask = (cols["scenario"] == sc) & (cols["year"] == FIRST)
            vals[mask] = np.array([COUNTRIES[c] for c in cols["country"][mask]]) * (1 + s / 100)
        cols["co2_projected"] = vals
        return pd.DataFrame(cols)
    return edit


def fit(slope, ci):
    return {"fit": {"slope": slope, "ci95_hac": ci}, "range": [1850, T0], "label": "x", "x_indicator": "x"}


def write(tmp_path, headline="ok", scenario_edit=None, owid_edit=None, world_edit=None, no_scenario=False, vintage="2025-01-10T04:48:46+00:00", notices=None, baseline="match"):
    # world series 1850..T0
    years = list(range(1850, T0 + 1))
    luc = [LUC if y > T0 - 5 else 0.0 for y in years]
    fossil = [WORLD_T0 if y == T0 else 1000.0 for y in years]
    w = pd.DataFrame({"year": years, "co2_mt": fossil, "land_use_change_co2_mt": luc, "total_co2_incl_luc_mt": [a + b for a, b in zip(fossil, luc)],
                      "cumulative_co2_mt": np.cumsum(fossil)})
    if world_edit:
        w = world_edit(w)
    w.to_csv(tmp_path / "owid_world_co2_annual.csv", index=False)
    pd.DataFrame({"year": list(ANOM) + list(range(1850, 1996)), "anomaly_1850_1900_c": list(ANOM.values()) + [0.0] * 146}).sort_values("year").to_csv(tmp_path / "temperature_anomaly_annual.csv", index=False)
    hj = {"headline": fit(SLOPE_H, CI_H), "secondary_fossil_only": fit(SLOPE_F, CI_F), "attribution": {"required_citation_format": "Global Carbon Project. (<year>) ..."}}
    if headline == "none":
        hj["headline"] = None
    if headline == "no_fossil":
        hj["secondary_fossil_only"] = None
    (tmp_path / "correlation_headline.json").write_text(json.dumps(hj))
    raw = pd.DataFrame([(c, T0, v) for c, v in COUNTRIES.items()] + [("Europe", T0, 123.0)], columns=["country", "year", "co2"])
    if owid_edit:
        raw = owid_edit(raw)
    raw.to_csv(tmp_path / "owid-co2-data.csv", index=False)
    rows = [(c, FIRST + i, sc, v) for sc, d in PATH.items() for c, vals in d.items() for i, v in enumerate(vals)]
    proj = pd.DataFrame(rows, columns=["country", "year", "scenario", "co2_projected"])
    if scenario_edit:
        proj = scenario_edit(proj)
    if not no_scenario:
        proj.to_csv(tmp_path / "scenario_projections.csv", index=False)
    write_baseline(tmp_path, baseline)
    (tmp_path / "provenance.json").write_text(json.dumps({"temperature_anomaly_annual": {"source_release": {"http_last_modified": vintage}}}))
    npath = tmp_path / "notices.json"
    npath.write_text(json.dumps(notices or {}))


def write_baseline(tmp_path, kind):
    """The pipeline's current baseline (ets_baseline_full_data.csv/.json): by default exactly the default BAU pathway, i.e. the scenario file IS on the current baseline."""
    rows = [(c, FIRST + i, float(v)) for c, vals in PATH["BAU"].items() for i, v in enumerate(vals)]
    df = pd.DataFrame(rows, columns=["country", "year", "mean"])
    if kind == "none":
        return
    if kind == "stale":
        df = pd.DataFrame({"country": df["country"], "year": df["year"], "mean": df["mean"].to_numpy() * 0.97})
    elif kind == "tiny":
        df = pd.DataFrame({"country": df["country"], "year": df["year"], "mean": df["mean"].to_numpy() + 0.005})
    elif kind == "missing_country_year":
        df = df.iloc[1:]
    elif kind == "empty":
        df = df.iloc[0:0]
    elif kind == "no_mean_column":
        df = df.rename(columns={"mean": "value"})
    df.to_csv(tmp_path / "ets_baseline_full_data.csv", index=False)
    if kind == "unavailable_json":
        (tmp_path / "ets_baseline_full_data.json").write_text(json.dumps({"unavailable_reason": "OWID CO2 for 1990-2024 is missing for: Aland"}))
    else:
        (tmp_path / "ets_baseline_full_data.json").write_text(json.dumps({"last_observed_year": T0}))


def go(tmp_path, **kw):
    write(tmp_path, **kw)
    rep = T.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"), scenario_path=str(tmp_path / "scenario_projections.csv"), owid_path=str(tmp_path / "owid-co2-data.csv"))
    return rep, json.loads((tmp_path / "correlation_scenario_temperature.json").read_text())


ROW_SHARE = 1 - 1_000_000 / WORLD_T0  # 0.2


def expected(scenario):
    cov = [sum(PATH[scenario][c][i] for c in COUNTRIES) for i in range(3)]
    glob = [x / (1 - ROW_SHARE) for x in cov]
    inc_t = np.cumsum([g + LUC for g in glob])
    inc_f = np.cumsum(glob)
    return cov, glob, inc_t, inc_f


# ---------------------------------------------------------------- the translation, by hand


def test_rest_of_world_share_global_emissions_and_the_flat_land_use_assumption(tmp_path):
    rep, out = go(tmp_path)
    assert rep.deviations == []
    a = out["assumptions"]
    assert a["rest_of_world"]["share"] == pytest.approx(0.2) and a["rest_of_world"]["year"] == T0 and "global_t = covered_t / (1 - share)" == a["rest_of_world"]["formula"]
    assert a["land_use"]["mt_per_year"] == LUC and a["land_use"]["window"] == [1996, 2000] and "trailing 5-year mean" in a["land_use"]["rule"]
    for sc in PATH:
        cov, glob, _, _ = expected(sc)
        for i, r in enumerate(out["scenarios"][sc]):
            assert r["year"] == FIRST + i and r["covered_mt"] == pytest.approx(cov[i], abs=1e-4) and r["global_fossil_mt"] == pytest.approx(glob[i], abs=1e-4)
            assert r["rest_of_world_mt"] == pytest.approx(glob[i] - cov[i], abs=1e-4) and r["land_use_mt"] == LUC
            assert r["rest_of_world_mt"] == pytest.approx(0.25 * cov[i], abs=1e-4)  # RoW moves proportionally with the covered pathway: 0.2/(1-0.2)


def test_implied_warming_is_slope_times_cumulative_emissions_since_the_last_observed_year(tmp_path):
    _, out = go(tmp_path)
    for sc in PATH:
        _, _, inc_t, _ = expected(sc)
        for i, r in enumerate(out["scenarios"][sc]):
            h = r["headline"]
            assert r["cumulative_increment_mt"] == pytest.approx(inc_t[i], abs=1e-3)
            assert h["delta_t_c"] == pytest.approx(SLOPE_H * inc_t[i] / 1e6, abs=1e-6)
            assert h["delta_t_ci95"] == pytest.approx([CI_H[0] * inc_t[i] / 1e6, CI_H[1] * inc_t[i] / 1e6], abs=1e-6)  # slope uncertainty only


def test_the_fossil_only_line_uses_its_own_slope_and_fossil_only_increments(tmp_path):
    _, out = go(tmp_path)
    for sc in PATH:
        _, _, inc_t, inc_f = expected(sc)
        for i, r in enumerate(out["scenarios"][sc]):
            f = r["fossil_only"]
            assert r["fossil_only_cumulative_increment_mt"] == pytest.approx(inc_f[i], abs=1e-3) and r["fossil_only_cumulative_increment_mt"] < r["cumulative_increment_mt"]  # no land-use term
            assert f["delta_t_c"] == pytest.approx(SLOPE_F * inc_f[i] / 1e6, abs=1e-6) and f["delta_t_ci95"][0] == pytest.approx(CI_F[0] * inc_f[i] / 1e6, abs=1e-6)


def test_the_anchor_is_the_trailing_five_year_mean_not_the_last_year_and_the_curve_does_not_jump(tmp_path):
    _, out = go(tmp_path)
    b = out["base"]["anchor"]
    assert b["value_c"] == pytest.approx(1.30) and b["last_year_value_c"] == 1.90 and "trailing 5-year mean" in b["definition"] and "1996-2000" in b["definition"]
    for sc in PATH:
        for r in out["scenarios"][sc]:
            for key in ("headline", "fossil_only"):
                assert r[key]["level_c"] == pytest.approx(1.30 + r[key]["delta_t_c"], abs=1e-6) and r[key]["level_ci95"][0] == pytest.approx(1.30 + r[key]["delta_t_ci95"][0], abs=1e-6)
        first = out["scenarios"][sc][0]["headline"]
        assert first["level_c"] - 1.30 == pytest.approx(first["delta_t_c"], abs=1e-9) and first["level_c"] - 1.90 != pytest.approx(first["delta_t_c"])  # anchor + one year's increment, not last-year value + increment


def test_scenarios_are_translated_independently_and_ordered_by_their_emissions(tmp_path):
    _, out = go(tmp_path)
    assert sorted(out["scenarios"]) == ["Aggressive", "BAU", "Moderate"] and out["scenario_source"]["scenarios"] == ["Aggressive", "BAU", "Moderate"]
    last = {sc: rows[-1]["headline"]["level_c"] for sc, rows in out["scenarios"].items()}
    assert last["BAU"] > last["Moderate"] > last["Aggressive"]  # ordered by their emissions


def test_base_block_states_the_last_observed_totals_and_the_cumulative_base(tmp_path):
    _, out = go(tmp_path)
    b = out["base"]
    assert b["last_observed_year"] == T0 and b["world_co2_mt"] == WORLD_T0 and b["covered_co2_mt"] == 1_000_000.0 and b["covered_share_of_world"] == pytest.approx(0.8)
    assert b["world_cumulative_total_co2_since_1850_mt"] == pytest.approx(sum(1000.0 for _ in range(1850, T0)) + WORLD_T0 + 5 * LUC) and [c["country"] for c in out["covered_countries"]] == ["Aland", "Bland"]


def test_labels_and_the_causation_note_are_exactly_the_required_wording(tmp_path):
    _, out = go(tmp_path)
    assert out["labels"] == ["illustrative, partial-coverage translation", "Implied temperature outcomes",
                             "Dependent on the selected regression period, emissions source and model assumptions", "Illustrative analytical translations, not formal climate-model projections"]
    assert "not proof of causation" in out["note"] and out["name"] == "Scenario temperature translation"


# ---------------------------------------------------------------- guards (decision 39)


def test_a_stale_scenario_file_gives_explicit_nulls_and_overwrites_the_previous_output(tmp_path):
    _, good = go(tmp_path)
    assert good["scenarios"] is not None
    write(tmp_path, scenario_edit=lambda p: p.assign(year=p.year + 1))  # the scenarios now start in 2002: OWID still ends in 2000
    rep = T.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"), scenario_path=str(tmp_path / "scenario_projections.csv"), owid_path=str(tmp_path / "owid-co2-data.csv"))
    out = json.loads((tmp_path / "correlation_scenario_temperature.json").read_text())
    assert out["scenarios"] is None and "scenarios are stale relative to OWID" in out["unavailable_reason"] and "first scenario year is 2002 but the last observed year is 2000" in out["unavailable_reason"]
    assert "rerun the Week 5 notebook" in out["unavailable_reason"] and any("translation unavailable" in d for d in rep.deviations)


def test_scenarios_that_start_before_the_next_year_are_also_refused(tmp_path):
    _, out = go(tmp_path, scenario_edit=lambda p: p.assign(year=p.year - 1))  # first year 2000 == T0: overlaps the observed year
    assert out["scenarios"] is None and "stale relative to OWID" in out["unavailable_reason"]


@pytest.mark.parametrize("name,edit,fragment", [
    ("missing year", lambda p: p[~((p.scenario == "BAU") & (p.country == "Bland") & (p.year == FIRST + 1))], "not a complete country x year grid"),
    ("country in one scenario only", lambda p: p[~((p.scenario == "Aggressive") & (p.country == "Bland"))], "not a complete country x year grid"),
    ("duplicates", lambda p: pd.concat([p, p.head(1)]), "duplicate scenario/country/year rows"),
    ("negative", lambda p: p.assign(co2_projected=np.where(p.index == 0, -1.0, p.co2_projected)), "missing, non-numeric, non-finite or negative projected emissions"),
    ("missing value", lambda p: p.assign(co2_projected=np.where(p.index == 0, np.nan, p.co2_projected)), "missing, non-numeric, non-finite or negative projected emissions"),
    ("missing column", lambda p: p.drop(columns=["scenario"]), "required column missing: scenario"),
])
def test_malformed_scenario_files_are_explicit_nulls_with_the_reason(tmp_path, name, edit, fragment):
    rep, out = go(tmp_path, scenario_edit=lambda p: edit(p.reset_index(drop=True)))
    assert out["scenarios"] is None and fragment in out["unavailable_reason"] and any("translation unavailable" in d for d in rep.deviations)


def test_scenario_countries_without_an_owid_value_at_the_last_year_are_named(tmp_path):
    _, out = go(tmp_path, owid_edit=lambda r: r[r.country != "Bland"])
    assert out["scenarios"] is None and "scenario countries with no OWID CO2 value in 2000: Bland" in out["unavailable_reason"]
    _, out2 = go(tmp_path / "n" if (tmp_path / "n").mkdir() is None else tmp_path, owid_edit=lambda r: r.assign(co2=np.where(r.country == "Aland", np.nan, r.co2)))
    assert "Aland" in out2["unavailable_reason"]


def test_covered_countries_that_are_not_a_proper_part_of_the_world_total_are_refused(tmp_path):
    _, out = go(tmp_path, world_edit=lambda w: w.assign(co2_mt=np.where(w.year == T0, 900_000.0, w.co2_mt)))  # World below the covered 1,000,000
    assert out["scenarios"] is None and "are not a proper part of the World total" in out["unavailable_reason"]


def test_a_headline_regression_that_is_unavailable_means_no_translation(tmp_path):
    _, out = go(tmp_path, headline="none")
    assert out["scenarios"] is None and "headline regression is unavailable" in out["unavailable_reason"]


def test_without_the_fossil_regression_the_headline_line_survives_and_the_gap_is_flagged(tmp_path):
    rep, out = go(tmp_path, headline="no_fossil")
    assert out["scenarios"] is not None and all(r["fossil_only"] is None and r["headline"] is not None for rows in out["scenarios"].values() for r in rows)
    assert out["assumptions"]["slope"]["fossil_only"] is None and any("fossil-only line is unavailable" in d for d in rep.deviations)


@pytest.mark.parametrize("missing", ["scenario_projections.csv", "owid_world_co2_annual.csv", "temperature_anomaly_annual.csv", "correlation_headline.json", "owid-co2-data.csv"])
def test_a_missing_input_is_an_explicit_null_naming_the_file_and_never_a_crash(tmp_path, missing):
    write(tmp_path)
    os.remove(tmp_path / missing)
    rep = T.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"), scenario_path=str(tmp_path / "scenario_projections.csv"), owid_path=str(tmp_path / "owid-co2-data.csv"))
    out = json.loads((tmp_path / "correlation_scenario_temperature.json").read_text())
    assert out["scenarios"] is None and missing in out["unavailable_reason"]  # the reason names the file that is not there
    assert any("translation unavailable" in d for d in rep.deviations)


def test_too_little_temperature_history_for_the_anchor_is_refused(tmp_path):
    def short(d):
        p = d / "temperature_anomaly_annual.csv"
        pd.read_csv(p).query("year >= 1998").to_csv(p, index=False)

    write(tmp_path)
    short(tmp_path)
    T.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"), scenario_path=str(tmp_path / "scenario_projections.csv"), owid_path=str(tmp_path / "owid-co2-data.csv"))
    out = json.loads((tmp_path / "correlation_scenario_temperature.json").read_text())
    assert out["scenarios"] is None and "not all available up to 2000" in out["unavailable_reason"]


# ---------------------------------------------------------------- metadata, continuity, provenance


def test_metadata_is_complete_even_when_the_translation_is_unavailable(tmp_path):
    _, out = go(tmp_path, scenario_edit=lambda p: p.assign(year=p.year + 5))
    assert out["scenarios"] is None and out["labels"] and out["note"] and out["temperature_source_vintage"]["caveat"] in out["caveats"]
    c = " ".join(out["caveats"])
    assert "not a complete climate model" in c and "No formal license (e.g., CC BY) is stated" in c and "+/-0.7 GtC/yr" in c and "Based on Berkeley Earth file vintage 2025-01-10" in c


def test_the_vintage_caveat_is_removed_only_when_the_owner_records_a_reconciliation(tmp_path):
    _, out = go(tmp_path, notices={"berkeley_earth": {"vintage_reconciled": True}})
    assert out["temperature_source_vintage"]["reconciled"] is True and not any("Berkeley Earth file vintage" in c for c in out["caveats"])


def test_scenarios_that_start_at_different_levels_are_each_reported(tmp_path):
    _, out = go(tmp_path, scenario_edit=with_steps(BAU=10.0, Moderate=3.0, Aggressive=-4.0), baseline="none")  # against 1,000,000 observed
    b = out["base"]
    assert b["first_scenario_year_covered_mt"] == {"Aggressive": pytest.approx(960_000.0), "BAU": pytest.approx(1_100_000.0), "Moderate": pytest.approx(1_030_000.0)}
    assert b["first_scenario_year_vs_last_observed_pct"] == {"Aggressive": pytest.approx(-4.0), "BAU": pytest.approx(10.0), "Moderate": pytest.approx(3.0)}
    text = [c for c in out["caveats"] if c.startswith("The scenario pathways start ")]
    assert len(text) == 1 and "Aggressive -4.0%, BAU +10.0%, Moderate +3.0%" in text[0]
    assert "(1,000,000 Mt in 2000; Aggressive 960,000 Mt, BAU 1,100,000 Mt, Moderate 1,030,000 Mt in 2001)" in text[0]
    assert "each scenario carries that step" in text[0]


def test_when_every_scenario_starts_at_the_same_level_the_caveat_says_so_once(tmp_path):
    _, out = go(tmp_path, scenario_edit=with_steps(BAU=10.0, Moderate=10.0, Aggressive=10.0), baseline="none")
    text = [c for c in out["caveats"] if c.startswith("The scenario pathways start ")]
    assert len(text) == 1 and text[0].startswith("The scenario pathways start +10.0% from the last observed total for the covered countries (1,000,000 Mt in 2000 to 1,100,000 Mt in 2001)")


def test_a_smooth_start_gets_no_continuity_caveat(tmp_path):
    def smooth(p):
        q = p.copy()
        q.loc[q.year == FIRST, "co2_projected"] = q.loc[q.year == FIRST, "country"].map({"Aland": 603_000.0, "Bland": 401_000.0})
        return q

    _, out = go(tmp_path, scenario_edit=lambda p: smooth(p.reset_index(drop=True)))
    assert all(abs(j) < 2.0 for j in out["base"]["first_scenario_year_vs_last_observed_pct"].values()) and not any(c.startswith("The scenario pathways start ") for c in out["caveats"])


def test_scenario_source_provenance_matches_the_file_bytes(tmp_path):
    _, out = go(tmp_path)
    raw = (tmp_path / "scenario_projections.csv").read_bytes()
    s = out["scenario_source"]
    assert s["sha256"] == hashlib.sha256(raw).hexdigest() and s["file"] == "scenario_projections.csv" and s["rows"] == 18 and s["years"] == [FIRST, FIRST + 2]  # 3 scenarios x 2 countries x 3 years
    assert out["attribution"]["required_citation_format"].startswith("Global Carbon Project")


def test_the_slope_block_publishes_both_slopes_and_says_the_band_is_slope_uncertainty_only(tmp_path):
    _, out = go(tmp_path)
    s = out["assumptions"]["slope"]
    assert s["headline"]["slope"] == SLOPE_H and s["headline"]["ci95_hac"] == CI_H and s["fossil_only"]["slope"] == SLOPE_F and s["unit"] == "°C per 1,000 GtCO2"
    assert "slope uncertainty only, not scenario or climate uncertainty" in s["note"]


def test_translate_is_pure_and_handles_a_missing_regression():
    proj = pd.DataFrame([("A", 2001, "S", 100.0), ("A", 2002, "S", 200.0)], columns=["country", "year", "scenario", "co2_projected"])
    r = T.translate(proj, 2000, 500.0, 1000.0, 10.0, None, {"slope": 1.0, "ci95_hac": [0.5, 1.5]}, 1.0)
    rows = r["scenarios"]["S"]
    assert r["rest_of_world_share"] == 0.5 and rows[0]["headline"] is None and rows[0]["global_fossil_mt"] == 200.0 and rows[1]["global_fossil_mt"] == 400.0
    assert rows[1]["fossil_only"]["delta_t_c"] == pytest.approx(1.0 * 600.0 / 1e6, abs=1e-12)


def test_the_output_is_deterministic_and_the_stage_is_registered_and_gated(tmp_path):
    from pipeline import run

    _, a = go(tmp_path)
    T.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"), scenario_path=str(tmp_path / "scenario_projections.csv"), owid_path=str(tmp_path / "owid-co2-data.csv"))
    b = json.loads((tmp_path / "correlation_scenario_temperature.json").read_text())
    for d in (a, b):
        d.pop("generated_at")
    assert a == b
    assert "scenario_temperature" in run.DERIVED_SOURCES and "scenario_temperature" not in run.ACTIVE_SOURCES and run.DEPENDS_ON["scenario_temperature"] == ("correlate", "owid", "berkeley_earth")


# ---------------------------------------------------------------- Copilot review on #218


def set_cell(df, idx, col, value):
    """A copy with one cell replaced, built from numpy arrays: any pandas setitem/assign here trips the false-positive chained-assignment warning on Python 3.14."""
    cols = {c: df[c].to_numpy().copy() for c in df.columns}
    arr = cols[col].astype(object if isinstance(value, str) else float)
    arr[idx] = value
    cols[col] = arr
    return pd.DataFrame(cols)


def strict_json(path):
    """Parse like a strict client: NaN / Infinity are not valid JSON."""
    def refuse(c):
        raise ValueError(f"non-standard JSON constant {c}")
    return json.loads(path.read_text(), parse_constant=refuse)


@pytest.mark.parametrize("metadata_file,contents", [("provenance.json", "{not json"), ("notices.json", "{not json")])
def test_malformed_vintage_metadata_overwrites_the_stale_output_with_nulls_and_does_not_raise(tmp_path, metadata_file, contents):
    _, good = go(tmp_path)
    assert good["scenarios"] is not None
    (tmp_path / metadata_file).write_text(contents)
    rep = T.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"), scenario_path=str(tmp_path / "scenario_projections.csv"), owid_path=str(tmp_path / "owid-co2-data.csv"))
    out = strict_json(tmp_path / "correlation_scenario_temperature.json")
    assert out["scenarios"] is None and "scenario metadata unavailable: temperature vintage metadata" in out["unavailable_reason"]
    assert out["temperature_source_vintage"]["caveat"] in out["caveats"] and "could not be read" in out["temperature_source_vintage"]["caveat"]
    assert any("scenario temperature translation unavailable" in d for d in rep.deviations)


@pytest.mark.parametrize("bad", [np.inf, -np.inf, np.nan])
def test_non_finite_projected_emissions_are_refused_and_never_reach_the_file(tmp_path, bad):
    rep, out = go(tmp_path, scenario_edit=lambda p: set_cell(p, 3, "co2_projected", bad))
    assert out["scenarios"] is None and "non-finite" in out["unavailable_reason"] and any("translation unavailable" in d for d in rep.deviations)
    strict_json(tmp_path / "correlation_scenario_temperature.json")  # parses under a strict parser: no Infinity / NaN


def test_non_numeric_projected_emissions_and_a_non_integer_year_are_refused(tmp_path):
    _, out = go(tmp_path, scenario_edit=lambda p: set_cell(p, 2, "co2_projected", "lots"))
    assert out["scenarios"] is None and "non-numeric" in out["unavailable_reason"]
    _, out2 = go(tmp_path / "y" if (tmp_path / "y").mkdir() is None else tmp_path, scenario_edit=lambda p: set_cell(p, 0, "year", 2001.5))
    assert out2["scenarios"] is None and "non-integer year" in out2["unavailable_reason"]


def test_non_finite_values_in_the_other_inputs_are_refused(tmp_path):
    _, a = go(tmp_path, owid_edit=lambda r: r.assign(co2=np.where(r.country == "Aland", np.inf, r.co2)))
    assert a["scenarios"] is None and "non-finite OWID CO2 value" in a["unavailable_reason"]
    _, b = go(tmp_path / "w" if (tmp_path / "w").mkdir() is None else tmp_path, world_edit=lambda w: w.assign(co2_mt=np.where(w.year == T0, np.inf, w.co2_mt)))
    assert b["scenarios"] is None and "not a proper part of the World total" in b["unavailable_reason"]
    write(tmp_path / "w")
    hj = json.loads((tmp_path / "w" / "correlation_headline.json").read_text())
    hj["headline"]["fit"]["slope"] = "NaN-ish"
    (tmp_path / "w" / "correlation_headline.json").write_text(json.dumps(hj))
    T.run(str(tmp_path / "w"), notices_path=str(tmp_path / "w" / "notices.json"), scenario_path=str(tmp_path / "w" / "scenario_projections.csv"), owid_path=str(tmp_path / "w" / "owid-co2-data.csv"))
    c = strict_json(tmp_path / "w" / "correlation_scenario_temperature.json")
    assert c["scenarios"] is None and "regression statistics in correlation_headline.json are not finite numbers" in c["unavailable_reason"]


def test_require_finite_rejects_non_finite_numbers_anywhere_in_the_structure():
    T._require_finite({"a": [1.0, {"b": 2.0}], "c": 3})
    for bad in ({"a": float("inf")}, {"a": [1.0, {"b": float("nan")}]}, [float("-inf")]):
        with pytest.raises(T.Unavailable, match="non-finite number"):
            T._require_finite(bad)


def test_a_non_finite_value_produced_by_the_translation_leaves_no_partial_result(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "translate", lambda *a, **k: {"rest_of_world_share": 0.1, "scenarios": {"S": [{"year": 2001, "x": float("inf")}]}})
    rep, out = go(tmp_path)
    assert out["scenarios"] is None and out["base"] is None and out["covered_countries"] is None and "non-finite number" in out["unavailable_reason"]
    assert out["assumptions"]["rest_of_world"]["share"] is None and out["assumptions"]["land_use"]["mt_per_year"] is None  # nothing from the failed translation was kept
    strict_json(tmp_path / "correlation_scenario_temperature.json")


# ---- the complete schema, whether or not the translation is available


def test_an_unavailable_output_has_exactly_the_same_keys_as_an_available_one(tmp_path):
    _, good = go(tmp_path)
    _, bad = go(tmp_path / "b" if (tmp_path / "b").mkdir() is None else tmp_path, scenario_edit=lambda p: p.assign(year=p.year + 3))
    assert set(bad) - {"unavailable_reason"} == set(good) and bad["scenarios"] is None and bad["base"] is None and bad["covered_countries"] is None
    assert set(bad["assumptions"]) == set(good["assumptions"]) and set(bad["assumptions"]["rest_of_world"]) == set(good["assumptions"]["rest_of_world"])
    assert set(bad["inputs"]) == set(good["inputs"]) == set(T.INPUT_FILES)


def test_the_unavailable_output_keeps_the_method_assumption_rules_labels_and_the_scenario_checksum(tmp_path):
    _, out = go(tmp_path, scenario_edit=lambda p: p.assign(year=p.year + 3))  # stale: the file is readable but refused
    raw = (tmp_path / "scenario_projections.csv").read_bytes()
    assert out["method"].startswith("implied warming = slope x cumulative emissions since the last observed year")
    assert out["scenario_source"]["sha256"] == hashlib.sha256(raw).hexdigest() and out["scenario_source"]["file"] == "scenario_projections.csv"  # the checksum is retained once the bytes were read
    assert "held at its last-observed share" in out["assumptions"]["rest_of_world"]["rule"] and out["assumptions"]["rest_of_world"]["share"] is None
    assert "trailing 5-year mean" in out["assumptions"]["land_use"]["rule"] and out["assumptions"]["slope"]["unit"] == "°C per 1,000 GtCO2"
    assert "slope uncertainty only" in out["assumptions"]["slope"]["note"] and out["assumptions"]["fossil_only_line"]
    assert out["labels"] and out["attribution"]["required_citation_format"].startswith("Global Carbon Project")  # attribution was readable from the headline file


def test_each_input_is_recorded_as_available_as_soon_as_it_was_read_and_not_before(tmp_path):
    _, out = go(tmp_path, scenario_edit=lambda p: p.assign(year=p.year + 3))  # fails in the grid check, before OWID country data and the temperature series are read
    i = out["inputs"]
    assert i["owid_world_co2_annual.csv"] == {"available": True, "last_observed_year": T0} and i["correlation_headline.json"]["headline_regression"] is True
    assert i["scenario_projections.csv"]["available"] is True and i["owid-co2-data.csv"] == {"available": False} and i["temperature_anomaly_annual.csv"] == {"available": False}
    _, out2 = go(tmp_path / "m" if (tmp_path / "m").mkdir() is None else tmp_path, no_scenario=True)
    assert out2["inputs"]["scenario_projections.csv"] == {"available": False} and out2["scenario_source"] is None and out2["inputs"]["correlation_headline.json"]["available"] is True


def test_the_regression_slopes_read_so_far_are_kept_when_a_later_input_fails(tmp_path):
    _, out = go(tmp_path, scenario_edit=lambda p: p.assign(year=p.year + 3))
    s = out["assumptions"]["slope"]
    assert s["headline"]["slope"] == SLOPE_H and s["fossil_only"]["slope"] == SLOPE_F
    _, out2 = go(tmp_path / "h" if (tmp_path / "h").mkdir() is None else tmp_path, headline="none")
    assert out2["assumptions"]["slope"]["headline"] is None and out2["inputs"]["correlation_headline.json"]["headline_regression"] is False


def test_every_output_the_stage_writes_is_valid_strict_json(tmp_path):
    go(tmp_path)
    strict_json(tmp_path / "correlation_scenario_temperature.json")
    go(tmp_path / "u" if (tmp_path / "u").mkdir() is None else tmp_path, scenario_edit=lambda p: p.assign(year=p.year + 3))
    strict_json(tmp_path / "correlation_scenario_temperature.json")


def test_a_failure_after_the_translation_is_filled_in_still_leaves_no_partial_result(tmp_path, monkeypatch):
    """The reset in the failure handler is defensive (nothing assigns a translation before the last step), so force a failure after it was assigned."""
    calls = {"n": 0}
    real = T.RunReport.deviate

    def flaky(self, msg):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom after the translation was filled in")
        return real(self, msg)

    monkeypatch.setattr(T.RunReport, "deviate", flaky)
    rep, out = go(tmp_path, headline="no_fossil")  # the missing fossil regression makes the success path call report.deviate
    assert out["scenarios"] is None and out["base"] is None and out["covered_countries"] is None
    assert "boom after the translation was filled in" in out["unavailable_reason"]
    strict_json(tmp_path / "correlation_scenario_temperature.json")


# ---------------------------------------------------------------- the owner's review edits on #218 (applied on GitHub after the last commit)


@pytest.mark.parametrize("name,edit,found", [
    ("Moderate missing", lambda p: p[p.scenario != "Moderate"], "['Aggressive', 'BAU']"),
    ("Aggressive missing", lambda p: p[p.scenario != "Aggressive"], "['BAU', 'Moderate']"),
    ("an extra scenario", lambda p: pd.concat([p, p[p.scenario == "BAU"].assign(scenario="Extreme")]), "['Aggressive', 'BAU', 'Extreme', 'Moderate']"),
    ("a renamed scenario", lambda p: p.assign(scenario=p.scenario.replace({"Moderate": "Medium"})), "['Aggressive', 'BAU', 'Medium']"),
    ("a lower-case scenario", lambda p: p.assign(scenario=p.scenario.replace({"BAU": "bau"})), "['Aggressive', 'Moderate', 'bau']"),
])
def test_the_scenario_file_must_contain_exactly_bau_moderate_and_aggressive(tmp_path, name, edit, found):
    rep, out = go(tmp_path, scenario_edit=lambda p: edit(p.reset_index(drop=True)))
    assert out["scenarios"] is None and f"scenario_projections.csv must contain exactly BAU, Moderate and Aggressive; found {found}" in out["unavailable_reason"]
    assert any("translation unavailable" in d for d in rep.deviations)
    strict_json(tmp_path / "correlation_scenario_temperature.json")


def test_the_three_scenarios_translate_together_when_present(tmp_path):
    rep, out = go(tmp_path)
    assert rep.deviations == [] and sorted(out["scenarios"]) == ["Aggressive", "BAU", "Moderate"] and all(len(rows) == 3 for rows in out["scenarios"].values())


def test_the_land_use_mean_needs_every_year_of_its_window(tmp_path):
    """A mean over fewer than five years (a gap, or NaN inside the window) is refused instead of quietly averaging what is left."""
    _, a = go(tmp_path, world_edit=lambda w: w.assign(land_use_change_co2_mt=np.where(w.year == T0 - 2, np.nan, w.land_use_change_co2_mt)))
    assert a["scenarios"] is None and "land-use" in a["unavailable_reason"] and "not all available up to 2000" in a["unavailable_reason"]
    x = tmp_path / "short"
    x.mkdir()
    _, b = go(x, world_edit=lambda w: w[w.year != T0 - 1])  # a missing year: only four in the window
    assert b["scenarios"] is None and "not all available up to 2000" in b["unavailable_reason"]
    y = tmp_path / "ok"
    y.mkdir()
    _, c = go(y)
    assert c["scenarios"] is not None and c["assumptions"]["land_use"]["mt_per_year"] == LUC


def test_a_nan_in_the_cumulative_total_is_refused_not_skipped(tmp_path):
    _, out = go(tmp_path, world_edit=lambda w: w.assign(total_co2_incl_luc_mt=np.where(w.year == 1900, np.nan, w.total_co2_incl_luc_mt)))
    assert out["scenarios"] is None and "non-finite number" in out["unavailable_reason"] and "world_cumulative_total_co2_since_1850_mt" in out["unavailable_reason"]
    strict_json(tmp_path / "correlation_scenario_temperature.json")


def test_the_finite_check_covers_the_attribution_and_the_slope_blocks(tmp_path):
    write(tmp_path)
    hj = json.loads((tmp_path / "correlation_headline.json").read_text())
    hj["attribution"] = {"required_citation_format": "Global Carbon Project", "weight": float("inf")}
    (tmp_path / "correlation_headline.json").write_text(json.dumps(hj))  # json.dumps writes Infinity, which json.load reads back as inf
    T.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"), scenario_path=str(tmp_path / "scenario_projections.csv"), owid_path=str(tmp_path / "owid-co2-data.csv"))
    out = strict_json(tmp_path / "correlation_scenario_temperature.json")
    assert out["scenarios"] is None and "non-finite number" in out["unavailable_reason"] and "attribution" in out["unavailable_reason"]


def test_a_non_finite_value_in_the_metadata_never_survives_into_an_unavailable_output(tmp_path):
    """The rejected value is read into the output before the check refuses it, so the failure path must remove it: Infinity is not valid JSON."""
    write(tmp_path)
    hj = json.loads((tmp_path / "correlation_headline.json").read_text())
    hj["attribution"] = {"citation": "GCP", "weights": [1.0, float("inf"), float("nan")]}
    hj["headline"]["fit"]["ci95_hac"] = [0.4, float("inf")]
    (tmp_path / "correlation_headline.json").write_text(json.dumps(hj))
    rep = T.run(str(tmp_path), notices_path=str(tmp_path / "notices.json"), scenario_path=str(tmp_path / "scenario_projections.csv"), owid_path=str(tmp_path / "owid-co2-data.csv"))
    out = strict_json(tmp_path / "correlation_scenario_temperature.json")  # parses under a strict parser
    assert out["scenarios"] is None and out["attribution"]["weights"] == [1.0, None, None] and out["attribution"]["citation"] == "GCP"
    assert "not finite numbers" in out["unavailable_reason"] or "non-finite" in out["unavailable_reason"]
    assert any("translation unavailable" in d for d in rep.deviations)


def test_the_scrub_replaces_only_non_finite_numbers_and_reports_their_paths():
    clean, bad = T._scrub_non_finite({"a": 1.5, "b": [2.0, float("inf")], "c": {"d": float("nan"), "e": "x", "f": None, "g": 7}})
    assert clean == {"a": 1.5, "b": [2.0, None], "c": {"d": None, "e": "x", "f": None, "g": 7}} and bad == ["output.b[1]", "output.c.d"]
    same, none = T._scrub_non_finite({"a": [1.0, {"b": 2}]})
    assert same == {"a": [1.0, {"b": 2}]} and none == []


# ---------------------------------------------------------------- the first-year step check (Backlog B2: +/-2% aggregate, +/-5% per country)


def many_countries(monkeypatch, n=20, per_country_step=None):
    """A larger covered set (n countries of 50,000 Mt each, 1,000,000 in total) so a single outlier is below the systematic share."""
    countries = {f"C{i:02d}": 1_000_000.0 / n for i in range(n)}
    steps = per_country_step or {}
    path = {sc: {c: [v * (1 + (steps.get(c, 0.0) if sc == "BAU" else 0.0) / 100) * f for f in (1.0, 1.04, 1.08)] for c, v in countries.items()} for sc in ("BAU", "Moderate", "Aggressive")}
    monkeypatch.setattr(sys.modules[__name__], "COUNTRIES", countries)
    monkeypatch.setattr(sys.modules[__name__], "PATH", path)


import sys  # noqa: E402


def test_the_default_pathways_are_within_the_thresholds_and_the_step_checks_are_published(tmp_path):
    rep, out = go(tmp_path)
    assert rep.deviations == [] and not any("start outside" in n for n in rep.notes)
    sc = out["base"]["step_check"]
    assert sorted(sc) == ["Aggressive", "BAU", "Moderate"]
    for name, pct in (("BAU", 1.0), ("Moderate", 0.5), ("Aggressive", -0.5)):
        r = sc[name]
        assert r["aggregate_step_pct"] == pytest.approx(pct, abs=1e-9) and r["aggregate_breach"] is False and r["flagged_countries"] == [] and r["systematic_breach"] is False
        assert r["aggregate_tolerance_pct"] == 2.0 and r["country_tolerance_pct"] == 5.0 and set(r["country_steps_pct"]) == set(COUNTRIES) and r["n_countries"] == 2
        assert r["rule"].startswith("aggregate step within +/-2%")
    assert out["base"]["first_scenario_year_vs_last_observed_pct"] == {k: pytest.approx(v["aggregate_step_pct"]) for k, v in sc.items()}  # one source of truth


@pytest.mark.parametrize("pct,breach", [(0.0, False), (1.99, False), (2.0, False), (2.01, True), (-2.0, False), (-2.01, True), (3.7, True)])
def test_the_aggregate_threshold_is_two_percent_and_inclusive(tmp_path, pct, breach):
    rep, out = go(tmp_path, scenario_edit=with_steps(BAU=pct, Moderate=pct, Aggressive=pct), baseline="none")
    assert out["base"]["step_check"]["BAU"]["aggregate_breach"] is breach and out["scenarios"] is not None  # the translation still publishes: a step is reported, not refused
    assert (len([d for d in rep.deviations if "the aggregate first-year step is" in d]) == 1) is breach


def test_each_distinct_scenario_start_gets_its_own_aggregate_deviation(tmp_path):
    rep, out = go(tmp_path, scenario_edit=with_steps(BAU=10.0, Moderate=3.0, Aggressive=-4.0), baseline="none")
    dev = [d for d in rep.deviations if "the aggregate first-year step is" in d]
    assert len(dev) == 3
    assert any("(BAU), first year 2001: the aggregate first-year step is +10.0% from the last observed total (tolerance ±2%)" in d for d in dev)
    assert any("(Moderate), first year 2001" in d and "+3.0%" in d for d in dev) and any("(Aggressive), first year 2001" in d and "-4.0%" in d for d in dev)


def test_scenarios_that_start_identically_are_reported_once(tmp_path):
    rep, _ = go(tmp_path, scenario_edit=with_steps(BAU=10.0, Moderate=10.0, Aggressive=10.0), baseline="none")
    dev = [d for d in rep.deviations if "the aggregate first-year step is" in d]
    assert len(dev) == 1 and "scenario pathways (Aggressive, BAU, Moderate), first year 2001: the aggregate first-year step is +10.0%" in dev[0]


def test_a_breaching_start_does_not_stop_the_translation(tmp_path):
    _, out = go(tmp_path, scenario_edit=with_steps(BAU=10.0, Moderate=10.0, Aggressive=10.0), baseline="none")
    assert out["scenarios"] is not None and out["base"]["step_check"]["BAU"]["aggregate_breach"] is True


def test_in_a_small_set_one_outlier_country_is_systematic_and_a_deviation(tmp_path):
    def one_country(p):
        cols = {c: p.reset_index(drop=True)[c].to_numpy().copy() for c in p.columns}
        v = cols["co2_projected"].astype(float)
        m = (cols["year"] == FIRST) & (cols["country"] == "Aland")
        v[m] = 600_000.0 * 1.08  # Aland +8%: 1 of 2 countries = 50% of the set
        cols["co2_projected"] = v
        return pd.DataFrame(cols)

    rep, out = go(tmp_path, scenario_edit=one_country, baseline="none")
    r = out["base"]["step_check"]["BAU"]
    assert r["systematic_breach"] is True and [f["country"] for f in r["flagged_countries"]] == ["Aland"]
    assert any("1 of 2 countries start outside ±5%" in d and "Aland +8.0%" in d and "more than the systematic threshold" in d for d in rep.deviations)


def test_in_a_large_set_one_outlier_is_a_note_with_the_country_and_not_a_deviation(tmp_path, monkeypatch):
    many_countries(monkeypatch, n=20, per_country_step={"C03": 12.0, "C04": -1.0})
    rep, out = go(tmp_path, baseline="none")
    r = out["base"]["step_check"]["BAU"]
    assert [f["country"] for f in r["flagged_countries"]] == ["C03"] and r["flagged_share"] == pytest.approx(0.05) and r["systematic_breach"] is False
    assert not any("start outside" in d for d in rep.deviations)
    assert any("1 of 20 countries start outside ±5%" in n and "C03 +12.0%" in n for n in rep.notes)
    assert out["base"]["step_check"]["BAU"]["aggregate_step_pct"] == pytest.approx((0.12 * 1 - 0.01) / 20 * 100, abs=1e-6)


def test_more_than_ten_percent_of_countries_outside_is_systematic_even_in_a_large_set(tmp_path, monkeypatch):
    many_countries(monkeypatch, n=20, per_country_step={f"C{i:02d}": 9.0 for i in range(3)})  # 3 of 20 = 15%
    rep, out = go(tmp_path, baseline="none")
    assert out["base"]["step_check"]["BAU"]["systematic_breach"] is True and any("3 of 20 countries start outside" in d for d in rep.deviations)


def test_a_non_positive_observed_value_makes_the_step_undefined_and_the_translation_unavailable(tmp_path):
    _, out = go(tmp_path, owid_edit=lambda r: r.assign(co2=np.where(r.country == "Aland", 0.0, r.co2)))
    assert out["scenarios"] is None and "first-year step check cannot be computed" in out["unavailable_reason"] and "observed total is not positive for: Aland" in out["unavailable_reason"]


def test_the_continuity_caveat_uses_the_shared_two_percent_threshold(tmp_path):
    from pipeline import step_check

    assert step_check.AGGREGATE_TOL_PCT == 2.0
    _, a = go(tmp_path, scenario_edit=with_steps(BAU=1.99, Moderate=1.99, Aggressive=1.99), baseline="none")
    assert not any(c.startswith("The scenario pathways start ") for c in a["caveats"])
    x = tmp_path / "b"
    x.mkdir()
    _, b = go(x, scenario_edit=with_steps(BAU=2.5, Moderate=2.5, Aggressive=2.5), baseline="none")
    assert any(c.startswith("The scenario pathways start +2.5%") for c in b["caveats"])


# ---------------------------------------------------------------- is the scenario file's BAU the current baseline?


def test_a_scenario_file_on_the_current_baseline_is_reported_current_with_no_alert(tmp_path):
    rep, out = go(tmp_path)
    pb = out["base"]["pathway_baseline"]
    assert pb["status"] == "current" and pb["max_abs_difference_mt"] == 0.0 and pb["n_country_years_compared"] == 6 and pb["file"] == "ets_baseline_full_data.csv"
    assert pb["aggregate"][str(FIRST)]["difference_pct"] == pytest.approx(0.0) and pb["aggregate"][str(FIRST + 2)]["difference_pct"] == pytest.approx(0.0)
    assert rep.deviations == [] and not any("older ETS fit" in c for c in out["caveats"])


def test_a_scenario_file_from_an_older_fit_is_a_deviation_with_the_cause_and_the_fix_and_a_caveat(tmp_path):
    rep, out = go(tmp_path, baseline="stale")  # the current baseline is 3% below the scenario file's BAU
    pb = out["base"]["pathway_baseline"]
    assert pb["status"] == "stale" and pb["max_abs_difference_mt"] > 0.01
    expect_first = (1_010_000.0 / (1_010_000.0 * 0.97) - 1) * 100
    assert pb["aggregate"][str(FIRST)]["difference_pct"] == pytest.approx(expect_first, abs=1e-6) and pb["aggregate"][str(FIRST)]["scenario_bau_mt"] == pytest.approx(1_010_000.0)
    dev = [d for d in rep.deviations if "BAU is not the current baseline" in d]
    assert len(dev) == 1 and "ets_baseline_full_data.csv" in dev[0] and "older fit" in dev[0] and "rerun the Week 5 notebook (Backlog B2)" in dev[0] and f"{expect_first:+.1f}%" in dev[0]
    assert any(c.startswith("The BAU in these scenario pathways comes from an older ETS fit than the current baseline") for c in out["caveats"]) and out["scenarios"] is not None


def test_a_difference_within_the_rounding_tolerance_is_still_current(tmp_path):
    rep, out = go(tmp_path, baseline="tiny")  # +0.005 Mt on every value: below 0.01
    assert out["base"]["pathway_baseline"]["status"] == "current" and rep.deviations == []


@pytest.mark.parametrize("kind,reason_fragment", [
    ("none", "ets_baseline_full_data.csv not found: the ets_baseline stage has not run"),
    ("unavailable_json", "the current baseline is unavailable: OWID CO2 for 1990-2024 is missing for: Aland"),
    ("missing_country_year", "the current baseline has no value for 1 of the scenario file's BAU country-years (e.g. Aland 2001)"),
    ("empty", "is empty or lacks country/year/mean columns"),
    ("no_mean_column", "is empty or lacks country/year/mean columns"),
])
def test_a_missing_or_unusable_baseline_is_a_note_not_a_deviation_and_the_translation_still_publishes(tmp_path, kind, reason_fragment):
    rep, out = go(tmp_path, baseline=kind)
    pb = out["base"]["pathway_baseline"]
    assert pb["status"] == "unavailable" and reason_fragment in pb["reason"] and out["scenarios"] is not None
    assert not any("current baseline" in d for d in rep.deviations) and any("were not compared with the current baseline" in n for n in rep.notes)


def test_the_stale_and_step_alerts_are_independent(tmp_path):
    """A stale file with a healthy first-year step gets the baseline alert only; a breaching step on the current baseline file gets the step alert only."""
    rep, _ = go(tmp_path, baseline="stale")
    assert any("BAU is not the current baseline" in d for d in rep.deviations) and not any("aggregate first-year step" in d for d in rep.deviations)
    x = tmp_path / "b"
    x.mkdir()
    rep2, _ = go(x, scenario_edit=with_steps(BAU=5.0, Moderate=5.0, Aggressive=5.0))  # the baseline file is still the unedited default BAU
    assert any("aggregate first-year step" in d for d in rep2.deviations)


def test_the_new_blocks_never_make_the_output_invalid_json_and_the_unavailable_schema_is_unchanged(tmp_path):
    _, good = go(tmp_path)
    strict_json(tmp_path / "correlation_scenario_temperature.json")
    x = tmp_path / "u"
    x.mkdir()
    _, bad = go(x, scenario_edit=lambda p: p.assign(year=p.year + 3))
    assert set(bad) - {"unavailable_reason"} == set(good) and bad["base"] is None
    strict_json(x / "correlation_scenario_temperature.json")


# ---------------------------------------------------------------- spread block and generated reading note (decision 43)


def wide_apart(factor):
    """A scenario_edit that scales Aggressive's years after the first by `factor`, so the highest/lowest 2003 emissions ratio is controlled."""
    def edit(p):
        cols = {c: p.reset_index(drop=True)[c].to_numpy().copy() for c in p.columns}
        v = cols["co2_projected"].astype(float)
        m = (cols["scenario"] == "Aggressive") & (cols["year"] > FIRST)
        v[m] = v[m] * factor
        cols["co2_projected"] = v
        return pd.DataFrame(cols)
    return edit


def test_the_spread_block_has_per_year_max_min_ratio_and_level_gap(tmp_path):
    _, out = go(tmp_path)
    sp = out["spread"]
    assert [r["year"] for r in sp["per_year"]] == [FIRST, FIRST + 1, FIRST + 2]
    for i, r in enumerate(sp["per_year"]):
        em = [out["scenarios"][s][i]["global_fossil_mt"] for s in out["scenarios"]]
        lv = [out["scenarios"][s][i]["headline"]["level_c"] for s in out["scenarios"]]
        assert r["emissions_max_mt"] == pytest.approx(max(em), rel=1e-5) and r["emissions_min_mt"] == pytest.approx(min(em), rel=1e-5)
        assert r["emissions_ratio"] == pytest.approx(max(em) / min(em), rel=1e-5) and r["level_gap_c"] == pytest.approx(max(lv) - min(lv), abs=1e-5)
    assert sp["min_ratio_for_reading_note"] == 1.25


def test_the_reading_note_is_generated_from_the_output_numbers(tmp_path):
    _, out = go(tmp_path)  # BAU 700k+460k=1,160,000 vs Aggressive 520k+360k=880,000 covered in 2003 -> ratio 1.318
    f = out["spread"]["reading_note_facts"]
    s = out["scenarios"]
    hi, lo = s["BAU"][-1], s["Aggressive"][-1]
    assert (f["highest"], f["lowest"], f["year"]) == ("BAU", "Aggressive", FIRST + 2) and f["emissions_ratio"] == pytest.approx(hi["global_fossil_mt"] / lo["global_fossil_mt"], rel=1e-5)
    anchor = out["base"]["anchor"]["value_c"]
    assert f["lowest_adds_less_pct"] == pytest.approx((1 - lo["headline"]["delta_t_c"] / hi["headline"]["delta_t_c"]) * 100, rel=1e-4)
    assert f["already_observed_pct_range"] == [pytest.approx(anchor / max(x["headline"]["level_c"] for x in (hi, lo, s["Moderate"][-1])) * 100, rel=1e-4),
                                              pytest.approx(anchor / min(x["headline"]["level_c"] for x in (hi, lo, s["Moderate"][-1])) * 100, rel=1e-4)]
    rows = {r["year"]: r for r in out["spread"]["per_year"]}
    lv = lambda sc: s[sc][-1]["headline"]["level_c"]  # noqa: E731
    assert f["gap_end_c"] == pytest.approx(lv("BAU") - lv("Aggressive"), abs=1e-5) and f["gap_end_c"] == pytest.approx(rows[FIRST + 2]["level_gap_c"], abs=1e-5) and f["gap_end_c"] > 0
    assert f["gap_mid_c"] == pytest.approx(rows[f["gap_mid_year"]]["level_gap_c"], abs=1e-5) and f["gap_mid_year"] < FIRST + 2 and f["gap_mid_c"] < f["gap_end_c"]
    n = out["reading_note"]
    assert f"({hi and 'BAU'} {hi['global_fossil_mt']:,.0f} vs Aggressive {lo['global_fossil_mt']:,.0f} Mt a year, {f['emissions_ratio']:.1f}×)" in n
    assert f"differ by only {f['gap_end_c']:.2f} °C" in n and f"the {T0 + 1 - 1 - 1850 + 1} years of emissions already accumulated" in n
    assert f"{anchor:.2f} °C) is warming already observed by {T0}, before any scenario begins" in n
    assert f"the Aggressive pathway adds {f['lowest_adds_less_pct']:.0f}% less than BAU" in n and "The gap widens every year the pathways stay apart" in n
    assert out["spread"]["reading_note_omitted_reason"] is None


def test_the_note_is_omitted_when_the_emissions_ratio_is_below_the_threshold(tmp_path):
    _, out = go(tmp_path, scenario_edit=wide_apart(1.35))  # lifts Aggressive towards BAU: ratio < 1.25
    assert out["reading_note"] is None and "below the 1.25x" in out["spread"]["reading_note_omitted_reason"] and "reading_note_facts" not in out["spread"]
    assert out["spread"]["per_year"] and out["scenarios"] is not None  # the spread itself is still published


@pytest.mark.parametrize("factor,expect", [(1.0, True), (1.2, False)])
def test_the_threshold_is_applied_to_the_last_year_ratio(tmp_path, factor, expect):
    _, out = go(tmp_path, scenario_edit=wide_apart(factor))
    assert (out["reading_note"] is not None) is expect


def test_an_unavailable_headline_regression_leaves_the_whole_translation_and_so_the_spread_and_note_null(tmp_path):
    _, out = go(tmp_path, headline="none")
    assert out["scenarios"] is None and out["spread"] is None and out["reading_note"] is None


def test_the_spread_helper_omits_the_note_with_a_reason_if_a_headline_line_is_missing():
    row = lambda y, em: {"year": y, "global_fossil_mt": em, "headline": None}  # noqa: E731
    sp, note = T._spread({"A": [row(2001, 100.0), row(2002, 100.0)], "B": [row(2001, 50.0), row(2002, 50.0)]}, 2000, 1.3, 151)
    assert note is None and "headline regression is unavailable" in sp["reading_note_omitted_reason"] and all(r["level_gap_c"] is None for r in sp["per_year"])
    assert sp["per_year"][1]["emissions_ratio"] == 2.0


def test_the_unavailable_output_has_the_same_keys_with_null_spread_and_note(tmp_path):
    _, good = go(tmp_path)
    x = tmp_path / "u"
    x.mkdir()
    _, bad = go(x, scenario_edit=lambda p: p.assign(year=p.year + 3))
    assert set(bad) - {"unavailable_reason"} == set(good) and bad["spread"] is None and bad["reading_note"] is None
    strict_json(tmp_path / "correlation_scenario_temperature.json")
