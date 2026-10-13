"""`follow_up_links` -- SPEC.md §15.5, §15.10.

Real in-app navigation links shown under the latest result (requirement §3.5: follow-ups "linking
into Overview, Forecasts, or Scenario Comparison"). Distinct from `suggested_prompts` (prefill the
prompt bar, opinion turns only) and from the follow-up *chips* (prompts, SPEC.md §15.10).

A fixed tool -> route lookup, never model judgment, so a link can only point at a page that exists.
Routes are the dashboard's own paths (`climate-dashboard-react/src/App.tsx`); every hash is an
anchor that page really defines (`*_ANCHOR` constants) -- `tests/test_area2_widgets.py` checks both
against the dashboard's source so a rename there fails here. URL state (countries, year range) is
carried on the links (ENHANCEMENTS.md decision 107, corrected): `?countries=` (repeated) on Historical Trends and
Scenario Comparison, `?gas=` on Historical Trends, `?country=` on Country Profile, `?year=` on Overview. Values are the
RESOLVED names from the result (the pages canonicalise and drop unknowns). A parameter is omitted when it is the page's
default, so the common link stays clean. No page has a year-range control, so none is carried.
"""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlencode

from .state import FollowUpLink, ToolCallRecord
from .ui_selection import is_error_result, select_share_view

MAX_FOLLOW_UP_LINKS = 3
# The dashboard's pickers cap a selection at this many countries (climate-dashboard-react constants.ts,
# MAX_SELECTED_COUNTRIES); a longer list would be truncated by the page anyway.
MAX_LINK_COUNTRIES = 10
# Country Profile's anchor for its cumulative section (`CUMULATIVE_ANCHOR` in climate-dashboard-react/src/pages/CountryProfilePage.tsx; pinned by tests).
COUNTRY_PROFILE_CUMULATIVE_ANCHOR = "cumulative"

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


def _query(params: list[tuple[str, str]]) -> str:
    return f"?{urlencode(params)}" if params else ""


def _result(record: ToolCallRecord) -> dict:
    return record.result if isinstance(record.result, dict) else {}


def _historical(record: ToolCallRecord) -> list[FollowUpLink]:
    r = _result(record)
    # A sovereign-scope result can hold countries the page cannot show: its picker validates against the EXPANDED list and
    # silently falls back to its defaults for names it does not know, so a link carrying them would open a different view than
    # the answer's. The MCP tool marks each series `in_expanded_scope`; carry exactly the flagged names (an explicit China at
    # sovereign scope is still representable). When the flag is absent (an older MCP build) fall back to the scope: sovereign
    # carries none, anything narrower carries all. The gas is carried regardless: every page knows it.
    scope = record.args.get("scope", "expanded")

    def representable(series: dict) -> bool:
        flag = series.get("in_expanded_scope")
        return flag if isinstance(flag, bool) else scope != "sovereign"

    names = [s["name"] for s in r.get("series") or [] if isinstance(s, dict) and s.get("name") and representable(s)][:MAX_LINK_COUNTRIES]
    params = [("countries", n) for n in names]
    if r.get("gas") and r["gas"] != "co2":  # co2 is the page's default
        params.append(("gas", r["gas"]))
    return [FollowUpLink(label="Open in Historical Trends", route=f"/historical{_query(params)}")]


def _compare_scenarios(record: ToolCallRecord) -> list[FollowUpLink]:
    names = [c for c in _result(record).get("countries") or [] if isinstance(c, str)][:MAX_LINK_COUNTRIES]
    return [FollowUpLink(label="Open in Scenario Comparison", route=f"/scenarios{_query([('countries', n) for n in names])}")]


def _top_emitters(record: ToolCallRecord) -> list[FollowUpLink]:
    # Overview's ?year= is only worth carrying when the user asked for a specific year; the default (latest)
    # needs no parameter, and a link must not pin an old answer to a year that is no longer the latest.
    year = _result(record).get("year") if record.args.get("year") is not None else None
    params = [("year", str(year))] if year else []
    return [FollowUpLink(label="Open in Overview", route=f"/overview{_query(params)}#top-emitters")]


def _profile(record: ToolCallRecord) -> list[FollowUpLink]:
    r = _result(record)
    country = r.get("country") or record.args.get("country")  # the resolved name, not a typo
    label = f"Open {country} in Country Profile" if country else "Open in Country Profile"
    return [FollowUpLink(label=label, route=f"/country-profile{_query([('country', country)] if country else [])}")]


def _share(record: ToolCallRecord, current_query: str = "") -> list[FollowUpLink]:
    """The cumulative-share tool (Release 24.4, R12). A SERIES of OWID shares is what Historical Trends' Cumulative / Share views and Country Profile's
    cumulative section show, so those open with the same countries and the view the answer drew; the page's picker only knows the Expanded set, so only the
    countries the API flags `in_expanded_scope` are carried (a link must not open a different view than the answer's). A ranking, a PRIMAP-hist share, or a
    selection with no Expanded country keeps the two fixed links."""
    r = _result(record)
    summary = r.get("summary") or {}
    fixed = [_correlation("country-view"), _OVERVIEW_EMITTERS]
    # A "since YYYY" answer is the emissions of a period; the pages show totals counted from the first record until they get the counting-from toggle (a link
    # would open numbers that disagree with the answer's), so it keeps the fixed links.
    if summary.get("mode") != "series" or r.get("source") != "owid_co2" or summary.get("since"):
        return fixed
    flagged = [c["name"] for c in summary.get("countries") or [] if isinstance(c, dict) and c.get("name") and c.get("in_expanded_scope") is True][:MAX_LINK_COUNTRIES]
    if not flagged:
        return fixed
    view = "cumulative" if select_share_view(current_query, summary, r.get("source")) == "cumulative_area" else "share"
    links = [FollowUpLink(label="Open in Historical Trends", route=f"/historical{_query([('view', view), *[('countries', n) for n in flagged]])}")]
    if len(flagged) == 1:
        links.append(FollowUpLink(label=f"Open {flagged[0]} in Country Profile", route=f"/country-profile{_query([('country', flagged[0])])}#{COUNTRY_PROFILE_CUMULATIVE_ANCHOR}"))
    return [*links, *fixed]


def _fixed(*links: FollowUpLink) -> Callable[[ToolCallRecord], list[FollowUpLink]]:
    return lambda record: list(links)


_LINKS_BY_TOOL: dict[str, Callable[[ToolCallRecord], list[FollowUpLink]]] = {
    # Area 2 climate-context tools
    "get_co2_concentration": _fixed(_OVERVIEW_SIGNAL, _correlation("global-relationship")),
    "get_temperature_anomaly": _fixed(_OVERVIEW_SIGNAL, _correlation("global-relationship")),
    "get_emissions_temperature_relationship": _relationship,
    "get_ghg_composition": _fixed(_correlation("gas-composition"), _OVERVIEW_SIGNAL),
    "get_country_cumulative_share": _share,
    "get_scenario_temperature": _fixed(_correlation("scenarios"), _SCENARIOS),
    # Emissions-only tools (owner, 2026-10-08: every data answer gets a way into its page)
    "get_historical_emissions": _historical,
    "get_gas_composition_by_decade": _fixed(_HISTORICAL),
    "get_country_profile": _profile,
    "get_forecast": _fixed(_FORECASTS),
    "get_forecast_comparison": _fixed(_FORECASTS),
    "get_forecast_summary": _fixed(_FORECASTS),
    "get_model_comparison": _fixed(_FORECASTS),
    "get_scenario_projection": _fixed(_SCENARIOS),
    "get_scenario_cumulative_impact": _fixed(_SCENARIOS),
    "compare_scenarios_across_countries": _compare_scenarios,
    "get_top_emitters": _top_emitters,
    "get_emissions_change_summary": _fixed(_OVERVIEW_EMITTERS),
    # No link: methodology text, the metadata record, and the internal country lookup.
}


def follow_up_links(records: list[ToolCallRecord], current_query: str = "") -> list[FollowUpLink]:
    """Links for the tools that succeeded this turn: tool-run order, de-duplicated by route (the
    first label wins), at most MAX_FOLLOW_UP_LINKS. `current_query` is only read by the builders whose link depends on what the user asked (the share tool's view)."""
    out: list[FollowUpLink] = []
    seen: set[str] = set()
    for record in records:
        if is_error_result(record.result):
            continue
        builder = _LINKS_BY_TOOL.get(record.tool_name)
        links = _share(record, current_query) if builder is _share else (builder(record) if builder else [])
        for link in links:
            if link.route not in seen:
                seen.add(link.route)
                out.append(link)
    return out[:MAX_FOLLOW_UP_LINKS]
