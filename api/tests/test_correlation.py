"""`/api/correlation/*` Phase 1.4a: /meta, /concentration, /temperature (ENHANCEMENTS.md Release 21, decisions 44-55).

Contract fixture: the climate directory is produced by running the REAL `pipeline` harmonize stage on small stubbed inputs (the same writer the pipeline's own tests use), so a
change to the pipeline's output schema breaks these tests rather than production. Only the few files the stage does not produce (monthly CSV, last_run.json, the correlation
outputs) are written by hand. Tests that need a variant copy the shared directory into tmp_path; nothing touches the real data/climate.
"""

import json
import math
import shutil

import pytest
from fastapi.testclient import TestClient

from api import climate_loaders as cl
from api.main import app
from pipeline.tests.test_country_share import go as share_go
from pipeline.tests.test_harmonize import run as run_harmonize
from pipeline.tests.test_scenario_temperature import go as scen_go


def _windows(starts, end, slope, n_of):
    return [{"start": s, "end": end, "n_years": n_of(s), "slope": slope + i * 0.1, "ci95_hac": [slope + i * 0.1 - 0.05, slope + i * 0.1 + 0.05], "r_squared": 0.9, "maxlags": 5} for i, s in enumerate(starts)]


def _block(label, slope, starts, extra=None):
    b = {"label": label, "unit": "°C per 1,000 GtCO2", "range": [starts[0], 2024], "n_years": 2025 - starts[0], "fit": {"slope": slope, "intercept": -0.1, "r_squared": 0.9},
         "windows": _windows(starts, 2024, slope, lambda s: 2025 - s), "stability": {"summary": "stable", "seed": 20261002}, "hac_sensitivity": [{"maxlags": 4}],
         "vs_ar6": {"within_very_likely_range": True}}
    b.update(extra or {})
    return b


def headline_doc():
    return {"schema_version": 1, "generated_at": "2026-10-02T01:00:00+00:00", "note": "Paired series are shown for interpretive context.", "ar6_reference": {"best_estimate": 0.45},
            "definition": "total anthropogenic CO2", "method": "OLS", "methodology": "a simplified analog to the TCRE", "caveats": ["headline caveat"],
            "temperature_source_vintage": {"file_last_modified": "2025-01-10", "reconciled": False, "caveat": "stale"},
            "headline": _block("Total anthropogenic CO2", 0.52, [1850, 1900, 1950, 1970], {"fit_quality_note": {"text": "Including land-use emissions aligns this estimate."},
                                                                                         "land_use_sensitivity": [{"land_use_scale": 0.7}], "land_use_weight_scan": {"weights": []}}),
            "secondary_fossil_only": _block("Fossil + cement CO2 only", 0.8, [1850, 1900, 1950, 1970])}


def all_gas_doc():
    return {"schema_version": 1, "generated_at": "2026-10-02T02:00:00+00:00", "note": "Paired series are shown for interpretive context.", "definition": "cumulative PRIMAP-hist total GHG from 1970",
            "method": "OLS", "caveats": ["all-gas caveat"], "temperature_source_vintage": {"file_last_modified": "2025-01-10"}, "recent_all_gas": _block("Recent all-gas relationship", 0.58, [1970])}


def write_composition(d, drop_rows_for=None):
    rows, years = [], []
    for y in (2022, 2023, 2024):
        vals = {"co2": 70.0, "ch4": 20.0, "n2o": 8.0, "fgas": 2.0 if y != 2022 else None}
        inc = [g for g, v in vals.items() if v is not None]
        tot = sum(v for v in vals.values() if v is not None)
        years.append({"year": y, "gases_included": inc, "components_total_mtco2e": tot * 100, "national_total_mtco2e": tot * 100 + 1, "residual_pct": -0.01})
        if y == drop_rows_for:
            continue
        for g, name in (("co2", "CO₂"), ("ch4", "CH₄"), ("n2o", "N₂O"), ("fgas", "Fluorinated gases")):
            v = vals[g]
            rows.append(f"{y},{g},{name},{'' if v is None else v * 100},{'' if v is None else v / tot * 100}")
    (d / "correlation_composition_annual.csv").write_text("year,gas,gas_name,mtco2e,share_pct\n" + "\n".join(rows) + "\n")
    (d / "correlation_composition.json").write_text(json.dumps({
        "schema_version": 1, "generated_at": "2026-10-02T03:00:00+00:00", "name": "Global greenhouse-gas composition", "basis": "PRIMAP-hist, AR5 GWP-100", "units": "MtCO2e (CO2 in Mt CO2)",
        "gases": [{"id": g, "name": n, "source_column": c} for g, n, c in (("co2", "CO₂", "co2_mt"), ("ch4", "CH₄", "ch4"), ("n2o", "N₂O", "n2o"), ("fgas", "Fluorinated gases", "fgas"))],
        "caveats": ["composition caveat"], "years": years, "coverage": [2022, 2024], "n_years": 3, "reconciliation": {"max_abs_residual_pct": 0.01, "tolerance_pct": 1.0},
        "excluded_incomplete_years": [2025]}))


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    d = tmp_path_factory.mktemp("climate_built")
    run_harmonize(d)
    (d / "co2_concentration_monthly_mlo.csv").write_text("year,month,co2_ppm,co2_deseasonalized_ppm\n1958,3,315.7,314.4\n1958,4,317.4,315.1\n2024,1,422.8,422.5\n2024,2,424.0,\n")
    prov = json.loads((d / "provenance.json").read_text())
    prov["co2_concentration_monthly_mlo"] = {"source": "NOAA GML Mauna Loa monthly mean", "coverage": [1958, 2024], "license": "NOAA GML: public domain, citation requested.", "retrieved_at": "t",
                                             "source_release": {"z": 3}, "units": "ppm"}
    (d / "provenance.json").write_text(json.dumps(prov))
    (d / "last_run.json").write_text(json.dumps({"started_at": "2026-10-02T00:00:00+00:00", "finished_at": "2026-10-02T00:01:00+00:00",
                                                 "sources": {"harmonize": {"records": {"harmonized_global": 10}, "deviations": ["d1", "d2"], "notes": []}}, "failures": {"x": "boom"}}))
    (d / "correlation_headline.json").write_text(json.dumps(headline_doc()))
    (d / "correlation_all_gas.json").write_text(json.dumps(all_gas_doc()))
    write_composition(d)
    # contract fixtures: the REAL country-share and scenario-temperature stages run on the pipeline tests' stubbed inputs
    share_dir, scen_dir = tmp_path_factory.mktemp("share"), tmp_path_factory.mktemp("scenario")
    share_go(share_dir)
    scen_go(scen_dir)
    for name in ("correlation_country_share.json", "correlation_country_share.csv"):
        shutil.copy(share_dir / name, d / name)
    shutil.copy(scen_dir / "correlation_scenario_temperature.json", d / "correlation_scenario_temperature.json")
    return d


@pytest.fixture
def climate(built, tmp_path, monkeypatch):
    d = tmp_path / "climate"
    shutil.copytree(built, d)
    monkeypatch.setattr(cl, "CLIMATE_DIR", str(d))
    cl.clear_caches()
    yield d
    cl.clear_caches()


@pytest.fixture
def api(climate):
    return TestClient(app)


def strict(r):
    """Parse a response body as strict JSON: NaN/Infinity are not valid JSON and must never be served."""
    return json.loads(r.text, parse_constant=lambda c: (_ for _ in ()).throw(AssertionError(f"non-standard JSON constant {c}")))


# ------------------------------------------------------------------ /concentration


def test_concentration_defaults_to_the_annual_level_series_with_envelope(api):
    r = api.get("/api/correlation/concentration")
    assert r.status_code == 200
    j = strict(r)
    assert j["indicator"]["id"] == "co2_concentration_ppm" and j["indicator"]["unit"] == "ppm" and j["view"] == "level" and j["resolution"] == "annual" and j["baseline"] is None
    assert j["coverage"] == [1750, 2025] and len(j["points"]) == 276 and j["points"][0]["year"] == 1750 and j["points"][0]["value"] == 280.0
    assert j["note"] and j["attribution"] and j["attribution"][0]["series"] == "co2_concentration_annual" and j["attribution"][0]["license"] == "cite"
    assert j["source_vintage"] == {"x": 1} and j["schema_version"] == 1 and j["generated_at"]


def test_concentration_uncertainty_is_null_before_the_instrumental_record_and_present_after(api):
    pts = {p["year"]: p for p in api.get("/api/correlation/concentration").json()["points"]}
    assert pts[1750]["uncertainty"] is None and pts[2000]["uncertainty"] == pytest.approx(0.12)


def test_concentration_year_range_is_inclusive_and_clipped_to_coverage(api):
    j = api.get("/api/correlation/concentration?start_year=2020&end_year=2030").json()
    assert [p["year"] for p in j["points"]] == [2020, 2021, 2022, 2023, 2024, 2025] and j["start_year"] == 2020 and j["end_year"] == 2030
    assert api.get("/api/correlation/concentration?start_year=2025&end_year=2025").json()["points"][0]["year"] == 2025


def test_a_range_wholly_outside_coverage_is_an_empty_list_with_the_coverage_not_an_error(api):
    r = api.get("/api/correlation/concentration?start_year=2100")
    j = r.json()
    assert r.status_code == 200 and j["points"] == [] and j["coverage"] == [1750, 2025] and any("no data in the requested range" in n and "1750-2025" in n for n in j["notes"])


@pytest.mark.parametrize("view,sid", [("yoy_pct", "co2_concentration_ppm__yoy_pct"), ("mean5y", "co2_concentration_ppm__mean5y")])
def test_concentration_derived_views_use_the_catalog_indicator(api, view, sid):
    j = api.get(f"/api/correlation/concentration?view={view}&start_year=2000&end_year=2002").json()
    assert j["indicator"]["id"] == sid and j["view"] == view and [p["year"] for p in j["points"]] == [2000, 2001, 2002] and all(p["uncertainty"] is None for p in j["points"])


@pytest.mark.parametrize("baseline", ["preindustrial", "1970", "1990"])
def test_concentration_index_view_per_baseline(api, baseline):
    j = api.get(f"/api/correlation/concentration?view=index&baseline={baseline}&start_year=2024&end_year=2024").json()
    assert j["indicator"]["id"] == f"co2_concentration_ppm__index_{baseline}" and j["baseline"] == baseline and j["points"][0]["value"] is not None
    base_year = {"preindustrial": 1850, "1970": 1970, "1990": 1990}[baseline]
    assert j["points"][0]["value"] == pytest.approx((280.0 + 0.5 * 274) / (280.0 + 0.5 * (base_year - 1750)) * 100, rel=1e-3)


def test_concentration_validation_rules_are_422_with_the_rule_named(api):
    for url, frag in [("view=index", "requires baseline"), ("view=level&baseline=1990", "applies only to view=index"), ("resolution=monthly&view=yoy_pct", "monthly supports view=level only"),
                      ("start_year=2020&end_year=2010", "after end_year"), ("view=nope", "level"), ("baseline=2000&view=index", "preindustrial"), ("resolution=daily", "annual")]:
        r = api.get(f"/api/correlation/concentration?{url}")
        assert r.status_code == 422 and frag in r.text, (url, r.text)


def test_concentration_monthly_serves_mauna_loa_with_the_deseasonalized_value_and_nulls(api):
    j = strict(api.get("/api/correlation/concentration?resolution=monthly"))
    assert j["resolution"] == "monthly" and j["coverage"] == [1958, 2024] and len(j["points"]) == 4
    assert j["points"][0] == {"year": 1958, "month": 3, "value": 315.7, "uncertainty": None, "deseasonalized": 314.4}
    assert j["points"][3]["value"] == 424.0 and j["points"][3]["deseasonalized"] is None  # a missing deseasonalized value stays null
    assert api.get("/api/correlation/concentration?resolution=monthly&start_year=2024").json()["points"][0]["month"] == 1
    assert j["attribution"][0]["series"] == "co2_concentration_monthly_mlo"


def test_a_series_without_a_provenance_entry_is_a_503_not_served_without_attribution(api, climate):
    prov = json.loads((climate / "provenance.json").read_text())
    del prov["co2_concentration_annual"]
    (climate / "provenance.json").write_text(json.dumps(prov))
    cl.clear_caches()
    r = api.get("/api/correlation/concentration")
    assert r.status_code == 503 and "no entry for co2_concentration_annual" in r.json()["detail"]
    assert api.get("/api/correlation/temperature").status_code == 200


def test_concentration_503_when_the_series_file_is_missing_or_unusable(api, climate):
    (climate / "harmonized_global_annual.csv").unlink()
    cl.clear_caches()
    r = api.get("/api/correlation/concentration")
    assert r.status_code == 503 and "harmonized_global_annual.csv has not been generated yet" in r.json()["detail"]
    assert api.get("/api/correlation/concentration?resolution=monthly").status_code == 200  # an unrelated source is unaffected


def test_a_missing_indicator_in_the_harmonized_layer_is_a_503_not_an_empty_answer(api, climate):
    import pandas as pd
    df = pd.read_csv(climate / "harmonized_global_annual.csv")
    df[df["indicator_id"] != "co2_concentration_ppm__yoy_pct"].to_csv(climate / "harmonized_global_annual.csv", index=False)
    cl.clear_caches()
    r = api.get("/api/correlation/concentration?view=yoy_pct")
    assert r.status_code == 503 and "co2_concentration_ppm__yoy_pct has no rows" in r.json()["detail"]
    assert api.get("/api/correlation/concentration").status_code == 200


def test_an_interior_missing_year_is_an_explicit_null_not_interpolated(api, climate):
    import pandas as pd
    df = pd.read_csv(climate / "harmonized_global_annual.csv")
    df[~((df["indicator_id"] == "co2_concentration_ppm") & (df["year"] == 2000))].to_csv(climate / "harmonized_global_annual.csv", index=False)
    cl.clear_caches()
    j = strict(api.get("/api/correlation/concentration?start_year=1999&end_year=2001"))
    assert [(p["year"], p["value"] is None) for p in j["points"]] == [(1999, False), (2000, True), (2001, False)]
    assert any("1 year(s) have no value and are returned as null, not interpolated: [2000]" in n for n in j["notes"])


# ------------------------------------------------------------------ /temperature


def test_temperature_defaults_to_the_1850_1900_series_with_uncertainty_and_the_offset(api):
    j = strict(api.get("/api/correlation/temperature"))
    assert j["indicator"]["id"] == "temperature_anomaly_1850_1900_c" and j["baseline"] == "1850_1900" and j["coverage"] == [1850, 2024] and len(j["points"]) == 175
    assert j["points"][0]["uncertainty"] == pytest.approx(0.05) and j["attribution"][0]["license"] == "CC BY-NC 4.0" and j["source_vintage"] == {"y": 2}
    assert j["note"] and "measured" in j["note"]


def test_temperature_native_baseline_and_trailing_mean(api):
    n = api.get("/api/correlation/temperature?baseline=1951_1980&start_year=2024").json()
    assert n["indicator"]["id"] == "temperature_anomaly_1951_1980_c" and n["points"][0]["value"] == pytest.approx(1.3) and n["details"]["offset"] is None
    m = api.get("/api/correlation/temperature?view=mean5y&start_year=2024").json()
    assert m["indicator"]["id"] == "temperature_anomaly_1850_1900_c__mean5y" and m["points"][0]["uncertainty"] is None and any("trailing 5-year mean carries no uncertainty" in x for x in m["notes"])


def test_temperature_validation_and_empty_range(api):
    for url, frag in [("baseline=1990", "1850_1900"), ("view=index", "level"), ("start_year=2000&end_year=1990", "after end_year")]:
        r = api.get(f"/api/correlation/temperature?{url}")
        assert r.status_code == 422 and frag in r.text, (url, r.text)
    j = api.get("/api/correlation/temperature?start_year=2030").json()
    assert j["points"] == [] and j["coverage"] == [1850, 2024]


def test_temperature_503_when_the_provenance_or_catalog_is_missing(api, climate):
    (climate / "indicator_catalog.json").unlink()
    cl.clear_caches()
    r = api.get("/api/correlation/temperature")
    assert r.status_code == 503 and "indicator_catalog.json has not been generated yet" in r.json()["detail"]


# ------------------------------------------------------------------ /meta


def test_meta_describes_sources_baselines_matrix_and_the_two_totals(api):
    j = strict(api.get("/api/correlation/meta"))
    assert {s["id"] for s in j["sources"]} >= {"co2_concentration_annual", "temperature_anomaly_annual", "owid_world_co2_annual", "primap_global_composition_annual"}
    assert next(s for s in j["sources"] if s["id"] == "temperature_anomaly_annual")["license"] == "CC BY-NC 4.0"
    assert "raw_sha256" not in json.dumps(j["sources"]) and "checksum" not in json.dumps(j["sources"])
    assert set(j["baselines"]["index_baselines"]) == {"1990", "1970", "preindustrial"} and j["baselines"]["trailing_window_years"] == 5
    assert "different global totals" in j["two_global_totals"] or "Two different global totals" in j["two_global_totals"]
    assert {(m["source"], m["baseline"]): m["valid"] for m in j["source_baseline_matrix"]}[("primap_ghg", "preindustrial")] is False
    assert {i["id"] for i in j["indicators"]} >= {"co2_concentration_ppm", "temperature_anomaly_1850_1900_c"} and j["endpoints"][0] == "/api/correlation/meta"
    assert j["attribution"] and j["note"]


def test_meta_reports_each_output_as_available_missing_or_unavailable(api, climate):
    (climate / "correlation_all_gas.json").write_text(json.dumps({"schema_version": 1, "unavailable_reason": "PRIMAP missing"}))
    (climate / "correlation_composition.json").unlink()
    cl.clear_caches()
    o = api.get("/api/correlation/meta").json()["outputs"]
    assert {k: v for k, v in o["correlation_headline.json"].items() if k not in ("age_days", "stale")} == {"status": "available", "generated_at": "2026-10-02T01:00:00+00:00", "reason": None}
    assert o["correlation_all_gas.json"]["status"] == "unavailable" and "PRIMAP missing" in o["correlation_all_gas.json"]["reason"]
    assert o["correlation_composition.json"] == {"status": "missing", "generated_at": None, "age_days": None, "stale": None, "reason": "not generated yet"}


def test_meta_summarises_the_last_pipeline_run_without_dumping_deviation_text(api):
    lr = api.get("/api/correlation/meta").json()["pipeline_last_run"]
    assert lr["finished_at"] == "2026-10-02T00:01:00+00:00" and lr["sources"] == {"harmonize": {"records": {"harmonized_global": 10}, "deviations": 2}} and lr["failures"] == {"x": "boom"}


def test_meta_tolerates_a_missing_or_malformed_last_run(api, climate):
    (climate / "last_run.json").write_text("{not json")
    cl.clear_caches()
    assert api.get("/api/correlation/meta").json()["pipeline_last_run"] is None
    (climate / "last_run.json").unlink()
    assert api.get("/api/correlation/meta").json()["pipeline_last_run"] is None


def test_meta_503_without_provenance_and_the_offset_derivation_is_published(api, climate):
    prov = json.loads((climate / "provenance.json").read_text())
    prov["temperature_anomaly_annual"]["preindustrial_offset"] = {"value_c": -0.3062, "reference_period": [1850, 1900], "derivation": "mean over 1850-1900"}
    (climate / "provenance.json").write_text(json.dumps(prov))
    cl.clear_caches()
    j = api.get("/api/correlation/meta").json()
    assert j["temperature_offset"]["value_c"] == -0.3062 and "1850-1900" in j["temperature_offset"]["derivation"]
    t = api.get("/api/correlation/temperature").json()
    assert t["details"]["offset"]["value_c"] == -0.3062
    (climate / "provenance.json").unlink()
    cl.clear_caches()
    assert api.get("/api/correlation/meta").status_code == 503


# ------------------------------------------------------------------ loaders (decision 45)


def test_an_unavailable_pipeline_output_is_a_503_with_its_reason(climate):
    (climate / "correlation_all_gas.json").write_text(json.dumps({"schema_version": 1, "unavailable_reason": "PRIMAP missing"}))
    cl.clear_caches()
    with pytest.raises(cl.ClimateDataUnavailable, match="correlation_all_gas.json is unavailable: PRIMAP missing"):
        cl.load_json("correlation_all_gas.json")


def test_an_unsupported_schema_version_is_a_503(climate):
    (climate / "correlation_headline.json").write_text(json.dumps({"schema_version": 2}))
    cl.clear_caches()
    with pytest.raises(cl.ClimateDataUnavailable, match="schema_version 2"):
        cl.load_json("correlation_headline.json")


def test_a_non_finite_number_in_a_source_file_is_a_503_never_served(climate):
    (climate / "correlation_headline.json").write_text('{"schema_version": 1, "headline": {"x": NaN}}')
    cl.clear_caches()
    with pytest.raises(cl.ClimateDataUnavailable, match="non-finite"):
        cl.load_json("correlation_headline.json")


def test_malformed_or_non_object_json_is_a_503(climate):
    for body in ("{broken", "[1, 2]"):
        (climate / "correlation_headline.json").write_text(body)
        cl.clear_caches()
        with pytest.raises(cl.ClimateDataUnavailable):
            cl.load_json("correlation_headline.json")


def test_the_climate_dir_setting_resolution(monkeypatch, tmp_path):
    monkeypatch.setattr(cl, "CLIMATE_DIR", None)
    monkeypatch.setenv(cl.CLIMATE_DATA_DIR_ENV, str(tmp_path / "env"))
    assert cl.climate_dir() == str(tmp_path / "env")
    monkeypatch.delenv(cl.CLIMATE_DATA_DIR_ENV)
    assert cl.climate_dir().endswith("data/climate")
    monkeypatch.setattr(cl, "CLIMATE_DIR", "/explicit")
    assert cl.climate_dir() == "/explicit"


def test_every_response_is_strict_json_and_carries_the_envelope(api):
    for url in ("/meta", "/concentration", "/concentration?resolution=monthly", "/temperature", "/temperature?view=mean5y"):
        r = api.get("/api/correlation" + url)
        j = strict(r)
        assert r.status_code == 200 and j["note"] and "attribution" in j and "caveats" in j and j["schema_version"] == 1, url
        assert all(not (isinstance(v, float) and not math.isfinite(v)) for v in json.loads(r.text).get("points", [{"value": 0}])[0].values() if isinstance(v, float))


# ------------------------------------------------------------------ /emissions-temperature (decision 48)

ET = "/api/correlation/emissions-temperature"


def test_default_is_the_owid_total_headline_pair_with_its_fit_and_full_context(api):
    j = strict(api.get(ET))
    assert (j["source"], j["variant"], j["baseline"], j["window"], j["n_years"]) == ("owid_co2", "total", "preindustrial", [1850, 2024], 175)
    assert j["x"]["id"] == "owid_total_co2_world_cumulative_mt" and j["y"]["id"] == "temperature_anomaly_1850_1900_c" and len(j["points"]) == 175
    assert j["points"][0]["year"] == 1850 and j["points"][-1]["year"] == 2024 and j["points"][0]["cumulative_emissions"] > 0
    assert j["fit"]["slope"] == pytest.approx(0.52) and j["fit"]["n_years"] == 175 and j["fit"]["start"] == 1850 and j["fit"]["end"] == 2024 and j["fit"]["unit"] == "°C per 1,000 GtCO2"
    ctx = j["fit_context"]
    assert ctx["ar6_reference"]["best_estimate"] == 0.45 and ctx["vs_ar6"]["within_very_likely_range"] is True and ctx["fit_quality_note"]["text"].startswith("Including land-use")
    assert ctx["stability"]["seed"] == 20261002 and ctx["land_use_sensitivity"] and ctx["definition"] == "total anthropogenic CO2"
    assert j["note"] == "Paired series are shown for interpretive context." and j["source_vintage"]["file_last_modified"] == "2025-01-10" and "headline caveat" in j["caveats"]
    assert [a["series"] for a in j["attribution"]] == ["owid_world_co2_annual", "temperature_anomaly_annual"] and j["warnings"] == [] and j["omitted_years"] == []


def test_the_fossil_variant_uses_the_fossil_indicator_and_block_without_the_land_use_fit_quality_note(api):
    j = api.get(ET + "?variant=fossil").json()
    assert j["variant"] == "fossil" and j["x"]["id"] == "owid_co2_world_cumulative_mt" and j["fit"]["slope"] == pytest.approx(0.8) and j["fit"]["label"] == "Fossil + cement CO2 only"
    assert "fit_quality_note" not in j["fit_context"] and j["fit_context"]["vs_ar6"]["within_very_likely_range"] is True


def test_the_1970_window_serves_the_published_secondary_fit_with_only_a_pointer_to_the_primary_context(api):
    j = api.get(ET + "?baseline=1970").json()
    assert j["window"] == [1970, 2024] and j["n_years"] == 55 and j["points"][0]["year"] == 1970
    assert j["fit"]["slope"] == pytest.approx(0.52 + 0.3) and j["fit"]["n_years"] == 55  # the 4th published window (start 1970)
    assert list(j["fit_context"]) == ["note"] and "primary window only" in j["fit_context"]["note"]


@pytest.mark.parametrize("source,expect_note", [("owid_co2", "no fit is published for the 1990-2024 window of 35 year(s)"), ("primap_ghg", "no fit is published for the 1990-2024 window of 35 year(s)")])
def test_a_1990_window_returns_the_pair_without_a_fit_and_with_a_short_window_warning(api, source, expect_note):
    j = api.get(ET + f"?source={source}&baseline=1990").json()
    assert j["fit"] is None and j["fit_context"] == {} and j["window"] == [1990, 2024] and j["n_years"] == 35
    assert any(expect_note in n for n in j["notes"]) and any("35-year window is short" in w for w in j["warnings"])


def test_primap_defaults_to_1970_with_the_all_gas_fit_never_called_tcre_and_no_ar6_comparison(api):
    j = strict(api.get(ET + "?source=primap_ghg"))
    assert (j["source"], j["variant"], j["baseline"], j["window"]) == ("primap_ghg", None, "1970", [1970, 2024]) and j["x"]["id"] == "primap_ghg_total_cumulative_mtco2e"
    assert j["fit"]["slope"] == pytest.approx(0.58) and "vs_ar6" not in j["fit_context"] and "ar6_reference" not in j["fit_context"] and "fit_quality_note" not in j["fit_context"]
    assert any("never called TCRE" in c and "never compared with the AR6" in c for c in j["caveats"]) and "all-gas caveat" in j["caveats"]
    assert [a["series"] for a in j["attribution"]] == ["primap_global_composition_annual", "temperature_anomaly_annual"] and "TCRE" not in j["fit"]["label"]


def test_unsupported_and_invalid_combinations_are_422_never_substituted(api):
    for q, frag in [("source=primap_ghg&baseline=preindustrial", "no 1850-based fit exists"), ("source=primap_ghg&variant=total", "variant applies only to source=owid_co2"),
                    ("source=primap_ghg&variant=fossil", "variant applies only"), ("source=edgar_total_ghg", "owid_co2"), ("baseline=1800", "preindustrial"), ("variant=net", "total")]:
        r = api.get(ET + "?" + q)
        assert r.status_code == 422 and frag in r.text, (q, r.text)


def test_a_year_with_a_missing_series_value_is_omitted_with_the_reason_and_the_now_mismatched_fit_is_withheld(api, climate):
    import pandas as pd
    df = pd.read_csv(climate / "harmonized_global_annual.csv")
    df[~((df["indicator_id"] == "temperature_anomaly_1850_1900_c") & (df["year"] == 1960))].to_csv(climate / "harmonized_global_annual.csv", index=False)
    cl.clear_caches()
    j = api.get(ET).json()
    assert j["n_years"] == 174 and j["omitted_years"] == [{"year": 1960, "reason": "temperature missing"}] and all(p["year"] != 1960 for p in j["points"])
    assert j["fit"] is None and any("no fit is published for the 1850-2024 window of 174 year(s)" in n for n in j["notes"]) and any("1 year(s) in 1850-2024 are omitted" in n for n in j["notes"])


def test_both_series_missing_and_emissions_missing_reasons(api, climate):
    import pandas as pd
    df = pd.read_csv(climate / "harmonized_global_annual.csv")
    drop = ((df["indicator_id"] == "temperature_anomaly_1850_1900_c") & (df["year"].isin([1960, 1961]))) | ((df["indicator_id"] == "owid_total_co2_world_cumulative_mt") & (df["year"].isin([1961, 1962])))
    df[~drop].to_csv(climate / "harmonized_global_annual.csv", index=False)
    cl.clear_caches()
    assert {o["year"]: o["reason"] for o in api.get(ET).json()["omitted_years"]} == {1960: "temperature missing", 1961: "both series missing", 1962: "emissions missing"}


def test_a_published_fit_for_a_different_end_year_is_not_attached_to_a_newer_pair(api, climate):
    doc = headline_doc()
    for b in ("headline", "secondary_fossil_only"):
        for w in doc[b]["windows"]:
            w["end"] = 2023
    (climate / "correlation_headline.json").write_text(json.dumps(doc))
    cl.clear_caches()
    j = api.get(ET).json()
    assert j["fit"] is None and j["fit_context"] == {} and j["n_years"] == 175 and any("no fit is published" in n for n in j["notes"])


def test_unavailable_or_malformed_fit_output_is_a_503_for_its_source_only(api, climate):
    (climate / "correlation_all_gas.json").write_text(json.dumps({"schema_version": 1, "unavailable_reason": "PRIMAP missing"}))
    cl.clear_caches()
    r = api.get(ET + "?source=primap_ghg")
    assert r.status_code == 503 and "PRIMAP missing" in r.json()["detail"] and api.get(ET).status_code == 200
    doc = headline_doc()
    del doc["headline"]
    (climate / "correlation_headline.json").write_text(json.dumps(doc))
    cl.clear_caches()
    r = api.get(ET)
    assert r.status_code == 503 and "no headline block" in r.json()["detail"] and api.get(ET + "?variant=fossil").status_code == 200


def test_a_missing_indicator_makes_the_pair_a_503(api, climate):
    import pandas as pd
    df = pd.read_csv(climate / "harmonized_global_annual.csv")
    df[df["indicator_id"] != "primap_ghg_total_cumulative_mtco2e"].to_csv(climate / "harmonized_global_annual.csv", index=False)
    cl.clear_caches()
    assert api.get(ET + "?source=primap_ghg").status_code == 503 and api.get(ET).status_code == 200


# ------------------------------------------------------------------ /ghg-composition (decision 49)

GC = "/api/correlation/ghg-composition"


def test_composition_returns_every_year_with_gases_in_published_order_and_the_envelope(api):
    j = strict(api.get(GC))
    assert [y["year"] for y in j["years"]] == [2022, 2023, 2024] and j["coverage"] == [2022, 2024] and j["name"] == "Global greenhouse-gas composition"
    y = j["years"][1]
    assert [v["gas"] for v in y["values"]] == ["co2", "ch4", "n2o", "fgas"] and y["values"][0] == {"gas": "co2", "name": "CO₂", "mtco2e": 7000.0, "share_pct": pytest.approx(70.0)}
    assert sum(v["share_pct"] for v in y["values"]) == pytest.approx(100.0) and y["residual_pct"] == -0.01 and y["national_total_mtco2e"] == 10001.0
    assert j["reconciliation"]["tolerance_pct"] == 1.0 and j["excluded_incomplete_years"] == [2025] and "composition caveat" in j["caveats"]
    assert j["attribution"][0]["series"] == "primap_global_composition_annual" and j["note"] == "PRIMAP-hist, AR5 GWP-100" and j["units"].startswith("MtCO2e")


def test_a_gas_with_no_value_is_null_and_left_out_of_gases_included_with_shares_over_the_rest(api):
    y = api.get(GC + "?year=2022").json()["years"][0]
    assert y["gases_included"] == ["co2", "ch4", "n2o"] and y["values"][3] == {"gas": "fgas", "name": "Fluorinated gases", "mtco2e": None, "share_pct": None}
    assert sum(v["share_pct"] for v in y["values"] if v["share_pct"] is not None) == pytest.approx(100.0)
    assert any("null" in n for n in api.get(GC).json()["notes"])


def test_composition_single_year_range_and_empty_selection(api):
    j = api.get(GC + "?year=2023").json()
    assert [y["year"] for y in j["years"]] == [2023] and j["year"] == 2023
    assert [y["year"] for y in api.get(GC + "?start_year=2023&end_year=2024").json()["years"]] == [2023, 2024]
    assert [y["year"] for y in api.get(GC + "?start_year=2024").json()["years"]] == [2024] and [y["year"] for y in api.get(GC + "?end_year=2022").json()["years"]] == [2022]
    e = api.get(GC + "?year=1700").json()
    assert e["years"] == [] and e["coverage"] == [2022, 2024] and any("coverage is 2022-2024" in n for n in e["notes"])


def test_composition_validation_rules_are_422(api):
    for q, frag in [("year=2023&start_year=2022", "cannot be combined"), ("year=2023&end_year=2024", "cannot be combined"), ("start_year=2024&end_year=2023", "after end_year"), ("year=abc", "integer")]:
        r = api.get(GC + "?" + q)
        assert r.status_code == 422 and frag in r.text, (q, r.text)


def test_composition_503_for_missing_unavailable_or_inconsistent_files(api, climate):
    write_composition(climate, drop_rows_for=2023)
    cl.clear_caches()
    r = api.get(GC)
    assert r.status_code == 503 and "no rows for 2023" in r.json()["detail"] and api.get(GC + "?year=2024").status_code == 200
    (climate / "correlation_composition_annual.csv").unlink()
    cl.clear_caches()
    assert api.get(GC).status_code == 503
    write_composition(climate)
    doc = json.loads((climate / "correlation_composition.json").read_text())
    doc["unavailable_reason"] = "composition unavailable: missing input"
    (climate / "correlation_composition.json").write_text(json.dumps(doc))
    cl.clear_caches()
    r = api.get(GC)
    assert r.status_code == 503 and "missing input" in r.json()["detail"]


def _csv_lines(climate):
    return (climate / "correlation_composition_annual.csv").read_text().splitlines()


def test_a_year_with_a_gas_row_missing_from_the_csv_is_a_503_not_an_incomplete_200(api, climate):
    lines = [ln for ln in _csv_lines(climate) if ln != "2023,n2o,N₂O,800.0,8.0"]
    assert len(lines) == len(_csv_lines(climate)) - 1  # the row to remove really exists
    (climate / "correlation_composition_annual.csv").write_text("\n".join(lines) + "\n")
    cl.clear_caches()
    r = api.get(GC + "?year=2023")
    assert r.status_code == 503 and "for 2023" in r.json()["detail"] and "publishes" in r.json()["detail"]
    assert api.get(GC + "?year=2024").status_code == 200  # only the inconsistent year is refused


def test_a_duplicated_gas_row_is_a_503(api, climate):
    (climate / "correlation_composition_annual.csv").write_text("\n".join(_csv_lines(climate) + ["2024,co2,CO₂,7000.0,70.0"]) + "\n")
    cl.clear_caches()
    assert api.get(GC + "?year=2024").status_code == 503


def test_a_value_that_disagrees_with_gases_included_is_a_503_in_both_directions(api, climate):
    lines = _csv_lines(climate)
    # 2022 lists fgas as not included: a value for it is a disagreement
    (climate / "correlation_composition_annual.csv").write_text("\n".join(ln.replace("2022,fgas,Fluorinated gases,,", "2022,fgas,Fluorinated gases,200.0,2.0") for ln in lines) + "\n")
    cl.clear_caches()
    r = api.get(GC + "?year=2022")
    assert r.status_code == 503 and "disagrees with gases_included" in r.json()["detail"] and "fgas" in r.json()["detail"]
    # 2023 lists fgas as included: a null for it is a disagreement
    (climate / "correlation_composition_annual.csv").write_text("\n".join(ln.replace("2023,fgas,Fluorinated gases,200.0,2.0", "2023,fgas,Fluorinated gases,,") for ln in lines) + "\n")
    cl.clear_caches()
    assert api.get(GC + "?year=2023").status_code == 503 and api.get(GC + "?year=2024").status_code == 200


@pytest.mark.parametrize("bad", [["co2", "ch4", "n2o", "fgas", "sf6"], ["co2", "co2", "ch4", "n2o"], "co2", [1, 2], None, []])
def test_gases_included_must_be_a_unique_subset_of_the_published_gas_ids(api, climate, bad):
    doc = json.loads((climate / "correlation_composition.json").read_text())
    doc["years"][2]["gases_included"] = bad  # 2024
    (climate / "correlation_composition.json").write_text(json.dumps(doc))
    cl.clear_caches()
    r = api.get(GC + "?year=2024")
    assert r.status_code == 503 and "not a non-empty, unique list of published gas ids" in r.json()["detail"]
    assert api.get(GC + "?year=2023").status_code == 200


def test_a_share_that_disagrees_with_gases_included_is_a_503_even_when_the_value_agrees(api, climate):
    lines = _csv_lines(climate)
    # 2022: fgas not included, value null -- but a share is present
    (climate / "correlation_composition_annual.csv").write_text("\n".join(ln.replace("2022,fgas,Fluorinated gases,,", "2022,fgas,Fluorinated gases,,2.0") for ln in lines) + "\n")
    cl.clear_caches()
    r = api.get(GC + "?year=2022")
    assert r.status_code == 503 and "value or share" in r.json()["detail"] and "fgas" in r.json()["detail"]
    # 2023: fgas included, value present -- but its share is null
    (climate / "correlation_composition_annual.csv").write_text("\n".join(ln.replace("2023,fgas,Fluorinated gases,200.0,2.0", "2023,fgas,Fluorinated gases,200.0,") for ln in lines) + "\n")
    cl.clear_caches()
    assert api.get(GC + "?year=2023").status_code == 503 and api.get(GC + "?year=2024").status_code == 200


def test_composition_csv_without_its_columns_is_a_503(api, climate):
    (climate / "correlation_composition_annual.csv").write_text("year,gas\n2022,co2\n")
    cl.clear_caches()
    assert api.get(GC).status_code == 503


def test_meta_lists_the_new_endpoints_and_every_new_response_is_strict_json_with_the_envelope(api):
    assert {"/api/correlation/emissions-temperature", "/api/correlation/ghg-composition"} <= set(api.get("/api/correlation/meta").json()["endpoints"])
    for url in (ET, ET + "?source=primap_ghg", ET + "?baseline=1990", GC, GC + "?year=2022"):
        j = strict(api.get(url))
        assert j["note"] and "attribution" in j and "caveats" in j and j["schema_version"] == 1 and j["generated_at"], url


def test_a_year_with_no_included_gas_is_a_503_even_when_every_csv_value_and_share_is_null(api, climate):
    doc = json.loads((climate / "correlation_composition.json").read_text())
    doc["years"][2]["gases_included"] = []
    (climate / "correlation_composition.json").write_text(json.dumps(doc))
    (climate / "correlation_composition_annual.csv").write_text("\n".join(f"2024,{g},{n},," if ln.startswith("2024,") and ln.split(",")[1] == g else ln
                                                                          for ln in _csv_lines(climate) for g, n in [(ln.split(",")[1], ln.split(",")[2])]) + "\n")
    cl.clear_caches()
    r = api.get(GC + "?year=2024")
    assert r.status_code == 503 and "non-empty" in r.json()["detail"] and api.get(GC + "?year=2023").status_code == 200


# ------------------------------------------------------------------ /country-share (decision 50)

CS = "/api/correlation/country-share"


def test_the_default_is_the_latest_year_ranking_for_the_first_owid_combination(api):
    j = strict(api.get(CS))
    assert (j["mode"], j["source"], j["gas_scope"], j["year"], j["limit"], j["coverage"]) == ("ranking", "owid_co2", "co2", 2000, 15, [1850, 2000])
    rows = j["rows"]
    assert [r["rank"] for r in rows] == [1, 2, 3, 4] and [r["country"] for r in rows][0] == "AAA" and rows[0]["name"] == "Aland"
    assert [r["share_pct"] for r in rows] == sorted((r["share_pct"] for r in rows), reverse=True) and sum(r["share_pct"] for r in rows) == pytest.approx(100.0, abs=1e-6)
    assert j["total_cumulative_mt"] == pytest.approx(sum(r["cumulative_mt"] for r in rows)) and j["unit"] == "Mt CO2" and j["label"]
    assert "not a measure of responsibility" in j["note"] and j["denominator"]["definition"] and j["reconciliation"]["tolerance"] == 1e-06 and j["caveats"]
    assert {a["series"] for a in j["attribution"]} == {"owid", "primap_hist"} and j["cumulative_from"] == 1840 and j["details"]["published_from"] == 1850


def test_a_ranking_honours_year_and_limit_and_orders_ties_by_country(api):
    j = api.get(CS + "?year=1900&limit=2").json()
    assert j["year"] == 1900 and j["limit"] == 2 and len(j["rows"]) == 2 and [r["rank"] for r in j["rows"]] == [1, 2]
    e = api.get(CS + "?year=1700").json()
    assert e["rows"] == [] and e["total_cumulative_mt"] is None and any("no data for 1700: coverage is 1850-2000" in n for n in e["notes"])


@pytest.mark.parametrize("q,scope,unit", [("source=primap_hist", "co2", "Mt CO2"), ("source=primap_hist&gas_scope=total_ghg", "total_ghg", "MtCO2e"), ("source=owid_co2&gas_scope=co2", "co2", "Mt CO2")])
def test_each_published_combination_is_served_with_its_own_unit(api, q, scope, unit):
    j = api.get(CS + "?" + q).json()
    assert j["gas_scope"] == scope and j["unit"] == unit and j["rows"] and j["source"] == q.split("&")[0].split("=")[1]


def test_unsupported_combinations_are_422_listing_the_published_ones_never_substituted(api):
    for q in ("source=edgar", "source=owid_co2&gas_scope=total_ghg", "source=primap_hist&gas_scope=ch4"):
        r = api.get(CS + "?" + q)
        assert r.status_code == 422 and "the published combinations are" in r.text and "source=primap_hist&gas_scope=total_ghg" in r.text, (q, r.text)


def test_a_countries_series_is_per_country_points_with_names_and_is_case_insensitive(api):
    j = strict(api.get(CS + "?countries=aaa&countries=BBB&countries=AAA&start_year=1998"))
    assert j["mode"] == "series" and j["rows"] == [] and [s["country"] for s in j["series"]] == ["AAA", "BBB"]  # a repeated code is served once
    assert [s["name"] for s in j["series"]] == ["Aland", "Bland"] and [p["year"] for p in j["series"][0]["points"]] == [1998, 1999, 2000]
    assert j["start_year"] == 1998 and j["series"][0]["points"][0]["share_pct"] > j["series"][1]["points"][0]["share_pct"]


def test_unknown_country_codes_are_404_and_a_known_country_without_rows_is_an_empty_series_with_a_note(api, climate):
    r = api.get(CS + "?countries=AAA&countries=ZZZ&countries=QQQ")
    assert r.status_code == 404 and "ZZZ, QQQ" in r.json()["detail"]
    j = api.get(CS + "?countries=AAA&start_year=3000").json()
    assert j["series"][0]["points"] == [] and any("AAA has no rows" in n for n in j["notes"])


def test_country_share_validation_rules(api):
    cs11 = "&".join(f"countries=C{i:02d}" for i in range(11))
    for q, frag in [("countries=AAA&year=1990", "cannot be combined"), ("start_year=1990", "apply to a countries series"), (cs11, "at most 10 countries"), ("limit=0", "greater than or equal to 1"),
                    ("limit=51", "less than or equal to 50"), ("countries=AAA&start_year=2000&end_year=1990", "after end_year")]:
        r = api.get(CS + "?" + q)
        assert r.status_code == 422 and frag in r.text, (q, r.text)
    assert api.get(CS + "?" + "&".join(f"countries=AAA{i}" for i in range(10))).status_code == 404  # exactly 10 is allowed (and then unknown)


def test_country_share_503_cases(api, climate):
    (climate / "correlation_country_share.csv").write_text("country,year\nAAA,2000\n")
    cl.clear_caches()
    assert api.get(CS).status_code == 503
    (climate / "correlation_country_share.csv").unlink()
    cl.clear_caches()
    assert api.get(CS).status_code == 503
    doc = json.loads((climate / "correlation_country_share.json").read_text())
    doc["unavailable_reason"] = "OWID missing"
    (climate / "correlation_country_share.json").write_text(json.dumps(doc))
    cl.clear_caches()
    r = api.get(CS)
    assert r.status_code == 503 and "OWID missing" in r.json()["detail"]


@pytest.mark.parametrize("bad", ["", "nan", "inf", "-inf"])
def test_a_blank_nan_or_infinite_value_in_the_share_csv_is_a_503_never_a_500(api, climate, bad):
    lines = (climate / "correlation_country_share.csv").read_text().splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("AAA,2000,owid_co2,co2,"))
    parts = lines[i].split(",")
    parts[4] = bad
    lines[i] = ",".join(parts)
    (climate / "correlation_country_share.csv").write_text("\n".join(lines) + "\n")
    cl.clear_caches()
    for q in ("", "?year=1900", "?countries=BBB"):  # the whole combination is unusable, whichever view asks for it
        r = api.get(CS + q)
        assert r.status_code == 503 and "NaN or infinite" in r.json()["detail"], (q, r.status_code)
    assert api.get(CS + "?source=primap_hist").status_code == 200  # another combination is unaffected


def test_a_share_series_whose_file_ends_before_the_published_coverage_is_a_503_not_an_older_ranking_as_latest(api, climate):
    import pandas as pd
    df = pd.read_csv(climate / "correlation_country_share.csv")
    df[~((df["source"] == "owid_co2") & (df["year"] == 2000))].to_csv(climate / "correlation_country_share.csv", index=False)
    cl.clear_caches()
    r = api.get(CS)
    assert r.status_code == 503 and "spans 1850-1999" in r.json()["detail"] and "publishes coverage 1850-2000" in r.json()["detail"]
    assert api.get(CS + "?source=primap_hist").status_code == 200


@pytest.mark.parametrize("col", [4, 5])
def test_a_non_numeric_token_in_a_numeric_share_column_is_a_503_never_a_500(api, climate, col):
    lines = (climate / "correlation_country_share.csv").read_text().splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("BBB,1900,owid_co2,co2,"))
    parts = lines[i].split(",")
    parts[col] = "abc"
    lines[i] = ",".join(parts)
    (climate / "correlation_country_share.csv").write_text("\n".join(lines) + "\n")
    cl.clear_caches()
    for q in ("", "?year=1900", "?countries=AAA"):
        r = api.get(CS + q)
        assert r.status_code == 503 and "non-numeric" in r.json()["detail"], (q, r.status_code)


@pytest.mark.parametrize("bad_year", ["", "abc", "inf", "1900.5", "-1"])
def test_a_malformed_year_in_the_share_csv_is_a_503_never_a_500(api, climate, bad_year):
    lines = (climate / "correlation_country_share.csv").read_text().splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("BBB,1900,owid_co2,co2,"))
    parts = lines[i].split(",")
    parts[1] = bad_year
    lines[i] = ",".join(parts)
    (climate / "correlation_country_share.csv").write_text("\n".join(lines) + "\n")
    cl.clear_caches()
    for q in ("", "?countries=BBB"):
        r = api.get(CS + q)
        assert r.status_code == 503 and "non-integer year" in r.json()["detail"], (q, r.text)


def test_an_interior_row_missing_while_the_year_bounds_still_match_is_a_503(api, climate):
    lines = (climate / "correlation_country_share.csv").read_text().splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("AAA,1900,owid_co2,co2,"))
    del lines[i]  # first/last year are untouched, one country-year is gone
    (climate / "correlation_country_share.csv").write_text("\n".join(lines) + "\n")
    cl.clear_caches()
    for q in ("", "?countries=AAA"):
        r = api.get(CS + q)
        assert r.status_code == 503 and "publishes" in r.json()["detail"] and "rows for" in r.json()["detail"], (q, r.text)
    assert api.get(CS + "?source=primap_hist").status_code == 200


def test_a_missing_country_year_replaced_by_a_duplicate_row_is_a_503(api, climate):
    lines = (climate / "correlation_country_share.csv").read_text().splitlines()
    missing = next(k for k, ln in enumerate(lines) if ln.startswith("AAA,1900,owid_co2,co2,"))
    duplicate = next(ln for ln in lines if ln.startswith("AAA,1901,owid_co2,co2,"))
    lines[missing] = duplicate
    (climate / "correlation_country_share.csv").write_text("\n".join(lines) + "\n")
    cl.clear_caches()
    for q in ("", "?countries=AAA"):
        r = api.get(CS + q)
        assert r.status_code == 503 and "duplicate country/year rows" in r.json()["detail"], (q, r.text)
    assert api.get(CS + "?source=primap_hist").status_code == 200


def test_a_country_relabelled_onto_another_keeps_the_row_count_but_fails_the_country_count(api, climate):
    lines = (climate / "correlation_country_share.csv").read_text().splitlines()
    out = [ln.replace("DDD,", "AAA,", 1) if ln.startswith("DDD,") and ",owid_co2," in ln else ln for ln in lines]
    assert len(out) == len(lines) and out != lines
    (climate / "correlation_country_share.csv").write_text("\n".join(out) + "\n")
    cl.clear_caches()
    r = api.get(CS)
    assert r.status_code == 503 and "3 countries" in r.json()["detail"] and "for 4 countries" in r.json()["detail"]


def test_a_country_missing_entirely_is_a_503_via_the_country_count(api, climate):
    import pandas as pd
    df = pd.read_csv(climate / "correlation_country_share.csv")
    df[~((df["source"] == "owid_co2") & (df["country"] == "DDD"))].to_csv(climate / "correlation_country_share.csv", index=False)
    cl.clear_caches()
    r = api.get(CS)
    assert r.status_code == 503 and "countries" in r.json()["detail"]


def test_a_share_series_that_starts_after_the_published_coverage_is_a_503(api, climate):
    import pandas as pd
    df = pd.read_csv(climate / "correlation_country_share.csv")
    df[~((df["source"] == "owid_co2") & (df["year"] == 1850))].to_csv(climate / "correlation_country_share.csv", index=False)
    cl.clear_caches()
    assert api.get(CS + "?countries=AAA").status_code == 503


def test_a_combination_published_as_available_with_no_csv_rows_is_a_503(api, climate):
    import pandas as pd
    df = pd.read_csv(climate / "correlation_country_share.csv")
    df[df["gas_scope"] != "total_ghg"].to_csv(climate / "correlation_country_share.csv", index=False)
    cl.clear_caches()
    r = api.get(CS + "?source=primap_hist&gas_scope=total_ghg")
    assert r.status_code == 503 and "no rows for source=primap_hist, gas_scope=total_ghg" in r.json()["detail"] and api.get(CS).status_code == 200


def test_an_unavailable_combination_is_not_offered(api, climate):
    doc = json.loads((climate / "correlation_country_share.json").read_text())
    for c in doc["combinations"]:
        if c["source"] == "primap_hist":
            c["available"] = False
    (climate / "correlation_country_share.json").write_text(json.dumps(doc))
    cl.clear_caches()
    r = api.get(CS + "?source=primap_hist")
    assert r.status_code == 422 and "source=owid_co2&gas_scope=co2" in r.text and "primap_hist" not in r.text.split("published combinations are:")[1]


# ------------------------------------------------------------------ /scenario-temperature (decision 51)

ST = "/api/correlation/scenario-temperature"


def test_scenario_temperature_serves_the_translation_with_every_mandatory_label_and_block(api):
    j = strict(api.get(ST))
    assert j["selected_scenarios"] == ["Aggressive", "BAU", "Moderate"] and j["line"] == "both" and sorted(j["scenarios"]) == ["Aggressive", "BAU", "Moderate"]
    assert j["labels"] == ["illustrative, partial-coverage translation", "Implied temperature outcomes", "Dependent on the selected regression period, emissions source and model assumptions",
                           "Illustrative analytical translations, not formal climate-model projections"]
    row = j["scenarios"]["BAU"][0]
    assert {"year", "covered_mt", "global_fossil_mt", "cumulative_increment_mt", "headline", "fossil_only"} <= set(row) and row["headline"]["level_c"] and len(row["headline"]["level_ci95"]) == 2
    assert {"rest_of_world", "land_use", "slope"} <= set(j["assumptions"]) and {"anchor", "step_check", "pathway_baseline", "first_scenario_year_vs_last_observed_pct"} <= set(j["base"])
    assert j["spread"]["per_year"] and j["reading_note"].startswith("Scenarios diverge sharply") and j["covered_countries"] and j["scenario_source"]["scenarios"] == ["Aggressive", "BAU", "Moderate"]
    assert "not proof of causation" in j["note"]
    assert j["source_vintage"] and j["attribution"] and j["attribution"][0]["series"] == "owid_world_co2_annual" and j["caveats"] and j["notes"] == []


def test_the_scenario_filter_keeps_only_the_named_scenarios_and_says_the_spread_is_unfiltered(api):
    j = api.get(ST + "?scenario=BAU&scenario=Aggressive").json()
    assert j["selected_scenarios"] == ["Aggressive", "BAU"] and sorted(j["scenarios"]) == ["Aggressive", "BAU"]
    assert any("`spread` and `reading_note` describe all published scenarios" in n for n in j["notes"]) and j["spread"] and j["reading_note"]
    assert api.get(ST + "?scenario=BAU&scenario=Moderate&scenario=Aggressive").json()["notes"] == []


@pytest.mark.parametrize("line,present,absent", [("headline", "headline", "fossil_only"), ("fossil_only", "fossil_only", "headline"), ("both", "headline", None)])
def test_the_line_filter_drops_the_other_temperature_line_from_every_row(api, line, present, absent):
    j = api.get(ST + f"?line={line}").json()
    for rows in j["scenarios"].values():
        for row in rows:
            assert present in row and (absent is None or absent not in row) and ("fossil_only" in row if line == "both" else True)
    assert j["line"] == line and (line == "both" or j["notes"])


def test_scenario_validation_is_422_with_the_allowed_values(api):
    for q, frag in [("scenario=Nope", "BAU"), ("line=net", "headline"), ("scenario=bau", "BAU")]:
        r = api.get(ST + "?" + q)
        assert r.status_code == 422 and frag in r.text, (q, r.text)


def test_a_stale_or_failed_translation_is_a_503_with_the_reason(api, climate):
    doc = json.loads((climate / "correlation_scenario_temperature.json").read_text())
    doc["unavailable_reason"] = "scenario file is stale"
    (climate / "correlation_scenario_temperature.json").write_text(json.dumps(doc))
    cl.clear_caches()
    r = api.get(ST)
    assert r.status_code == 503 and "scenario file is stale" in r.json()["detail"]
    (climate / "correlation_scenario_temperature.json").unlink()
    cl.clear_caches()
    assert api.get(ST).status_code == 503


def test_a_malformed_translation_file_is_a_503_not_a_500(api, climate):
    good = json.loads((climate / "correlation_scenario_temperature.json").read_text())
    for mutate in (lambda d: d.pop("scenarios"), lambda d: d.update(scenarios={}), lambda d: d.pop("assumptions"), lambda d: d.pop("base")):
        d = json.loads(json.dumps(good))
        mutate(d)
        (climate / "correlation_scenario_temperature.json").write_text(json.dumps(d))
        cl.clear_caches()
        assert api.get(ST).status_code == 503


def test_a_selected_scenario_the_file_lacks_is_a_503(api, climate):
    doc = json.loads((climate / "correlation_scenario_temperature.json").read_text())
    del doc["scenarios"]["Moderate"]
    (climate / "correlation_scenario_temperature.json").write_text(json.dumps(doc))
    cl.clear_caches()
    r = api.get(ST + "?scenario=Moderate")
    assert r.status_code == 503 and "no Moderate scenario" in r.json()["detail"] and api.get(ST + "?scenario=BAU").status_code == 200


def test_the_final_contract_every_endpoint_is_strict_json_with_the_envelope_and_listed_in_meta(api):
    meta = api.get("/api/correlation/meta").json()
    assert set(meta["endpoints"]) == {f"/api/correlation/{n}" for n in ("meta", "concentration", "temperature", "emissions-temperature", "ghg-composition", "country-share", "scenario-temperature")}
    for url in meta["endpoints"]:
        r = api.get(url)
        j = strict(r)
        assert r.status_code == 200 and j["note"] is not None and "attribution" in j and "caveats" in j and j["schema_version"] == 1, url
        assert url == "/api/correlation/meta" or j["generated_at"], url


# ------------------------------------------------------------------ Phase 1.5: freshness, caching and unit consistency


def _at(monkeypatch, iso):
    from datetime import datetime

    from api.routers import correlation as router
    monkeypatch.setattr(router, "_now", lambda: datetime.fromisoformat(iso))


def test_meta_flags_an_output_older_than_the_stale_threshold_and_reports_its_age(api, climate, monkeypatch):
    _at(monkeypatch, "2026-10-12T01:00:00+00:00")  # headline generated 2026-10-02T01:00:00 -> exactly 10 days
    j = api.get("/api/correlation/meta").json()
    h = j["outputs"]["correlation_headline.json"]
    assert h["age_days"] == 10.0 and h["stale"] is False and j["freshness"]["stale_after_days"] == 45 and j["freshness"]["refresh_cadence_days"] == 31
    assert j["freshness"]["checked_at"].startswith("2026-10-12")
    _at(monkeypatch, "2026-11-16T01:00:00+00:00")  # 45 days: not yet stale (the threshold is exclusive)
    assert api.get("/api/correlation/meta").json()["outputs"]["correlation_headline.json"]["stale"] is False
    _at(monkeypatch, "2026-11-16T01:01:00+00:00")  # just over 45 days
    j = api.get("/api/correlation/meta").json()
    assert j["outputs"]["correlation_headline.json"]["stale"] is True and j["outputs"]["correlation_headline.json"]["age_days"] >= 45.0  # the reported age is rounded to 2 decimals; the flag uses the exact age


def test_freshness_is_unknown_never_assumed_fresh_when_the_timestamp_is_missing_or_unparsable(api, climate, monkeypatch):
    _at(monkeypatch, "2026-10-12T00:00:00+00:00")
    for bad in (None, "not a date", 12345):
        doc = json.loads((climate / "correlation_headline.json").read_text())
        doc["generated_at"] = bad
        (climate / "correlation_headline.json").write_text(json.dumps(doc))
        cl.clear_caches()
        h = api.get("/api/correlation/meta").json()["outputs"]["correlation_headline.json"]
        assert h["status"] == "available" and h["age_days"] is None and h["stale"] is None, bad


def test_a_future_or_naive_timestamp_does_not_produce_a_negative_age(api, climate, monkeypatch):
    _at(monkeypatch, "2026-10-01T00:00:00+00:00")  # the file claims to be from the future
    assert api.get("/api/correlation/meta").json()["outputs"]["correlation_headline.json"]["age_days"] == 0.0
    doc = json.loads((climate / "correlation_headline.json").read_text())
    doc["generated_at"] = "2026-09-20T00:00:00"  # no timezone: read as UTC
    (climate / "correlation_headline.json").write_text(json.dumps(doc))
    cl.clear_caches()
    assert api.get("/api/correlation/meta").json()["outputs"]["correlation_headline.json"]["age_days"] == 11.0


def test_missing_and_unavailable_outputs_have_no_freshness(api, climate):
    (climate / "correlation_all_gas.json").write_text(json.dumps({"schema_version": 1, "unavailable_reason": "x"}))
    (climate / "correlation_composition.json").unlink()
    cl.clear_caches()
    o = api.get("/api/correlation/meta").json()["outputs"]
    for n in ("correlation_all_gas.json", "correlation_composition.json"):
        assert o[n]["age_days"] is None and o[n]["stale"] is None


def test_a_second_request_reads_no_file_again(api, monkeypatch):
    import builtins
    import pandas as pd
    urls = ["/meta", "/concentration", "/concentration?resolution=monthly", "/temperature", "/emissions-temperature", "/emissions-temperature?source=primap_ghg", "/ghg-composition",
            "/country-share", "/country-share?countries=AAA", "/scenario-temperature"]
    for u in urls:
        assert api.get("/api/correlation" + u).status_code == 200  # warm every cache
    opened, csv_reads = [], []
    real_open, real_read_csv = builtins.open, pd.read_csv
    monkeypatch.setattr(builtins, "open", lambda f, *a, **k: (opened.append(str(f)) if str(f).endswith((".json", ".csv")) else None, real_open(f, *a, **k))[1])
    monkeypatch.setattr(pd, "read_csv", lambda *a, **k: (csv_reads.append(str(a[0])), real_read_csv(*a, **k))[1])
    for u in urls:
        api.get("/api/correlation" + u)
    # /meta reads last_run.json and checks output files each time (it reports live status); no data series file is re-read
    assert csv_reads == [] and sorted(set(opened)) == sorted({o for o in opened if o.endswith("last_run.json")}), (csv_reads, opened)


def test_every_series_response_unit_equals_its_catalog_unit_and_catalog_units_are_known(api):
    cat = {i["id"]: i for i in api.get("/api/correlation/meta").json()["indicators"]}
    known = {"ppm", "°C", "Mt CO2", "MtCO2e", "%", "index (1990 = 100)", "index (1970 = 100)", "index (1850 = 100)"}  # the catalog's whole unit vocabulary
    unknown = {i["id"]: i["unit"] for i in cat.values() if i["unit"] not in known}
    assert unknown == {}, f"units outside the known vocabulary: {unknown}"
    for url in ("/concentration", "/concentration?view=yoy_pct", "/concentration?view=index&baseline=1990", "/temperature", "/temperature?view=mean5y", "/temperature?baseline=1951_1980"):
        j = api.get("/api/correlation" + url).json()
        assert j["indicator"]["unit"] == cat[j["indicator"]["id"]]["unit"] and j["indicator"]["unit"], url
    for url in ("/emissions-temperature", "/emissions-temperature?source=primap_ghg"):
        j = api.get("/api/correlation" + url).json()
        assert j["x"]["unit"] == cat[j["x"]["id"]]["unit"] and j["y"]["unit"] == "°C" and j["fit"]["unit"], url


def test_the_series_endpoints_never_serve_a_year_outside_the_data_coverage(api):
    for url in ("/concentration", "/temperature", "/emissions-temperature"):
        j = api.get("/api/correlation" + url + ("?start_year=0&end_year=9999" if "emissions" not in url else "")).json()
        years = [p["year"] for p in j["points"]]
        lo, hi = (j["coverage"] if "coverage" in j else j["window"])
        assert years == sorted(set(years)) and years[0] >= lo and years[-1] <= hi, url


# ------------------------------------------------------------------ /country-share: all_countries snapshot + annual values (decision 60)


def test_ranking_rows_and_series_points_carry_the_years_own_emissions_and_share(api):
    j = strict(api.get(CS))
    by = {r["country"]: r for r in j["rows"]}
    # fixture, year 2000: AAA 10/yr, BBB 5/yr, CCC 1/yr, DDD's record ended in 1970 (annual 0)
    assert [by[c]["annual_mt"] for c in ("AAA", "BBB", "CCC", "DDD")] == [10.0, 5.0, 1.0, 0.0]
    assert by["AAA"]["annual_share_pct"] == pytest.approx(10 / 16 * 100, abs=1e-6) and sum(r["annual_share_pct"] for r in j["rows"]) == pytest.approx(100.0, abs=1e-6)
    assert j["annual_total_mt"] == pytest.approx(16.0)
    s = strict(api.get(CS + "?countries=AAA&countries=BBB&start_year=1999")).get("series")
    assert [p["annual_mt"] for p in s[0]["points"]] == [10.0, 10.0] and [p["annual_mt"] for p in s[1]["points"]] == [5.0, 5.0]
    assert s[0]["points"][0]["annual_share_pct"] == pytest.approx(10 / 16 * 100, abs=1e-6)


def test_all_countries_returns_every_country_ranked_with_no_limit(api):
    j = strict(api.get(CS + "?all_countries=true&year=1900"))
    assert j["mode"] == "ranking" and j["limit"] is None and j["year"] == 1900
    assert sorted(r["country"] for r in j["rows"]) == ["AAA", "BBB", "CCC", "DDD"]
    assert [r["rank"] for r in j["rows"]] == [1, 2, 3, 4] and [r["share_pct"] for r in j["rows"]] == sorted((r["share_pct"] for r in j["rows"]), reverse=True)
    assert j["total_cumulative_mt"] == pytest.approx(sum(r["cumulative_mt"] for r in j["rows"]))
    assert len(api.get(CS + "?year=1900&limit=2").json()["rows"]) == 2  # the existing limited form is unchanged
    assert api.get(CS + "?all_countries=false").json()["limit"] == 15


def test_all_countries_defaults_to_the_latest_year_and_serves_each_combination(api):
    j = api.get(CS + "?all_countries=true&source=primap_hist&gas_scope=total_ghg").json()
    assert j["year"] == 2000 and j["unit"] == "MtCO2e" and len(j["rows"]) == 4 and j["rows"][0]["annual_mt"] is not None


def test_all_countries_cannot_be_combined_with_countries_or_limit(api):
    for q, frag in [("all_countries=true&countries=AAA", "cannot be combined with countries"), ("all_countries=true&limit=5", "cannot be combined with limit"),
                    ("all_countries=true&start_year=1990", "apply to a countries series")]:
        r = api.get(CS + "?" + q)
        assert r.status_code == 422 and frag in r.text, (q, r.text)


def test_an_output_that_predates_the_annual_columns_still_serves_with_null_annual_fields_and_a_note(api, climate):
    import pandas as pd
    p = climate / "correlation_country_share.csv"
    pd.read_csv(p).drop(columns=["annual_mt", "annual_share_pct"]).to_csv(p, index=False)
    cl.clear_caches()
    j = api.get(CS + "?all_countries=true").json()
    assert len(j["rows"]) == 4 and all(r["annual_mt"] is None and r["annual_share_pct"] is None for r in j["rows"])
    assert j["annual_total_mt"] is None and any("predates those columns" in n for n in j["notes"])
    s = api.get(CS + "?countries=AAA&start_year=1999").json()
    assert s["series"][0]["points"][0]["annual_mt"] is None and any("predates those columns" in n for n in s["notes"])


def test_malformed_annual_columns_are_a_503_never_a_500(api, climate):
    import pandas as pd
    p = climate / "correlation_country_share.csv"
    good = pd.read_csv(p)
    good.drop(columns=["annual_share_pct"]).to_csv(p, index=False)  # only one of the pair
    cl.clear_caches()
    r = api.get(CS)
    assert r.status_code == 503 and "written together" in r.json()["detail"]
    bad = good.copy()
    bad.loc[(bad["country"] == "AAA") & (bad["year"] == 2000) & (bad["source"] == "owid_co2"), "annual_mt"] = float("nan")
    bad.to_csv(p, index=False)
    cl.clear_caches()
    r = api.get(CS)
    assert r.status_code == 503 and "annual_mt/annual_share_pct" in r.json()["detail"]
