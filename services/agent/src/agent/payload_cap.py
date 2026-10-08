"""Model-facing payload cap -- SPEC.md §15.4.

The widget needs a tool's full series; the model does not. `tools_node` stores every result in
full in `ToolCallRecord.result` (the widget's source and the thread cache's value) and hands the
model the capped copy built here. The MCP tools deliberately return full data (mcp-server
SPEC.md §5.1 convention 3), so this server-agnostic trimming lives on the agent side.

What is capped is only what the model cannot use: long evenly-sampled series (its `summary`,
`fit` and envelope already describe the full series), and bulky provenance/diagnostic blocks that
answer no question (per-source methodology prose, the land-use weight scan). Envelope fields
(`note`, `caveats`, `attribution`) and every `summary` are never touched. Tools not listed here
(all the Stage 1 emissions tools) pass through unchanged.
"""

from __future__ import annotations

import copy
from typing import Any

MODEL_POINT_CAP = 25
SAMPLE_NOTE = (
    "Long series are shown to you as an evenly spaced sample (first and last always included); "
    "`summary`, `fit` and the `*_total` counts describe the full series."
)
# Source-record fields that are long prose or URLs, not answer material; the licence, coverage,
# release and caveats stay.
_SOURCE_DROP = ("methodology", "citations", "required_citation_format", "source_urls", "land_use_license_note")


def sample_evenly(items: list, cap: int = MODEL_POINT_CAP) -> list:
    n = len(items)
    if n <= cap:
        return items
    indices = sorted({round(i * (n - 1) / (cap - 1)) for i in range(cap)})
    return [items[i] for i in indices]


def _cap_list(container: dict, key: str, total_key: str, shown_key: str) -> bool:
    items = container.get(key)
    if not isinstance(items, list) or len(items) <= MODEL_POINT_CAP:
        return False
    container[total_key], container[shown_key] = len(items), MODEL_POINT_CAP
    container[key] = sample_evenly(items)
    container[shown_key] = len(container[key])
    return True


def _cap_points(result: dict) -> bool:
    return _cap_list(result, "points", "points_total", "points_shown")


def _cap_relationship(result: dict) -> bool:
    changed = _cap_points(result)
    ctx = result.get("fit_context")
    if isinstance(ctx, dict) and "land_use_weight_scan" in ctx:
        ctx["land_use_weight_scan"] = "omitted from this view (diagnostic); ask for the methodology to see it"
        changed = True
    return changed


def _cap_composition(result: dict) -> bool:
    return _cap_list(result, "years", "years_total", "years_shown")


def _cap_share(result: dict) -> bool:
    changed = False
    for series in result.get("series") or []:
        if isinstance(series, dict):
            changed |= _cap_points(series)
    return changed


def _cap_metadata(result: dict) -> bool:
    changed = False
    for source in result.get("sources") or []:
        if isinstance(source, dict):
            for field in _SOURCE_DROP:
                changed |= source.pop(field, None) is not None
    return changed


def _cap_methodology(result: dict) -> bool:
    ctx = (result.get("headline_derivation") or {}).get("fit_context")
    if isinstance(ctx, dict) and "land_use_weight_scan" in ctx:
        ctx["land_use_weight_scan"] = "omitted from this view (diagnostic)"
        return True
    return False


_CAPPERS = {
    "get_co2_concentration": _cap_points,
    "get_temperature_anomaly": _cap_points,
    "get_emissions_temperature_relationship": _cap_relationship,
    "get_ghg_composition": _cap_composition,
    "get_country_cumulative_share": _cap_share,
    "get_correlation_metadata": _cap_metadata,
    "get_methodology_notes": _cap_methodology,
}


def cap_for_model(tool_name: str, result: Any) -> tuple[Any, bool]:
    """(what the model sees, whether anything was trimmed). The input is never mutated."""
    capper = _CAPPERS.get(tool_name)
    if capper is None or not isinstance(result, dict) or "error" in result:
        return result, False
    view = copy.deepcopy(result)
    if not capper(view):
        return result, False
    view["model_view_note"] = SAMPLE_NOTE
    return view, True
