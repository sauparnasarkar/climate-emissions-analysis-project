"""Mandatory climate-context notes -- SPEC.md §15.3 rule 1.

When an Area 2 tool succeeded this turn, the notes below are appended to `scope_notes` (rendered
as the existing `InlineAlert` above the widgets) by deterministic Python, so a required statement
cannot be omitted or drift the way model-written narration can.

Fixed per-tool statements rather than a pass-through of each result's raw envelope `caveats`: the
raw lists carry pipeline-internal and licence prose (up to seven items per call, some already
outdated upstream) that does not belong in a user-facing alert. The model still receives the full
envelope in the tool result; this module only guarantees the few statements the requirements make
mandatory (§3.4, §3.6; ENHANCEMENTS.md decisions 93-94).
"""

from __future__ import annotations

from .state import ToolCallRecord

PRELIMINARY_TEMPERATURE_NOTE = (
    "Temperature figures come from Berkeley Earth's high-resolution dataset, a preliminary release "
    "that is not yet peer reviewed; values may be revised."
)
LONG_RUN_NOTE = (
    "This describes a long-run relationship between observed series. It is not a complete climate "
    "model and does not by itself show cause."
)
ALL_GAS_NOTE = (
    "The recent all-gas relationship (PRIMAP-hist total greenhouse gases, 1970 onward) is a "
    "separate descriptive regression, not the headline long-run relationship."
)
SCENARIO_NOTE = (
    "Illustrative, partial-coverage translation of the scenario pathways, not a climate-model "
    "projection; it depends on the regression period, the emissions source and the stated "
    "assumptions."
)
COMPOSITION_NOTE = (
    "PRIMAP-hist national totals in CO2-equivalent (AR5 GWP-100), excluding land-use change and "
    "international aviation and shipping."
)

_TEMPERATURE_TOOLS = {"get_temperature_anomaly", "get_emissions_temperature_relationship", "get_scenario_temperature"}


def _ok(record: ToolCallRecord) -> dict | None:
    result = record.result
    if isinstance(result, dict) and "error" not in result:
        return result
    return None


def _notes_for(record: ToolCallRecord, result: dict) -> list[str]:
    name = record.tool_name
    notes: list[str] = []
    if name in _TEMPERATURE_TOOLS:
        notes.append(PRELIMINARY_TEMPERATURE_NOTE)
    if name == "get_emissions_temperature_relationship":
        notes.append(LONG_RUN_NOTE)
        if (result.get("summary") or {}).get("source") == "primap_ghg":
            notes.append(ALL_GAS_NOTE)
    elif name == "get_scenario_temperature":
        notes.append(SCENARIO_NOTE)
    elif name == "get_ghg_composition":
        notes.append(COMPOSITION_NOTE)
    elif name == "get_country_cumulative_share":
        if isinstance(result.get("interpretation_note"), str):
            notes.append(result["interpretation_note"])
    elif name == "get_co2_concentration":
        splice = (result.get("details") or {}).get("splice") or {}
        if splice.get("splice_year"):
            notes.append(
                "Concentration is NOAA Mauna Loa measurements spliced to Law Dome ice-core data at "
                f"{splice['splice_year']}; the two records are from different sites."
            )
    return notes


def mandatory_notes(records: list[ToolCallRecord]) -> list[str]:
    """Deduplicated, in order of first appearance; failed calls contribute nothing."""
    out: list[str] = []
    for record in records:
        result = _ok(record)
        if result is None:
            continue
        for note in _notes_for(record, result):
            if note not in out:
                out.append(note)
    return out
