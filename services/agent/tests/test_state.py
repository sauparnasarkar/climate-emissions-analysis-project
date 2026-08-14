from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, StateGraph

from agent.state import AgentState, ToolCallRecord, WidgetSpec


def test_agent_state_defaults():
    state = AgentState(current_query="What are China's emissions?")
    assert state.messages == []
    assert state.classification is None
    assert state.tool_calls == []
    assert state.tool_call_count == 0
    assert state.tool_cache == {}
    assert state.scope_notes == []
    assert state.widgets == []
    assert state.suggested_prompts == []
    assert state.response_text == ""


def test_agent_state_instances_do_not_share_mutable_defaults():
    a = AgentState(current_query="a")
    b = AgentState(current_query="b")
    a.scope_notes.append("only on a")
    assert b.scope_notes == []


def test_tool_call_record_round_trip():
    record = ToolCallRecord(
        tool_name="get_historical_emissions",
        args={"countries": ["China", "India"]},
        result={"data": [1, 2, 3]},
        progress_label="Fetching historical emissions for China, India",
    )
    assert record.tool_name == "get_historical_emissions"
    assert record.result == {"data": [1, 2, 3]}


def test_tool_call_record_accepts_non_dict_result():
    # `result: Any | None` is deliberately permissive -- every one of the 13 real
    # services/mcp-server tools today returns an object-shaped response (each api/ endpoint
    # declares a BaseModel response_model, never a bare top-level list), so `dict | None` would
    # be accurate for the current catalog. `Any` is kept anyway as forward-looking slack for
    # tool shapes added in later steps, not because a current tool needs it.
    record = ToolCallRecord(
        tool_name="hypothetical_future_tool",
        args={},
        result=["China", "India", "USA"],
        progress_label="Example",
    )
    assert record.result == ["China", "India", "USA"]


def test_widget_spec_requires_intent_and_rejects_unknown_chart_kind():
    widget = WidgetSpec(
        intent="chart",
        chart_kind="line",
        title="China historical emissions",
        source_tool_call="call-1",
        props={},
    )
    assert widget.chart_kind == "line"

    try:
        WidgetSpec(
            intent="chart",
            chart_kind="pie",  # not one of the five real SyChart kinds
            title="bad",
            source_tool_call="call-1",
            props={},
        )
        raise AssertionError("expected a validation error for an unsupported chart_kind")
    except ValueError:
        pass


def test_add_messages_reducer_appends_across_nodes():
    """Real StateGraph invocation, not just model construction -- the reducer only kicks in
    when LangGraph merges a node's returned partial update into the channel, so this is the
    only way to actually prove the annotation works on this Pydantic state shape."""

    def node_a(state: AgentState):
        return {"messages": [HumanMessage(content="hello")]}

    def node_b(state: AgentState):
        return {"messages": [AIMessage(content="world")]}

    graph = StateGraph(AgentState)
    graph.add_node("a", node_a)
    graph.add_node("b", node_b)
    graph.set_entry_point("a")
    graph.add_edge("a", "b")
    graph.add_edge("b", END)
    compiled = graph.compile()

    result = compiled.invoke(AgentState(current_query="test"))
    assert [m.content for m in result["messages"]] == ["hello", "world"]
