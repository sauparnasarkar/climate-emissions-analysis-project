from agent.prompts import AGENT_SYSTEM_PROMPT


def test_agent_system_prompt_forbids_exposing_tool_names():
    # SPEC.md "Corrections applied" #28: agent_node binds the real MCP tools, so a zero-tool-call
    # explanation of "what I can offer instead" could otherwise leak raw snake_case tool names
    # (confirmed live: `get_gas_composition_by_decade` etc. shown to the user). Regression guard
    # against silently dropping the instruction that stops that.
    assert "never mention your own tool or function names" in AGENT_SYSTEM_PROMPT
