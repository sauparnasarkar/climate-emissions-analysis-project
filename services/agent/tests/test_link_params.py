"""URL state on the follow-up links (ENHANCEMENTS.md decision 107, corrected): the params the dashboard pages read."""

import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from agent.follow_ups import MAX_LINK_COUNTRIES, follow_up_links
from agent.state import ToolCallRecord


def _rec(name, result, args=None):
    return ToolCallRecord(tool_name=name, args=args or {}, result=result, progress_label="x")


def _link(rec):
    return follow_up_links([rec])[0]


def _query(route):
    return parse_qs(urlsplit(route).query)


# --- Historical Trends -----------------------------------------------------------------------------


def test_historical_link_carries_the_resolved_countries_in_order():
    r = {"gas": "co2", "series": [{"name": "China"}, {"name": "India"}, {"name": "United States"}]}
    link = _link(_rec("get_historical_emissions", r, {"countries": ["Chinaa", "india"]}))  # the args may hold typos
    assert link.route == "/historical?countries=China&countries=India&countries=United+States"
    assert _query(link.route) == {"countries": ["China", "India", "United States"]}


def test_historical_link_adds_the_gas_only_when_it_is_not_the_default():
    methane = _link(_rec("get_historical_emissions", {"gas": "methane", "series": [{"name": "China"}]}))
    assert _query(methane.route) == {"countries": ["China"], "gas": ["methane"]}
    co2 = _link(_rec("get_historical_emissions", {"gas": "co2", "series": [{"name": "China"}]}))
    assert "gas" not in _query(co2.route)


def test_historical_link_is_capped_at_the_pickers_maximum_and_bare_when_no_series():
    many = {"gas": "co2", "series": [{"name": f"Country{i}"} for i in range(40)]}
    assert len(_query(_link(_rec("get_historical_emissions", many)).route)["countries"]) == MAX_LINK_COUNTRIES
    assert _link(_rec("get_historical_emissions", {"gas": "co2", "series": []})).route == "/historical"


def test_a_country_name_needing_encoding_survives_a_round_trip():
    link = _link(_rec("get_historical_emissions", {"gas": "co2", "series": [{"name": "Côte d'Ivoire & Co"}]}))
    assert _query(link.route)["countries"] == ["Côte d'Ivoire & Co"]


# --- Country Profile, Scenario Comparison, Overview ---------------------------------------------------


def test_country_profile_link_uses_the_resolved_name_not_the_typo():
    link = _link(_rec("get_country_profile", {"country": "China"}, {"country": "Chinaa"}))
    assert link.route == "/country-profile?country=China" and link.label == "Open China in Country Profile"


def test_compare_scenarios_link_carries_the_compared_countries():
    link = _link(_rec("compare_scenarios_across_countries", {"countries": ["China", "India"], "scenarios": {}}))
    assert link.route == "/scenarios?countries=China&countries=India"
    assert _link(_rec("compare_scenarios_across_countries", {"countries": [], "scenarios": {}})).route == "/scenarios"


def test_other_scenario_tools_link_to_the_bare_page():
    assert _link(_rec("get_scenario_cumulative_impact", {"rows": []})).route == "/scenarios"
    assert _link(_rec("get_scenario_projection", {"scenarios": {}})).route == "/scenarios"


def test_top_emitters_carries_the_year_only_when_the_user_asked_for_one():
    named = _link(_rec("get_top_emitters", {"year": 2000, "emitters": []}, {"year": 2000, "n": 10}))
    assert named.route == "/overview?year=2000#top-emitters"
    # the model omitted the year -> the tool used the latest; the link must not pin it
    latest = _link(_rec("get_top_emitters", {"year": 2024, "emitters": []}, {"n": 10}))
    assert latest.route == "/overview#top-emitters"


def test_links_with_different_params_are_different_links_but_the_same_route_dedupes():
    a = _rec("get_historical_emissions", {"gas": "co2", "series": [{"name": "China"}]})
    b = _rec("get_historical_emissions", {"gas": "co2", "series": [{"name": "China"}]})
    assert len(follow_up_links([a, b])) == 1
    c = _rec("get_historical_emissions", {"gas": "co2", "series": [{"name": "India"}]})
    assert len(follow_up_links([a, c])) == 2  # different countries are a genuinely different view


# --- every param is one the dashboard really reads ---------------------------------------------------------


def test_every_param_the_links_use_is_read_by_the_page_they_point_at():
    """Param names are scraped from the dashboard's own source, so a rename there fails here."""
    src = Path(__file__).resolve().parents[3] / "climate-dashboard-react" / "src"
    if not src.exists():
        import pytest

        pytest.skip("climate-dashboard-react/src not present")
    hooks = (src / "hooks" / "useCountrySelection.ts").read_text()
    multi = re.search(r"MULTI_PARAM = '(\w+)'", hooks).group(1)
    single = re.search(r"SINGLE_PARAM = '(\w+)'", hooks).group(1)
    year = re.search(r"PARAM = '(\w+)'", (src / "hooks" / "usePageYear.ts").read_text()).group(1)
    gas = re.search(r"useUrlChoice\('(\w+)'", (src / "pages" / "HistoricalTrendsPage.tsx").read_text()).group(1)
    pages_reading = {
        "/historical": {multi, gas},
        "/scenarios": {multi},
        "/country-profile": {single},
        "/overview": {year},
    }
    # the pages must really call the hooks that read them (not just define them)
    assert "useSelectedCountries" in (src / "pages" / "ScenarioComparisonPage.tsx").read_text()
    assert "useSelectedCountry(" in (src / "pages" / "CountryProfilePage.tsx").read_text()
    assert "usePageYear" in (src / "pages" / "OverviewPage.tsx").read_text()

    from agent.follow_ups import _LINKS_BY_TOOL

    probes = [
        _rec("get_historical_emissions", {"gas": "methane", "series": [{"name": "China"}]}),
        _rec("compare_scenarios_across_countries", {"countries": ["China"]}),
        _rec("get_country_profile", {"country": "China"}),
        _rec("get_top_emitters", {"year": 2000, "emitters": []}, {"year": 2000}),
    ]
    seen = 0
    for rec in probes:
        for link in _LINKS_BY_TOOL[rec.tool_name](rec):
            parts = urlsplit(link.route)
            for key in parse_qs(parts.query):
                seen += 1
                assert key in pages_reading[parts.path], (link.route, key)
    assert seen >= 5  # the probes really exercised params


# --- a scope the page cannot represent (Copilot review of #275) ----------------------------------------------------


def test_a_sovereign_scope_historical_link_omits_the_countries_the_page_cannot_show():
    # The page's picker validates against the expanded list and falls back to its defaults for unknown names, so a link
    # carrying sovereign-only countries would open a different view than the answer.
    r = {"gas": "co2", "series": [{"name": "Bhutan"}, {"name": "Nepal"}]}
    assert _link(_rec("get_historical_emissions", r, {"countries": ["Bhutan", "Nepal"], "scope": "sovereign"})).route == "/historical"


def test_a_sovereign_scope_link_still_carries_the_gas():
    r = {"gas": "methane", "series": [{"name": "Bhutan"}]}
    link = _link(_rec("get_historical_emissions", r, {"scope": "sovereign", "gas": "methane"}))
    assert _query(link.route) == {"gas": ["methane"]}  # countries omitted, gas kept


def test_expanded_featured_and_default_scopes_still_carry_the_countries():
    r = {"gas": "co2", "series": [{"name": "China"}, {"name": "India"}]}
    for args in ({}, {"scope": "expanded"}, {"scope": "featured"}):
        assert _query(_link(_rec("get_historical_emissions", r, args)).route)["countries"] == ["China", "India"], args


def test_scenario_and_profile_links_are_unaffected_because_their_tools_enforce_the_expanded_scope():
    # compare_scenarios_across_countries and get_country_profile resolve every name against the EXPANDED scope in the MCP
    # server, so their results cannot hold a name the page does not know; their links keep their params.
    assert _link(_rec("compare_scenarios_across_countries", {"countries": ["China"], "scenarios": {}})).route == "/scenarios?countries=China"
    assert _link(_rec("get_country_profile", {"country": "China"})).route == "/country-profile?country=China"


# --- the in_expanded_scope flag from the MCP tool (Copilot, second pass on #275) -------------------------------------


def test_a_sovereign_result_carries_exactly_the_names_the_page_can_show():
    # An explicit China at sovereign scope IS representable; Bhutan is not. The blunt "omit all" rule threw China away.
    r = {"gas": "co2", "series": [{"name": "China", "in_expanded_scope": True}, {"name": "Bhutan", "in_expanded_scope": False}, {"name": "India", "in_expanded_scope": True}]}
    link = _link(_rec("get_historical_emissions", r, {"scope": "sovereign"}))
    assert _query(link.route) == {"countries": ["China", "India"]}


def test_a_sovereign_result_with_no_representable_name_opens_the_bare_page():
    r = {"gas": "co2", "series": [{"name": "Bhutan", "in_expanded_scope": False}, {"name": "Nepal", "in_expanded_scope": False}]}
    assert _link(_rec("get_historical_emissions", r, {"scope": "sovereign"})).route == "/historical"


def test_the_flag_wins_over_the_scope_either_way():
    # a flagged-true name is carried even though the scope says sovereign; a flagged-false one is dropped even at expanded scope
    carried = _link(_rec("get_historical_emissions", {"series": [{"name": "China", "in_expanded_scope": True}]}, {"scope": "sovereign"}))
    assert _query(carried.route)["countries"] == ["China"]
    dropped = _link(_rec("get_historical_emissions", {"series": [{"name": "Atlantis", "in_expanded_scope": False}]}, {"scope": "expanded"}))
    assert dropped.route == "/historical"


def test_without_the_flag_an_older_mcp_build_falls_back_to_the_scope_rule():
    r = {"gas": "co2", "series": [{"name": "China"}]}
    assert _link(_rec("get_historical_emissions", r, {"scope": "sovereign"})).route == "/historical"
    assert _query(_link(_rec("get_historical_emissions", r, {"scope": "expanded"})).route)["countries"] == ["China"]
