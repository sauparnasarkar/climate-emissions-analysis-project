import uuid

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from agent.graph import build_graph
from agent.server import app, get_graph

from .fakes import ScriptedChatModel


def test_health():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def _tool_call(name: str, args: dict, call_id: str) -> dict:
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


async def _make_methodology_tool() -> StructuredTool:
    async def _run() -> dict:
        return {"notes": "ETS(A,Ad,N) explanation..."}

    return StructuredTool.from_function(coroutine=_run, name="get_methodology_notes", description="fake")


def _parse_sse(body: str) -> list[dict]:
    """Minimal SSE parser -- splits on blank-line-separated events, extracts `event:`/`data:`
    fields. Good enough for asserting on this test suite's own known-shape output, not a
    general-purpose SSE client. `sse_starlette`'s `EventSourceResponse` writes `\\r\\n` line
    endings (per the SSE spec), not bare `\\n` -- normalize first, or a naive `split("\\n\\n")`
    never matches and every event gets silently merged into one (confirmed empirically: this
    exact bug, not a real server bug, was the first version of this helper)."""
    normalized = body.replace("\r\n", "\n")
    events = []
    for block in normalized.strip().split("\n\n"):
        event_type = None
        data_lines = []
        for line in block.splitlines():
            if line.startswith("event:"):
                event_type = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data_lines.append(line[len("data:") :].strip())
        if event_type:
            events.append({"event": event_type, "data": "\n".join(data_lines)})
    return events


async def test_query_streams_progress_then_result():
    import json

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
    app.dependency_overrides[get_graph] = lambda: graph
    try:
        client = TestClient(app)
        response = client.post("/query", json={"query": "how does the forecast model work?"})
    finally:
        app.dependency_overrides.pop(get_graph, None)

    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert [e["event"] for e in events] == ["progress", "result"]

    progress_payload = json.loads(events[0]["data"])
    assert progress_payload["label"] == "Fetching methodology notes"
    assert progress_payload["percent"] < 100

    result_payload = json.loads(events[1]["data"])
    assert result_payload["response_text"] == "Here's the methodology."
    assert result_payload["percent"] == 100
    assert len(result_payload["widgets"]) == 1
    assert result_payload["widgets"][0]["intent"] == "text"
    uuid.UUID(result_payload["thread_id"])  # server-minted, must be a real UUID


def test_query_rejects_malformed_thread_id():
    # get_graph() is resolved (as a FastAPI dependency) before the endpoint body runs its own
    # thread_id validation, so app.state.graph must exist for *any* request to this route, even
    # one that's about to be rejected -- a placeholder is fine here since stream_query() is never
    # reached.
    app.dependency_overrides[get_graph] = lambda: object()
    try:
        client = TestClient(app)
        response = client.post("/query", json={"query": "hello", "thread_id": "not-a-uuid"})
    finally:
        app.dependency_overrides.pop(get_graph, None)
    assert response.status_code == 400


async def test_query_against_real_mcp_server(running_mcp_server):
    """The one true end-to-end test: a real services/mcp-server subprocess, through the real
    ASGI /query endpoint (not calling stream_query directly) -- proves the FastAPI/SSE wiring
    and the real MCP wire protocol fit together, not just each in isolation."""
    import json

    from agent.mcp_client import get_mcp_tools

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
    app.dependency_overrides[get_graph] = lambda: graph
    try:
        client = TestClient(app)
        response = client.post("/query", json={"query": "how does the forecast model work?"})
    finally:
        app.dependency_overrides.pop(get_graph, None)

    events = _parse_sse(response.text)
    assert [e["event"] for e in events] == ["progress", "result"]
    result_payload = json.loads(events[1]["data"])
    assert result_payload["response_text"] == "Here's the real methodology."
