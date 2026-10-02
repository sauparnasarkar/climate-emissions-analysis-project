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
        q.loc[(q.year == FIRST) & (q.scenario == "Aggressive") & (q.country == "Aland"), "co2_projected"] = 660_000.0
        q.loc[(q.year == FIRST) & (q.scenario == "Aggressive") & (q.country == "Bland"), "co2_projected"] = 440_000.0
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
