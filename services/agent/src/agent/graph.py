"""LangGraph node catalog -- SPEC.md §8.

Every LLM-backed node takes `llm` as an injectable argument (via `functools.partial` at graph-
build time) rather than calling `get_llm()` itself, so graph-routing tests can inject a stub and
never require a real `ANTHROPIC_API_KEY` -- see `llm.py`'s module docstring.

Turn-reset fields (SPEC.md §7/§8: "tool_calls/tool_call_count reset at the start of every turn,
before guardrail_router runs") are reset by `guardrail_router_node` itself, since it's the graph's
entry point and the only node guaranteed to run exactly once per turn before anything else. This
matters specifically because of how state persists across turns: `build_graph`'s checkpointer
keeps `AgentState` alive across separate `.invoke()` calls on the same `thread_id`, and invoking
with a *partial* update dict (e.g. `{"current_query": "..."}"`, not a fresh `AgentState(...)`)
is what makes that persistence actually work -- passing a full fresh model instance overwrites
every field, including `tool_cache`, which SPEC.md §7 requires to survive across turns. See
`tests/test_graph.py`'s persistence test for the empirical proof of both halves of this.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Awaitable, Callable
from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from .cache import cache_key
from .llm import get_llm
from .mcp_client import get_mcp_tools
from .progress_labels import progress_label
from .prompts import (
    AGENT_SYSTEM_PROMPT,
    COMPOSE_RESPONSE_SYSTEM_PROMPT,
    GENERAL_CLIMATE_SYSTEM_PROMPT,
    GUARDRAIL_SYSTEM_PROMPT,
    OFF_TOPIC_RESPONSE,
    OPINION_SYSTEM_PROMPT,
    UI_SELECTION_COUNTRY_PROFILE_PROMPT,
)
from .state import AgentState, ToolCallRecord, WidgetSpec
from .ui_selection import build_country_profile_widgets, build_widget, is_error_result

MAX_TOOL_CALLS_PER_TURN = 6  # SPEC.md §10 -- generous headroom, tune after real usage

ProgressCallback = Callable[[str], None]


class _Classification(BaseModel):
    classification: Literal["off_topic", "opinion", "general_climate", "data_query"]


class _OpinionOutput(BaseModel):
    response_text: str
    suggested_prompts: list[str]


class _CountryProfileSelection(BaseModel):
    include_chart: bool


class _ComposedResponse(BaseModel):
    response_text: str


def _reset_turn_fields() -> dict[str, Any]:
    return {
        "tool_calls": [],
        "tool_call_count": 0,
        "widgets": [],
        "scope_notes": [],
        "suggested_prompts": [],
        "response_text": "",
    }


async def guardrail_router_node(state: AgentState, *, llm: BaseChatModel) -> dict[str, Any]:
    classifier = llm.with_structured_output(_Classification)
    result = await classifier.ainvoke(
        [SystemMessage(content=GUARDRAIL_SYSTEM_PROMPT), *state.messages, HumanMessage(content=state.current_query)]
    )
    return {
        **_reset_turn_fields(),
        "classification": result.classification,
        "messages": [HumanMessage(content=state.current_query)],
    }


def route_after_guardrail(state: AgentState) -> Literal["off_topic", "opinion", "general_climate", "agent"]:
    if state.classification == "data_query":
        return "agent"
    return state.classification  # "off_topic" | "opinion" | "general_climate"


async def off_topic_node(state: AgentState) -> dict[str, Any]:
    return {"response_text": OFF_TOPIC_RESPONSE}


async def opinion_node(state: AgentState, *, llm: BaseChatModel) -> dict[str, Any]:
    structured = llm.with_structured_output(_OpinionOutput)
    result = await structured.ainvoke(
        [SystemMessage(content=OPINION_SYSTEM_PROMPT), HumanMessage(content=state.current_query)]
    )
    return {"response_text": result.response_text, "suggested_prompts": result.suggested_prompts}


async def general_climate_node(state: AgentState, *, llm: BaseChatModel) -> dict[str, Any]:
    messages = [SystemMessage(content=GENERAL_CLIMATE_SYSTEM_PROMPT), *state.messages]
    response = await llm.ainvoke(messages)
    widget = WidgetSpec(intent="text", title="Climate context", source_tool_call="general_climate", props={"text": response.content})
    return {"response_text": response.content, "widgets": [widget]}


async def agent_node(state: AgentState, *, llm: BaseChatModel, mcp_tools: list[BaseTool]) -> dict[str, Any]:
    bound = llm.bind_tools(mcp_tools)
    messages = [SystemMessage(content=AGENT_SYSTEM_PROMPT), *state.messages]
    ai_message: AIMessage = await bound.ainvoke(messages)
    return {"messages": [ai_message]}


def route_after_agent(state: AgentState) -> Literal["tools", "call_cap_notice", "ui_selection"]:
    last = state.messages[-1]
    pending = getattr(last, "tool_calls", None)
    if not pending:
        return "ui_selection"
    if state.tool_call_count >= MAX_TOOL_CALLS_PER_TURN:
        return "call_cap_notice"
    return "tools"


async def call_cap_notice_node(state: AgentState) -> dict[str, Any]:
    # A dedicated node, not a write inside route_after_agent -- conditional-edge functions only
    # supply a route, they don't produce channel updates; a state write there is silently
    # discarded. Only reachable when the agent still wanted to call a tool but was blocked, so
    # this never misfires on a turn that finished naturally exactly at the cap.
    note = f"Stopped after {MAX_TOOL_CALLS_PER_TURN} tool calls -- this response may be based on partial data."
    return {"scope_notes": [*state.scope_notes, note]}


def _text_from_content_blocks(blocks: list) -> str | None:
    # A real MCP tool's ToolMessage.content arrives as a list of LangChain content blocks
    # (langchain_mcp_adapters' conversion from the MCP wire protocol's CallToolResult), not a
    # plain string -- confirmed against a real services/mcp-server subprocess in
    # tests/test_graph.py's test_data_query_against_real_mcp_server, which a locally-built fake
    # StructuredTool (plain-string content) doesn't reproduce. Joins every text block's `text`;
    # returns None if there are no text blocks (e.g. an image-only result), so the caller can
    # fall back to passing the raw block list through untouched.
    texts = [block.get("text") for block in blocks if isinstance(block, dict) and block.get("type") == "text" and "text" in block]
    return "".join(texts) if texts else None


def _tool_result_from_message(message: ToolMessage) -> Any:
    content = message.content
    if isinstance(content, list):
        text = _text_from_content_blocks(content)
        content = text if text is not None else content
    if message.status == "error":
        return {"error": content}
    if isinstance(content, str):
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return content
    return content


async def tools_node(
    state: AgentState,
    *,
    mcp_tools: list[BaseTool],
    on_progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    tools_by_name = {tool.name: tool for tool in mcp_tools}
    last = state.messages[-1]
    pending_calls = getattr(last, "tool_calls", None) or []

    tool_calls = list(state.tool_calls)
    tool_cache = dict(state.tool_cache)
    tool_call_count = state.tool_call_count
    new_messages: list[ToolMessage] = []

    for call in pending_calls:
        # Every tool_use block needs a matching tool_result in the same turn, cap-exhausted or
        # not -- Anthropic 400s the next agent turn otherwise. So a skipped call still gets a
        # (error-status) ToolMessage, it just isn't executed and doesn't consume more budget.
        if tool_call_count >= MAX_TOOL_CALLS_PER_TURN:
            new_messages.append(
                ToolMessage(
                    content="Skipped -- this turn's tool-call budget is exhausted.",
                    tool_call_id=call["id"],
                    status="error",
                )
            )
            continue

        key = cache_key(call["name"], call["args"])
        if key in tool_cache:
            record = tool_cache[key]
            if on_progress:
                on_progress(f"Reusing: {record.progress_label}")
            is_error = isinstance(record.result, dict) and "error" in record.result
            content = record.result["error"] if is_error else json.dumps(record.result)
            new_messages.append(
                ToolMessage(content=content, tool_call_id=call["id"], status="error" if is_error else "success")
            )
        else:
            tool = tools_by_name.get(call["name"])
            label = progress_label(call["name"], call["args"])
            if tool is None:
                error_text = f"Unknown tool: {call['name']}"
                record = ToolCallRecord(
                    tool_name=call["name"], args=call["args"], result={"error": error_text}, progress_label=label
                )
                new_messages.append(ToolMessage(content=error_text, tool_call_id=call["id"], status="error"))
            else:
                if on_progress:
                    on_progress(label)
                tool_message: ToolMessage = await tool.ainvoke(call)
                result = _tool_result_from_message(tool_message)
                record = ToolCallRecord(tool_name=call["name"], args=call["args"], result=result, progress_label=label)
                new_messages.append(tool_message)
            tool_cache[key] = record

        tool_calls.append(record)
        tool_call_count += 1

    return {
        "tool_calls": tool_calls,
        "tool_cache": tool_cache,
        "tool_call_count": tool_call_count,
        "messages": new_messages,
    }


async def ui_selection_node(state: AgentState, *, llm: BaseChatModel) -> dict[str, Any]:
    widgets: list[WidgetSpec] = []
    for record in state.tool_calls:
        if is_error_result(record.result):
            continue  # no widget from a failed call, and no point spending an LLM call on it
        if record.tool_name == "get_country_profile":
            structured = llm.with_structured_output(_CountryProfileSelection)
            selection = await structured.ainvoke(
                [SystemMessage(content=UI_SELECTION_COUNTRY_PROFILE_PROMPT), HumanMessage(content=state.current_query)]
            )
            widgets.extend(build_country_profile_widgets(record, include_chart=selection.include_chart))
        else:
            widget = build_widget(record, state.current_query)
            if widget is not None:
                widgets.append(widget)
    return {"widgets": widgets}


async def compose_response_node(state: AgentState, *, llm: BaseChatModel) -> dict[str, Any]:
    structured = llm.with_structured_output(_ComposedResponse)
    widgets_summary = [w.model_dump(exclude={"props"}) for w in state.widgets]
    payload = json.dumps({"query": state.current_query, "widgets": widgets_summary, "scope_notes": state.scope_notes})
    result = await structured.ainvoke([SystemMessage(content=COMPOSE_RESPONSE_SYSTEM_PROMPT), HumanMessage(content=payload)])
    return {"response_text": result.response_text}


async def finalize_node(state: AgentState) -> dict[str, Any]:
    # The one place a compact assistant-turn summary is appended to `messages` -- individual
    # path nodes (off_topic/opinion/general_climate/compose_response) deliberately don't append
    # their own raw output, avoiding duplicate/near-duplicate messages across turns. Full widget
    # payloads are never appended, to bound context growth (SPEC.md §8's finalize row).
    summary = state.response_text[:500] if state.response_text else "(no response text)"
    return {"messages": [AIMessage(content=summary)]}


async def build_graph(
    llm: BaseChatModel | None = None,
    mcp_tools: list[BaseTool] | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
    on_progress: ProgressCallback | None = None,
) -> CompiledStateGraph:
    """Builds and compiles the full graph. `mcp_tools` is fetched once here (async, hence this
    factory is async too) rather than inside `agent_node`/`tools_node` per invocation -- fetching
    per node call would refetch the tool list on every single turn and every loop iteration.

    A checkpointer is required for SPEC.md §7's thread-scoped `tool_cache`/`messages`
    persistence to actually work across turns -- defaults to an in-process `MemorySaver` (this
    service runs as a single, unreplicated process; losing in-flight conversations on restart is
    acceptable, matching this project's "no server-side caching beyond what's explicit" bias).
    Callers must invoke the compiled graph with a partial update dict (e.g.
    `{"current_query": "..."}"`) under a stable `config={"configurable": {"thread_id": ...}}`,
    not a fresh `AgentState(...)` instance -- see this module's docstring.
    """
    llm = llm or get_llm()
    if mcp_tools is None:
        mcp_tools = await get_mcp_tools()

    graph: StateGraph[AgentState] = StateGraph(AgentState)
    graph.add_node("guardrail_router", functools.partial(guardrail_router_node, llm=llm))
    graph.add_node("off_topic", off_topic_node)
    graph.add_node("opinion", functools.partial(opinion_node, llm=llm))
    graph.add_node("general_climate", functools.partial(general_climate_node, llm=llm))
    graph.add_node("agent", functools.partial(agent_node, llm=llm, mcp_tools=mcp_tools))
    graph.add_node("tools", functools.partial(tools_node, mcp_tools=mcp_tools, on_progress=on_progress))
    graph.add_node("call_cap_notice", call_cap_notice_node)
    graph.add_node("ui_selection", functools.partial(ui_selection_node, llm=llm))
    graph.add_node("compose_response", functools.partial(compose_response_node, llm=llm))
    graph.add_node("finalize", finalize_node)

    graph.set_entry_point("guardrail_router")
    graph.add_conditional_edges(
        "guardrail_router",
        route_after_guardrail,
        {"off_topic": "off_topic", "opinion": "opinion", "general_climate": "general_climate", "agent": "agent"},
    )
    graph.add_conditional_edges(
        "agent",
        route_after_agent,
        {"tools": "tools", "call_cap_notice": "call_cap_notice", "ui_selection": "ui_selection"},
    )
    graph.add_edge("tools", "agent")
    graph.add_edge("call_cap_notice", "ui_selection")
    graph.add_edge("ui_selection", "compose_response")
    graph.add_edge("compose_response", "finalize")
    graph.add_edge("off_topic", "finalize")
    graph.add_edge("opinion", "finalize")
    graph.add_edge("general_climate", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=checkpointer or MemorySaver())
