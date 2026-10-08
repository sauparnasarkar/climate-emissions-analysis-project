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
        if not f:
            continue
        # The API drops the other line's fields (line='headline' / 'fossil_only'), so read whichever
        # level is present; a fossil-only card says so, since its level differs from the headline's.
        headline = f.get("headline_level_c")
        level = headline if headline is not None else f.get("fossil_only_level_c")
        if level is None:
            continue
        mt = f.get("annual_global_fossil_mt")
        parts = [f"{mt:,.0f} MtCO\u2082 a year"] if mt is not None else []
        if headline is None:
            parts.append("fossil-only line")
        out.append(
            Kpi(label=name, value=level, unit="\u00b0C", decimals=2, year=f.get("year"), sub=" \u00b7 ".join(parts) or None, series=name)
        )
    return out


def _forecast_kpis(rec: ToolCallRecord) -> list[Kpi]:
    """The three largest 2040 forecasts -- only when the ranking really is by the 2040 forecast over the whole
    ~40-country (expanded) set: ranked_by forecast_2040, or nothing was capped. Over the featured ten the "#1" would
    only be the largest of those ten, so no ranked cards are shown for it."""
    s = widget_summary(rec)
    if not s or s.get("scope") != "expanded" or not (s["ranked_by"] == "forecast_2040" or not s.get("scope_note")):
        return []
    top = sorted((t for t in s["top"] if t.get("forecast_2040") is not None), key=lambda t: t["forecast_2040"], reverse=True)
    out = []
    for i, t in enumerate(top[:MAX_KPIS], start=1):
        pct = t.get("pct_change_2020_2040")
        sub = f"{pct:+.1f}% vs 2020" if pct is not None else None
        out.append(Kpi(label=f"#{i} {t['name']}", value=t["forecast_2040"], unit="Mt", decimals=0, year=2040, sub=sub))
    return out


def _relationship_kpis(rec: ToolCallRecord) -> list[Kpi]:
    """Cumulative emissions, warming and the fitted slope -- each from the tool's own summary, in the unit it states."""
    s = widget_summary(rec) or {}
    out: list[Kpi] = []
    window = s.get("window") or []
    cum = s.get("cumulative")
    if cum and cum.get("last") is not None:
        since = f"since {cum['first_year']}"
        out.append(Kpi(label="Cumulative emissions", value=cum["last"], unit=str(cum["unit"]).replace("Gt ", "Gt"), decimals=0, year=cum["last_year"], sub=since))
    last = s.get("last_pair") or {}
    if last.get("temperature") is not None:
        # The pair's temperature is ALWAYS the anomaly vs 1850-1900 (the API's `y`); `baseline` only chooses where the cumulative emissions start.
        out.append(Kpi(label="Warming", value=last["temperature"], unit="\u00b0C", decimals=2, year=last.get("year"), sub=f"vs {PREINDUSTRIAL}"))
    fit = s.get("fit")
    if fit and fit.get("slope") is not None:
        ci = fit.get("ci95_hac")
        parts = [f"95% interval {ci[0]:.2f}\u2013{ci[1]:.2f}"] if ci and len(ci) == 2 else []
        if fit.get("r_squared") is not None:
            parts.append(f"R\u00b2 {fit['r_squared']:.2f}")
        out.append(Kpi(label="Slope", value=fit["slope"], unit=str(fit.get("unit") or "\u00b0C per 1,000 GtCO\u2082"), decimals=2, year=window[1] if len(window) == 2 else None, sub=" \u00b7 ".join(parts) or None))
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
        elif rec.tool_name == "get_forecast_summary":
            out += _forecast_kpis(rec)
        elif rec.tool_name == "get_emissions_temperature_relationship":
            out += _relationship_kpis(rec)
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
