"""Preview server for the Ask page -- a design/QA aid, not a runtime component.

Serves the agent's real FastAPI app (`agent.server.app`: the real `/query` SSE route, real graph, real MCP tools, real `api/` data) with ONE
substitution: the LLM. A deterministic stand-in picks the tool calls from the question (the six starter prompts and the follow-up chips) and
writes a short lead from the answer blocks, so the whole page -- widgets, KPI row, source lines, links, chips -- can be reviewed and
screenshotted with real data and no Anthropic key. The lead text is a stand-in: production writes it with the model.

    # terminal 1 (repo root):   services/mcp-server/.venv/bin/python -m uvicorn api.main:app --port 8081
    # terminal 2:               cd services/mcp-server && API_BASE_URL=http://127.0.0.1:8081/api MCP_TRANSPORT=streamable-http \\
    #                           MCP_SERVER_PORT=8765 PYTHONPATH=src .venv/bin/python -m mcp_server
    # terminal 3:               cd services/agent && .venv/bin/python evals/preview_server.py        # serves :8766
    # terminal 4:               cd climate-dashboard-react && npm run dev    # its proxy sends /agent to :8766
"""

from __future__ import annotations

import json
import re
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import uvicorn  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402

from agent import server  # noqa: E402
from agent.graph import _default_checkpointer, build_graph  # noqa: E402
from agent.mcp_client import get_mcp_tools  # noqa: E402

TOP5 = ["China", "India", "United States", "Russia", "Japan"]

# (pattern on the lower-cased question, tool calls). First match wins; order matters.
PLANS: list[tuple[str, list[tuple[str, dict]]]] = [
    (r"relationship between cumulative emissions and warming", [("get_emissions_temperature_relationship", {})]),
    (r"temperature outcomes|emissions pathways", [("get_scenario_temperature", {})]),
    (r"share of historical emissions", [("get_country_cumulative_share", {"countries": ["China"]})]),
    (r"mix of co", [("get_ghg_composition", {})]),
    (r"atmospheric co", [("get_co2_concentration", {}), ("get_temperature_anomaly", {})]),
    (r"latest.*temperature|temperature anomaly", [("get_temperature_anomaly", {})]),
    (r"today's top 10 emitters compare|compare with the projected", [("get_top_emitters", {}), ("get_forecast_summary", {"scope": "expanded"})]),
    (r"top 10 forecasted", [("get_forecast_summary", {"scope": "expanded"})]),
    (r"china.*top 10|top 10.*china", [("get_top_emitters", {}), ("get_country_profile", {"country": "China"}), ("get_historical_emissions", {"countries": ["China", "India", "United States", "Russia", "Japan", "Germany", "Iran", "Saudi Arabia", "Indonesia", "South Korea"]})]),
    (r"india", [("get_country_profile", {"country": "India"}), ("get_historical_emissions", {"countries": TOP5})]),
]
DEFAULT_PLAN = [("get_methodology_notes", {})]


def plan_for(query: str) -> list[tuple[str, dict]]:
    q = query.lower()
    return next((calls for pat, calls in PLANS if re.search(pat, q)), DEFAULT_PLAN)


class _Structured:
    def __init__(self, schema):
        self.schema = schema

    async def ainvoke(self, messages):
        name = self.schema.__name__
        if name == "_Classification":
            return self.schema(classification="data_query")
        if name == "_CountryProfileSelection":
            return self.schema(include_chart=False)
        if name == "_ComposedResponse":
            return self.schema(response_text=compose_text(json.loads(messages[-1].content)))
        raise NotImplementedError(f"preview LLM has no stand-in for {name}")


def compose_text(payload: dict) -> str:
    """A stand-in lead built only from the answer blocks it is given."""
    kpis = payload.get("kpis") or []
    if kpis:
        k = kpis[0]
        n = f"{k['value']:,.{k.get('decimals', 0)}f}"
        return f"{k['label']} was {n} {k['unit']} in {k.get('year', 'the latest year')}. (Preview lead; production writes this with the model.)"
    titles = ", ".join(w["title"] for w in payload.get("widgets", [])[:2])
    return f"Here is {titles or 'what the data shows'}. (Preview lead; production writes this with the model.)"


class PreviewLLM:
    def bind_tools(self, tools):  # noqa: ARG002
        return self

    def with_structured_output(self, schema):
        return _Structured(schema)

    async def ainvoke(self, messages):
        last_human = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
        if any(isinstance(m, ToolMessage) for m in messages[last_human:]):
            return AIMessage(content="done")
        calls = plan_for(messages[last_human].content)
        return AIMessage(content="", tool_calls=[{"name": n, "args": a, "id": f"preview-{i}", "type": "tool_call"} for i, (n, a) in enumerate(calls)])


@asynccontextmanager
async def preview_lifespan(app):
    checkpointer = _default_checkpointer()
    tools = await get_mcp_tools()
    app.state.checkpointer, app.state.mcp_tools = checkpointer, tools
    app.state.graph = await build_graph(llm=PreviewLLM(), mcp_tools=tools, checkpointer=checkpointer)
    yield


if __name__ == "__main__":
    server.app.router.lifespan_context = preview_lifespan
    uvicorn.run(server.app, host="127.0.0.1", port=8766)
