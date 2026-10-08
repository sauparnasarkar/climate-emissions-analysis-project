"""SPEC.md §15.3 rule 1: deterministic climate-context notes."""

from agent.caveats import (
    ALL_GAS_NOTE,
    COMPOSITION_NOTE,
    LONG_RUN_NOTE,
    PRELIMINARY_TEMPERATURE_NOTE,
    SCENARIO_NOTE,
    mandatory_notes,
)
from agent.state import ToolCallRecord


def _rec(name, result, args=None):
    return ToolCallRecord(tool_name=name, args=args or {}, result=result, progress_label="x")


def test_temperature_tool_carries_the_preliminary_note():
    assert mandatory_notes([_rec("get_temperature_anomaly", {"points": []})]) == [PRELIMINARY_TEMPERATURE_NOTE]


def test_headline_relationship_has_preliminary_and_long_run_but_not_the_all_gas_note():
    notes = mandatory_notes([_rec("get_emissions_temperature_relationship", {"summary": {"source": "owid_co2"}})])
    assert notes == [PRELIMINARY_TEMPERATURE_NOTE, LONG_RUN_NOTE]


def test_all_gas_relationship_adds_the_distinction_note():
    notes = mandatory_notes([_rec("get_emissions_temperature_relationship", {"summary": {"source": "primap_ghg"}})])
    assert notes == [PRELIMINARY_TEMPERATURE_NOTE, LONG_RUN_NOTE, ALL_GAS_NOTE]
    assert "TCRE" not in ALL_GAS_NOTE


def test_scenario_composition_and_share_notes():
    assert SCENARIO_NOTE in mandatory_notes([_rec("get_scenario_temperature", {})])
    assert mandatory_notes([_rec("get_ghg_composition", {})]) == [COMPOSITION_NOTE]
    share = _rec("get_country_cumulative_share", {"interpretation_note": "Not a contribution to warming."})
    assert mandatory_notes([share]) == ["Not a contribution to warming."]


def test_concentration_note_reads_the_splice_year_from_the_result():
    rec = _rec("get_co2_concentration", {"details": {"splice": {"splice_year": 1959}}})
    assert "1959" in mandatory_notes([rec])[0]
    assert mandatory_notes([_rec("get_co2_concentration", {"details": {}})]) == []


def test_failed_calls_and_emissions_tools_contribute_nothing():
    assert mandatory_notes([_rec("get_temperature_anomaly", {"error": "503"})]) == []
    assert mandatory_notes([_rec("get_historical_emissions", {"series": []})]) == []


def test_notes_are_deduplicated_across_calls_in_order():
    recs = [_rec("get_temperature_anomaly", {}), _rec("get_scenario_temperature", {}), _rec("get_temperature_anomaly", {})]
    assert mandatory_notes(recs) == [PRELIMINARY_TEMPERATURE_NOTE, SCENARIO_NOTE]
