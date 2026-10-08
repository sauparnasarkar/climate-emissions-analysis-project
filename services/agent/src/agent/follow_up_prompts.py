"""Follow-up prompt chips -- SPEC.md §15.11 (ENHANCEMENTS.md decision 106).

Up to three prompts for the docked input, moving the user from emissions toward climate outcomes.
Prompts, not links (links are `follow_ups.py`). A fixed per-tool lookup of questions the agent can
answer with its tools -- never model-written, so a chip cannot promise something unsupported.
"""

from __future__ import annotations

from .state import ToolCallRecord
from .ui_selection import is_error_result

MAX_FOLLOW_UP_PROMPTS = 3

P_REL = "Show the relationship between cumulative emissions and warming."
P_SCEN = "How do temperature outcomes vary based on different emissions pathways?"
P_MIX = "How has the mix of CO₂, methane, nitrous oxide and F-gases changed?"
P_CO2 = "How has atmospheric CO₂ changed over time compared with emissions growth?"
P_FORECAST = "What are the top 10 forecasted emitters in 2040?"
P_COMPARE_2040 = "How do today's top 10 emitters compare with the projected top 10 in 2040?"
P_CHANGE = "How many countries have increased their emissions since 1990?"

# The tool whose answer a prompt IS: skipped when that tool already ran this turn.
_ANSWERED_BY = {
    P_REL: "get_emissions_temperature_relationship",
    P_SCEN: "get_scenario_temperature",
    P_MIX: "get_ghg_composition",
    P_CO2: "get_co2_concentration",
    P_CHANGE: "get_emissions_change_summary",
}
_SHARE_TOOL = "get_country_cumulative_share"


def _share(country: str | None) -> str | None:
    return f"What share of historical emissions comes from {country}?" if country else None


def _country(record: ToolCallRecord) -> str | None:
    args, r = record.args, record.result if isinstance(record.result, dict) else {}
    if args.get("country"):
        return args["country"]
    if args.get("countries"):
        return args["countries"][0]
    series = r.get("series") or []
    if series and isinstance(series[0], dict) and series[0].get("name"):
        return series[0]["name"]
    emitters = r.get("emitters") or []
    return emitters[0].get("country") if emitters else None


def _candidates(record: ToolCallRecord) -> list[str | None]:
    n = record.tool_name
    c = _country(record)
    if n in ("get_historical_emissions", "get_country_profile"):
        return [_share(c), P_REL, P_FORECAST]
    if n == "get_top_emitters":
        return [_share(c), P_REL, P_COMPARE_2040]
    if n in ("get_forecast", "get_forecast_comparison", "get_forecast_summary", "get_model_comparison"):
        return [P_SCEN, P_REL, P_CHANGE]
    if n in ("get_scenario_projection", "get_scenario_cumulative_impact", "compare_scenarios_across_countries"):
        return [P_SCEN, P_REL, P_FORECAST]
    if n == "get_emissions_change_summary":
        return [P_REL, P_FORECAST]
    if n == "get_gas_composition_by_decade":
        return [P_REL, P_CO2]
    if n == "get_co2_concentration":
        return [P_REL, P_SCEN, P_MIX]
    if n == "get_temperature_anomaly":
        return [P_REL, P_CO2, P_SCEN]
    if n == "get_emissions_temperature_relationship":
        return [P_SCEN, P_MIX, P_CO2]
    if n == "get_ghg_composition":
        return [P_REL, P_SCEN, P_CO2]
    if n == "get_country_cumulative_share":
        return [P_REL, P_SCEN, P_FORECAST]
    if n == "get_scenario_temperature":
        return [P_REL, P_FORECAST, P_MIX]
    return []


def follow_up_prompts(records: list[ToolCallRecord], current_query: str) -> list[str]:
    ok = [r for r in records if not is_error_result(r.result)]
    ran = {r.tool_name for r in ok}
    asked = current_query.strip().lower()
    out: list[str] = []
    for record in ok:
        for prompt in _candidates(record):
            if not prompt or prompt in out or prompt.strip().lower() == asked:
                continue
            if _ANSWERED_BY.get(prompt) in ran or (prompt.startswith("What share of historical") and _SHARE_TOOL in ran):
                continue
            out.append(prompt)
    return out[:MAX_FOLLOW_UP_PROMPTS]
