"""Graph-routing, caching, and call-count-guard tests -- SPEC.md §8-§10.

Uses `ScriptedChatModel` (fakes.py) for the LLM seam throughout, so this file never needs a real
`ANTHROPIC_API_KEY`. Uses small local fake tools (built with `langchain_core.tools.tool`) for
the mechanics tests (cache, guard, persistence) since those exercise `tools_node`'s own logic,
not the real MCP wire protocol -- `test_data_query_against_real_mcp_server` below is the one
test that goes end-to-end against a real `services/mcp-server` subprocess, matching this
project's real-data-over-mocks philosophy for the one test that should prove the seams actually
fit together.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import MemorySaver

from agent.graph import MAX_TOOL_CALLS_PER_TURN, _capability_summary, _OpinionOutput, build_graph
from agent.mcp_client import get_mcp_tools
from agent.prompts import OFF_TOPIC_RESPONSE

from .fakes import ScriptedChatModel

THREAD_CONFIG = {"configurable": {"thread_id": "test-thread"}}


def _tool_call(name: str, args: dict, call_id: str) -> dict:
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


async def _make_methodology_tool() -> StructuredTool:
    async def _run() -> dict:
        return {"notes": "ETS(A,Ad,N) explanation..."}

    return StructuredTool.from_function(coroutine=_run, name="get_methodology_notes", description="fake methodology tool")


async def _make_counter_tool() -> StructuredTool:
    async def _run(n: int = 0) -> dict:
        return {"n": n}

    return StructuredTool.from_function(coroutine=_run, name="get_methodology_notes", description="fake counter tool")


async def test_off_topic_routing():
    llm = ScriptedChatModel([{"classification": "off_topic"}])
    graph = await build_graph(llm=llm, mcp_tools=[])
    result = await graph.ainvoke({"current_query": "write me a poem about cats"}, config=THREAD_CONFIG)
    assert result["classification"] == "off_topic"
    assert result["response_text"] == OFF_TOPIC_RESPONSE
    assert result["widgets"] == []
    assert llm.exhausted


async def test_opinion_routing():
    llm = ScriptedChatModel(
        [
            {"classification": "opinion"},
            {"response_text": "I can't weigh in on that.", "suggested_prompts": ["How has China's trend changed?"]},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[])
    result = await graph.ainvoke({"current_query": "should China do more?"}, config=THREAD_CONFIG)
    assert result["classification"] == "opinion"
    assert result["response_text"] == "I can't weigh in on that."
    assert result["suggested_prompts"] == ["How has China's trend changed?"]
    assert llm.exhausted


def test_opinion_output_coerces_a_bare_string_suggested_prompt_into_a_list():
    # SPEC.md "Corrections applied" #31: confirmed live -- grounding suggested_prompts in the
    # real tool catalog (correction #29) can narrow the model down to a single good reframe, and
    # it sometimes returns that as a bare string instead of a one-element list. Previously
    # crashed the entire turn with a pydantic ValidationError (worse than the ungrounded-
    # suggestion issue #29 was fixing) -- now tolerated instead.
    output = _OpinionOutput(response_text="I can't weigh in.", suggested_prompts="How has X changed?")
    assert output.suggested_prompts == ["How has X changed?"]


def test_opinion_output_still_accepts_a_real_list():
    output = _OpinionOutput(response_text="I can't weigh in.", suggested_prompts=["a", "b"])
    assert output.suggested_prompts == ["a", "b"]


async def test_opinion_routing_survives_a_bare_string_suggested_prompt_from_the_model():
    # End-to-end version of the two tests above -- proves the coercion actually reaches the
    # real opinion_node -> with_structured_output(_OpinionOutput) path, not just the model class
    # in isolation. ScriptedChatModel's own `_schema(**value)` construction (fakes.py) is exactly
    # how the real langchain_core structured-output parser builds `_OpinionOutput` from the
    # model's raw tool-call args, so this reproduces the live crash faithfully.
    llm = ScriptedChatModel(
        [
            {"classification": "opinion"},
            {"response_text": "I can't weigh in on that.", "suggested_prompts": "How has China's trend changed?"},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[])
    result = await graph.ainvoke({"current_query": "should China do more?"}, config=THREAD_CONFIG)
    assert result["suggested_prompts"] == ["How has China's trend changed?"]


def test_capability_summary_uses_first_paragraph_only_never_the_tool_name():
    # SPEC.md "Corrections applied" #29: grounds opinion_node's reframes in what the dataset
    # actually supports -- using the raw tool name here would reintroduce #28's leak one node
    # over, and using the full docstring (IMPORTANT/edge-case paragraphs meant for the
    # tool-calling model) would bury the one summary sentence a reframe-suggestion prompt needs.
    tool = StructuredTool.from_function(
        coroutine=lambda: None,  # pragma: no cover -- never invoked, only .description is read
        name="get_gas_composition_by_decade",
        description=(
            "Decade-by-decade share of CO2/methane/nitrous oxide for one or more countries.\n\n"
            "IMPORTANT: only pass countries when the user named specific countries."
        ),
    )
    summary = _capability_summary([tool])
    assert summary == "- Decade-by-decade share of CO2/methane/nitrous oxide for one or more countries."
    assert "get_gas_composition_by_decade" not in summary
    assert "IMPORTANT" not in summary


async def test_opinion_routing_with_real_tools_present():
    # SPEC.md "Corrections applied" #29: opinion_node now receives mcp_tools (previously always
    # []) so its reframes can be grounded in what the dataset actually supports. Proves the
    # wiring through build_graph's functools.partial doesn't crash and still returns
    # suggested_prompts correctly with a real tool list present -- the grounding content itself
    # (first-paragraph extraction, no tool names) is unit-tested directly against
    # _capability_summary above, not re-verified here via prompt introspection (ScriptedChatModel
    # can't cleanly expose what a with_structured_output call sent to a test holding the
    # original, pre-clone `llm` reference -- see agent_node's own cache-control test for the one
    # case, bind_tools, where that introspection does work).
    tool = StructuredTool.from_function(
        coroutine=lambda: None,  # pragma: no cover -- never invoked, only .description is read
        name="get_historical_emissions",
        description="Historical yearly emissions time series for one or more countries.",
    )
    llm = ScriptedChatModel(
        [
            {"classification": "opinion"},
            {
                "response_text": "I can't weigh in on that.",
                "suggested_prompts": ["How has China's emissions trend compared to peers?"],
            },
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[tool])
    result = await graph.ainvoke({"current_query": "should China do more?"}, config=THREAD_CONFIG)
    assert result["suggested_prompts"] == ["How has China's emissions trend compared to peers?"]
    assert llm.exhausted


async def test_general_climate_routing():
    llm = ScriptedChatModel(
        [
            {"classification": "general_climate"},
            AIMessage(content="CO2 is a greenhouse gas that traps heat in the atmosphere."),
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[])
    result = await graph.ainvoke({"current_query": "what is CO2?"}, config=THREAD_CONFIG)
    assert result["classification"] == "general_climate"
    assert result["response_text"] == "CO2 is a greenhouse gas that traps heat in the atmosphere."
    assert len(result["widgets"]) == 1
    assert result["widgets"][0].intent == "text"
    assert llm.exhausted


async def test_general_climate_unwraps_list_content():
    # Claude Sonnet 5 runs adaptive thinking by default (llm.py's ChatAnthropic construction sets
    # no thinking= override) and returns content as a list of blocks -- a 'thinking' block plus a
    # 'text' block -- rather than a plain string. Reproduced live 2026-08-24: this shape reached
    # AgentState.response_text (a bare str field) unwrapped and crashed finalize with a pydantic
    # ValidationError. general_climate_node must unwrap it the same way ui_selection_node already
    # does via _text_from_content_blocks.
    llm = ScriptedChatModel(
        [
            {"classification": "general_climate"},
            AIMessage(
                content=[
                    {"type": "thinking", "thinking": "The user is asking a general question.", "signature": "sig"},
                    {"type": "text", "text": "CO2 is a greenhouse gas that traps heat in the atmosphere."},
                ]
            ),
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[])
    result = await graph.ainvoke({"current_query": "what is CO2?"}, config=THREAD_CONFIG)
    assert result["classification"] == "general_climate"
    assert result["response_text"] == "CO2 is a greenhouse gas that traps heat in the atmosphere."
    assert len(result["widgets"]) == 1
    assert result["widgets"][0].props["text"] == "CO2 is a greenhouse gas that traps heat in the atmosphere."
    assert llm.exhausted


async def test_data_query_single_tool_call():
    tool = await _make_methodology_tool()
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_methodology_notes", {}, "call-1")]),
            AIMessage(content="done"),  # no more tool calls -> route to ui_selection
            {"response_text": "Here's the methodology."},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[tool])
    result = await graph.ainvoke({"current_query": "how does the forecast model work?"}, config=THREAD_CONFIG)

    assert result["tool_call_count"] == 1
    assert len(result["tool_calls"]) == 1
    assert result["tool_calls"][0].result == {"notes": "ETS(A,Ad,N) explanation..."}
    assert len(result["widgets"]) == 1
    assert result["widgets"][0].intent == "text"
    assert result["response_text"] == "Here's the methodology."
    assert llm.exhausted


async def test_agent_node_marks_system_prompt_cacheable():
    # SPEC.md/CLAUDE.md: agent_node's system prompt (and, since Anthropic renders tools before
    # system, the ~13 MCP tool schemas bound alongside it) is the one call site worth a
    # cache_control breakpoint -- it repeats on every agent<->tools loop iteration and across
    # every user's query. Verified against langchain_anthropic's real source: for the direct
    # Anthropic API (not Bedrock/Vertex), cache_control must be a block-level key inside the
    # SystemMessage's own content, not the top-level kwarg (that only auto-hoists for non-direct
    # transports) -- this test pins the block-level form so a future edit can't silently drop it.
    tool = await _make_methodology_tool()
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_methodology_notes", {}, "call-1")]),
            AIMessage(content="done"),
            {"response_text": "Here's the methodology."},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[tool])
    await graph.ainvoke({"current_query": "how does the forecast model work?"}, config=THREAD_CONFIG)

    system_message = llm.last_messages[0]
    assert system_message.type == "system"
    assert isinstance(system_message.content, list)
    assert system_message.content[0]["cache_control"] == {"type": "ephemeral"}


async def test_cache_hit_still_increments_tool_call_count():
    tool = await _make_counter_tool()
    same_args = _tool_call("get_methodology_notes", {"n": 1}, "call-a")
    same_args_again = _tool_call("get_methodology_notes", {"n": 1}, "call-b")  # same args, new id
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[same_args]),
            AIMessage(content="", tool_calls=[same_args_again]),
            AIMessage(content="done"),
            {"response_text": "ok"},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[tool])
    result = await graph.ainvoke({"current_query": "call it twice"}, config=THREAD_CONFIG)

    # SPEC.md §9: a cache hit still counts toward tool_call_count -- exempting hits would let a
    # stuck agent spam free cached calls without ever tripping the §10 guard.
    assert result["tool_call_count"] == 2
    assert len(result["tool_calls"]) == 2
    assert result["tool_calls"][0].result == result["tool_calls"][1].result == {"n": 1}
    assert llm.exhausted


async def test_call_count_guard_stops_after_max_and_notes_it():
    tool = await _make_counter_tool()
    scripted = [{"classification": "data_query"}]
    # MAX_TOOL_CALLS_PER_TURN successful calls (distinct args, so none are cache hits), then one
    # more request that must be blocked by the cap rather than executed.
    for i in range(MAX_TOOL_CALLS_PER_TURN + 1):
        scripted.append(AIMessage(content="", tool_calls=[_tool_call("get_methodology_notes", {"n": i}, f"call-{i}")]))
    scripted.append({"response_text": "partial results"})
    llm = ScriptedChatModel(scripted)

    graph = await build_graph(llm=llm, mcp_tools=[tool])
    result = await graph.ainvoke({"current_query": "call it many times"}, config=THREAD_CONFIG)

    assert result["tool_call_count"] == MAX_TOOL_CALLS_PER_TURN
    assert len(result["tool_calls"]) == MAX_TOOL_CALLS_PER_TURN
    assert any("Stopped after" in note for note in result["scope_notes"])
    assert llm.exhausted


async def test_turn_reset_fields_and_thread_scoped_cache_persist():
    tool = await _make_methodology_tool()
    checkpointer = MemorySaver()

    turn1_llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_methodology_notes", {}, "call-1")]),
            AIMessage(content="done"),
            {"response_text": "Here's the methodology."},
        ]
    )
    graph = await build_graph(llm=turn1_llm, mcp_tools=[tool], checkpointer=checkpointer)
    turn1 = await graph.ainvoke({"current_query": "how does the forecast model work?"}, config=THREAD_CONFIG)
    assert len(turn1["widgets"]) == 1
    assert len(turn1["tool_cache"]) == 1

    # Second turn, same thread, off-topic this time -- widgets/tool_calls/scope_notes from turn 1
    # must be reset (guardrail_router_node's job), but tool_cache must survive (never resets).
    turn2_graph = await build_graph(llm=ScriptedChatModel([{"classification": "off_topic"}]), mcp_tools=[tool], checkpointer=checkpointer)
    turn2 = await turn2_graph.ainvoke({"current_query": "write me a poem"}, config=THREAD_CONFIG)

    assert turn2["widgets"] == []
    assert turn2["tool_calls"] == []
    assert turn2["response_text"] == OFF_TOPIC_RESPONSE
    assert len(turn2["tool_cache"]) == 1  # survived from turn 1, per SPEC.md §7/§9


async def test_zero_tool_call_turn_reuses_prior_context_and_skips_compose_response():
    # SPEC.md correction #21: confirmed live against the real Anthropic API and against Claude
    # Desktop's own MCP client behavior for the identical scenario -- when a data_query turn makes
    # zero tool calls, that's the model reasonably reusing a prior turn's tool result already in
    # context (e.g. a broad historical-emissions pull that already covered the new question), not
    # a malfunction. agent_node's own answer is used directly as response_text; compose_response_
    # node (which has no widgets to synthesize from) must never run for this path -- if it did,
    # the LLM's scripted queue below would be short a response and `exhausted` would fail.
    tool = await _make_methodology_tool()
    checkpointer = MemorySaver()

    turn1_llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_methodology_notes", {}, "call-1")]),
            AIMessage(content="Here's the methodology, freshly fetched."),
            {"response_text": "Here's the methodology."},
        ]
    )
    graph = await build_graph(llm=turn1_llm, mcp_tools=[tool], checkpointer=checkpointer)
    turn1 = await graph.ainvoke({"current_query": "how does the forecast model work?"}, config=THREAD_CONFIG)
    assert turn1["response_text"] == "Here's the methodology."

    # Turn 2: the model answers directly from turn 1's still-present context, no new tool call --
    # content is a list of blocks (thinking + text), matching the real API's shape, to prove the
    # extraction handles that form and not just a plain string.
    turn2_llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(
                content=[
                    {"type": "thinking", "thinking": "I already have this.", "signature": "sig"},
                    {"type": "text", "text": "Based on what I already fetched, here's a follow-up answer."},
                ]
            ),
        ]
    )
    turn2_graph = await build_graph(llm=turn2_llm, mcp_tools=[tool], checkpointer=checkpointer)
    turn2 = await turn2_graph.ainvoke({"current_query": "can you elaborate on that?"}, config=THREAD_CONFIG)

    assert turn2["tool_calls"] == []
    assert turn2["response_text"] == "Based on what I already fetched, here's a follow-up answer."
    assert turn2_llm.exhausted  # compose_response_node never ran -- nothing left unconsumed

    # SPEC.md correction #22: a widget is built too, tagged "context_reuse" (not "general_climate"
    # -- semantically different, even though both render as a single text widget) -- so the
    # frontend's !hasWidgets check (meant for off_topic/opinion's short guardrail text) doesn't
    # catch this path's substantive answers and show them inside an alert box.
    assert len(turn2["widgets"]) == 1
    assert turn2["widgets"][0].intent == "text"
    assert turn2["widgets"][0].source_tool_call == "context_reuse"
    assert turn2["widgets"][0].props["text"] == "Based on what I already fetched, here's a follow-up answer."


async def test_data_query_against_real_mcp_server(running_mcp_server):
    """The one end-to-end test against a real services/mcp-server subprocess and its real
    get_methodology_notes tool, not a local fake -- proves get_mcp_tools()/agent_node/tools_node
    actually fit together over the real MCP wire protocol."""
    real_tools = await get_mcp_tools(running_mcp_server)
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_methodology_notes", {}, "call-1")]),
            AIMessage(content="done"),
            {"response_text": "Here's the real methodology."},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=real_tools)
    result = await graph.ainvoke({"current_query": "how does the forecast model work?"}, config=THREAD_CONFIG)

    assert result["tool_call_count"] == 1
    assert isinstance(result["tool_calls"][0].result, dict)
    assert "error" not in result["tool_calls"][0].result
    assert result["response_text"] == "Here's the real methodology."
    assert llm.exhausted


async def test_real_tool_execution_error_surfaces_without_crashing(running_mcp_server):
    """A real MCP tool failure (running_mcp_server's API_BASE_URL is deliberately unreachable,
    so any tool that actually calls api/ fails) must surface as a normal, non-crashing tool
    result the model can react to -- proves handle_tool_errors=True's error path (SPEC.md §8's
    "inherited for free" claim) actually round-trips through _tool_result_from_message's
    content-block unwrapping, not just the success path test_data_query_against_real_mcp_server
    covers."""
    real_tools = await get_mcp_tools(running_mcp_server)
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_country_profile", {"country": "China"}, "call-1")]),
            AIMessage(content="I couldn't complete that request."),
            {"response_text": "The data service is unavailable right now."},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=real_tools)
    result = await graph.ainvoke({"current_query": "what's China's emissions profile?"}, config=THREAD_CONFIG)

    assert result["tool_call_count"] == 1
    record = result["tool_calls"][0]
    assert isinstance(record.result, dict)
    assert "error" in record.result
    # No widget should be built from a failed tool call.
    assert result["widgets"] == []
    # Every tool call this turn errored -- ui_selection_node must flag this as a transient
    # failure, not let compose_response_node's LLM invent a generic "rephrase your question"
    # apology that looks identical to a genuine no-match case.
    assert any("transient failure" in note for note in result["scope_notes"])


async def test_partial_tool_failure_does_not_trigger_transient_failure_note(running_mcp_server):
    """One call succeeds (get_methodology_notes, which never reaches api/) and one fails
    (get_country_profile, against running_mcp_server's deliberately unreachable API_BASE_URL) in
    the same turn -- the transient-failure scope_note above must only fire when *every* call in
    the turn errored, not whenever any one of several does."""
    real_tools = await get_mcp_tools(running_mcp_server)
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(
                content="",
                tool_calls=[
                    _tool_call("get_methodology_notes", {}, "call-1"),
                    _tool_call("get_country_profile", {"country": "China"}, "call-2"),
                ],
            ),
            AIMessage(content="done"),
            {"response_text": "Here's what I found, though China's profile is unavailable."},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=real_tools)
    result = await graph.ainvoke({"current_query": "how does the forecast model work, and what's China's profile?"}, config=THREAD_CONFIG)

    assert result["tool_call_count"] == 2
    assert len(result["widgets"]) == 1  # only the successful call produces a widget
    assert not any("transient failure" in note for note in result["scope_notes"])
    assert llm.exhausted


async def test_partial_tool_failure_adds_a_distinct_partial_data_note(running_mcp_server):
    """Same setup as the transient-failure-suppression test above, but checking the other half:
    a partial failure must still leave *some* trace in scope_notes, distinctly worded from the
    all-failed "transient failure" note. Without this, compose_response_node's payload (widgets
    built from successful calls only, plus scope_notes) carries zero signal that
    get_country_profile ever failed -- it can't narrate a gap it was never told about, so a real
    (un-scripted) LLM will confidently answer from only the data it has. Caught live: qwen2.5:14b
    answered a compound starter-prompt query from partial data with no acknowledgment that half
    the tool calls failed, because nothing in its payload said so."""
    real_tools = await get_mcp_tools(running_mcp_server)
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(
                content="",
                tool_calls=[
                    _tool_call("get_methodology_notes", {}, "call-1"),
                    _tool_call("get_country_profile", {"country": "China"}, "call-2"),
                ],
            ),
            AIMessage(content="done"),
            {"response_text": "Here's what I found, though China's profile is unavailable."},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=real_tools)
    result = await graph.ainvoke({"current_query": "how does the forecast model work, and what's China's profile?"}, config=THREAD_CONFIG)

    assert not any("transient failure" in note for note in result["scope_notes"])
    # Plain-language (progress_label), never the raw tool name -- scope_notes reaches the client
    # verbatim and AGENT_SYSTEM_PROMPT forbids ever naming a tool/function to the user.
    assert any("partial data" in note and "China's emissions profile" in note for note in result["scope_notes"])
    assert not any("get_country_profile" in note for note in result["scope_notes"])


async def test_node_execution_logs_timing(caplog):
    import logging

    tool = await _make_methodology_tool()
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_methodology_notes", {}, "call-1")]),
            AIMessage(content="done"),
            {"response_text": "ok"},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[tool])
    with caplog.at_level(logging.INFO, logger="agent.graph"):
        await graph.ainvoke({"current_query": "how does the forecast model work?"}, config=THREAD_CONFIG)

    node_lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("node=")]
    for expected_node in ("node=guardrail_router", "node=agent", "node=tools", "node=compose_response"):
        matches = [line for line in node_lines if line.startswith(expected_node + " ")]
        assert matches, f"no log line for {expected_node!r} -- got {node_lines}"
        assert "status=ok" in matches[0]
        assert "elapsed=" in matches[0]


async def test_tool_call_logs_cache_hit_and_miss(caplog):
    import logging

    tool = await _make_counter_tool()
    same_args = _tool_call("get_methodology_notes", {"n": 1}, "call-a")
    same_args_again = _tool_call("get_methodology_notes", {"n": 1}, "call-b")
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[same_args]),
            AIMessage(content="", tool_calls=[same_args_again]),
            AIMessage(content="done"),
            {"response_text": "ok"},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[tool])
    with caplog.at_level(logging.INFO, logger="agent.graph"):
        await graph.ainvoke({"current_query": "call it twice"}, config=THREAD_CONFIG)

    tool_call_lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("tool_call ")]
    assert any("cache=miss" in line and "get_methodology_notes" in line for line in tool_call_lines)
    assert any("cache=hit" in line and "elapsed=0.000s" in line for line in tool_call_lines)


async def test_ui_selection_llm_call_logs_timing(caplog):
    import logging

    async def _run(country: str = "China") -> dict:
        return {"country": country}

    tool = StructuredTool.from_function(coroutine=_run, name="get_country_profile", description="fake")
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_country_profile", {"country": "China"}, "call-1")]),
            AIMessage(content="done"),
            {"include_chart": True},
            {"response_text": "ok"},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[tool])
    with caplog.at_level(logging.INFO, logger="agent.graph"):
        result = await graph.ainvoke({"current_query": "what's China's emissions profile?"}, config=THREAD_CONFIG)

    assert len(result["widgets"]) == 2  # card + chart, since include_chart=True was scripted
    llm_call_lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("llm_call ")]
    assert any("node=ui_selection" in line and "elapsed=" in line for line in llm_call_lines)


# === Release 21 Section 3, step 3.3: model-facing cap and mandatory climate notes ============


def _fake_tool(name: str, payload: dict) -> StructuredTool:
    async def _run(**kwargs) -> dict:
        return payload

    return StructuredTool.from_function(coroutine=_run, name=name, description=f"fake {name}")


def _temperature_payload(n: int = 176) -> dict:
    return {
        "points": [{"year": 1850 + i, "value": i / 100} for i in range(n)],
        "summary": {"first_year": 1850, "last_year": 1850 + n - 1},
        "caveats": ["raw upstream caveat"],
        "details": {},
    }


async def test_model_sees_a_capped_tool_result_while_the_record_keeps_the_full_one():
    tool = _fake_tool("get_temperature_anomaly", _temperature_payload())
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_temperature_anomaly", {}, "t1")]),
            AIMessage(content="done"),
            {"response_text": "Warming shown."},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[tool])
    result = await graph.ainvoke({"current_query": "how much has temperature risen?"}, config=THREAD_CONFIG)

    record = result["tool_calls"][0]
    assert len(record.result["points"]) == 176  # the widget's source is the full series
    tool_msgs = [m for m in result["messages"] if isinstance(m, ToolMessage)]
    import json as _json

    seen = _json.loads(tool_msgs[0].content)
    assert seen["points_total"] == 176 and len(seen["points"]) <= 25
    assert seen["summary"]["last_year"] == 2025 and seen["caveats"] == ["raw upstream caveat"]
    assert llm.exhausted


async def test_cache_hit_also_serves_the_model_the_capped_view():
    tool = _fake_tool("get_temperature_anomaly", _temperature_payload())
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_temperature_anomaly", {}, "t1")]),
            AIMessage(content="", tool_calls=[_tool_call("get_temperature_anomaly", {}, "t2")]),  # same args -> cache hit
            AIMessage(content="done"),
            {"response_text": "ok"},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[tool])
    result = await graph.ainvoke({"current_query": "temperature?"}, config=THREAD_CONFIG)
    import json as _json

    contents = [_json.loads(m.content) for m in result["messages"] if isinstance(m, ToolMessage)]
    assert len(contents) == 2 and all(c["points_total"] == 176 for c in contents)


async def test_climate_tool_results_add_the_mandatory_notes_to_scope_notes():
    from agent.caveats import LONG_RUN_NOTE, PRELIMINARY_TEMPERATURE_NOTE

    tool = _fake_tool("get_emissions_temperature_relationship", {"points": [], "summary": {"source": "owid_co2"}})
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_emissions_temperature_relationship", {}, "r1")]),
            AIMessage(content="done"),
            {"response_text": "Related."},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[tool])
    result = await graph.ainvoke({"current_query": "how do emissions relate to warming?"}, config=THREAD_CONFIG)
    assert PRELIMINARY_TEMPERATURE_NOTE in result["scope_notes"] and LONG_RUN_NOTE in result["scope_notes"]


async def test_emissions_only_turns_get_no_climate_notes():
    graph = await build_graph(
        llm=ScriptedChatModel(
            [
                {"classification": "data_query"},
                AIMessage(content="", tool_calls=[_tool_call("get_methodology_notes", {}, "m1")]),
                AIMessage(content="done"),
                {"response_text": "Method."},
            ]
        ),
        mcp_tools=[await _make_methodology_tool()],
    )
    result = await graph.ainvoke({"current_query": "how does the forecast work?"}, config=THREAD_CONFIG)
    assert result["scope_notes"] == []


# === step 3.4: follow_up_links and the compose payload =======================================


async def test_follow_up_links_are_set_per_turn_and_reset_on_the_next():
    tool = _fake_tool("get_scenario_temperature", {"scenarios": {}, "summary": {"line": "both"}})
    meth = await _make_methodology_tool()
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_scenario_temperature", {}, "s1")]),
            AIMessage(content="done"),
            {"response_text": "Scenarios."},
            # second turn on the same thread: a methodology-only question
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_methodology_notes", {}, "m1")]),
            AIMessage(content="done"),
            {"response_text": "Method."},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[tool, meth])
    first = await graph.ainvoke({"current_query": "temperature by scenario"}, config=THREAD_CONFIG)
    assert [l.route for l in first["follow_up_links"]] == ["/climate-correlation#scenarios", "/scenarios"]
    second = await graph.ainvoke({"current_query": "how does the forecast work?"}, config=THREAD_CONFIG)
    assert second["follow_up_links"] == []  # reset at the turn boundary, not carried over


async def test_non_data_turns_have_no_follow_up_links():
    llm = ScriptedChatModel([{"classification": "off_topic"}])
    graph = await build_graph(llm=llm, mcp_tools=[])
    result = await graph.ainvoke({"current_query": "write a poem"}, config=THREAD_CONFIG)
    assert result["follow_up_links"] == []


async def test_compose_payload_carries_widget_summaries_and_kpis_but_not_other_props():
    import json as _json

    tool = _fake_tool(
        "get_emissions_temperature_relationship",
        {"points": [{"year": y} for y in range(60)], "summary": {"relationship": "headline long-run relationship", "window": [1850, 2024], "fit": {"slope": 0.486}, "source": "owid_co2"}},
    )
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_emissions_temperature_relationship", {}, "r1")]),
            AIMessage(content="done"),
            {"response_text": "ok"},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[tool])
    await graph.ainvoke({"current_query": "relationship between emissions and warming"}, config=THREAD_CONFIG)
    payload = _json.loads(llm.structured_calls[-1][1][-1].content)
    widget = payload["widgets"][0]
    assert widget["summary"]["fit"]["slope"] == 0.486 and "kpis" in payload
    assert "props" not in widget and "points" not in _json.dumps(widget)  # bulk props stay out
    assert "source_line" not in widget and "badge" not in widget  # presentation fields stay out too


async def test_compose_payload_has_no_summary_for_widgets_without_one():
    import json as _json

    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_methodology_notes", {}, "m1")]),
            AIMessage(content="done"),
            {"response_text": "ok"},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[await _make_methodology_tool()])
    await graph.ainvoke({"current_query": "how does the forecast work?"}, config=THREAD_CONFIG)
    assert "summary" not in _json.loads(llm.structured_calls[-1][1][-1].content)["widgets"][0]


# === step 3.5a: answer blocks through the graph ===================================================

_SCENARIO_RESULT = {
    "scenarios": {},
    "reading_note": "Scenarios diverge sharply in annual emissions by 2040 (2.2x), but temperatures differ by only 0.10 degC.",
    "summary": {
        "line": "both",
        "final_year_by_scenario": {
            "BAU": {"year": 2040, "headline_level_c": 1.68239, "annual_global_fossil_mt": 44877.4},
            "Moderate": {"year": 2040, "headline_level_c": 1.636621, "annual_global_fossil_mt": 33145.06},
            "Aggressive": {"year": 2040, "headline_level_c": 1.58219, "annual_global_fossil_mt": 20791.3},
        },
    },
}


async def test_a_scenario_only_turn_uses_the_deterministic_lead_with_no_compose_llm_call():
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_scenario_temperature", {}, "s1")]),
            AIMessage(content="done"),
            # NO compose script entry: reaching the LLM would raise "ran out of scripted responses"
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=[_fake_tool("get_scenario_temperature", _SCENARIO_RESULT)])
    result = await graph.ainvoke({"current_query": "how do temperature outcomes vary by pathway?"}, config=THREAD_CONFIG)
    assert result["response_text"].startswith("By 2040 the platform's three emissions pathways imply 1.58\u20131.68 \u00b0C above 1850\u20131900.")
    assert _SCENARIO_RESULT["reading_note"] in result["response_text"]
    assert [k.label for k in result["kpis"]] == ["BAU", "Moderate", "Aggressive"]
    assert result["widgets"][0].badge.startswith("Illustrative")
    assert llm.exhausted


async def test_answer_blocks_reach_the_result_event_and_reset_next_turn():
    from agent.follow_up_prompts import P_REL

    profile = {"country": "China", "years": [1990, 2023, 2024], "co2": [2483.5, 12000.0, 12289.0], "co2_per_capita": [2.15, 8.5, 8.66],
               "table": [{"year": 2024, "co2": 12289.0, "co2_per_capita": 8.66, "co2_yoy_pct_change": 1.0}]}
    tools = [_fake_tool("get_country_profile", profile), await _make_methodology_tool()]
    llm = ScriptedChatModel(
        [
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_country_profile", {"country": "China"}, "p1")]),
            AIMessage(content="done"),
            {"include_chart": False},
            {"response_text": "China emitted 12,289 Mt."},
            {"classification": "data_query"},
            AIMessage(content="", tool_calls=[_tool_call("get_methodology_notes", {}, "m1")]),
            AIMessage(content="done"),
            {"response_text": "Method."},
        ]
    )
    graph = await build_graph(llm=llm, mcp_tools=tools)
    first = await graph.ainvoke({"current_query": "China emissions"}, config=THREAD_CONFIG)
    assert [k.label for k in first["kpis"]] == ["CO\u2082 emissions", "Per capita", "Change vs 2023"]
    assert first["follow_up_prompts"][0] == "What share of historical emissions comes from China?" and P_REL in first["follow_up_prompts"]
    assert first["widgets"][0].source_line.startswith("Source: OWID, 1990\u20132024") and first["widgets"][0].summary["co2_mt"] == 12289.0
    second = await graph.ainvoke({"current_query": "how does the forecast work?"}, config=THREAD_CONFIG)
    assert second["kpis"] == [] and second["follow_up_prompts"] == []


# === Ask-page polish: no duplicate single-country chart ===========================================

_PROFILE_CHINA = {"country": "China", "years": [1990, 2024], "co2": [2483.5, 12289.0], "co2_per_capita": [2.15, 8.66],
                  "table": [{"year": 2024, "co2": 12289.0, "co2_per_capita": 8.66, "co2_yoy_pct_change": 1.0}]}


def _historical(*names):
    return {"gas": "co2", "series": [{"name": n, "years": [1990, 2024], "values": [1.0, 2.0]} for n in names]}


async def _profile_turn(historical_names, profile_arg="China", script_chart_choice=None):
    calls = [_tool_call("get_country_profile", {"country": profile_arg}, "p1")]
    tools = [_fake_tool("get_country_profile", _PROFILE_CHINA)]
    if historical_names:
        calls.append(_tool_call("get_historical_emissions", {"countries": historical_names}, "h1"))
        tools.append(_fake_tool("get_historical_emissions", _historical(*historical_names)))
    script = [{"classification": "data_query"}, AIMessage(content="", tool_calls=calls), AIMessage(content="done")]
    if script_chart_choice is not None:
        script.append({"include_chart": script_chart_choice})
    script.append({"response_text": "ok"})
    llm = ScriptedChatModel(script)
    graph = await build_graph(llm=llm, mcp_tools=tools)
    result = await graph.ainvoke({"current_query": "China's emissions trend"}, config=THREAD_CONFIG)
    return result, llm


async def test_profile_chart_is_dropped_when_a_historical_chart_already_covers_the_country():
    # No "include_chart" entry is scripted: reaching that LLM judgment call would raise.
    result, llm = await _profile_turn(["China", "India"], script_chart_choice=None)
    profile_widgets = [w for w in result["widgets"] if w.source_tool_call.startswith("get_country_profile")]
    assert [w.intent for w in profile_widgets] == ["card"]
    assert any(w.intent == "chart" and w.source_tool_call.startswith("get_historical_emissions") for w in result["widgets"])
    assert llm.exhausted


async def test_the_match_uses_the_resolved_country_name_so_a_typo_still_dedupes():
    result, llm = await _profile_turn(["China"], profile_arg="Chinaa")  # the fake returns the resolved "China"
    assert [w.intent for w in result["widgets"] if w.source_tool_call.startswith("get_country_profile")] == ["card"]
    assert llm.exhausted


async def test_the_profile_chart_is_kept_when_the_historical_chart_is_about_other_countries():
    result, llm = await _profile_turn(["India", "Brazil"], script_chart_choice=True)
    assert sorted(w.intent for w in result["widgets"] if w.source_tool_call.startswith("get_country_profile")) == ["card", "chart"]
    assert llm.exhausted


async def test_the_profile_chart_choice_is_unchanged_with_no_historical_call_at_all():
    result, llm = await _profile_turn(None, script_chart_choice=True)
    assert sorted(w.intent for w in result["widgets"]) == ["card", "chart"] and llm.exhausted


async def test_the_profile_chart_is_kept_when_the_historical_chart_is_a_different_gas():
    # Copilot review of #272: a methane/nitrous-oxide history for the same country is not a duplicate
    # of the profile's CO2 trend chart, so the profile chart (and its LLM choice) must stay.
    for gas in ("methane", "nitrous_oxide"):
        calls = [_tool_call("get_country_profile", {"country": "China"}, "p1"), _tool_call("get_historical_emissions", {"countries": ["China"], "gas": gas}, "h1")]
        hist = {"gas": gas, "series": [{"name": "China", "years": [1990, 2024], "values": [1.0, 2.0]}]}
        tools = [_fake_tool("get_country_profile", _PROFILE_CHINA), _fake_tool("get_historical_emissions", hist)]
        llm = ScriptedChatModel([{"classification": "data_query"}, AIMessage(content="", tool_calls=calls), AIMessage(content="done"), {"include_chart": True}, {"response_text": "ok"}])
        graph = await build_graph(llm=llm, mcp_tools=tools)
        result = await graph.ainvoke({"current_query": "China's emissions"}, config={"configurable": {"thread_id": f"gas-{gas}"}})
        assert sorted(w.intent for w in result["widgets"] if w.source_tool_call.startswith("get_country_profile")) == ["card", "chart"], gas
        assert llm.exhausted


def test_a_historical_result_with_no_gas_field_is_treated_as_co2():
    from agent.state import ToolCallRecord
    from agent.ui_selection import historical_chart_covers

    profile = ToolCallRecord(tool_name="get_country_profile", args={}, result={"country": "China"}, progress_label="x")
    bare = ToolCallRecord(tool_name="get_historical_emissions", args={}, result={"series": [{"name": "China"}]}, progress_label="x")
    methane = ToolCallRecord(tool_name="get_historical_emissions", args={}, result={"gas": "methane", "series": [{"name": "China"}]}, progress_label="x")
    assert historical_chart_covers(profile, [profile, bare]) is True
    assert historical_chart_covers(profile, [profile, methane]) is False


async def test_the_scenario_widget_is_flagged_when_the_lead_already_carries_the_reading_note():
    llm = ScriptedChatModel([{"classification": "data_query"}, AIMessage(content="", tool_calls=[_tool_call("get_scenario_temperature", {}, "s1")]), AIMessage(content="done")])
    graph = await build_graph(llm=llm, mcp_tools=[_fake_tool("get_scenario_temperature", _SCENARIO_RESULT)])
    result = await graph.ainvoke({"current_query": "pathways?"}, config=THREAD_CONFIG)
    assert result["widgets"][0].summary["lead_includes_reading_note"] is True
    assert _SCENARIO_RESULT["reading_note"] in result["response_text"]


async def test_the_flag_is_absent_when_the_lead_is_composed_across_tools():
    # Scenario + another data tool -> the lead is LLM-composed and need not carry the note, so the widget keeps its own panel.
    tools = [_fake_tool("get_scenario_temperature", _SCENARIO_RESULT), _fake_tool("get_top_emitters", {"year": 2024, "emitters": [{"country": "China", "co2": 1.0}]})]
    calls = [_tool_call("get_scenario_temperature", {}, "s1"), _tool_call("get_top_emitters", {}, "t1")]
    llm = ScriptedChatModel([{"classification": "data_query"}, AIMessage(content="", tool_calls=calls), AIMessage(content="done"), {"response_text": "composed"}])
    graph = await build_graph(llm=llm, mcp_tools=tools)
    result = await graph.ainvoke({"current_query": "pathways and top emitters"}, config=THREAD_CONFIG)
    scenario = next(w for w in result["widgets"] if w.source_tool_call.startswith("get_scenario_temperature"))
    assert "lead_includes_reading_note" not in (scenario.summary or {})
