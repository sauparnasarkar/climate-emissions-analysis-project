"""Widget key figures -- SPEC.md §15.11.

`WidgetSpec.summary` is what `compose_response_node` quotes: a small dict of the numbers an answer's
lead should state. Area 2 tools already return one (`summary` in the tool result); the Stage 1
emissions tools do not, so the three that the Ask-page answers lead with get one built here. All
deterministic Python from the tool result -- the model never derives a figure from a series.
"""

from __future__ import annotations

from .state import ToolCallRecord

AREA2_TOOLS = {
    "get_co2_concentration",
    "get_temperature_anomaly",
    "get_correlation_metadata",
    "get_emissions_temperature_relationship",
    "get_ghg_composition",
    "get_country_cumulative_share",
    "get_scenario_temperature",
}
MAX_SUMMARY_SERIES = 12


def _ok(record: ToolCallRecord) -> dict | None:
    r = record.result
    return r if isinstance(r, dict) and "error" not in r else None


def _first_last(values: list, years: list) -> tuple | None:
    pairs = [(y, v) for y, v in zip(years, values) if v is not None]
    return (pairs[0], pairs[-1]) if pairs else None


def _profile_summary(r: dict) -> dict | None:
    fl = _first_last(r.get("co2") or [], r.get("years") or [])
    if fl is None:
        return None
    (y0, v0), (y1, v1) = fl
    table = r.get("table") or []
    yoy = table[-1].get("co2_yoy_pct_change") if table else None
    pc = _first_last(r.get("co2_per_capita") or [], r.get("years") or [])
    return {
        "country": r.get("country"),
        "year": y1,
        "co2_mt": round(v1, 1),
        "per_capita_t": round(pc[1][1], 2) if pc else None,
        "yoy_pct": round(yoy, 1) if yoy is not None else None,
        "first_year": y0,
        "multiple_of_first_year": round(v1 / v0, 1) if v0 else None,
    }


def _historical_summary(r: dict) -> dict | None:
    rows = []
    for s in (r.get("series") or [])[:MAX_SUMMARY_SERIES]:
        fl = _first_last(s.get("values") or [], s.get("years") or [])
        if fl:
            (y0, v0), (y1, v1) = fl
            rows.append({"name": s.get("name"), "first_year": y0, "first_value": round(v0, 1), "last_year": y1, "last_value": round(v1, 1)})
    if not rows:
        return None
    for rank, row in enumerate(sorted(rows, key=lambda x: x["last_value"], reverse=True), start=1):
        row["rank"] = rank
    return {"gas": r.get("gas"), "series": rows}


def _top_emitters_summary(r: dict) -> dict | None:
    emitters = r.get("emitters") or []
    if not emitters:
        return None
    out = {
        "year": r.get("year"),
        "top": [{"rank": i, "name": e.get("country"), "co2": round(e["co2"], 1)} for i, e in enumerate(emitters[:5], start=1)],
    }
    for key in ("n_ranked", "top_n_share_pct", "total_mt"):
        if r.get(key) is not None:
            out[key] = r[key]
    out["top_n"] = len(emitters)
    return out


def _forecast_summary(r: dict) -> dict | None:
    """The forecast snapshot's countries in the order the tool ranked them (`ranked_by`), each with the
    figures an answer quotes -- so "the top 10 forecasted emitters in 2040" is read from the data, not
    from a grid the model never sees."""
    rows = [row for row in (r.get("rows") or []) if row.get("country")]
    if not rows:
        return None
    ranked_by = r.get("ranked_by") or "actual_2020"
    ordered = sorted(rows, key=lambda row: row.get(ranked_by) if row.get(ranked_by) is not None else float("-inf"), reverse=True)
    out = {
        "ranked_by": ranked_by,
        # The scope the tool actually served (not the one requested: the API falls back to the featured ten when its expanded list is missing).
        # 'featured' is the 10 curated countries, 'expanded' the ~40 major emitters; a ranking over the featured ten is a ranking of those ten, not
        # of the world. A result without the field (an older server) is treated as featured, the conservative reading.
        "scope": r.get("effective_scope") or "featured",
        "unit": "Mt CO\u2082",
        "top": [
            {
                "rank": i,
                "name": row["country"],
                "forecast_2030": row.get("forecast_2030"),
                "forecast_2040": row.get("forecast_2040"),
                "actual_2020": row.get("actual_2020"),
                "pct_change_2020_2040": row.get("pct_change_2020_2040"),
            }
            for i, row in enumerate(ordered[:10], start=1)
        ],
        "n_rows": len(rows),
    }
    if r.get("scope_note"):
        out["scope_note"] = r["scope_note"]
    return out


def widget_summary(record: ToolCallRecord) -> dict | None:
    r = _ok(record)
    if r is None:
        return None
    if record.tool_name in AREA2_TOOLS:
        s = r.get("summary")
        return s if isinstance(s, dict) else None
    if record.tool_name == "get_country_profile":
        return _profile_summary(r)
    if record.tool_name == "get_historical_emissions":
        return _historical_summary(r)
    if record.tool_name == "get_top_emitters":
        return _top_emitters_summary(r)
    if record.tool_name == "get_forecast_summary":
        return _forecast_summary(r)
    return None
