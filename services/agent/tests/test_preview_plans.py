"""The preview server's question -> tool plan (a review aid; its plans must stay in step with the starter prompts and chips)."""

import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("preview_server", Path(__file__).resolve().parents[1] / "evals" / "preview_server.py")
preview = importlib.util.module_from_spec(spec)
spec.loader.exec_module(preview)

STARTERS = {
    "What are China's historical emissions trends, and how do they compare to the other top 10 emitters?": "get_historical_emissions",
    "How have India's emissions grown compared with other countries?": "get_historical_emissions",
    "Show the relationship between cumulative emissions and warming.": "get_emissions_temperature_relationship",
    "How do temperature outcomes vary based on different emissions pathways?": "get_scenario_temperature",
    "What are the top 10 forecasted emitters in 2040?": "get_forecast_summary",
    "How do today's top 10 emitters compare with the projected top 10 in 2040?": "get_forecast_summary",
}


@pytest.mark.parametrize("prompt,tool", STARTERS.items())
def test_every_starter_prompt_has_a_plan_using_the_expected_tool(prompt, tool):
    assert tool in [name for name, _ in preview.plan_for(prompt)]


def test_every_follow_up_chip_has_a_plan_that_is_not_the_default():
    from agent import follow_up_prompts as chips

    prompts = [chips.P_REL, chips.P_SCEN, chips.P_MIX, chips.P_CO2, chips.P_FORECAST, chips.P_COMPARE_2040, chips.P_CHANGE.replace("How many countries have increased their emissions since 1990?", "What share of historical emissions comes from China?")]
    for p in prompts:
        assert preview.plan_for(p) != preview.DEFAULT_PLAN, p


def test_unknown_questions_fall_back_to_the_methodology_plan():
    assert preview.plan_for("something unrelated") == preview.DEFAULT_PLAN


def test_the_stand_in_lead_uses_only_the_answer_blocks_it_is_given():
    text = preview.compose_text({"kpis": [{"label": "CO₂ emissions", "value": 12289, "unit": "Mt", "decimals": 0, "year": 2024}], "widgets": []})
    assert "12,289 Mt" in text and "2024" in text and "Preview lead" in text
