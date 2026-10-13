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
    "PRIMAP-hist national totals in CO₂-equivalent (AR5 GWP-100), excluding land-use change and "
    "international aviation and shipping."
)

# Country-share answers (Release 24.4): what the share is OF, where the totals count from, and what Rest of world is. Deterministic, shown with every such answer.
SHARE_BASIS_OWID = "Shares are of the World total, which includes international aviation and shipping (OWID fossil-fuel and cement CO₂, land use excluded)."
SHARE_BASIS_PRIMAP = "Shares are of PRIMAP-hist's own total: it has no world aggregate and excludes international aviation and shipping."
# An older OWID pipeline output (no World remainder) is still served: its shares are of the sum of the countries, and the note must not say World total.
SHARE_BASIS_OWID_COUNTRY_SUM = "Shares are of the sum of the countries, not of a World total (this OWID output predates the World-total basis; fossil-fuel and cement CO₂, land use excluded)."
SHARE_COUNTED_FROM = "Cumulative totals count from each country's first record, whatever year the chart starts."
# A "since YYYY" answer (Release 24.7): what the period figures are. Replaces the counted-from sentence, which describes the other quantity.
SHARE_SINCE = "Amounts for {period} are the emissions of those years: each country's cumulative total at the end year minus its total the year before {start}; shares are of the World's emissions in the period."
SHARE_SINCE_OWN = "Amounts for {period} are the emissions of those years: each country's cumulative total at the end year minus its total the year before {start}; shares are of the source's own total in the period."

_TEMPERATURE_TOOLS = {"get_temperature_anomaly", "get_emissions_temperature_relationship", "get_scenario_temperature"}


def _ok(record: ToolCallRecord) -> dict | None:
    result = record.result
    if isinstance(result, dict) and "error" not in result:
        return result
    return None


def _share_is_world(result: dict, since: dict | None) -> bool:
    """Whether a share result's shares are of a World total: never PRIMAP-hist (no world aggregate); for OWID what the data says (`since.basis`, else the denominator kind;
    none given = the current World pipeline)."""
    if result.get("source") == "primap_hist":
        return False
    basis = (since or {}).get("basis")
    if isinstance(basis, str):
        return "World" in basis
    den = result.get("denominator")
    kind = den.get("kind") if isinstance(den, dict) else None
    return den is None if kind is None else kind == "world"


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
        summary = result.get("summary") or {}
        # ONE note, not three banners: what the share is of, and (for a series) where the totals count from. What Rest of world is belongs to the chart that draws
        # it (the stacked area's caption), not to every answer that merely has the numbers.
        # The basis comes from what the data itself says (a period answer's `since.basis`, else the response's denominator kind), not from the source alone: an older OWID
        # output without a World remainder has shares of the country sum.
        since = summary.get("since")
        world = _share_is_world(result, since)
        basis = (SHARE_BASIS_OWID if world else SHARE_BASIS_OWID_COUNTRY_SUM) if result.get("source") == "owid_co2" else SHARE_BASIS_PRIMAP if result.get("source") == "primap_hist" else None
        if basis:
            if since and since.get("period"):  # emissions in a period: say what they are instead of where totals count from
                tmpl = SHARE_SINCE if world else SHARE_SINCE_OWN
                notes.append(f"{basis} {tmpl.format(period=since['period'], start=since['year'])}")
            else:
                notes.append(f"{basis} {SHARE_COUNTED_FROM}" if summary.get("mode") == "series" else basis)
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
