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

Progress events (SPEC.md §5) are read from `graph.astream(..., stream_mode="updates")`, not a
callback baked into `tools_node` at build time -- a callback bound once at graph-construction
time would have every concurrent request's progress interleave into whichever caller's queue
was bound first, since Step 3's server builds and reuses one graph across all requests. Each
`ToolCallRecord` already carries its own `progress_label`, so the `tools` node's per-superstep
update dict is enough on its own; `server.py` does the diffing against what it's already
streamed. This does mean a label surfaces after that tool call finishes, not before it starts
(`stream_mode="updates"` emits post-node) -- acceptable per SPEC.md §5's own "running estimate"
framing, and far simpler than `astream_events`' pre-execution `on_tool_start` hook.
"""

from __future__ import annotations

import functools
import json
import logging
from typing import Any, Literal

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, field_validator

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

logger = logging.getLogger(__name__)

MAX_TOOL_CALLS_PER_TURN = 6  # SPEC.md §10 -- generous headroom, tune after real usage


class _Classification(BaseModel):
    classification: Literal["off_topic", "opinion", "general_climate", "data_query"]


class _OpinionOutput(BaseModel):
    response_text: str
    suggested_prompts: list[str]

    @field_validator("suggested_prompts", mode="before")
    @classmethod
    def _coerce_single_reframe_to_list(cls, v: object) -> object:
        # Confirmed live in production (SPEC.md "Corrections applied" #31): grounding
        # suggested_prompts in the real tool catalog (#29) can narrow the model down to a
        # single good reframe, and it sometimes returns that as a bare string instead of a
        # one-element list -- a schema technicality, not a content problem, but one that
        # previously crashed the entire turn (ValidationError -> the generic client-facing
        # "Something went wrong" message, worse than the original ungrounded-suggestion issue
        # this was fixing). Tolerate the shape rather than failing on it.
        return [v] if isinstance(v, str) else v


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


def _capability_summary(mcp_tools: list[BaseTool]) -> str:
    """First paragraph of each tool's own docstring, whitespace-collapsed to one line -- every
    tool docstring in services/mcp-server leads with a plain-language summary sentence(s) before
    the IMPORTANT/edge-case detail paragraphs meant for the tool-calling model, not for grounding
    a reframe suggestion (SPEC.md "Corrections applied" #28 already stops user-facing text from
    referencing tool names directly -- this only ever surfaces what each tool is *for*, never its
    name)."""
    lines = []
    for t in mcp_tools:
        first_paragraph = t.description.strip().split("\n\n")[0]
        lines.append(f"- {' '.join(first_paragraph.split())}")
    return "\n".join(lines)


async def opinion_node(state: AgentState, *, llm: BaseChatModel, mcp_tools: list[BaseTool]) -> dict[str, Any]:
    # SPEC.md "Corrections applied" #29: opinion_node used to have zero grounding in the real
    # tool catalog, so its reframe suggestions were plausible-sounding guesses about what a
    # climate-emissions dataset "should" support, not what this one actually does -- confirmed
    # live (suggested a sector-level breakdown reframe when the dataset only tracks gas type).
    structured = llm.with_structured_output(_OpinionOutput)
    system_prompt = OPINION_SYSTEM_PROMPT
    if mcp_tools:
        system_prompt = f"{OPINION_SYSTEM_PROMPT}\n\nCapability summary:\n{_capability_summary(mcp_tools)}"
    result = await structured.ainvoke(
        [SystemMessage(content=system_prompt), HumanMessage(content=state.current_query)]
    )
    return {"response_text": result.response_text, "suggested_prompts": result.suggested_prompts}


async def general_climate_node(state: AgentState, *, llm: BaseChatModel) -> dict[str, Any]:
    messages = [SystemMessage(content=GENERAL_CLIMATE_SYSTEM_PROMPT), *state.messages]
    response = await llm.ainvoke(messages)
    widget = WidgetSpec(intent="text", title="Climate context", source_tool_call="general_climate", props={"text": response.content})
    return {"response_text": response.content, "widgets": [widget]}


async def agent_node(state: AgentState, *, llm: BaseChatModel, mcp_tools: list[BaseTool]) -> dict[str, Any]:
    bound = llm.bind_tools(mcp_tools)
    # cache_control on the system block caches AGENT_SYSTEM_PROMPT *and* the ~13 MCP tool
    # schemas bound above -- Anthropic's render order is tools -> system -> messages, so one
    # breakpoint here covers both. This is the one call site worth marking: it repeats
    # identically on every agent<->tools loop iteration within a turn (up to
    # MAX_TOOL_CALLS_PER_TURN) and across every user's query, and the tool-schema payload alone
    # measures ~12.5K characters (~3K+ tokens) against the real deployed services/mcp-server --
    # comfortably over Sonnet's 1024-token cache-eligibility floor. The other five LLM nodes
    # each carry a single-shot prompt under that floor; marking them would only add the
    # cache-write premium with no read-side payoff, so this is deliberately not applied there.
    # ChatAnthropic's own top-level `cache_control` kwarg only auto-hoists onto the last
    # eligible block for non-direct transports (e.g. Bedrock) -- confirmed by reading
    # langchain_anthropic's source directly, not assumed -- so the direct API this service uses
    # needs the block-level form below instead.
    # `cache_control` is an Anthropic-only content-block key. Gated on the actual injected `llm`
    # (isinstance check), not the `LLM_PROVIDER` env var -- graph-building functions take `llm` as
    # an argument precisely so it can be swapped independently of env vars (e.g. a caller could
    # inject ChatOpenAI directly without setting LLM_PROVIDER), so the env var isn't authoritative
    # over what was actually passed in. ScriptedChatModel (the fake used in tests) isn't a
    # ChatOpenAI instance, so the unit test pinning this block's presence still exercises it.
    if isinstance(llm, ChatOpenAI):
        system_message = SystemMessage(content=AGENT_SYSTEM_PROMPT)
    else:
        system_message = SystemMessage(
            content=[{"type": "text", "text": AGENT_SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}]
        )
    messages = [system_message, *state.messages]
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
            # Note: the record kept here retains its original progress_label (not re-prefixed
            # "Reusing: ..." per SPEC.md §9's pseudocode) -- server.py's SSE progress stream reads
            # labels straight off ToolCallRecord via astream(stream_mode="updates"), with no live
            # callback to decorate per-instance (see this module's docstring). A cache hit's
            # progress event is therefore indistinguishable from a fresh fetch's; the functional
            # guarantee (no re-fetch, still counts toward the §10 cap) is unaffected.
            record = tool_cache[key]
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
                logger.warning("tools_node: %s", error_text)
                record = ToolCallRecord(
                    tool_name=call["name"], args=call["args"], result={"error": error_text}, progress_label=label
                )
                new_messages.append(ToolMessage(content=error_text, tool_call_id=call["id"], status="error"))
            else:
                tool_message: ToolMessage = await tool.ainvoke(call)
                result = _tool_result_from_message(tool_message)
                if is_error_result(result):
                    logger.warning("tools_node: %s failed: %s", call["name"], result.get("error"))
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

    scope_notes = state.scope_notes
    failed_records = [record for record in state.tool_calls if is_error_result(record.result)]
    # Distinguishes "every tool call this turn failed" (a real backend/network problem) from
    # "tools succeeded but nothing matched a widget" -- without this, compose_response_node sees
    # an empty widgets list either way and invents a generic "try rephrasing" apology even when
    # the actual cause was a transient failure, not an ambiguous query.
    if state.tool_calls and len(failed_records) == len(state.tool_calls):
        note = "The underlying data service didn't return results for this query -- this looks like a transient failure, not a problem with the question itself."
        logger.warning("ui_selection_node: all %d tool call(s) this turn failed", len(state.tool_calls))
        scope_notes = [*scope_notes, note]
    elif failed_records:
        # Some (not all) calls failed this turn. compose_response_node only ever sees widgets
        # (built from successful calls only) and scope_notes -- a failed call otherwise leaves
        # zero trace anywhere in its payload, so without this note it has no way to know part of
        # the answer is missing and will narrate confidently from only the data it did get. This
        # is a distinctly-worded note (not "transient failure", reserved for the all-failed case
        # above) so it doesn't trip test_partial_tool_failure_does_not_trigger_transient_failure_note.
        # scope_notes reaches the client verbatim (server.py streams it, rendered as an
        # InlineAlert) -- AGENT_SYSTEM_PROMPT explicitly forbids ever naming a tool/function to
        # the user, and list_countries in particular is internal-only and must never surface at
        # all. Uses each record's own progress_label (already the plain-language description
        # tools_node computed, e.g. "Fetching China's emissions profile") instead of tool_name;
        # the raw tool name stays confined to the log line below.
        failed_descriptions = sorted({record.progress_label for record in failed_records})
        note = f"Some of the data needed to fully answer this couldn't be retrieved ({', '.join(failed_descriptions)}) -- this response may be based on partial data."
        logger.warning(
            "ui_selection_node: %d of %d tool call(s) this turn failed (%s)",
            len(failed_records),
            len(state.tool_calls),
            ", ".join(sorted({record.tool_name for record in failed_records})),
        )
        scope_notes = [*scope_notes, note]

    result: dict[str, Any] = {"widgets": widgets, "scope_notes": scope_notes}

    if not state.tool_calls:
        # A data_query turn that made zero tool calls at all -- confirmed reachable (SPEC.md
        # correction #21), and confirmed *correct* model behavior, not a bug: with a substantial
        # prior tool result still in context (e.g. a previous turn's get_historical_emissions),
        # the model can reasonably answer a follow-up directly instead of re-fetching data it
        # already has -- exactly what Claude Desktop's own MCP client does for the same sequence.
        # agent_node's own final message already carries that real, data-grounded answer; route_
        # after_ui_selection sends this turn straight to finalize instead of compose_response_node,
        # which has no widgets to synthesize from and would otherwise invent a misleading "no data"
        # apology that contradicts what the model just said.
        #
        # A widget is built here too (SPEC.md correction #22), not just response_text -- mirroring
        # general_climate_node's own text-only pattern, but with a distinct "context_reuse" tag
        # rather than reusing "general_climate": the two are semantically different (this path
        # reused prior tool data; general_climate never calls a tool at all) even though they
        # render identically. Without a widget, the frontend's `!hasWidgets` check (AgentPage.tsx)
        # -- meant to flag off_topic/opinion's short guardrail text as an InlineAlert -- also
        # caught this path's substantive, often markdown-table-heavy answers, showing them inside
        # an alert box instead of as a normal response. Confirmed live before this fix.
        last = state.messages[-1]
        content = last.content
        text = _text_from_content_blocks(content) if isinstance(content, list) else content
        text = text or "(no response text)"
        result["response_text"] = text
        result["widgets"] = [WidgetSpec(intent="text", title="Answer", source_tool_call="context_reuse", props={"text": text})]

    return result


def route_after_ui_selection(state: AgentState) -> Literal["compose_response", "finalize"]:
    # Zero tool calls this turn means ui_selection_node already set response_text directly from
    # agent_node's own answer -- compose_response_node has no widgets to synthesize from in that
    # case and would overwrite a good answer with an apology. See ui_selection_node's own comment.
    return "compose_response" if state.tool_calls else "finalize"


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
    #
    # This turn's raw agent<->tools round trip (tool_use AIMessages and ToolMessages) is
    # deliberately left in `state.messages`, not pruned -- SPEC.md correction #21. An earlier draft
    # of this fix pruned it via RemoveMessage on the theory that a large prior tool result (e.g.
    # get_historical_emissions(scope="sovereign")'s ~31KB/215-country payload) left in context was
    # confusing the model into skipping tool calls on a later, unrelated turn. Confirmed wrong: the
    # model's own text for that "skipped" turn was a correct, data-grounded answer reusing the
    # prior tool result already in context -- exactly what Claude Desktop's own MCP client does for
    # the same sequence, not a malfunction. Pruning this history would have silently traded away
    # that reuse capability (forcing a wasteful re-fetch on every follow-up) to paper over a
    # different bug, now fixed properly in ui_selection_node/route_after_ui_selection instead.
    summary = state.response_text[:500] if state.response_text else "(no response text)"
    return {"messages": [AIMessage(content=summary)]}


def _default_checkpointer() -> MemorySaver:
    # allowed_msgpack_modules is required, not cosmetic: without it, langgraph's default serde
    # logs "Deserializing unregistered type ... will be blocked in a future version" every time
    # tool_cache (dict[str, ToolCallRecord]) round-trips through a checkpoint, and a future
    # langgraph version turns that into a hard failure. Confirmed empirically that both
    # ToolCallRecord and WidgetSpec need registering -- both flow through persisted state.
    serde = JsonPlusSerializer(
        allowed_msgpack_modules=[("agent.state", "ToolCallRecord"), ("agent.state", "WidgetSpec")]
    )
    return MemorySaver(serde=serde)


async def build_graph(
    llm: BaseChatModel | None = None,
    mcp_tools: list[BaseTool] | None = None,
    checkpointer: BaseCheckpointSaver | None = None,
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
    graph.add_node("opinion", functools.partial(opinion_node, llm=llm, mcp_tools=mcp_tools))
    graph.add_node("general_climate", functools.partial(general_climate_node, llm=llm))
    graph.add_node("agent", functools.partial(agent_node, llm=llm, mcp_tools=mcp_tools))
    graph.add_node("tools", functools.partial(tools_node, mcp_tools=mcp_tools))
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
    graph.add_conditional_edges(
        "ui_selection",
        route_after_ui_selection,
        {"compose_response": "compose_response", "finalize": "finalize"},
    )
    graph.add_edge("compose_response", "finalize")
    graph.add_edge("off_topic", "finalize")
    graph.add_edge("opinion", "finalize")
    graph.add_edge("general_climate", "finalize")
    graph.add_edge("finalize", END)

    return graph.compile(checkpointer=checkpointer or _default_checkpointer())
