"""Agent state schema -- SPEC.md §7.

`AgentState` is passed as the state schema to LangGraph's `StateGraph`. `messages` uses the
`add_messages` reducer so that a node returning `{"messages": [new_msg]}` appends rather than
overwrites -- every other field uses LangGraph's default whole-value replace, which is what
`tool_calls`/`tool_call_count`/`tool_cache`/`scope_notes`/`widgets` all need (each node computes
and replaces its own owned fields; nothing else is auto-merged, e.g. `tool_cache` updates must be
returned as a full new dict from the node that mutates it).
"""

from typing import Annotated, Any, Literal

from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


class ToolCallRecord(BaseModel):
    tool_name: str
    args: dict
    result: Any | None = None
    progress_label: str


class WidgetSpec(BaseModel):
    intent: Literal["chart", "grid", "card", "text"]
    chart_kind: Literal["line", "bar", "band", "choropleth"] | None = None
    title: str
    as_of: str | None = None
    source_tool_call: str
    props: dict


class AgentState(BaseModel):
    messages: Annotated[list, add_messages] = Field(default_factory=list)
    current_query: str = ""
    classification: Literal["off_topic", "opinion", "general_climate", "data_query"] | None = None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    tool_call_count: int = 0
    tool_cache: dict[str, ToolCallRecord] = Field(default_factory=dict)
    scope_notes: list[str] = Field(default_factory=list)
    widgets: list[WidgetSpec] = Field(default_factory=list)
    suggested_prompts: list[str] = Field(default_factory=list)
    response_text: str = ""
