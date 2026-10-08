"""SPEC.md §5.1 Area 2 indicator tools, against the real api/ app on pipeline-built fixtures."""

import json

import pytest

from mcp_server.climate import ClimateApiError, summarize_points
from mcp_server.tools.climate import get_co2_concentration, get_correlation_metadata, get_temperature_anomaly


# --- summarize_points (pure) ---------------------------------------------------------------


def test_summarize_points_first_last_change_and_pct():
    pts = [{"year": 2000, "value": 100.0}, {"year": 2001, "value": None}, {"year": 2002, "value": 110.0, "uncertainty": 0.5}]
    s = summarize_points(pts, include_pct=True)
    assert s == {
        "n_years": 3, "n_null_years": 1, "first_year": 2000, "first_value": 100.0, "last_year": 2002,
        "last_value": 110.0, "change": 10.0, "change_pct": 10.0, "last_uncertainty": 0.5,
    }


def test_summarize_points_omits_pct_for_anomaly_series():
    s = summarize_points([{"year": 1, "value": -0.1}, {"year": 2, "value": 1.5}], include_pct=False)
    assert s["change"] == 1.6 and "change_pct" not in s


def test_summarize_points_all_null_has_counts_only():
    assert summarize_points([{"year": 1, "value": None}], include_pct=True) == {"n_years": 1, "n_null_years": 1}


# --- get_co2_concentration -----------------------------------------------------------------


async def test_concentration_returns_series_envelope_and_summary(climate_client):
    body = await get_co2_concentration()
    assert body["indicator"]["unit"] == "ppm" and body["resolution"] == "annual"
    assert body["attribution"] and body["note"] and "details" in body
    s = body["summary"]
    assert s["first_year"] == 1750 and s["first_value"] == 280.0 and s["last_year"] == 2025
    assert s["change"] == pytest.approx(s["last_value"] - s["first_value"], abs=0.01)
    assert s["change_pct"] > 0
    assert len(body["points"]) == s["n_years"]  # full series stays in the result (§5.1 convention 3)


async def test_concentration_year_range_is_passed_through(climate_client):
    body = await get_co2_concentration(start_year=2020, end_year=2024)
    assert [p["year"] for p in body["points"]] == [2020, 2021, 2022, 2023, 2024]
    assert body["summary"]["first_year"] == 2020


async def test_concentration_range_outside_coverage_is_empty_with_a_note_not_an_error(climate_client):
    body = await get_co2_concentration(start_year=2100)
    assert body["points"] == [] and body["summary"] == {"n_years": 0, "n_null_years": 0}
    assert any("no data in the requested range" in n for n in body["notes"])


async def test_concentration_reversed_range_raises_with_the_api_message(climate_client):
    with pytest.raises(ClimateApiError, match=r"422.*start_year.*after end_year"):
        await get_co2_concentration(start_year=2020, end_year=2010)


# --- get_temperature_anomaly ---------------------------------------------------------------


async def test_temperature_defaults_to_preindustrial_reference_with_no_pct(climate_client):
    body = await get_temperature_anomaly()
    assert body["baseline"] == "1850_1900" and body["summary"]["reference"] == "1850-1900"
    assert "change_pct" not in body["summary"]
    assert "offset" in body["details"]  # the 1850-1900 offset derivation slot is present (null only when the pipeline has none)


async def test_temperature_native_reference_has_no_offset(climate_client):
    body = await get_temperature_anomaly(reference="1951-1980")
    assert body["baseline"] == "1951_1980" and body["summary"]["reference"] == "1951-1980"
    assert body["details"]["offset"] is None


async def test_temperature_unknown_reference_names_the_valid_ones(climate_client):
    with pytest.raises(ValueError, match="1850-1900.*1951-1980"):
        await get_temperature_anomaly(reference="1990")


# --- get_correlation_metadata --------------------------------------------------------------


async def test_metadata_summarises_sources_and_trims_the_indicator_catalog(climate_client):
    body = await get_correlation_metadata()
    assert "indicators" not in body and body["indicator_count"] > 0
    ids = {s["id"] for s in body["summary"]["sources"]}
    assert "temperature_anomaly_annual" in ids and "co2_concentration_annual" in ids
    assert body["two_global_totals"] and body["source_baseline_matrix"]
    assert body["summary"]["temperature_offset"] == body["temperature_offset"]


async def test_metadata_reports_pipeline_failures_and_missing_outputs(climate_client):
    body = await get_correlation_metadata()
    # the shared fixture's last_run.json records one failure ("x": "boom")
    assert body["summary"]["pipeline_failures"] == {"x": "boom"}
    assert isinstance(body["summary"]["stale_outputs"], list)


# --- error paths ---------------------------------------------------------------------------


async def test_unavailable_climate_data_is_a_503_tool_error_naming_the_cause(climate_client, climate):
    import api.climate_loaders as cl

    (climate / "indicator_catalog.json").unlink()
    cl.clear_caches()
    with pytest.raises(ClimateApiError, match="currently unavailable"):
        await get_co2_concentration()
