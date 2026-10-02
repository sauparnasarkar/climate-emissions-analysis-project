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
PATH = {"BAU": {"Aland": [660_000, 700_000, 740_000], "Bland": [440_000, 460_000, 480_000]},
        "Aggressive": {"Aland": [580_000, 520_000, 460_000], "Bland": [380_000, 340_000, 300_000]}}


def fit(slope, ci):
    return {"fit": {"slope": slope, "ci95_hac": ci}, "range": [1850, T0], "label": "x", "x_indicator": "x"}


def write(tmp_path, headline="ok", scenario_edit=None, owid_edit=None, world_edit=None, no_scenario=False, vintage="2025-01-10T04:48:46+00:00", notices=None):
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
    (tmp_path / "provenance.json").write_text(json.dumps({"temperature_anomaly_annual": {"source_release": {"http_last_modified": vintage}}}))
    npath = tmp_path / "notices.json"
    npath.write_text(json.dumps(notices or {}))


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
    assert sorted(out["scenarios"]) == ["Aggressive", "BAU"] and out["scenario_source"]["scenarios"] == ["Aggressive", "BAU"]
    last = {sc: rows[-1]["headline"]["level_c"] for sc, rows in out["scenarios"].items()}
    assert last["BAU"] > last["Aggressive"]


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
    ("negative", lambda p: p.assign(co2_projected=np.where(p.index == 0, -1.0, p.co2_projected)), "missing or negative projected emissions"),
    ("missing value", lambda p: p.assign(co2_projected=np.where(p.index == 0, np.nan, p.co2_projected)), "missing or negative projected emissions"),
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
    _, out = go(tmp_path)  # synthetic: BAU starts at 1,100,000 (+10%), Aggressive at 960,000 (-4%) against 1,000,000 observed
    b = out["base"]
    assert b["first_scenario_year_covered_mt"] == {"Aggressive": pytest.approx(960_000.0), "BAU": pytest.approx(1_100_000.0)}
    assert b["first_scenario_year_vs_last_observed_pct"] == {"Aggressive": pytest.approx(-4.0), "BAU": pytest.approx(10.0)}
    text = [c for c in out["caveats"] if c.startswith("The scenario pathways start ")]
    assert len(text) == 1 and "Aggressive -4.0%, BAU +10.0%" in text[0] and "(1,000,000 Mt in 2000; Aggressive 960,000 Mt, BAU 1,100,000 Mt in 2001)" in text[0]
    assert "each scenario carries that step" in text[0]


def test_when_every_scenario_starts_at_the_same_level_the_caveat_says_so_once(tmp_path):
    def same_start(p):
        q = p.copy()
        q.loc[(q.year == FIRST) & (q.country == "Aland"), "co2_projected"] = 660_000.0
        q.loc[(q.year == FIRST) & (q.country == "Bland"), "co2_projected"] = 440_000.0
        return q

    _, out = go(tmp_path, scenario_edit=lambda p: same_start(p.reset_index(drop=True)))
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
    assert s["sha256"] == hashlib.sha256(raw).hexdigest() and s["file"] == "scenario_projections.csv" and s["rows"] == 12 and s["years"] == [FIRST, FIRST + 2]
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
