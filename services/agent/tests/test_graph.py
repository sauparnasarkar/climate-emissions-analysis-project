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
