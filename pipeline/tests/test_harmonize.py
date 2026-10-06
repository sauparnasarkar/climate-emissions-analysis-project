import json
import os

import numpy as np
import pandas as pd
import pytest

from pipeline import common, harmonize
from pipeline.common import RunReport

YEARS = list(range(1750, 2025))  # 1750-2024


def write_inputs(d, drop=(), cum_gap=False, extra_ppm_year=True, prov_coverage_override=None):
    d = str(d)
    y = np.array(YEARS)
    ppm_years = YEARS + ([2025] if extra_ppm_year else [])
    pd.DataFrame({"year": ppm_years, "co2_ppm": [280.0 + 0.5 * (v - 1750) for v in ppm_years], "uncertainty_ppm": [np.nan if v < 1959 else 0.12 for v in ppm_years],
                  "source": "x"}).to_csv(os.path.join(d, "co2_concentration_annual.csv"), index=False)
    pd.DataFrame({"year": range(1850, 2025), "anomaly_1951_1980_c": np.linspace(-0.4, 1.3, 175), "anomaly_1850_1900_c": np.linspace(-0.13, 1.6, 175),
                  "uncertainty_95_c": 0.05}).to_csv(os.path.join(d, "temperature_anomaly_annual.csv"), index=False)
    pd.DataFrame({"year": y, "co2_mt": 10.0 * (y - 1749), "cumulative_co2_mt": np.cumsum(10.0 * (y - 1749)), "national_sum_mt": 9.0 * (y - 1749),
                  "countries_reporting": 200, "international_transport_mt": np.where(y >= 1950, 1.0 * (y - 1949), np.nan),
                  "land_use_change_co2_mt": np.where(y >= 1850, 3.0 * (y - 1849), np.nan),  # land-use CO2 exists from 1850 only
                  "total_co2_incl_luc_mt": np.where(y >= 1850, 10.0 * (y - 1749) + 3.0 * (y - 1849), np.nan)}).to_csv(os.path.join(d, "owid_world_co2_annual.csv"), index=False)
    tot = 100.0 * (y - 1749)
    pd.DataFrame({"year": y, "co2_mt": tot * 0.7, "ch4_mtco2e": tot * 0.2, "n2o_mtco2e": tot * 0.08, "fgas_mtco2e": np.where(y >= 1990, tot * 0.02, 0.0),
                  "total_ghg_mtco2e": tot}).to_csv(os.path.join(d, "primap_global_composition_annual.csv"), index=False)
    # a DENSE country frame well above the 32k-row threshold of the numpy-2.2.6/py3.14 reshape bug (300 years x 210 areas)
    cy = list(range(1725, 2025)) if False else list(range(1750, 2025))
    areas = [f"A{i:03d}" for i in range(210)]
    rows = []
    for i, a in enumerate(areas):
        for yr in cy:
            v = float((i + 1) * (yr - 1749))
            rows.append((a, yr, v * 0.7, v * 0.2, v * 0.08, np.nan if yr < 1990 else v * 0.02, v if not (cum_gap and a == "A005" and yr == 1900) else np.nan))
    pd.DataFrame(rows, columns=["iso3", "year", "co2_mt", "ch4_mtco2e", "n2o_mtco2e", "fgas_mtco2e", "total_ghg_mtco2e"]).to_csv(os.path.join(d, "primap_country_annual.csv"), index=False)
    prov = {
        "co2_concentration_annual": {"source": "NOAA+LawDome", "coverage": [1750, 2025 if extra_ppm_year else 2024], "license": "cite", "retrieved_at": "t", "source_release": {"x": 1}},
        "temperature_anomaly_annual": {"source": "Berkeley", "coverage": [1850, 2024], "license": "CC BY-NC 4.0", "retrieved_at": "t", "source_release": {"y": 2}},
        "owid_world_co2_annual": {"source": "OWID", "coverage": [1750, 2024], "license": "CC BY 4.0", "retrieved_at": "t", "source_release": {}},
        "primap_global_composition_annual": {"source": "PRIMAP", "coverage": prov_coverage_override or [1750, 2024], "license": "CC BY-NC-SA 4.0", "retrieved_at": "t", "source_release": {"version": "v9"},
                                             "raw_sha256": {"csv": "ab" * 32}, "checksum_verified": {"csv": "md5:cd"}, "source_urls": ["https://z.test/f.csv"]},
        "primap_country_annual": {"source": "PRIMAP", "coverage": [1750, 2024], "license": "CC BY-NC-SA 4.0", "retrieved_at": "t", "source_release": {"version": "v9"}},
    }
    for k in drop:
        prov.pop(k, None)
    json.dump(prov, open(os.path.join(d, "provenance.json"), "w"))
    return str(os.path.join(d, "provenance.json"))


def run(tmp_path, **kw):
    prov = write_inputs(tmp_path, **kw)
    return harmonize.run(str(tmp_path), prov)


def read(tmp_path):
    return (pd.read_csv(tmp_path / "harmonized_global_annual.csv"), pd.read_csv(tmp_path / "harmonized_country_annual.csv"),
            json.loads((tmp_path / "indicator_catalog.json").read_text()))


def test_builds_three_outputs_with_catalog_and_counts(tmp_path):
    rep = run(tmp_path)
    g, c, cat = read(tmp_path)
    ids = {e["id"]: e for e in cat["indicators"]}
    assert rep.deviations == [] and rep.records["indicator_catalog"] == len(cat["indicators"])
    assert cat["schema_version"] == 1 and set(cat["baselines"]) == {"1990", "1970", "preindustrial"} and cat["baselines"]["preindustrial"]["year"] == 1850
    assert ids["co2_concentration_ppm"]["scope"] == "global" and ids["primap_country_ghg_total_mtco2e"]["scope"] == "country"
    assert set(g.indicator_id) <= {i for i, e in ids.items() if e["scope"] == "global"} and set(c.indicator_id) <= {i for i, e in ids.items() if e["scope"] == "country"}
    assert not g.value.isna().any() and not c.value.isna().any()  # nulls are absent rows, never NaN values
    # each base indicator links its provenance, with the source release, licence and coverage
    p = ids["temperature_anomaly_1850_1900_c"]["provenance"]
    assert p["series"] == "temperature_anomaly_annual" and p["license"] == "CC BY-NC 4.0" and p["coverage"] == [1850, 2024]


def test_each_indicator_keeps_its_own_coverage(tmp_path):
    run(tmp_path)
    ids = {e["id"]: e for e in read(tmp_path)[2]["indicators"]}
    assert ids["co2_concentration_ppm"]["coverage"] == [1750, 2025]  # concentration runs a year longer than the rest
    assert ids["owid_co2_world_mt"]["coverage"] == [1750, 2024] and ids["temperature_anomaly_1850_1900_c"]["coverage"] == [1850, 2024]
    assert ids["co2_concentration_uncertainty_ppm"]["coverage"][0] == 1959  # null before NOAA; no fabricated values


def test_derived_values_match_hand_calculation(tmp_path):
    run(tmp_path)
    g, _, _ = read(tmp_path)

    def val(i, y):
        return g[(g.indicator_id == i) & (g.year == y)].value.iloc[0]

    ow = lambda y: 10.0 * (y - 1749)
    assert val("owid_co2_world_mt__index_1990", 2000) == pytest.approx(100 * ow(2000) / ow(1990))
    assert val("owid_co2_world_mt__index_1990", 1990) == pytest.approx(100.0)
    assert val("owid_co2_world_mt__yoy_pct", 2000) == pytest.approx(100 * (ow(2000) / ow(1999) - 1))
    assert val("owid_co2_world_mt__mean5y", 2000) == pytest.approx(np.mean([ow(y) for y in range(1996, 2001)]))
    assert val("primap_ghg_total_cumulative_mtco2e", 2000) == pytest.approx(sum(100.0 * (y - 1749) for y in range(1750, 2001)))
    assert val("co2_concentration_ppm__index_preindustrial", 2025) == pytest.approx(100 * (280 + 0.5 * 275) / (280 + 0.5 * 100))  # 1850 = year 100


def test_anomalies_are_never_indexed_but_levels_are(tmp_path):
    run(tmp_path)
    ids = {e["id"] for e in read(tmp_path)[2]["indicators"]}
    assert not any(i.startswith("temperature_") and "__" in i and "index" in i for i in ids)
    assert not any(i.startswith("temperature_") and i.endswith("__yoy_pct") for i in ids)  # a % change of an anomaly is undefined
    assert {"temperature_anomaly_1850_1900_c", "temperature_anomaly_1951_1980_c", "temperature_uncertainty_95_c"} <= ids  # both native references kept
    assert not any(i.startswith("owid_co2_world_cumulative_mt__") for i in ids)  # a running total is never indexed or averaged
    assert {"owid_co2_world_mt__index_1990", "owid_co2_world_mt__index_1970", "owid_co2_world_mt__index_preindustrial"} <= ids


def test_undefined_baselines_are_excluded_with_a_reason_and_published_nowhere(tmp_path):
    rep = run(tmp_path)
    cat = {e["id"]: e for e in read(tmp_path)[2]["indicators"]}
    t = cat["owid_co2_international_transport_mt"]  # starts in 1950 in the fixture: no 1850 value
    assert t["excluded_baselines"] == {"preindustrial": "no value in the baseline year 1850"} and t["allowed_baselines"] == ["1990", "1970"]
    assert "owid_co2_international_transport_mt__index_preindustrial" not in cat
    ix = cat["owid_co2_world_mt__index_1990"]
    assert ix["baseline"]["year"] == 1990 and ix["baseline"]["formula"] == "100 × value[y] / value[1990]" and ix["is_default_baseline"] is True
    assert ix["unit"] == "index (1990 = 100)" and cat["primap_ghg_total_mtco2e"]["default_baseline"] == "1970" and cat["co2_concentration_ppm"]["default_baseline"] == "preindustrial"
    assert any("baselines not defined for" in n for n in rep.notes)


def test_country_values_are_exact_on_a_dense_frame_above_the_32k_row_reshape_bug(tmp_path):
    """63,000-row dense country frame (300x210 would be the same class): a dense pandas pivot corrupts the year labels on
    numpy 2.2.6/Python 3.14. This must be exact on every stack, because harmonize avoids reshapes."""
    run(tmp_path)
    _, c, _ = read(tmp_path)
    tot = c[c.indicator_id == "primap_country_ghg_total_mtco2e"]
    assert len(tot) == 210 * 275 and tot.year.min() == 1750 and tot.year.max() == 2024 and tot.groupby("iso3").year.nunique().eq(275).all()
    for i in (0, 77, 209):
        a = f"A{i:03d}"
        row = tot[(tot.iso3 == a) & (tot.year == 1999)].value.iloc[0]
        assert row == pytest.approx((i + 1) * (1999 - 1749))
        cum = c[(c.indicator_id == "primap_country_ghg_total_cumulative_mtco2e") & (c.iso3 == a) & (c.year == 2024)].value.iloc[0]
        assert cum == pytest.approx(sum((i + 1) * (y - 1749) for y in range(1750, 2025)))
    fg = c[c.indicator_id == "primap_country_fgas_mtco2e"]
    assert fg.year.min() == 1990  # null F-gas years are absent rows


def test_country_cumulative_stops_at_an_interior_gap_not_silently_continuing(tmp_path):
    run(tmp_path, cum_gap=True)  # A005 has no total in 1900
    _, c, _ = read(tmp_path)
    cum = c[(c.indicator_id == "primap_country_ghg_total_cumulative_mtco2e") & (c.iso3 == "A005")]
    assert cum.year.max() == 1899  # nothing after the gap: a total that skipped 1900 would be silently too small
    other = c[(c.indicator_id == "primap_country_ghg_total_cumulative_mtco2e") & (c.iso3 == "A006")]
    assert other.year.max() == 2024


def test_missing_input_skips_only_what_depends_on_it_with_a_deviation(tmp_path):
    prov = write_inputs(tmp_path)
    os.remove(tmp_path / "owid_world_co2_annual.csv")
    rep = harmonize.run(str(tmp_path), prov)
    ids = {e["id"] for e in read(tmp_path)[2]["indicators"]}
    assert any("input owid_world_co2_annual.csv not found" in d for d in rep.deviations)
    assert not any(i.startswith("owid_") for i in ids) and "primap_ghg_total_mtco2e" in ids and "co2_concentration_ppm" in ids


def test_no_inputs_at_all_raises(tmp_path):
    (tmp_path / "provenance.json").write_text("{}")
    with pytest.raises(ValueError, match="no input series found"):
        harmonize.run(str(tmp_path), str(tmp_path / "provenance.json"))


def test_missing_provenance_entry_is_one_deviation_per_series(tmp_path):
    rep = run(tmp_path, drop=("primap_global_composition_annual",))
    msgs = [d for d in rep.deviations if "primap_global_composition_annual" in d and "no entry in provenance.json" in d]
    assert len(msgs) == 1  # not one per indicator built from it
    ids = {e["id"]: e for e in read(tmp_path)[2]["indicators"]}
    assert ids["primap_ghg_total_mtco2e"]["provenance"] is None


def test_file_span_disagreeing_with_its_provenance_is_a_deviation(tmp_path):
    rep = run(tmp_path, prov_coverage_override=[1750, 2023])
    assert any("spans 1750-2024 but provenance says 1750-2023" in d for d in rep.deviations)


def test_duplicate_years_raise(tmp_path):
    prov = write_inputs(tmp_path)
    p = tmp_path / "owid_world_co2_annual.csv"
    df = pd.read_csv(p)
    pd.concat([df, df.iloc[[5]]]).to_csv(p, index=False)
    with pytest.raises(ValueError, match="duplicate years"):
        harmonize.run(str(tmp_path), prov)


def test_run_is_registered_as_a_derived_stage_after_the_sources():
    from pipeline import run as run_module

    assert "harmonize" in run_module.DERIVED_SOURCES and "harmonize" not in run_module.ACTIVE_SOURCES
    assert list(run_module.SOURCES)[:len(run_module.ACTIVE_SOURCES)] == list(run_module.ACTIVE_SOURCES)


# ---------------------------------------------------------------- the reshape canary


def test_canary_detects_a_corrupting_pivot_and_stays_quiet_on_a_sound_one(monkeypatch):
    real_pivot = pd.DataFrame.pivot

    def broken(self, *a, **k):
        out = real_pivot(self, *a, **k)
        out.index = [out.index[min(i, 2)] for i in range(len(out.index))]  # the observed symptom: repeated, wrong labels
        return out

    monkeypatch.setattr(pd.DataFrame, "pivot", broken)
    msg = common.check_reshape_environment()
    assert msg and "corrupted labels" in msg and "numpy" in msg and ">= 2.3" in msg
    monkeypatch.setattr(pd.DataFrame, "pivot", real_pivot)
    sound = common.check_reshape_environment()
    assert sound is None or "corrupted labels" in sound  # on this stack the real result depends on the installed numpy


def test_main_reports_the_environment_problem_as_a_deviation_not_a_failure(tmp_path, monkeypatch):
    from pipeline import run as run_module

    monkeypatch.setattr(run_module, "CLIMATE_DIR", str(tmp_path))
    monkeypatch.setattr(run_module, "check_reshape_environment", lambda: "reshape bug here")
    monkeypatch.setitem(run_module.SOURCES, "noaa_gml", lambda: RunReport("noaa_gml"))
    assert run_module.main(["--source", "noaa_gml"]) == 0
    s = json.loads((tmp_path / "last_run.json").read_text())
    assert s["sources"]["environment"]["deviations"] == ["reshape bug here"]
    assert (tmp_path / "last_run.priority").read_text().strip() == "high" and "DEVIATION environment: reshape bug here" in (tmp_path / "last_run.message").read_text()


# ---------------------------------------------------------------- Copilot review of #207


def test_anomalies_carry_the_trailing_mean_and_nothing_else_derived(tmp_path):
    """Decision 28: anomalies keep both native references AND the trailing 5-year mean, but are never indexed."""
    run(tmp_path)
    g, _, cat = read(tmp_path)
    ids = {e["id"]: e for e in cat["indicators"]}
    anomalies = [i for i, e in ids.items() if e["kind"] == "anomaly"]
    assert sorted(anomalies) == ["temperature_anomaly_1850_1900_c", "temperature_anomaly_1951_1980_c"]
    for a in anomalies:
        derived = sorted(i for i, e in ids.items() if e.get("derived_from") == a)
        assert derived == [f"{a}__mean5y"]  # the trailing mean only: no index, no yoy
        assert "allowed_baselines" not in ids[a]  # baselines are a level-indicator concept
    anom = np.linspace(-0.13, 1.6, 175)  # the fixture's 1850-1900 anomaly, 1850..2024
    m = g[(g.indicator_id == "temperature_anomaly_1850_1900_c__mean5y")].set_index("year").value
    assert m.index.min() == 1854 and m[1854] == pytest.approx(anom[0:5].mean()) and m[2024] == pytest.approx(anom[-5:].mean())


def test_cumulative_indicators_advertise_no_baseline(tmp_path):
    run(tmp_path)
    cat = {e["id"]: e for e in read(tmp_path)[2]["indicators"]}
    for i in ("owid_co2_world_cumulative_mt", "primap_ghg_total_cumulative_mtco2e", "primap_country_ghg_total_cumulative_mtco2e"):
        assert cat[i]["kind"] == "cumulative" and "default_baseline" not in cat[i] and "allowed_baselines" not in cat[i]
    assert cat["primap_ghg_total_mtco2e"]["default_baseline"] == "1970"  # level indicators still do


def test_provenance_link_carries_the_source_checksums(tmp_path):
    run(tmp_path)
    cat = {e["id"]: e for e in read(tmp_path)[2]["indicators"]}
    for i in ("primap_ghg_total_mtco2e", "primap_ghg_total_mtco2e__index_1970"):  # base and derived
        p = cat[i]["provenance"]
        assert p["raw_sha256"] == {"csv": "ab" * 32} and p["checksum_verified"] == {"csv": "md5:cd"} and p["source_urls"] == ["https://z.test/f.csv"]
        assert p["license"] == "CC BY-NC-SA 4.0" and p["source_release"] == {"version": "v9"}


def test_derived_entries_inherit_description_and_caveats_from_their_base(tmp_path):
    run(tmp_path)
    cat = {e["id"]: e for e in read(tmp_path)[2]["indicators"]}
    base = cat["co2_concentration_ppm"]
    assert any("Spliced at 1959" in c for c in base["caveats"])
    for suffix in ("__yoy_pct", "__mean5y", "__index_1990", "__index_preindustrial"):
        d = cat["co2_concentration_ppm" + suffix]
        assert d["caveats"] == base["caveats"] and d["description"] == base["description"], suffix  # the splice limitation survives into every derived metric
    t = cat["temperature_anomaly_1850_1900_c__mean5y"]
    assert t["caveats"] == cat["temperature_anomaly_1850_1900_c"]["caveats"] and t["caveats"]


def test_country_cumulative_with_a_missing_source_column_is_skipped_with_a_deviation_not_a_crash(tmp_path):
    prov = write_inputs(tmp_path)
    p = tmp_path / "primap_country_annual.csv"
    pd.read_csv(p).drop(columns=["total_ghg_mtco2e"]).to_csv(p, index=False)
    rep = harmonize.run(str(tmp_path), prov)  # used to raise KeyError and fail the whole stage
    ids = {e["id"] for e in read(tmp_path)[2]["indicators"]}
    assert any("primap_country_ghg_total_mtco2e: column 'total_ghg_mtco2e' missing" in d for d in rep.deviations)
    assert any("primap_country_ghg_total_cumulative_mtco2e: its source column 'total_ghg_mtco2e'" in d for d in rep.deviations)
    assert "primap_country_ghg_total_cumulative_mtco2e" not in ids and "primap_country_co2_mt" in ids and "owid_co2_world_mt" in ids  # the rest of the stage still ran


# ---------------------------------------------------------------- total anthropogenic CO2 (decision 40)


def test_total_co2_indicators_values_coverage_and_headline_cumulative(tmp_path):
    run(tmp_path)
    g, _, cat = read(tmp_path)
    ids = {e["id"]: e for e in cat["indicators"]}
    for i in ("owid_luc_co2_world_mt", "owid_total_co2_world_mt", "owid_total_co2_world_cumulative_mt"):
        assert i in ids and ids[i]["scope"] == "global" and ids[i]["unit"] == "Mt CO2" and ids[i]["coverage"] == [1850, 2024]  # land-use exists from 1850, not 1750
    assert ids["owid_total_co2_world_cumulative_mt"]["kind"] == "cumulative" and ids["owid_total_co2_world_mt"]["kind"] == "level"
    s = lambda i: g[g.indicator_id == i].set_index("year")["value"]
    flow = lambda yr: 10.0 * (yr - 1749) + 3.0 * (yr - 1849)
    assert s("owid_total_co2_world_mt")[2000] == pytest.approx(flow(2000), abs=0.01)
    assert s("owid_luc_co2_world_mt")[2000] == pytest.approx(3.0 * 151, abs=0.01)
    # the headline X-variable: cumulative from 1850 INCLUSIVE, starting at the 1850 flow
    cum = s("owid_total_co2_world_cumulative_mt")
    assert cum[1850] == pytest.approx(flow(1850), abs=0.01) and cum[1900] == pytest.approx(sum(flow(y) for y in range(1850, 1901)), rel=1e-9)
    # the fossil-only cumulative keeps its 1750 start and is a different, labelled series
    assert ids["owid_co2_world_cumulative_mt"]["coverage"][0] == 1750 and "fossil" in ids["owid_co2_world_cumulative_mt"]["description"].lower()


def test_total_co2_indicators_carry_the_uncertainty_and_licence_caveats(tmp_path):
    run(tmp_path)
    _, _, cat = read(tmp_path)
    ids = {e["id"]: e for e in cat["indicators"]}
    for i in ("owid_luc_co2_world_mt", "owid_total_co2_world_mt", "owid_total_co2_world_cumulative_mt"):
        c = " ".join(ids[i]["caveats"])
        assert "+/-0.7 GtC/yr" in c and "No formal license (e.g., CC BY) is stated" in c and "No non-commercial, no-derivatives, or share-alike restrictions were found" in c
    # derived entries inherit them (decision 28)
    assert any("No formal license" in " ".join(e["caveats"]) for e in cat["indicators"] if e["id"].startswith("owid_total_co2_world_mt__"))


def test_missing_total_column_skips_the_total_indicators_with_deviations_not_a_crash(tmp_path):
    prov = write_inputs(tmp_path)
    p = tmp_path / "owid_world_co2_annual.csv"
    df = pd.read_csv(p).drop(columns=["total_co2_incl_luc_mt", "land_use_change_co2_mt"])
    df.to_csv(p, index=False)
    rep = harmonize.run(str(tmp_path), prov)
    assert any("owid_total_co2_world_mt" in d and "missing" in d for d in rep.deviations)
    assert any("owid_total_co2_world_cumulative_mt" in d and "not built" in d for d in rep.deviations)
    _, _, cat = read(tmp_path)
    assert "owid_co2_world_cumulative_mt" in {e["id"] for e in cat["indicators"]}  # the fossil-only series is unaffected


def test_land_use_cumulative_is_built_from_1850_and_the_total_is_the_sum_of_the_two_cumulatives(tmp_path):
    run(tmp_path)
    g, _, cat = read(tmp_path)
    ids = {e["id"]: e for e in cat["indicators"]}
    assert ids["owid_luc_co2_world_cumulative_mt"]["kind"] == "cumulative" and ids["owid_luc_co2_world_cumulative_mt"]["coverage"] == [1850, 2024]
    s = lambda i: g[g.indicator_id == i].set_index("year")["value"]
    luc_cum, tot_cum = s("owid_luc_co2_world_cumulative_mt"), s("owid_total_co2_world_cumulative_mt")
    assert luc_cum[1850] == pytest.approx(3.0) and luc_cum[1900] == pytest.approx(sum(3.0 * (y - 1849) for y in range(1850, 1901)), rel=1e-9)
    fossil_from_1850 = {y: sum(10.0 * (v - 1749) for v in range(1850, y + 1)) for y in (1900, 2024)}
    for y in (1900, 2024):
        assert tot_cum[y] == pytest.approx(fossil_from_1850[y] + luc_cum[y], rel=1e-9)
    assert "+/-0.7 GtC/yr" in " ".join(ids["owid_luc_co2_world_cumulative_mt"]["caveats"])


def test_attribution_fields_travel_in_every_land_use_indicators_provenance_link_base_and_derived(tmp_path):
    prov_path = write_inputs(tmp_path)
    prov = json.loads(open(prov_path).read())
    prov["owid_world_co2_annual"].update({"citations": ["Our World in Data ...", "Required by the GCP: Global Carbon Project. (<year>) ..."],
                                          "attribution_required": True, "required_citation_format": "Global Carbon Project. (<year>) ...", "land_use_license_note": "No formal license (e.g., CC BY) is stated"})
    open(prov_path, "w").write(json.dumps(prov))
    harmonize.run(str(tmp_path), prov_path)
    _, _, cat = read(tmp_path)
    land_use = [e for e in cat["indicators"] if "luc" in e["id"] or "total_co2" in e["id"]]
    assert len(land_use) >= 8  # base + derived
    base = [e for e in land_use if e["kind"] != "derived"]
    assert {e["id"] for e in base} == {"owid_luc_co2_world_mt", "owid_luc_co2_world_cumulative_mt", "owid_total_co2_world_mt", "owid_total_co2_world_cumulative_mt"}
    for e in base:
        pl = e["provenance"]
        assert pl["attribution_required"] is True and pl["required_citation_format"].startswith("Global Carbon Project") and len(pl["citations"]) == 2
        assert pl["land_use_license_note"].startswith("No formal license")
    # derived entries point at their base, whose provenance carries the attribution; they inherit the licence caveat text itself
    for e in (x for x in land_use if x["kind"] == "derived"):
        assert e["derived_from"] in {b["id"] for b in base} and "No formal license" in " ".join(e["caveats"])
    # a source that records no attribution fields gets none added (no noise)
    assert "citations" not in {x["id"]: x for x in cat["indicators"]}["temperature_anomaly_1850_1900_c"]["provenance"]


def test_preliminary_note_follows_the_provenance_flag_on_base_and_derived_temperature_entries(tmp_path):
    from pipeline.berkeley_earth import PRELIMINARY_NOTE

    def temp_caveats(preliminary):
        d = tmp_path / ("p" if preliminary else "f"); d.mkdir()
        prov_path = write_inputs(d)
        prov = json.load(open(prov_path)); prov["temperature_anomaly_annual"]["preliminary"] = preliminary
        json.dump(prov, open(prov_path, "w"))
        harmonize.run(str(d), prov_path)
        cat = json.load(open(d / "indicator_catalog.json"))["indicators"]
        return {e["id"]: e["caveats"] for e in cat if e["id"].startswith("temperature_anomaly")}

    on, off = temp_caveats(True), temp_caveats(False)
    assert on and all(PRELIMINARY_NOTE in c for c in on.values())  # base 1850/1951 and derived (mean5y) alike
    assert not any(PRELIMINARY_NOTE in c for c in off.values())  # a finalized file drops it with no code change
