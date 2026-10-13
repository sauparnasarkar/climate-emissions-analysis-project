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


def test_agent_prompt_tells_the_model_to_leave_the_year_out_of_top_emitters_unless_named():
    assert "leave the year out unless the user names a specific year" in AGENT_SYSTEM_PROMPT


def test_the_composer_keeps_all_time_context_out_of_a_since_answer():
    """The final text is written by the composer, not the main agent prompt, so the since-year rule must live here too (Copilot review of #299)."""
    from agent.prompts import COMPOSE_RESPONSE_SYSTEM_PROMPT as P

    assert "`since`" in P and 'labelled "all-time"' in P and "never quoting its rank or share" in P
    assert "`summary.top`" in P  # a ranking carries its country figures there, not in `since` (Copilot review of #299)


def test_the_composer_says_a_single_gas_cumulative_is_unavailable_even_when_annual_figures_follow():
    from agent.prompts import COMPOSE_RESPONSE_SYSTEM_PROMPT as P

    assert "CUMULATIVE total of a single gas other than CO2" in P and "not available" in P
    # a sentence of its own, not inside the climate-context clause: an annual methane answer comes from a historical-emissions widget (Copilot review of #299)
    assert P.index("CUMULATIVE total of a single gas") > P.index("not projections.")
