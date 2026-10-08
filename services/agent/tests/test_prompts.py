from agent.prompts import AGENT_SYSTEM_PROMPT


def test_agent_system_prompt_forbids_exposing_tool_names():
    # SPEC.md "Corrections applied" #28: agent_node binds the real MCP tools, so a zero-tool-call
    # explanation of "what I can offer instead" could otherwise leak raw snake_case tool names
    # (confirmed live: `get_gas_composition_by_decade` etc. shown to the user). Regression guard
    # against silently dropping the instruction that stops that.
    assert "never mention your own tool or function names" in AGENT_SYSTEM_PROMPT


def test_guardrail_prompt_routes_climate_data_questions_to_data_query_not_general_climate():
    from agent.prompts import GUARDRAIL_SYSTEM_PROMPT

    assert "is NOT general_climate" in GUARDRAIL_SYSTEM_PROMPT
    # "who is responsible for warming" must be answered with cumulative share, never declined as opinion.
    assert "NOT an opinion" in GUARDRAIL_SYSTEM_PROMPT


def test_agent_prompt_carries_the_area2_guardrail_rules():
    for phrase in (
        "never call it TCRE",
        "Never attribute",
        "illustrative, partial-coverage translation",
        "preliminary release",
        "never the IPCC's own figure",
        "5-8%",
    ):
        assert phrase in AGENT_SYSTEM_PROMPT, phrase
    assert "never mention your own tool or function names" in AGENT_SYSTEM_PROMPT  # still there


def test_compose_prompt_repeats_the_climate_framing():
    from agent.prompts import COMPOSE_RESPONSE_SYSTEM_PROMPT

    assert "never proof of cause" in COMPOSE_RESPONSE_SYSTEM_PROMPT and "TCRE" in COMPOSE_RESPONSE_SYSTEM_PROMPT
