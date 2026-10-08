"""SPEC.md §15.2 widgets/titles and §15.5 follow_up_links for the Area 2 tools."""

import json

import pytest

from agent.follow_ups import MAX_FOLLOW_UP_LINKS, follow_up_links
from agent.state import ToolCallRecord
from agent.ui_selection import build_widget, select_indicator_intent


def _rec(name, result, args=None):
    return ToolCallRecord(tool_name=name, args=args or {}, result=result, progress_label="x")


def _relationship(label, window, source="owid_co2"):
    return {"points": [{"year": 1}], "summary": {"relationship": label, "window": window, "source": source}}


# --- indicator intent heuristic --------------------------------------------------------------


@pytest.mark.parametrize(
    "query,expected",
    [
        ("What is the latest global temperature anomaly?", "card"),
        ("What is the current CO2 concentration?", "card"),
        ("How has atmospheric CO2 changed over time compared with emissions growth?", "chart"),
        ("Show the temperature trend since 1950", "chart"),
        ("What is the latest reading and how has it changed since 1990?", "chart"),  # trend wins
        ("Tell me about CO2 concentration", "chart"),  # no marker: default to the richer view
    ],
)
def test_indicator_intent_heuristic(query, expected):
    assert select_indicator_intent(query) == expected


def test_indicator_tools_build_a_card_or_a_line_chart_with_result_based_titles():
    result = {"points": [{"year": 1959}], "summary": {"first_year": 1959, "last_year": 2025, "reference": "1850-1900"}}
    chart = build_widget(_rec("get_co2_concentration", result), "how has CO2 changed over time?")
    assert (chart.intent, chart.chart_kind) == ("chart", "line")
    assert chart.title == "Atmospheric CO₂ concentration, ppm (1959–2025)" and chart.props == result
    card = build_widget(_rec("get_temperature_anomaly", result), "what is the latest temperature anomaly?")
    assert (card.intent, card.chart_kind) == ("card", None)
    assert card.title == "Global temperature anomaly, °C vs 1850-1900 (1959–2025)"


# --- relationship titles never mislabel -------------------------------------------------------


def test_headline_relationship_widget_is_a_scatter_titled_headline():
    w = build_widget(_rec("get_emissions_temperature_relationship", _relationship("headline long-run relationship (...)", [1850, 2024])), "q")
    assert (w.intent, w.chart_kind) == ("chart", "scatter") and w.title == "Emissions vs. temperature (headline, 1850–2024)"


def test_all_gas_relationship_is_never_titled_tcre_or_headline():
    w = build_widget(_rec("get_emissions_temperature_relationship", _relationship("recent all-gas relationship (...; never called TCRE)", [1970, 2024], "primap_ghg")), "q")
    assert w.title == "Recent all-gas relationship (1970–2024)"
    assert "TCRE" not in w.title and "headline" not in w.title.lower()


def test_non_preindustrial_owid_window_is_a_selected_window_not_headline():
    w = build_widget(_rec("get_emissions_temperature_relationship", _relationship("selected-window relationship, NOT the headline fit (...)", [1990, 2024])), "q")
    assert w.title == "Emissions vs. temperature (selected window, 1990–2024)" and "headline" not in w.title.lower()


def test_fossil_variant_title():
    w = build_widget(_rec("get_emissions_temperature_relationship", _relationship("secondary fossil-fuel-and-cement-only variant of the headline relationship", [1850, 2024])), "q")
    assert w.title == "Emissions vs. temperature (fossil-only variant, 1850–2024)"


# --- composition, share, scenario, metadata ---------------------------------------------------


def test_composition_is_a_stacked_area_over_a_range_and_a_grid_for_one_year():
    area = build_widget(_rec("get_ghg_composition", {"summary": {"n_years": 55, "first_year": 1970, "last_year": 2024}}), "q")
    assert (area.intent, area.chart_kind, area.title) == ("chart", "area", "Greenhouse-gas mix (1970–2024)")
    one = build_widget(_rec("get_ghg_composition", {"summary": {"n_years": 1, "first_year": 2024}}), "q")
    assert (one.intent, one.chart_kind, one.title) == ("grid", None, "Greenhouse-gas mix, 2024")


def test_country_share_series_is_a_line_and_a_ranking_is_a_bar():
    series = build_widget(_rec("get_country_cumulative_share", {"summary": {"mode": "series", "countries": [{"name": "China"}, {"name": "India"}]}}), "q")
    assert (series.chart_kind, series.title) == ("line", "Cumulative share of emissions -- China, India")
    ranking = build_widget(_rec("get_country_cumulative_share", {"summary": {"mode": "ranking", "year": 2024, "n_rows": 15}}), "q")
    assert (ranking.chart_kind, ranking.title) == ("bar", "Top 15 countries by cumulative share of emissions (2024)")


def test_scenario_temperature_is_a_line_titled_illustrative_and_metadata_is_a_grid():
    s = build_widget(_rec("get_scenario_temperature", {"scenarios": {}}), "q")
    assert (s.intent, s.chart_kind, s.title) == ("chart", "line", "Implied temperature by scenario (illustrative)")
    m = build_widget(_rec("get_correlation_metadata", {"sources": []}), "q")
    assert (m.intent, m.title) == ("grid", "Climate data sources and methodology")


def test_failed_area2_calls_build_no_widget():
    assert build_widget(_rec("get_scenario_temperature", {"error": "503"}), "q") is None


# --- follow_up_links --------------------------------------------------------------------------


def test_area2_tools_link_to_their_pages():
    assert [l.route for l in follow_up_links([_rec("get_scenario_temperature", {})])] == ["/scenarios", "/forecasts"]
    assert [l.route for l in follow_up_links([_rec("get_emissions_temperature_relationship", {})])] == ["/climate-correlation", "/overview"]


def test_emissions_only_tools_link_to_their_pages_too():
    expected = {
        "get_historical_emissions": "/historical",
        "get_country_profile": "/country-profile",
        "get_forecast": "/forecasts",
        "get_scenario_projection": "/scenarios",
        "get_top_emitters": "/overview",
    }
    for tool, route in expected.items():
        assert [l.route for l in follow_up_links([_rec(tool, {})])] == [route]


def test_no_links_for_methodology_metadata_or_failed_calls():
    for tool in ("get_methodology_notes", "get_correlation_metadata", "list_countries"):
        assert follow_up_links([_rec(tool, {})]) == []
    assert follow_up_links([_rec("get_forecast", {"error": "boom"})]) == []
    assert follow_up_links([]) == []


def test_links_are_deduplicated_by_route_ordered_by_tool_run_and_capped():
    recs = [_rec("get_top_emitters", {}), _rec("get_temperature_anomaly", {}), _rec("get_scenario_temperature", {})]
    links = follow_up_links(recs)
    routes = [l.route for l in links]
    assert routes == ["/overview", "/climate-correlation", "/scenarios"]  # /overview once, first label wins
    assert links[0].label == "See the top emitters on the Overview"
    assert len(links) == MAX_FOLLOW_UP_LINKS and len(set(routes)) == len(routes)


def test_every_route_is_a_real_dashboard_page():
    # The page paths in climate-dashboard-react/src/App.tsx; a typo here would ship a dead link.
    real = {"/overview", "/historical", "/country-profile", "/forecasts", "/scenarios", "/climate-correlation"}
    from agent.follow_ups import _LINKS_BY_TOOL

    assert {l.route for links in _LINKS_BY_TOOL.values() for l in links} <= real


def test_share_ranking_title_without_a_row_count_still_reads_cleanly():
    w = build_widget(_rec("get_country_cumulative_share", {"summary": {"mode": "ranking", "year": 2024}}), "q")
    assert w.title == "Countries by cumulative share of emissions (2024)"
