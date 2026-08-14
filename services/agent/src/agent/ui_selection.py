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

from .cache import cache_key
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
    "get_model_comparison": ("grid", None),
    "get_gas_composition_by_decade": ("grid", None),
    "get_forecast_summary": ("grid", None),
    "get_scenario_cumulative_impact": ("grid", None),
    "get_methodology_notes": ("text", None),
}

_GEOGRAPHIC_MARKERS = ("where", "map", "geographic", "geography", "around the world", "by region")
_CURRENT_MARKERS = ("now", "current", "today", "currently")
_FORECAST_MARKERS = ("forecast", "forecasted", "projected", "future")


def select_top_emitters_chart_kind(current_query: str) -> str:
    """SPEC.md §3.1: bar (ranked list, default), choropleth (geographic spread), or treemap
    (current size vs. a second/forecast metric -- only when the query names *both* a "current"
    concept and a "forecast" concept together; "forecasted emitters in 2040" alone is still a
    single-metric ranked list, i.e. still `bar`)."""
    query = current_query.lower()
    if any(marker in query for marker in _GEOGRAPHIC_MARKERS):
        return "choropleth"
    has_current = any(marker in query for marker in _CURRENT_MARKERS)
    has_forecast = any(marker in query for marker in _FORECAST_MARKERS)
    if has_current and has_forecast:
        return "treemap"
    return "bar"


def is_error_result(result) -> bool:
    return isinstance(result, dict) and "error" in result


def _title_for(record: ToolCallRecord) -> str:
    # Deterministic, generated from tool args (SPEC.md §3) -- reuses progress_label's phrasing
    # convention but titlecased for display; exact copy is a Step 4/frontend concern once the
    # renderer exists to show it.
    from .progress_labels import progress_label

    return progress_label(record.tool_name, record.args)


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
