"""`follow_up_links` -- SPEC.md §15.5, §15.10.

Real in-app navigation links shown under the latest result (requirement §3.5: follow-ups "linking
into Overview, Forecasts, or Scenario Comparison"). Distinct from `suggested_prompts` (prefill the
prompt bar, opinion turns only) and from the follow-up *chips* (prompts, SPEC.md §15.10).

A fixed tool -> route lookup, never model judgment, so a link can only point at a page that exists.
Routes are the dashboard's own paths (`climate-dashboard-react/src/App.tsx`); every hash is an
anchor that page really defines (`*_ANCHOR` constants) -- `tests/test_area2_widgets.py` checks both
against the dashboard's source so a rename there fails here. URL state (countries, year range) is
added by the dashboard's own PR (ENHANCEMENTS.md decision 107); until then pages ignore it.
"""

from __future__ import annotations

from collections.abc import Callable

from .state import FollowUpLink, ToolCallRecord
from .ui_selection import is_error_result

MAX_FOLLOW_UP_LINKS = 3

_OVERVIEW_SIGNAL = FollowUpLink(label="Open in Overview", route="/overview#climate-signal")
_OVERVIEW_RELATIONSHIP = FollowUpLink(label="Open in Overview", route="/overview#relationship")
_OVERVIEW_EMITTERS = FollowUpLink(label="Open in Overview", route="/overview#top-emitters")
_HISTORICAL = FollowUpLink(label="Open in Historical Trends", route="/historical")
_FORECASTS = FollowUpLink(label="Open in Forecasts", route="/forecasts")
_SCENARIOS = FollowUpLink(label="Open in Scenario Comparison", route="/scenarios")


def _correlation(anchor: str) -> FollowUpLink:
    return FollowUpLink(label="Open in Climate Correlation", route=f"/climate-correlation#{anchor}")


def _relationship(record: ToolCallRecord) -> list[FollowUpLink]:
    # The all-gas relationship has its own section; the headline lives under #global-relationship.
    summary = (record.result or {}).get("summary") or {} if isinstance(record.result, dict) else {}
    anchor = "recent-all-gas" if summary.get("source") == "primap_ghg" else "global-relationship"
    return [_correlation(anchor), _OVERVIEW_RELATIONSHIP]


def _profile(record: ToolCallRecord) -> list[FollowUpLink]:
    country = record.args.get("country")
    label = f"Open {country} in Country Profile" if country else "Open in Country Profile"
    return [FollowUpLink(label=label, route="/country-profile")]


def _fixed(*links: FollowUpLink) -> Callable[[ToolCallRecord], list[FollowUpLink]]:
    return lambda record: list(links)


_LINKS_BY_TOOL: dict[str, Callable[[ToolCallRecord], list[FollowUpLink]]] = {
    # Area 2 climate-context tools
    "get_co2_concentration": _fixed(_OVERVIEW_SIGNAL, _correlation("global-relationship")),
    "get_temperature_anomaly": _fixed(_OVERVIEW_SIGNAL, _correlation("global-relationship")),
    "get_emissions_temperature_relationship": _relationship,
    "get_ghg_composition": _fixed(_correlation("gas-composition"), _OVERVIEW_SIGNAL),
    "get_country_cumulative_share": _fixed(_correlation("country-view"), _OVERVIEW_EMITTERS),
    "get_scenario_temperature": _fixed(_correlation("scenarios"), _SCENARIOS),
    # Emissions-only tools (owner, 2026-10-08: every data answer gets a way into its page)
    "get_historical_emissions": _fixed(_HISTORICAL),
    "get_gas_composition_by_decade": _fixed(_HISTORICAL),
    "get_country_profile": _profile,
    "get_forecast": _fixed(_FORECASTS),
    "get_forecast_comparison": _fixed(_FORECASTS),
    "get_forecast_summary": _fixed(_FORECASTS),
    "get_model_comparison": _fixed(_FORECASTS),
    "get_scenario_projection": _fixed(_SCENARIOS),
    "get_scenario_cumulative_impact": _fixed(_SCENARIOS),
    "compare_scenarios_across_countries": _fixed(_SCENARIOS),
    "get_top_emitters": _fixed(_OVERVIEW_EMITTERS),
    "get_emissions_change_summary": _fixed(_OVERVIEW_EMITTERS),
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
        builder = _LINKS_BY_TOOL.get(record.tool_name)
        for link in builder(record) if builder else []:
            if link.route not in seen:
                seen.add(link.route)
                out.append(link)
    return out[:MAX_FOLLOW_UP_LINKS]
