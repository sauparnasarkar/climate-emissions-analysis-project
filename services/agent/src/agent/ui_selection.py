"""UI-intent selection -- SPEC.md §3, §8.

The fixed lookup handles every tool with an unambiguous intent, no LLM call. `get_top_emitters`'s
chart-kind pick (§3.1) is also kept deterministic (a keyword heuristic on `current_query`), per
SPEC.md §8's own claim that only `get_country_profile` needs the one LLM judgment call --
`graph.py`'s `ui_selection_node` is the only place that makes that one call.

`WidgetSpec.props` carries the raw tool result through unshaped. Building it into each real
design-system component's exact prop shape (e.g. `SyChart`'s `locations`/`colorValues`) is
Step 4's job, once the renderer exists to consume it -- nothing here would be exercised by a
Step 2 test, so it isn't built yet (see `SPEC.md` §3's "raw result passthrough" note).

`source_tool_call` uses the tool call's cache key (`cache.cache_key`) as its value: unique per
distinct `(tool_name, args)` pair and already computed by `tools_node`, so it traces a widget
back to the record that produced it without adding an id field `SPEC.md` §7's `ToolCallRecord`
doesn't have.
"""

from collections.abc import Callable

from .cache import cache_key
from .progress_labels import join_countries
from .state import ToolCallRecord, WidgetSpec

# Tool -> (intent, chart_kind) for every tool with a single, unambiguous mapping (SPEC.md §3
# table). get_top_emitters and get_country_profile are handled separately below/in graph.py.
# list_countries is excluded -- SPEC.md §3's note: internal resolution context, never its own
# widget.
_TOOL_INTENT: dict[str, tuple[str, str | None]] = {
    "get_historical_emissions": ("chart", "line"),
    "get_scenario_projection": ("chart", "line"),
    "compare_scenarios_across_countries": ("chart", "line"),
    "get_forecast": ("chart", "line"),  # + band CI, both series live in this one widget's props
    "get_forecast_comparison": ("chart", "line"),  # multi-country equivalent of get_forecast
    "get_model_comparison": ("grid", None),
    "get_gas_composition_by_decade": ("grid", None),
    "get_forecast_summary": ("grid", None),
    "get_scenario_cumulative_impact": ("grid", None),
    "get_methodology_notes": ("text", None),
}

_GEOGRAPHIC_MARKERS = ("where", "map", "geographic", "geography", "around the world", "by region")


def select_top_emitters_chart_kind(current_query: str) -> str:
    """SPEC.md §3.1: bar (ranked list, default) or choropleth (geographic spread).

    Corrected in Step 4 (SPEC.md "Corrections applied" #17): the original design also picked
    `treemap` for a query naming both a "current" and a "forecast" concept, sized by one metric
    and colored by the other. `get_top_emitters`'s real result (`composed.py`) carries exactly
    one metric (`co2`) -- a treemap coloring tiles by the same value that sizes them is
    decoration, not a second dimension. A genuine dual-metric treemap needs a merged result from
    two tool calls (`get_top_emitters` + `get_forecast_comparison`), which `ui_selection` doesn't
    build today -- see SPEC.md §12 open item. Until then this heuristic never returns `treemap`."""
    query = current_query.lower()
    if any(marker in query for marker in _GEOGRAPHIC_MARKERS):
        return "choropleth"
    return "bar"


def is_error_result(result) -> bool:
    return isinstance(result, dict) and "error" in result


# Tool -> noun-phrase title builder, one entry per tool `_title_for` covers (every
# `_TOOL_INTENT` entry plus get_top_emitters/get_country_profile, which build their own
# WidgetSpec elsewhere in this file). Deliberately NOT progress_labels.py's `_BUILDERS` --
# those are phrased as an in-progress verb ("Fetching...", "Running...") for the SSE
# progress bar, which is correct there but wrong here: `_title_for`'s output becomes a
# WidgetSpec.title, rendered by the frontend as a *permanent* card/chart header
# (ChartCard/CardHeader), not tied to loading state at all. Reported live: a widget's title
# literally read "Fetching historical emissions for Afghanistan, Albania, ..." forever,
# because it was reusing progress_label's verb-phrased text verbatim.
def _countries_or_scope(args: dict) -> str:
    # get_historical_emissions/get_gas_composition_by_decade/get_forecast_comparison all
    # accept an optional `countries` alongside a `scope` default -- when `countries` is
    # omitted, join_countries(None) alone would render as the generic "the selected
    # countries", silently dropping which scope pool (e.g. sovereign's ~209 vs expanded's
    # ~40) the tool actually used. Copilot review, PR #165.
    countries = args.get("countries")
    return join_countries(countries) if countries else f"{args.get('scope', 'expanded')} scope"


_TITLE_BUILDERS: dict[str, Callable[[dict], str]] = {
    "get_country_profile": lambda args: f"{args.get('country', 'Country')} emissions profile",
    "get_historical_emissions": lambda args: f"Historical emissions -- {_countries_or_scope(args)}",
    "get_gas_composition_by_decade": lambda args: f"Gas composition by decade -- {_countries_or_scope(args)}",
    "get_forecast": lambda args: f"{args.get('country', 'Country')} emissions forecast",
    "get_forecast_summary": lambda args: f"Forecast summary ({args.get('scope', 'featured')})",
    "get_forecast_comparison": lambda args: f"Forecast comparison -- {_countries_or_scope(args)}",
    "get_model_comparison": lambda args: "Model comparison",
    "get_top_emitters": lambda args: f"Top {args.get('n', 10)} emitters ({args.get('year', 'selected year')})",
    "get_scenario_projection": lambda args: (
        f"{args['country']} scenario projection"
        if args.get("country")
        else f"Global scenario projection ({args.get('scope', 'featured')})"
    ),
    "get_scenario_cumulative_impact": lambda args: f"Cumulative scenario impact (sorted by {args.get('sort_by', 'BAU')})",
    "compare_scenarios_across_countries": lambda args: f"Scenario comparison -- {join_countries(args.get('countries'))}",
    "get_methodology_notes": lambda args: "Methodology notes",
}


def _title_for(record: ToolCallRecord) -> str:
    # Deterministic, generated from tool args (SPEC.md §3), noun-phrased for a permanent
    # widget header -- see `_TITLE_BUILDERS`'s own comment for why this is a separate table
    # from progress_labels.py's verb-phrased `_BUILDERS` rather than a reuse of it.
    builder = _TITLE_BUILDERS.get(record.tool_name)
    if builder is None:
        return record.tool_name.replace("_", " ").capitalize()
    return builder(record.args)


def build_widget(record: ToolCallRecord, current_query: str) -> WidgetSpec | None:
    """Builds the widget for every tool except `get_country_profile` (handled in
    `graph.py`'s `ui_selection_node`, since it's the one case needing an LLM judgment call) and
    `list_countries` (never its own widget). Returns `None` for a failed tool call (`result`
    carries an `{"error": ...}` marker) -- no widget should be built from an error payload."""
    if record.tool_name == "list_countries" or is_error_result(record.result):
        return None

    source = cache_key(record.tool_name, record.args)

    if record.tool_name == "get_top_emitters":
        return WidgetSpec(
            intent="chart",
            chart_kind=select_top_emitters_chart_kind(current_query),
            title=_title_for(record),
            source_tool_call=source,
            props=record.result or {},
        )

    if record.tool_name == "get_emissions_change_summary":
        # The one widget whose title is built from `record.result`, not `record.args` (every
        # other title, including _TITLE_BUILDERS above, only ever sees args) -- deliberate,
        # not an oversight. compose_response_node (graph.py) only ever sees a widget's `title`,
        # never `props` (stripped to bound context size for every widget regardless of type),
        # so the real increased/decreased counts have to reach it through title or not at all.
        # Reported live: without this, the agent's answer to "how many countries
        # increased/decreased" couldn't state a real number -- see SPEC.md "Corrections
        # applied" #33.
        r = record.result or {}
        title = (
            f"Emissions change since {r.get('baseline_year', 1990)}: "
            f"{r.get('increased_count', '?')} up, {r.get('decreased_count', '?')} down "
            f"of {r.get('countries_with_data', '?')} countries ({r.get('scope', '')})"
        )
        return WidgetSpec(intent="grid", title=title, source_tool_call=source, props=r)

    intent, chart_kind = _TOOL_INTENT.get(record.tool_name, ("text", None))
    return WidgetSpec(
        intent=intent,
        chart_kind=chart_kind,
        title=_title_for(record),
        source_tool_call=source,
        props=record.result or {},
    )


def build_country_profile_widgets(record: ToolCallRecord, *, include_chart: bool) -> list[WidgetSpec]:
    """The one non-deterministic case (SPEC.md §8): always a `card`, plus a `chart` when the
    LLM judgment call (`graph.py`'s `ui_selection_node`) decides the query is trend-shaped."""
    if is_error_result(record.result):
        return []

    source = cache_key(record.tool_name, record.args)
    widgets = [
        WidgetSpec(
            intent="card",
            title=_title_for(record),
            source_tool_call=source,
            props=record.result or {},
        )
    ]
    if include_chart:
        widgets.append(
            WidgetSpec(
                intent="chart",
                chart_kind="line",
                title=f"{_title_for(record)} -- trend",
                source_tool_call=source,
                props=record.result or {},
            )
        )
    return widgets
