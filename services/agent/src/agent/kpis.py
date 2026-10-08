"""KPI row and deterministic scenario lead -- SPEC.md §15.11.

Built from tool results only. The KPI cards reproduce the Ask-page handoff's three kinds of row (a
country's latest emissions/per-capita/change, the latest climate readings, the scenario levels) with
the figures read from the data -- the handoff's own numbers were mock or pre-migration.
"""

from __future__ import annotations

from .state import Kpi, ToolCallRecord
from .summaries import widget_summary

MAX_KPIS = 3
SCENARIO_ORDER = ("BAU", "Moderate", "Aggressive")
PREINDUSTRIAL = "1850–1900"


def _ok(record: ToolCallRecord) -> dict | None:
    r = record.result
    return r if isinstance(r, dict) and "error" not in r else None


def _rank_sub(country: str | None, year: int | None, records: list[ToolCallRecord]) -> str | None:
    """'Largest of N countries' / '#k of N countries' -- only when a top-emitters result for the SAME
    year ranks this country (otherwise the rank would be a guess)."""
    for rec in records:
        r = _ok(rec)
        if rec.tool_name != "get_top_emitters" or r is None or r.get("year") != year or not r.get("n_ranked"):
            continue
        for i, e in enumerate(r.get("emitters") or [], start=1):
            if e.get("country") == country:
                return f"Largest of {r['n_ranked']} countries" if i == 1 else f"#{i} of {r['n_ranked']} countries"
    return None


def _profile_kpis(rec: ToolCallRecord, records: list[ToolCallRecord]) -> list[Kpi]:
    s = widget_summary(rec)
    if not s:
        return []
    year = s["year"]
    out = [Kpi(label="CO₂ emissions", value=s["co2_mt"], unit="Mt", decimals=0, year=year, sub=_rank_sub(s["country"], year, records))]
    if s.get("per_capita_t") is not None:
        out.append(Kpi(label="Per capita", value=s["per_capita_t"], unit="t", decimals=2, year=year))
    if s.get("yoy_pct") is not None:
        sub = f"{s['multiple_of_first_year']}× the {s['first_year']} level" if s.get("multiple_of_first_year") else None
        out.append(Kpi(label=f"Change vs {year - 1}", value=s["yoy_pct"], unit="%", decimals=1, year=year, sub=sub))
    return out


def _indicator_kpi(rec: ToolCallRecord) -> list[Kpi]:
    s = widget_summary(rec)
    if not s or s.get("last_value") is None:
        return []
    if rec.tool_name == "get_co2_concentration":
        return [Kpi(label="CO₂ concentration", value=s["last_value"], unit="ppm", decimals=1, year=s["last_year"])]
    return [Kpi(label="Temperature anomaly", value=s["last_value"], unit="°C", decimals=2, year=s["last_year"], sub=f"vs {s.get('reference', '1850-1900')}")]


def _scenario_kpis(rec: ToolCallRecord) -> list[Kpi]:
    s = widget_summary(rec) or {}
    final = s.get("final_year_by_scenario") or {}
    out = []
    for name in SCENARIO_ORDER:
        f = final.get(name)
        if not f or f.get("headline_level_c") is None:
            continue
        mt = f.get("annual_global_fossil_mt")
        out.append(
            Kpi(
                label=name,
                value=f["headline_level_c"],
                unit="°C",
                decimals=2,
                year=f.get("year"),
                sub=f"{mt:,.0f} MtCO₂ a year" if mt is not None else None,
                series=name,
            )
        )
    return out


def build_kpis(records: list[ToolCallRecord]) -> list[Kpi]:
    out: list[Kpi] = []
    for rec in records:
        if _ok(rec) is None:
            continue
        if rec.tool_name == "get_country_profile":
            out += _profile_kpis(rec, records)
        elif rec.tool_name in ("get_co2_concentration", "get_temperature_anomaly"):
            out += _indicator_kpi(rec)
        elif rec.tool_name == "get_scenario_temperature":
            out += _scenario_kpis(rec)
    return out[:MAX_KPIS]


def scenario_lead(records: list[ToolCallRecord]) -> str | None:
    """The deterministic lead for a scenario-temperature answer: one sentence from the result's own
    summary, then the pipeline's `reading_note` verbatim (ENHANCEMENTS.md decision 43). Only when the
    scenario translation is the turn's only data result -- otherwise the LLM composes across tools."""
    data = [r for r in records if r.tool_name != "list_countries" and _ok(r) is not None]
    if len(data) != 1 or data[0].tool_name != "get_scenario_temperature":
        return None
    result = _ok(data[0]) or {}
    final = (widget_summary(data[0]) or {}).get("final_year_by_scenario") or {}
    levels = {n: f["headline_level_c"] for n, f in final.items() if f.get("headline_level_c") is not None}
    if not levels:
        return None  # e.g. line='fossil_only': no headline levels to state
    year = next(iter(final.values())).get("year")
    if len(levels) == 1:
        (name, level), = levels.items()
        first = f"By {year} the {name} pathway implies {level:.2f} °C above {PREINDUSTRIAL}."
    else:
        words = {2: "two", 3: "three"}.get(len(levels), str(len(levels)))
        first = (
            f"By {year} the platform's {words} emissions pathways imply "
            f"{min(levels.values()):.2f}–{max(levels.values()):.2f} °C above {PREINDUSTRIAL}."
        )
    note = result.get("reading_note")
    # reading_note describes every published pathway; it is only accurate when all are shown.
    if isinstance(note, str) and note and len(levels) == len(SCENARIO_ORDER):
        return f"{first} {note}"
    return first
