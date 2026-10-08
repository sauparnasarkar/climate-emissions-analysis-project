"""SPEC.md §15.11: summaries, KPIs, scenario lead, source lines and prompt chips."""

from agent.follow_up_prompts import MAX_FOLLOW_UP_PROMPTS, P_REL, P_SCEN, follow_up_prompts
from agent.kpis import build_kpis, scenario_lead
from agent.source_lines import source_line
from agent.state import ToolCallRecord
from agent.summaries import widget_summary
from agent.ui_selection import SCENARIO_BADGE, build_widget


def _rec(name, result, args=None):
    return ToolCallRecord(tool_name=name, args=args or {}, result=result, progress_label="x")


PROFILE = {
    "country": "China",
    "years": [1990, 2023, 2024],
    "co2": [2483.5, 12166.0, 12289.0],
    "co2_per_capita": [2.15, 8.5, 8.66],
    "table": [{"year": 2024, "co2": 12289.0, "co2_per_capita": 8.66, "co2_yoy_pct_change": 1.01}],
}
TOP = {"year": 2024, "emitters": [{"country": "China", "co2": 12289.0}, {"country": "United States", "co2": 4900.0}], "n_ranked": 218, "total_mt": 37000.0, "top_n_share_pct": 46.5}


# --- summaries ------------------------------------------------------------------------------------


def test_profile_summary_has_the_latest_figures_and_the_multiple_of_the_first_year():
    s = widget_summary(_rec("get_country_profile", PROFILE))
    assert s == {"country": "China", "year": 2024, "co2_mt": 12289.0, "per_capita_t": 8.66, "yoy_pct": 1.0, "first_year": 1990, "multiple_of_first_year": 4.9}


def test_historical_summary_ranks_series_by_latest_value_and_skips_null_ends():
    result = {"gas": "co2", "series": [
        {"name": "India", "years": [1990, 2024], "values": [578.0, 3200.0]},
        {"name": "China", "years": [1990, 2023, 2024], "values": [2483.5, 12166.0, None]},  # trailing null: last valid is 2023
        {"name": "Empty", "years": [1990], "values": [None]},
    ]}
    rows = {r["name"]: r for r in widget_summary(_rec("get_historical_emissions", result))["series"]}
    assert rows["China"]["last_year"] == 2023 and rows["China"]["rank"] == 1 and rows["India"]["rank"] == 2 and "Empty" not in rows


def test_top_emitters_summary_carries_the_share_fields_when_present_and_omits_them_when_not():
    s = widget_summary(_rec("get_top_emitters", TOP))
    assert s["top_n_share_pct"] == 46.5 and s["n_ranked"] == 218 and s["top"][0] == {"rank": 1, "name": "China", "co2": 12289.0}
    old = widget_summary(_rec("get_top_emitters", {"year": 2020, "emitters": TOP["emitters"]}))
    assert "top_n_share_pct" not in old and old["top_n"] == 2


def test_area2_summary_passes_through_and_failures_and_other_tools_have_none():
    assert widget_summary(_rec("get_temperature_anomaly", {"summary": {"last_value": 1.45}})) == {"last_value": 1.45}
    assert widget_summary(_rec("get_country_profile", {"error": "x"})) is None
    assert widget_summary(_rec("get_forecast", {"anything": 1})) is None


# --- KPIs -----------------------------------------------------------------------------------------


def test_profile_kpis_match_the_handoffs_three_cards_from_the_data():
    kpis = build_kpis([_rec("get_country_profile", PROFILE, {"country": "China"})])
    assert [(k.label, k.value, k.unit, k.decimals, k.year) for k in kpis] == [
        ("CO₂ emissions", 12289.0, "Mt", 0, 2024),
        ("Per capita", 8.66, "t", 2, 2024),
        ("Change vs 2023", 1.0, "%", 1, 2024),
    ]
    assert kpis[0].sub is None  # no ranking in this turn: the rank is not guessed
    assert kpis[2].sub == "4.9× the 1990 level"


def test_rank_sub_comes_from_a_same_year_top_emitters_result_only():
    with_rank = build_kpis([_rec("get_top_emitters", TOP), _rec("get_country_profile", PROFILE)])
    assert with_rank[0].sub == "Largest of 218 countries"
    second = {**PROFILE, "country": "United States"}
    assert build_kpis([_rec("get_top_emitters", TOP), _rec("get_country_profile", second)])[0].sub == "#2 of 218 countries"
    other_year = {**TOP, "year": 2020}
    assert build_kpis([_rec("get_top_emitters", other_year), _rec("get_country_profile", PROFILE)])[0].sub is None


def test_indicator_and_scenario_kpis():
    t = build_kpis([_rec("get_temperature_anomaly", {"summary": {"last_value": 1.451, "last_year": 2025, "reference": "1850-1900"}})])
    assert (t[0].label, t[0].value, t[0].year, t[0].sub) == ("Temperature anomaly", 1.451, 2025, "vs 1850-1900")
    c = build_kpis([_rec("get_co2_concentration", {"summary": {"last_value": 427.35, "last_year": 2025}})])
    assert (c[0].unit, c[0].decimals) == ("ppm", 1)
    assert build_kpis([_rec("get_scenario_temperature", {"summary": {"final_year_by_scenario": {"Aggressive": {"year": 2040, "headline_level_c": 1.58}, "BAU": {"year": 2040, "headline_level_c": 1.68, "annual_global_fossil_mt": 44877.4}}}})])[0].series == "BAU"


def test_kpis_are_capped_at_three_and_failures_are_skipped():
    many = [_rec("get_country_profile", PROFILE), _rec("get_temperature_anomaly", {"summary": {"last_value": 1.4, "last_year": 2025}})]
    assert len(build_kpis(many)) == 3
    assert build_kpis([_rec("get_country_profile", {"error": "x"})]) == []


# --- deterministic scenario lead ------------------------------------------------------------------


_SCEN = {"reading_note": "Note.", "summary": {"final_year_by_scenario": {
    "BAU": {"year": 2040, "headline_level_c": 1.68}, "Moderate": {"year": 2040, "headline_level_c": 1.64}, "Aggressive": {"year": 2040, "headline_level_c": 1.58}}}}


def test_scenario_lead_states_the_range_then_the_pipelines_own_note():
    assert scenario_lead([_rec("get_scenario_temperature", _SCEN)]) == (
        "By 2040 the platform's three emissions pathways imply 1.58–1.68 °C above 1850–1900. Note."
    )


def test_scenario_lead_only_when_the_scenario_result_is_the_only_data():
    other = _rec("get_top_emitters", TOP)
    assert scenario_lead([_rec("get_scenario_temperature", _SCEN), other]) is None
    assert scenario_lead([_rec("list_countries", {}), _rec("get_scenario_temperature", _SCEN)]) is not None  # lookups don't count
    assert scenario_lead([_rec("get_scenario_temperature", {"error": "503"})]) is None


def test_scenario_lead_for_a_subset_omits_the_all_pathway_note_and_for_fossil_only_defers():
    one = {"reading_note": "Note.", "summary": {"final_year_by_scenario": {"Aggressive": {"year": 2040, "headline_level_c": 1.58}}}}
    assert scenario_lead([_rec("get_scenario_temperature", one)]) == "By 2040 the Aggressive pathway implies 1.58 °C above 1850–1900."
    fossil = {"reading_note": "Note.", "summary": {"final_year_by_scenario": {"BAU": {"year": 2040, "headline_level_c": None}}}}
    assert scenario_lead([_rec("get_scenario_temperature", fossil)]) is None


# --- source lines ---------------------------------------------------------------------------------


def test_owid_lines_state_the_land_use_scope_and_read_the_coverage_from_the_data():
    line = source_line(_rec("get_country_profile", PROFILE))
    assert line == "Source: OWID, 1990–2024 · territorial CO₂ from fossil fuels and cement; land-use change excluded"
    assert source_line(_rec("get_top_emitters", TOP)).startswith("Source: OWID, 2024")
    methane = {"gas": "methane", "gas_label": "methane", "series": [{"years": [1990, 2024]}]}
    assert "land-use" not in source_line(_rec("get_historical_emissions", methane)) and "methane" in source_line(_rec("get_historical_emissions", methane))


def test_headline_relationship_line_says_land_use_is_included_and_fossil_variant_says_excluded():
    head = source_line(_rec("get_emissions_temperature_relationship", {"summary": {"relationship": "headline long-run relationship (...)", "window": [1850, 2024]}}))
    assert "land use" in head and "land use excluded" not in head and "1850–2024" in head and "preliminary release" in head
    fossil = source_line(_rec("get_emissions_temperature_relationship", {"summary": {"relationship": "secondary fossil-fuel-and-cement-only variant", "window": [1850, 2024]}}))
    assert "land use excluded" in fossil


def test_all_gas_and_other_area2_lines():
    gas = source_line(_rec("get_emissions_temperature_relationship", {"summary": {"relationship": "recent all-gas relationship (...)", "window": [1970, 2024]}}))
    assert "PRIMAP-hist" in gas and "1970–2024" in gas and "TCRE" not in gas
    assert "1959" in source_line(_rec("get_co2_concentration", {"details": {"splice": {"splice_year": 1959}}}))
    assert "preliminary release" in source_line(_rec("get_temperature_anomaly", {"summary": {"reference": "1850-1900"}}))
    assert "PRIMAP-hist" in source_line(_rec("get_country_cumulative_share", {"source": "primap_hist", "gas_scope": "total_ghg"}))
    assert "OWID" in source_line(_rec("get_country_cumulative_share", {"source": "owid_co2"}))


def test_no_source_line_for_methodology_metadata_or_failed_calls():
    assert source_line(_rec("get_methodology_notes", {"a": 1})) is None
    assert source_line(_rec("get_correlation_metadata", {"a": 1})) is None
    assert source_line(_rec("get_country_profile", {"error": "x"})) is None


def test_build_widget_attaches_source_summary_and_the_scenario_badge():
    w = build_widget(_rec("get_country_profile", PROFILE), "q")
    assert w.source_line.startswith("Source: OWID") and w.summary["co2_mt"] == 12289.0 and w.badge is None
    s = build_widget(_rec("get_scenario_temperature", _SCEN), "q")
    assert s.badge == SCENARIO_BADGE and "climate-model projections" in s.badge


# --- follow-up prompt chips -----------------------------------------------------------------------


def test_a_country_trend_leads_to_that_countrys_share_then_the_climate_relationship():
    chips = follow_up_prompts([_rec("get_historical_emissions", {"series": [{"name": "China"}]}, {"countries": ["China", "India"]})], "q")
    assert chips[0] == "What share of historical emissions comes from China?" and P_REL in chips and len(chips) <= MAX_FOLLOW_UP_PROMPTS


def test_chips_skip_the_current_query_and_anything_the_turn_already_answered():
    ran = [_rec("get_emissions_temperature_relationship", {"summary": {}})]
    assert P_REL not in follow_up_prompts(ran, "q")  # the relationship tool already ran
    asked = follow_up_prompts([_rec("get_forecast", {})], P_SCEN.upper())  # case-insensitive match to the query
    assert P_SCEN not in asked
    share_ran = [_rec("get_country_profile", PROFILE, {"country": "China"}), _rec("get_country_cumulative_share", {"rows": []})]
    assert not any(p.startswith("What share of historical") for p in follow_up_prompts(share_ran, "q"))


def test_chips_are_deduplicated_capped_and_empty_for_methodology_or_failures():
    recs = [_rec("get_forecast", {}), _rec("get_scenario_projection", {})]
    chips = follow_up_prompts(recs, "q")
    assert len(chips) == len(set(chips)) <= MAX_FOLLOW_UP_PROMPTS
    assert follow_up_prompts([_rec("get_methodology_notes", {})], "q") == []
    assert follow_up_prompts([_rec("get_forecast", {"error": "x"})], "q") == []


# --- fossil-only / headline-only scenario lines (Copilot review of #270) -----------------------


def _scenario_result(line, headline, fossil):
    f = {"year": 2040, "headline_level_c": headline, "fossil_only_level_c": fossil, "annual_global_fossil_mt": 44877.4}
    return {"line": line, "summary": {"line": line, "final_year_by_scenario": {"BAU": f}}}


def test_fossil_only_scenario_still_gets_kpi_cards_and_says_which_line():
    kpis = build_kpis([_rec("get_scenario_temperature", _scenario_result("fossil_only", None, 1.823))])
    assert [(k.label, k.value, k.series) for k in kpis] == [("BAU", 1.823, "BAU")]
    assert kpis[0].sub == "44,877 MtCO\u2082 a year \u00b7 fossil-only line"


def test_headline_scenario_kpis_use_the_headline_level_and_do_not_mention_fossil():
    k = build_kpis([_rec("get_scenario_temperature", _scenario_result("both", 1.68, 1.82))])[0]
    assert k.value == 1.68 and "fossil" not in (k.sub or "")


def test_scenario_source_line_names_the_slope_that_was_actually_used():
    line = lambda name: source_line(_rec("get_scenario_temperature", _scenario_result(name, 1.7, 1.8)))
    assert "fossil-only regression slope" in line("fossil_only") and "headline" not in line("fossil_only")
    assert "the headline regression slope \u00b7" in line("headline")
    assert "headline regression slope (with a fossil-only second line)" in line("both")


# --- live-walkthrough fixes (ENHANCEMENTS.md Step 3.6): forecast ranking and cumulative units -----------------


def _forecast_rows(n=12):
    return [
        {"country": f"C{i}", "actual_2020": 100.0 - i, "forecast_2030": 5.0 * i, "forecast_2035": 6.0 * i,
         "forecast_2040": 10.0 * i, "pct_change_2020_2040": 2.5 * i}
        for i in range(n)
    ]


def test_forecast_summary_ranks_by_the_column_the_tool_used_and_carries_the_figures():
    rows = _forecast_rows(10)
    s = widget_summary(_rec("get_forecast_summary", {"rows": rows, "ranked_by": "forecast_2040"}))
    assert s["ranked_by"] == "forecast_2040" and s["unit"].startswith("Mt")
    # C9 has the largest 2040 forecast although C0 has the largest 2020 actual: the summary follows ranked_by.
    assert [t["name"] for t in s["top"]][:3] == ["C9", "C8", "C7"]
    assert s["top"][0]["forecast_2040"] == 90.0 and s["top"][0]["rank"] == 1
    assert widget_summary(_rec("get_forecast_summary", {"rows": []})) is None


def test_forecast_kpis_are_the_three_largest_2040_forecasts_and_only_when_the_ranking_is_trustworthy():
    ranked = _rec("get_forecast_summary", {"rows": _forecast_rows(10), "ranked_by": "forecast_2040", "scope_note": "capped"})
    kpis = build_kpis([ranked])
    assert [k.label for k in kpis] == ["#1 C9", "#2 C8", "#3 C7"]
    assert kpis[0].value == 90.0 and kpis[0].year == 2040 and kpis[0].sub == "+22.5% vs 2020"
    # Capped by the 2020 actuals: the top three by 2040 inside that set could be wrong globally -> no cards.
    capped_wrong = _rec("get_forecast_summary", {"rows": _forecast_rows(10), "ranked_by": "actual_2020", "scope_note": "capped"})
    assert build_kpis([capped_wrong]) == []
    # Nothing capped (no scope_note): the set is complete, so ranking it here is sound.
    assert len(build_kpis([_rec("get_forecast_summary", {"rows": _forecast_rows(5), "ranked_by": "actual_2020"})])) == 3


RELATIONSHIP = {
    "summary": {
        "window": [1850, 2024],
        "baseline": "preindustrial",
        "first_pair": {"year": 1850, "cumulative_emissions": 2910.87, "temperature": -0.0757},
        "last_pair": {"year": 2024, "cumulative_emissions": 2751504.433, "temperature": 1.5503},
        "cumulative": {"unit": "GtCO₂", "first_year": 1850, "first": 3, "last_year": 2024, "last": 2752},
        "fit": {"slope": 0.4856, "ci95_hac": [0.4416, 0.5297], "r_squared": 0.888, "unit": "°C per 1,000 GtCO₂"},
    }
}


def test_relationship_kpis_state_cumulative_emissions_in_gt_not_the_raw_mt_pair():
    kpis = build_kpis([_rec("get_emissions_temperature_relationship", RELATIONSHIP)])
    assert [k.label for k in kpis] == ["Cumulative emissions", "Warming", "Slope"]
    cum, warm, slope = kpis
    assert (cum.value, cum.unit, cum.year, cum.sub) == (2752, "GtCO₂", 2024, "since 1850")
    assert (warm.value, warm.unit, warm.sub) == (1.5503, "°C", "vs 1850–1900")
    assert slope.unit == "°C per 1,000 GtCO₂" and "95% interval 0.44–0.53" in slope.sub and "R² 0.89" in slope.sub
    assert all(k.value != 2751504.433 for k in kpis)


def test_relationship_kpis_degrade_without_a_fit():
    no_fit = {"summary": {**RELATIONSHIP["summary"], "fit": None}}
    assert [k.label for k in build_kpis([_rec("get_emissions_temperature_relationship", no_fit)])] == ["Cumulative emissions", "Warming"]


def test_warming_card_always_says_1850_1900_whatever_the_emissions_window():
    # The all-gas relationship starts its cumulative emissions in 1970, but the temperature is still the anomaly vs 1850-1900.
    all_gas = {"summary": {**RELATIONSHIP["summary"], "source": "primap_ghg", "baseline": "1970", "window": [1970, 2024]}}
    warming = next(k for k in build_kpis([_rec("get_emissions_temperature_relationship", all_gas)]) if k.label == "Warming")
    assert warming.sub == "vs 1850\u20131900"
