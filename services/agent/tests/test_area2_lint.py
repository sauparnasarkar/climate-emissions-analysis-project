"""The deterministic eval checks (agent.area2_lint) flag the wrong framing and pass the right one."""

import pytest

from agent.area2_lint import check_response


@pytest.mark.parametrize(
    "text",
    [
        "The all-gas relationship is the TCRE for total greenhouse gases.",
        "China caused most of the global warming.",
        "The United States is responsible for the warming we see.",
        "This proves that emissions drive temperature.",
        "The slope is 0.49 °C per 1,000 GtCO2.",
        "The two sources differ by 5-8% in measured terms.",
    ],
)
def test_wrong_framing_is_flagged(text):
    assert check_response(text)


@pytest.mark.parametrize(
    "text",
    [
        "The recent all-gas relationship is never called TCRE; it is a separate regression.",
        "China's cumulative share is large, but this is not its contribution to warming.",
        "This does not prove that emissions drive temperature; it shows long-run co-movement.",
        "The headline slope is 0.49 °C per 1,000 GtCO2 (temperature data is a preliminary release).",
        "The slope is 0.49 °C per 1,000 GtCO2.",  # fine when the note is in scope_notes, below
    ],
)
def test_right_framing_is_not_flagged(text):
    assert check_response(text, ["Temperature figures come from a preliminary release."]) == []


def test_scenario_answers_must_say_illustrative():
    assert check_response("Aggressive implies 1.58 °C.", scenario_answer=True)
    assert check_response("Aggressive implies 1.58 °C (an illustrative translation).", scenario_answer=True) == []
    assert check_response("Aggressive implies 1.58 °C.", ["Illustrative, partial-coverage translation."], scenario_answer=True) == []


def test_gap_figure_negation_is_judged_within_its_own_sentence():
    # An unrelated "do not" in a neighbouring sentence must not excuse a measured-sounding claim.
    assert check_response("The 5–8% difference is measured. These sources do not fully agree.")
    assert check_response("Sources differ by 5 to 8% in measured terms.")
    # ...while a negation inside the sentence that carries the figure still passes.
    assert check_response("The 5-8% figure has not been measured for PRIMAP-hist.") == []
    assert check_response("We do not quote 5–8% as a measured difference.") == []
