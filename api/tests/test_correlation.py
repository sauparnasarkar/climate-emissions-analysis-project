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
from pipeline.tests.test_harmonize import run as run_harmonize


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
    (d / "correlation_headline.json").write_text(json.dumps({"schema_version": 1, "generated_at": "2026-10-02T01:00:00+00:00", "headline": {}}))
    (d / "correlation_all_gas.json").write_text(json.dumps({"schema_version": 1, "unavailable_reason": "PRIMAP missing"}))
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


def test_meta_reports_each_output_as_available_missing_or_unavailable(api):
    o = api.get("/api/correlation/meta").json()["outputs"]
    assert o["correlation_headline.json"] == {"status": "available", "generated_at": "2026-10-02T01:00:00+00:00", "reason": None}
    assert o["correlation_all_gas.json"]["status"] == "unavailable" and "PRIMAP missing" in o["correlation_all_gas.json"]["reason"]
    assert o["correlation_composition.json"] == {"status": "missing", "generated_at": None, "reason": "not generated yet"}


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
