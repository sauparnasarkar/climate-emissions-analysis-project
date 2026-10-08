"""SPEC.md §15.4: the model sees a capped copy; the record/widget keeps the full result."""

import copy

from agent.payload_cap import MODEL_POINT_CAP, cap_for_model, sample_evenly


def _points(n):
    return [{"year": 1850 + i, "value": float(i)} for i in range(n)]


def test_sample_evenly_keeps_first_and_last_and_the_cap():
    items = list(range(176))
    out = sample_evenly(items)
    assert len(out) <= MODEL_POINT_CAP and out[0] == 0 and out[-1] == 175
    assert out == sorted(set(out))  # ordered, no duplicates


def test_short_series_is_returned_untouched():
    assert sample_evenly(list(range(10))) == list(range(10))


def test_points_tools_are_capped_with_counts_and_the_summary_survives():
    result = {"points": _points(176), "summary": {"first_year": 1850}, "caveats": ["c"], "note": "n"}
    view, capped = cap_for_model("get_temperature_anomaly", result)
    assert capped and view["points_total"] == 176 and view["points_shown"] == len(view["points"]) <= MODEL_POINT_CAP
    assert view["points"][0]["year"] == 1850 and view["points"][-1]["year"] == 2025
    assert view["summary"] == {"first_year": 1850} and view["caveats"] == ["c"] and view["note"] == "n"
    assert "model_view_note" in view


def test_the_input_is_never_mutated():
    result = {"points": _points(176), "summary": {}}
    before = copy.deepcopy(result)
    cap_for_model("get_co2_concentration", result)
    assert result == before and len(result["points"]) == 176


def test_a_short_result_reports_no_change():
    result = {"points": _points(5)}
    view, capped = cap_for_model("get_co2_concentration", result)
    assert not capped and view is result


def test_relationship_drops_the_weight_scan_and_caps_points():
    result = {"points": _points(176), "fit_context": {"stability": {"x": 1}, "land_use_weight_scan": {"weights": list(range(500))}}}
    view, capped = cap_for_model("get_emissions_temperature_relationship", result)
    assert capped and isinstance(view["fit_context"]["land_use_weight_scan"], str)
    assert view["fit_context"]["stability"] == {"x": 1}  # the rest of the context is kept


def test_composition_years_and_share_series_are_capped_per_series():
    comp, c1 = cap_for_model("get_ghg_composition", {"years": [{"year": y} for y in range(1970, 2025)]})
    assert c1 and comp["years_total"] == 55 and comp["years_shown"] <= MODEL_POINT_CAP
    share = {"series": [{"country": "A", "points": _points(175)}, {"country": "B", "points": _points(10)}]}
    view, c2 = cap_for_model("get_country_cumulative_share", share)
    assert c2 and view["series"][0]["points_total"] == 175 and "points_total" not in view["series"][1]
    assert len(view["series"][1]["points"]) == 10


def test_metadata_drops_prose_but_keeps_licence_and_caveats():
    src = {"id": "s", "license": "L", "caveats": ["c"], "coverage": [1, 2], "methodology": "long prose", "source_urls": ["u"]}
    view, capped = cap_for_model("get_correlation_metadata", {"sources": [src]})
    kept = view["sources"][0]
    assert capped and "methodology" not in kept and "source_urls" not in kept
    assert kept["license"] == "L" and kept["caveats"] == ["c"] and kept["coverage"] == [1, 2]


def test_unlisted_tools_and_error_results_pass_through():
    big = {"series": [{"values": list(range(500))}]}
    assert cap_for_model("get_historical_emissions", big) == (big, False)
    err = {"error": "boom", "points": _points(100)}
    assert cap_for_model("get_temperature_anomaly", err) == (err, False)
    assert cap_for_model("get_temperature_anomaly", "text") == ("text", False)
