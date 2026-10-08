"""SPEC.md §15.2 widgets/titles and §15.5 follow_up_links for the Area 2 tools."""

import json
import re
from pathlib import Path

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


def test_headline_relationship_widget_has_no_generic_chart_kind_and_is_titled_headline():
    # The frontend renders it with the Correlation module's own component, chosen by tool name
    # (ENHANCEMENTS.md decision 105), so there is no generic SyChart kind to name.
    w = build_widget(_rec("get_emissions_temperature_relationship", _relationship("headline long-run relationship (...)", [1850, 2024])), "q")
    assert (w.intent, w.chart_kind) == ("chart", None) and w.title == "Emissions vs. temperature (headline, 1850–2024)"


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


def test_composition_is_a_chart_over_a_range_and_a_grid_for_one_year():
    area = build_widget(_rec("get_ghg_composition", {"summary": {"n_years": 55, "first_year": 1970, "last_year": 2024}}), "q")
    assert (area.intent, area.chart_kind, area.title) == ("chart", None, "Greenhouse-gas mix (1970–2024)")
    one = build_widget(_rec("get_ghg_composition", {"summary": {"n_years": 1, "first_year": 2024}}), "q")
    assert (one.intent, one.chart_kind, one.title) == ("grid", None, "Greenhouse-gas mix, 2024")


def test_country_share_series_is_a_line_and_a_ranking_is_a_bar():
    series = build_widget(_rec("get_country_cumulative_share", {"summary": {"mode": "series", "countries": [{"name": "China"}, {"name": "India"}]}}), "q")
    assert (series.chart_kind, series.title) == ("line", "Cumulative share of emissions – China, India")
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


def _routes(records):
    return [l.route for l in follow_up_links(records)]


def test_area2_tools_link_to_their_confirmed_anchors():
    assert _routes([_rec("get_scenario_temperature", {})]) == ["/climate-correlation#scenarios", "/scenarios"]
    assert _routes([_rec("get_ghg_composition", {})]) == ["/climate-correlation#gas-composition", "/overview#climate-signal"]
    assert _routes([_rec("get_country_cumulative_share", {})]) == ["/climate-correlation#country-view", "/overview#top-emitters"]
    assert _routes([_rec("get_temperature_anomaly", {})]) == ["/overview#climate-signal", "/climate-correlation#global-relationship"]


def test_relationship_link_depends_on_headline_versus_all_gas():
    headline = _rec("get_emissions_temperature_relationship", {"summary": {"source": "owid_co2"}})
    all_gas = _rec("get_emissions_temperature_relationship", {"summary": {"source": "primap_ghg"}})
    assert _routes([headline]) == ["/climate-correlation#global-relationship", "/overview#relationship"]
    assert _routes([all_gas]) == ["/climate-correlation#recent-all-gas", "/overview#relationship"]
    # Not '#relationship' on the correlation page: that is the Overview's anchor (decision 107).
    assert "/climate-correlation#relationship" not in _routes([headline]) + _routes([all_gas])


def test_emissions_only_tools_link_to_their_pages_with_handoff_labels():
    expected = {
        "get_historical_emissions": ("/historical", "Open in Historical Trends"),
        "get_forecast": ("/forecasts", "Open in Forecasts"),
        "get_scenario_projection": ("/scenarios", "Open in Scenario Comparison"),
        "get_top_emitters": ("/overview#top-emitters", "Open in Overview"),
    }
    for tool, (route, label) in expected.items():
        links = follow_up_links([_rec(tool, {})])
        assert [(l.route, l.label) for l in links] == [(route, label)]


def test_country_profile_link_names_the_country():
    links = follow_up_links([_rec("get_country_profile", {}, {"country": "China"})])
    assert [(l.route, l.label) for l in links] == [("/country-profile?country=China", "Open China in Country Profile")]
    bare = follow_up_links([_rec("get_country_profile", {})])[0]
    assert (bare.label, bare.route) == ("Open in Country Profile", "/country-profile")  # no country known: no param


def test_no_links_for_methodology_metadata_or_failed_calls():
    for tool in ("get_methodology_notes", "get_correlation_metadata", "list_countries"):
        assert follow_up_links([_rec(tool, {})]) == []
    assert follow_up_links([_rec("get_forecast", {"error": "boom"})]) == []
    assert follow_up_links([]) == []


def test_links_are_deduplicated_by_route_ordered_by_tool_run_and_capped():
    recs = [_rec("get_top_emitters", {}), _rec("get_temperature_anomaly", {}), _rec("get_scenario_temperature", {})]
    links = follow_up_links(recs)
    routes = [l.route for l in links]
    assert routes == ["/overview#top-emitters", "/overview#climate-signal", "/climate-correlation#global-relationship"]
    assert len(links) == MAX_FOLLOW_UP_LINKS and len(set(routes)) == len(routes)
    # the same route from two tools appears once, with the first tool's label
    twice = follow_up_links([_rec("get_forecast", {}), _rec("get_forecast_summary", {})])
    assert [l.route for l in twice] == ["/forecasts"]


def _dashboard_src() -> Path:
    return Path(__file__).resolve().parents[3] / "climate-dashboard-react" / "src"


def test_every_link_points_at_a_real_dashboard_page_and_a_real_anchor():
    """Read from the dashboard's own source so a renamed page or anchor there fails here, not in
    production. Paths come from App.tsx's <Route>s; hashes from the `*_ANCHOR = '...'` constants."""
    src = _dashboard_src()
    if not src.exists():
        pytest.skip("climate-dashboard-react/src not present")
    pages = set(re.findall(r'path="(/[^"]*)"', (src / "App.tsx").read_text()))
    anchors = {m for f in src.rglob("*.ts*") for m in re.findall(r"_ANCHOR = '([a-z-]+)'", f.read_text())}
    assert {"/overview", "/climate-correlation", "/scenarios", "/forecasts"} <= pages and "global-relationship" in anchors  # the scrape worked
    from agent.follow_ups import _LINKS_BY_TOOL

    probe = ToolCallRecord(tool_name="x", args={"country": "China"}, result={"summary": {"source": "primap_ghg"}}, progress_label="x")
    probe_headline = ToolCallRecord(tool_name="x", args={}, result={"summary": {"source": "owid_co2"}}, progress_label="x")
    for builder in _LINKS_BY_TOOL.values():
        for link in builder(probe) + builder(probe_headline):
            path_and_query, _, anchor = link.route.partition("#")
            path = path_and_query.partition("?")[0]
            assert path in pages, link.route
            assert not anchor or anchor in anchors, link.route


# --- Ask-page polish (design review, decision 108) ---------------------------------------------


def test_top_emitters_title_reads_the_year_from_the_result_not_the_args():
    # The model now omits `year`; the tool defaults to the latest year and reports the one it used.
    w = build_widget(_rec("get_top_emitters", {"year": 2024, "emitters": [{"country": "A", "co2": 1.0}] * 10}, {"n": 10}), "q")
    assert w.title == "Top 10 emitters (2024)"
    explicit = build_widget(_rec("get_top_emitters", {"year": 2000, "emitters": [{"country": "A", "co2": 1.0}] * 3}, {"year": 2000, "n": 5}), "q")
    assert explicit.title == "Top 3 emitters (2000)"  # the count actually returned, not the requested 5
    assert "selected year" not in w.title


def test_no_user_facing_title_uses_a_double_hyphen_or_plain_co2():
    from agent.ui_selection import _RESULT_TITLE_BUILDERS, _TITLE_BUILDERS

    args = {"countries": ["China", "India"], "country": "China", "scope": "expanded", "sort_by": "BAU", "n": 10, "year": 2024}
    rec = lambda name: _rec(name, {"summary": {"mode": "series", "countries": [{"name": "China"}], "n_years": 3, "first_year": 1970, "last_year": 2024}}, args)
    titles = [b(args) for b in _TITLE_BUILDERS.values()] + [b(rec(n)) for n, b in _RESULT_TITLE_BUILDERS.items()]
    assert titles and all(" -- " not in t and "--" not in t and "CO2" not in t for t in titles), titles
    assert "Historical emissions – China, India" in titles


def test_other_user_facing_text_is_free_of_double_hyphens_and_plain_co2():
    from agent.caveats import COMPOSITION_NOTE, LONG_RUN_NOTE, PRELIMINARY_TEMPERATURE_NOTE, SCENARIO_NOTE
    from agent.prompts import OFF_TOPIC_RESPONSE
    from agent.progress_labels import progress_label

    texts = [COMPOSITION_NOTE, LONG_RUN_NOTE, PRELIMINARY_TEMPERATURE_NOTE, SCENARIO_NOTE, OFF_TOPIC_RESPONSE, progress_label("get_co2_concentration", {})]
    assert all("--" not in t and "CO2" not in t for t in texts), texts


def test_profile_card_title_uses_the_resolved_country_not_the_typo():
    from agent.ui_selection import build_country_profile_widgets

    w = build_country_profile_widgets(_rec("get_country_profile", {"country": "China", "years": [1990], "co2": [1.0]}, {"country": "Chinaa"}), include_chart=False)
    assert w[0].title == "China emissions profile"
    # ...and falls back to the arg when the result carries no name
    assert build_country_profile_widgets(_rec("get_country_profile", {"years": [1990]}, {"country": "Chinaa"}), include_chart=False)[0].title == "Chinaa emissions profile"


def test_top_emitters_progress_label_says_latest_year_when_none_is_given():
    from agent.progress_labels import progress_label

    assert progress_label("get_top_emitters", {}) == "Ranking top 10 emitters for the latest year"
    assert progress_label("get_top_emitters", {"year": 2000, "n": 5}) == "Ranking top 5 emitters for 2000"
