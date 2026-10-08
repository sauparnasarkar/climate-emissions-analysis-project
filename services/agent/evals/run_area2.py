"""Golden-prompt eval for the Area 2 climate-context guardrails -- SPEC.md §15.3 rule 6.

A manually-run script, NOT part of the pytest suite: it makes real LLM calls against a live
`services/mcp-server` + `api/`, and `CLAUDE.md` allows exactly one (gated) real-network LLM test
(`tests/test_llm_smoke.py`). Run it before deploying a prompt or guardrail change, on Sonnet (the
validated provider; Qwen is selectable but untested for climate-context questions):

    # terminal 1: api/   (uvicorn api.main:app --port 8081)
    # terminal 2: services/mcp-server   (API_BASE_URL=http://127.0.0.1:8081/api python -m mcp_server)
    # terminal 3:
    cd services/agent && ANTHROPIC_API_KEY=... .venv/bin/python evals/run_area2.py [--only ID]

Each prompt goes through the real graph. A case fails if (a) none of its expected tools was
called, or (b) `agent.area2_lint.check_response` flags the answer or the notes. Exit status 1 on
any failure, so it can gate a deploy. The lint is a coarse net: read the printed answers too.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent.area2_lint import check_response  # noqa: E402
from agent.graph import build_graph  # noqa: E402


@dataclass
class Case:
    id: str
    prompt: str
    expect_any_tool: set[str] = field(default_factory=set)  # empty = no tool expected (e.g. a refusal)
    scenario_answer: bool = False


CASES = [
    Case("headline", "Show the relationship between cumulative emissions and warming.", {"get_emissions_temperature_relationship"}),
    Case("scenarios", "How do temperature outcomes vary based on different emissions pathways?", {"get_scenario_temperature"}, scenario_answer=True),
    Case("co2-vs-emissions", "How has atmospheric CO2 changed over time compared with emissions growth?", {"get_co2_concentration"}),
    Case("gas-mix", "How has the mix of CO2, methane, nitrous oxide and F-gases changed?", {"get_ghg_composition"}),
    Case("share", "What share of historical emissions comes from China?", {"get_country_cumulative_share"}),
    Case("attribution-trap", "Which country is responsible for the most global warming?", {"get_country_cumulative_share"}),
    Case("tcre-trap", "Is the 1970-onward all-gas relationship the same thing as TCRE?", {"get_emissions_temperature_relationship", "get_methodology_notes"}),
    Case("combined", "Which countries contribute most to current emissions while global warming increases?", {"get_top_emitters", "get_country_cumulative_share", "get_temperature_anomaly"}),
    Case("unsupported-baseline", "Fit the all-gas relationship from a pre-industrial baseline.", {"get_emissions_temperature_relationship"}),
    Case("methodology", "How reliable is the slope between emissions and warming?", {"get_methodology_notes", "get_emissions_temperature_relationship"}),
]


async def run_case(graph, case: Case) -> tuple[bool, list[str]]:
    config = {"configurable": {"thread_id": f"eval-{case.id}-{uuid.uuid4().hex[:8]}"}}
    result = await graph.ainvoke({"current_query": case.prompt}, config=config)
    tools = [r.tool_name for r in result["tool_calls"]]
    problems: list[str] = []
    if case.expect_any_tool and not (case.expect_any_tool & set(tools)):
        problems.append(f"expected one of {sorted(case.expect_any_tool)}, called {tools or 'no tools'}")
    text = result["response_text"]
    problems += check_response(text, result["scope_notes"], scenario_answer=case.scenario_answer)
    print(f"\n=== {case.id}: {case.prompt}\n  classification={result['classification']} tools={tools}")
    print(f"  notes={len(result['scope_notes'])} widgets={len(result['widgets'])}\n  answer: {text[:600]}")
    for p in problems:
        print(f"  !! {p}")
    return not problems, problems


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", help="run one case id")
    args = parser.parse_args()
    cases = [c for c in CASES if not args.only or c.id == args.only]
    if not cases:
        print(f"no case {args.only!r}; ids: {[c.id for c in CASES]}")
        return 2
    graph = await build_graph()
    failures = 0
    for case in cases:
        ok, _ = await run_case(graph, case)
        failures += not ok
    print(f"\n{len(cases) - failures}/{len(cases)} cases clean")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
