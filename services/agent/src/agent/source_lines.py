"""The 'Source: ...' line under each chart -- SPEC.md §15.11.

A fixed per-tool template filled from the tool result (coverage years, splice year, the window the
relationship was fitted over), never from a design mock. The scope clause matters: OWID's `co2` is
territorial CO2 from fossil fuels and cement and EXCLUDES land-use change; the headline
relationship is the one place land use is included, and its line says so.
"""

from __future__ import annotations

from .state import ToolCallRecord

OWID_SCOPE = "territorial CO₂ from fossil fuels and cement; land-use change excluded"
NATIONAL_SUM = "national sum, international aviation and shipping excluded"
_DASH = "–"


def _span(years: list | None) -> str:
    ys = [y for y in (years or []) if y is not None]
    return f"{min(ys)}{_DASH}{max(ys)}" if ys else ""


def _ok(record: ToolCallRecord) -> dict | None:
    r = record.result
    return r if isinstance(r, dict) and "error" not in r else None


def _historical(r: dict) -> str:
    series = r.get("series") or []
    span = _span([y for s in series for y in (s.get("years") or [])])
    scope = OWID_SCOPE if r.get("gas") == "co2" else f"territorial {r.get('gas_label') or r.get('gas')} emissions"
    return f"Source: OWID, {span} · {scope}" if span else f"Source: OWID · {scope}"


def _relationship(r: dict) -> str:
    s = r.get("summary") or {}
    w = s.get("window") or []
    span = f"{w[0]}{_DASH}{w[1]}" if len(w) == 2 else ""
    label = s.get("relationship", "")
    tail = f", {span}" if span else ""
    if label.startswith("recent all-gas"):
        return (
            "Source: PRIMAP-hist cumulative total greenhouse gases (CO₂e, AR5 GWP-100; excludes land use and "
            f"international aviation and shipping) vs Berkeley Earth temperature (preliminary release){tail}"
        )
    emissions = (
        "OWID cumulative fossil-fuel and cement CO₂ (land use excluded)"
        if label.startswith("secondary") or "fossil-fuel-and-cement-only" in label
        else "OWID cumulative total CO₂ (fossil fuels, cement and land use)"
    )
    return f"Source: {emissions} vs Berkeley Earth temperature (preliminary release){tail}"


def _share(r: dict) -> str:
    if r.get("source") == "primap_hist":
        what = "total greenhouse gases (CO₂e)" if r.get("gas_scope") == "total_ghg" else "CO₂"
        return f"Source: PRIMAP-hist · cumulative {what}; {NATIONAL_SUM}"
    return f"Source: OWID · cumulative territorial CO₂ from fossil fuels and cement; {NATIONAL_SUM}"


def source_line(record: ToolCallRecord) -> str | None:
    r = _ok(record)
    if r is None:
        return None
    name = record.tool_name
    if name == "get_historical_emissions":
        return _historical(r)
    if name == "get_country_profile":
        span = _span(r.get("years"))
        return f"Source: OWID, {span} · {OWID_SCOPE}" if span else f"Source: OWID · {OWID_SCOPE}"
    if name == "get_top_emitters":
        return f"Source: OWID, {r.get('year')} · {OWID_SCOPE}"
    if name == "get_gas_composition_by_decade":
        return "Source: OWID · territorial CO₂, methane and nitrous oxide by decade"
    if name in ("get_forecast", "get_forecast_comparison", "get_forecast_summary"):
        return "Source: ETS(A,Ad,N) forecast fitted to OWID CO₂ · land-use change excluded"
    if name == "get_model_comparison":
        return "Source: backtest on OWID CO₂, trained 1990–2018 and tested 2019–2023"
    if name in ("get_scenario_projection", "get_scenario_cumulative_impact", "compare_scenarios_across_countries"):
        return "Source: BAU, Moderate and Aggressive pathways built on the ETS baseline of OWID CO₂"
    if name == "get_emissions_change_summary":
        return f"Source: OWID CO₂ · change since {r.get('baseline_year', 1990)}"
    if name == "get_co2_concentration":
        splice = ((r.get("details") or {}).get("splice") or {}).get("splice_year")
        tail = f"spliced to Law Dome ice-core data before {splice}" if splice else "spliced to Law Dome ice-core data"
        return f"Source: NOAA GML Mauna Loa, {tail}"
    if name == "get_temperature_anomaly":
        ref = (r.get("summary") or {}).get("reference", "1850-1900")
        return f"Source: Berkeley Earth (preliminary release) · anomaly vs {ref.replace('-', _DASH)}"
    if name == "get_emissions_temperature_relationship":
        return _relationship(r)
    if name == "get_ghg_composition":
        return "Source: PRIMAP-hist national totals, CO₂e (AR5 GWP-100) · excludes land use and international aviation and shipping"
    if name == "get_country_cumulative_share":
        return _share(r)
    if name == "get_scenario_temperature":
        return "Source: platform pathways on OWID CO₂ with the headline regression slope · illustrative, partial-coverage translation"
    return None  # methodology and metadata widgets have no chart to source
