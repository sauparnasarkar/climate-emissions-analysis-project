"""`follow_up_links` -- SPEC.md §15.5.

Real in-app navigation links shown under the latest result (requirement §3.5: follow-ups "linking
into Overview, Forecasts, or Scenario Comparison"). Distinct from `suggested_prompts`, which prefill
the prompt bar and exist only on `opinion` turns.

A fixed tool -> route lookup, never model judgment, so a link can only point at a page that exists.
Routes are the dashboard's own (`climate-dashboard-react/src/App.tsx`); no anchors are used until one
is confirmed in the built page (ENHANCEMENTS.md Section 3 open item b).
"""

from __future__ import annotations

from .state import FollowUpLink, ToolCallRecord
from .ui_selection import is_error_result

MAX_FOLLOW_UP_LINKS = 3

_OVERVIEW = FollowUpLink(label="See this on the Overview", route="/overview")
_OVERVIEW_EMITTERS = FollowUpLink(label="See the top emitters on the Overview", route="/overview")
_CORRELATION = FollowUpLink(label="Explore the Climate Correlation module", route="/climate-correlation")
_CORRELATION_COUNTRY = FollowUpLink(label="Explore country shares in the Climate Correlation module", route="/climate-correlation")
_HISTORICAL = FollowUpLink(label="Open Historical Trends", route="/historical")
_PROFILE = FollowUpLink(label="Open the Country Profile", route="/country-profile")
_FORECASTS = FollowUpLink(label="Open Forecasts", route="/forecasts")
_SCENARIOS = FollowUpLink(label="Compare scenarios", route="/scenarios")

_LINKS_BY_TOOL: dict[str, list[FollowUpLink]] = {
    # Area 2 climate-context tools
    "get_co2_concentration": [_OVERVIEW, _CORRELATION],
    "get_temperature_anomaly": [_OVERVIEW, _CORRELATION],
    "get_emissions_temperature_relationship": [_CORRELATION, _OVERVIEW],
    "get_ghg_composition": [_CORRELATION, _OVERVIEW],
    "get_country_cumulative_share": [_CORRELATION_COUNTRY, _OVERVIEW_EMITTERS],
    "get_scenario_temperature": [_SCENARIOS, _FORECASTS],
    # Emissions-only tools (owner, 2026-10-08: every data answer gets a way into its page)
    "get_historical_emissions": [_HISTORICAL],
    "get_gas_composition_by_decade": [_HISTORICAL],
    "get_country_profile": [_PROFILE],
    "get_forecast": [_FORECASTS],
    "get_forecast_comparison": [_FORECASTS],
    "get_forecast_summary": [_FORECASTS],
    "get_model_comparison": [_FORECASTS],
    "get_scenario_projection": [_SCENARIOS],
    "get_scenario_cumulative_impact": [_SCENARIOS],
    "compare_scenarios_across_countries": [_SCENARIOS],
    "get_top_emitters": [_OVERVIEW_EMITTERS],
    "get_emissions_change_summary": [_OVERVIEW_EMITTERS],
    # No link: methodology text, the metadata record, and the internal country lookup.
}


def follow_up_links(records: list[ToolCallRecord]) -> list[FollowUpLink]:
    """Links for the tools that succeeded this turn: tool-run order, de-duplicated by route (the
    first label wins), at most MAX_FOLLOW_UP_LINKS."""
    out: list[FollowUpLink] = []
    seen: set[str] = set()
    for record in records:
        if is_error_result(record.result):
            continue
        for link in _LINKS_BY_TOOL.get(record.tool_name, []):
            if link.route not in seen:
                seen.add(link.route)
                out.append(link)
    return out[:MAX_FOLLOW_UP_LINKS]
