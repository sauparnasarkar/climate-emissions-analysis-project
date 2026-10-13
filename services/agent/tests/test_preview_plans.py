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


def _page_starter_prompts() -> list[str]:
    """The starter prompts the CURRENT Ask page serves, read from its source so a reworded or added prompt cannot fall out of step."""
    import re

    page = Path(__file__).resolve().parents[3] / "climate-dashboard-react" / "src" / "agent" / "starterPrompts.ts"
    if not page.exists():
        pytest.skip("climate-dashboard-react not present")
    src = page.read_text()
    block = src[src.index("export const STARTER_COLUMNS") : src.index("export const STARTER_PROMPTS")]
    found = re.findall(r"^\s+(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*'),\s*$", block, re.M)
    return [f[1:-1].replace("\\'", "'").replace('\\"', '"') for f in found]


def test_every_prompt_the_current_page_serves_has_a_non_default_plan():
    prompts = _page_starter_prompts()
    assert len(prompts) >= 4  # the scrape worked
    for p in prompts:
        assert preview.plan_for(p) != preview.DEFAULT_PLAN, p


CUMULATIVE_QUESTIONS = {
    "How much CO₂ has China emitted in total?": {"countries": ["China"], "start_year": 1970},  # start_year=1970 as the prompt asks, so the chart starts where the dashboard's do
    "Is India's share of the world's cumulative CO₂ rising or falling?": {"countries": ["India"], "start_year": 1970},
    "Show cumulative emissions for the top emitters since 1970.": {"countries": preview.TOP5, "start_year": 1970},
    "Which countries have emitted the most since records began?": {"limit": 10},
    "How do China and the US compare on cumulative share?": {"countries": ["China", "United States"], "start_year": 1970},
    "What is China's cumulative CO₂ since 1990?": {"countries": ["China"], "since_year": 1990},
    "Which countries have emitted the most since 1970?": {"since_year": 1970, "limit": 10},
}


@pytest.mark.parametrize("prompt,args", CUMULATIVE_QUESTIONS.items())
def test_the_release_24_cumulative_questions_have_share_tool_plans(prompt, args):
    assert preview.plan_for(prompt) == [("get_country_cumulative_share", args)]


def test_the_new_plans_do_not_capture_the_existing_starter_prompts():
    # the generic "india" plan and the "share of historical emissions" plan must still win for their own prompts
    assert [n for n, _ in preview.plan_for("How have India's emissions grown compared with other countries?")] == ["get_country_profile", "get_historical_emissions"]
    assert [n for n, _ in preview.plan_for("What share of historical emissions comes from China?")] == ["get_country_cumulative_share"]

