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


# === Step 3.2: relationship tools ===========================================================

from mcp_server.resolution import CountryResolutionError  # noqa: E402
from mcp_server.tools.climate import (  # noqa: E402
    get_country_cumulative_share,
    get_emissions_temperature_relationship,
    get_ghg_composition,
    get_scenario_temperature,
)
from mcp_server.tools.composed import get_methodology_notes  # noqa: E402


# --- get_emissions_temperature_relationship ------------------------------------------------


async def test_headline_relationship_is_labelled_and_carries_the_fit(climate_client):
    body = await get_emissions_temperature_relationship()
    s = body["summary"]
    assert s["relationship"].startswith("headline long-run relationship")
    assert s["source"] == "owid_co2" and s["baseline"] == "preindustrial"
    assert s["fit"]["slope"] == pytest.approx(0.52) and len(s["fit"]["ci95_hac"]) == 2
    assert s["vs_ar6"] is not None  # the headline is compared with AR6
    assert s["first_pair"]["year"] == s["window"][0] and s["last_pair"]["year"] == s["window"][1]
    assert body["points"]  # full pairs stay in the result


async def test_fossil_variant_is_labelled_secondary(climate_client):
    s = (await get_emissions_temperature_relationship(variant="fossil"))["summary"]
    assert "secondary" in s["relationship"] and s["fit"]["slope"] == pytest.approx(0.8)


async def test_all_gas_relationship_is_never_called_tcre_and_has_no_ar6_comparison(climate_client):
    body = await get_emissions_temperature_relationship(source="primap_ghg")
    s = body["summary"]
    assert s["relationship"].startswith("recent all-gas relationship") and s["baseline"] == "1970"
    assert "vs_ar6" not in s
    # the label may say "never called TCRE" but must not present the all-gas fit AS the TCRE
    assert "headline" not in s["relationship"]


async def test_unsupported_source_baseline_pair_is_rejected_not_substituted(climate_client):
    with pytest.raises(ClimateApiError, match=r"422.*primap_ghg.*preindustrial"):
        await get_emissions_temperature_relationship(source="primap_ghg", baseline="preindustrial")


async def test_short_window_has_no_fit_and_says_so(climate_client):
    body = await get_emissions_temperature_relationship(baseline="1990")
    assert body["summary"]["fit"] is None and "context only" in body["summary"]["fit_note"]


# --- get_ghg_composition -------------------------------------------------------------------


async def test_composition_summary_has_first_last_shares_and_pp_change(climate_client):
    body = await get_ghg_composition()
    s = body["summary"]
    assert (s["first_year"], s["last_year"]) == (2022, 2024) and s["excluded_incomplete_years"] == [2025]
    assert set(s["last_shares_pct"]) == {"co2", "ch4", "n2o", "fgas"}
    # 2022 has no F-gas value in the fixture: its share is null and absent from the pp change
    assert s["first_shares_pct"]["fgas"] is None and "fgas" not in s["share_change_pp"]
    assert s["share_change_pp"]["co2"] == pytest.approx(s["last_shares_pct"]["co2"] - s["first_shares_pct"]["co2"], abs=0.01)


async def test_composition_single_year_and_year_with_range_conflict(climate_client):
    assert (await get_ghg_composition(year=2024))["summary"]["n_years"] == 1
    with pytest.raises(ClimateApiError, match="year cannot be combined"):
        await get_ghg_composition(year=2024, start_year=2022)


# --- get_country_cumulative_share ----------------------------------------------------------


async def test_share_ranking_has_interpretation_note_and_caveats(climate_client):
    body = await get_country_cumulative_share()
    assert body["summary"]["mode"] == "ranking" and body["rows"]
    assert "not an estimate of any country's contribution" in body["interpretation_note"]
    assert any("not a measure of responsibility" in c for c in body["caveats"])  # the API's own caveat survives


async def test_share_series_resolves_iso3_and_names_and_summarises(climate_client):
    roster = (await get_country_cumulative_share(limit=50))["rows"]
    first = roster[0]
    by_code = await get_country_cumulative_share(countries=[first["country"].lower()])
    by_name = await get_country_cumulative_share(countries=[first["name"]])
    assert by_code["summary"]["countries"][0]["country"] == first["country"] == by_name["summary"]["countries"][0]["country"]
    assert by_code["summary"]["mode"] == "series" and by_code["series"][0]["points"]


async def test_share_unknown_country_is_an_explicit_resolution_error(climate_client):
    with pytest.raises(CountryResolutionError, match="No match for 'Zzyzx"):
        await get_country_cumulative_share(countries=["Zzyzxland"])


async def test_share_series_with_a_year_is_rejected_by_the_api(climate_client):
    code = (await get_country_cumulative_share())["rows"][0]["country"]
    with pytest.raises(ClimateApiError, match="year"):
        await get_country_cumulative_share(countries=[code], year=1990)


async def test_share_unsupported_combination_names_the_published_ones(climate_client):
    with pytest.raises(ClimateApiError, match="published combinations"):
        await get_country_cumulative_share(source="owid_co2", gas_scope="total_ghg")


# --- get_scenario_temperature --------------------------------------------------------------


async def test_scenario_summary_has_final_year_levels_and_gap_vs_bau(climate_client):
    body = await get_scenario_temperature()
    s = body["summary"]
    assert set(s["final_year_by_scenario"]) == {"BAU", "Moderate", "Aggressive"}
    assert "step_check" not in body["base"]  # internal QA record trimmed
    assert body["assumptions"]
    gap = s["headline_level_gap_vs_bau_c"]
    assert set(gap) == {"Moderate", "Aggressive"}
    assert gap["Aggressive"] <= 0  # a more aggressive pathway never implies a warmer outcome than BAU


async def test_scenario_names_are_case_insensitive_and_unknown_ones_rejected(climate_client):
    body = await get_scenario_temperature(scenarios=["aggressive"], line="headline")
    assert body["selected_scenarios"] == ["Aggressive"]
    assert body["summary"]["final_year_by_scenario"]["Aggressive"]["fossil_only_level_c"] is None
    with pytest.raises(ValueError, match="BAU, Moderate, Aggressive"):
        await get_scenario_temperature(scenarios=["Extreme"])


# --- get_methodology_notes(topic) ----------------------------------------------------------


async def test_methodology_default_is_unchanged_and_makes_no_climate_call(api_client):
    body = await get_methodology_notes()
    assert "headline_derivation" not in body and "forecasting_methodology" in body


async def test_methodology_climate_topic_reads_live_figures_not_typed_ones(climate_client):
    body = await get_methodology_notes(topic="climate")
    assert "forecasting_methodology" not in body
    assert "not_a_climate_model" in body and "source_reconciliation" in body
    d = body["headline_derivation"]
    assert d["fit"]["slope"] == pytest.approx(0.52) and d["secondary_fossil_only_fit"]["slope"] == pytest.approx(0.8)
    assert d["fit_context"]["fit_quality_note"]["text"].startswith("Including land-use")
    assert len(d["outline"]) == 7
    assert "not yet been" in body["source_reconciliation"]  # the 5-8% figure is not presented as measured


async def test_methodology_all_merges_and_unknown_topic_is_rejected(climate_client):
    body = await get_methodology_notes(topic="all")
    assert "forecasting_methodology" in body and "headline_derivation" in body
    with pytest.raises(ValueError, match="Unknown topic"):
        await get_methodology_notes(topic="weather")


async def test_composition_defaults_to_1970_with_a_note_and_honours_an_explicit_start(climate_client):
    default = await get_ghg_composition()
    assert any("before 1970 are reconstructions" in n for n in default["notes"])
    explicit = await get_ghg_composition(start_year=2023)
    assert explicit["summary"]["first_year"] == 2023
    assert not any("reconstructions" in n for n in explicit["notes"])
    # a single year is not given a default start either
    assert not any("reconstructions" in n for n in (await get_ghg_composition(year=2024))["notes"])
