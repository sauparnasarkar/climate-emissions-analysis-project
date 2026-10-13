"""Golden-prompt eval for the cumulative-share answers -- ENHANCEMENTS.md Release 24 §24.7.

Manually run, like `run_area2.py`, NOT part of pytest: it makes real LLM calls against a live `services/mcp-server` + `api/`. Run it on Sonnet before deploying a change to the
share tool, the prompts or the share widgets:

    # terminal 1: api/   (uvicorn api.main:app --port 8081)
    # terminal 2: services/mcp-server   (API_BASE_URL=http://127.0.0.1:8081/api python -m mcp_server)
    # terminal 3:
    cd services/agent && ANTHROPIC_API_KEY=... .venv/bin/python evals/run_cumulative.py [--only ID]

A case fails if (a) none of its expected tools was called, (b) the answer's text does not match what the case requires (a "not available" statement, a basis, a refusal to
attribute warming), (c) the widget view is not the one the question should get, or (d) `agent.area2_lint.check_response` flags the answer (with `share_answer=True`, so a
share quoted without what it is a share of is flagged too). Exit status 1 on any failure. The lint is a coarse net: read the printed answers too.
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import uuid
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent.area2_lint import check_response, check_units  # noqa: E402
from agent.graph import build_graph  # noqa: E402

SHARE_TOOL = "get_country_cumulative_share"
NOT_AVAILABLE = r"not available|isn't available|is not something|isn't something this data can provide|cannot|can't|can not|unable|doesn't (?:have|offer|support)|no way to"


@dataclass
class Case:
    id: str
    prompt: str
    expect_any_tool: set[str] = field(default_factory=set)
    must_match: str | None = None  # a regex the answer must contain
    must_not_match: str | None = None  # a regex the answer must not contain
    view: str | None = None  # the share widget's `view` the question must get; None = not checked


CASES = [
    # the five questions the release is for (24.1)
    Case("total", "How much CO₂ has China emitted in total?", {SHARE_TOOL}, view="cumulative_area"),
    Case("rising", "Is India's share of the world's cumulative CO₂ rising or falling?", {SHARE_TOOL}, must_match=r"rising|falling|steady", view="share_vs_annual"),
    Case("top-emitters-area", "Show cumulative emissions for China, the US and India since 1970.", {SHARE_TOOL}, view="cumulative_area"),
    Case("most-ever", "Which countries have emitted the most since records began?", {SHARE_TOOL}),
    Case("compare-share", "How do China and the US compare on cumulative share?", {SHARE_TOOL}, view="share_lines"),
    # traps
    Case("attribution", "How much of global warming is China responsible for?", {SHARE_TOOL}, must_match=r"not (?:a|an|the)?\s*(?:\w+\s+)?(?:measure|estimate|contribution|attribut)|(?:does not|doesn't) (?:measure|estimate|attribute|quantify|show|say)|can't (?:directly )?answer|where (?:CO₂ |emissions )?(?:was |were )?(?:emitted|occurred)", must_not_match=r"China (?:is|was) responsible for \d"),
    # "since YYYY" is the emissions in the period (D7): the answer names the period and is not the total from the first record; the old "not available" answer fails.
    Case("since-1990", "What is China's cumulative CO₂ since 1990?", {SHARE_TOOL}, must_match=r"1990\s*(?:[-–to]+|and)\s*2024|since 1990", must_not_match=r"not available|isn't restarted|isn’t restarted|second among|2nd (?:of|among)", view="cumulative_area"),
    Case("top-since-1970", "Which countries have emitted the most since 1970?", {SHARE_TOOL}, must_match=r"1970\s*(?:[-–to]+|and)\s*2024|since 1970", must_not_match=r"not available|couldn't|partial"),
    Case("methane", "How much cumulative methane has the US emitted?", set(), must_match=NOT_AVAILABLE),
    Case("unknown-country", "What is Zzyzxland's cumulative share of emissions?", set(), must_match=r"did you mean|no match|couldn't find|could not find|not (?:a )?recogni[sz]ed|isn't"),
    Case("basis", "What is the US's share of cumulative emissions?", {SHARE_TOOL}, must_match=r"world|global|PRIMAP"),
    Case("two-sources", "Compare China's cumulative share in OWID CO₂ and in PRIMAP-hist total greenhouse gases.", {SHARE_TOOL}, must_match=r"OWID.*PRIMAP|PRIMAP.*OWID"),
]


async def run_case(graph, case: Case) -> tuple[bool, list[str]]:
    config = {"configurable": {"thread_id": f"eval-cum-{case.id}-{uuid.uuid4().hex[:8]}"}}
    result = await graph.ainvoke({"current_query": case.prompt}, config=config)
    tools = [r.tool_name for r in result["tool_calls"]]
    problems: list[str] = []
    if case.expect_any_tool and not (case.expect_any_tool & set(tools)):
        problems.append(f"expected one of {sorted(case.expect_any_tool)}, called {tools or 'no tools'}")
    text = result["response_text"]
    if case.must_match and not re.search(case.must_match, text, re.I | re.S):
        problems.append(f"answer lacks /{case.must_match}/")
    if case.must_not_match and re.search(case.must_not_match, text, re.I | re.S):
        problems.append(f"answer matches the forbidden /{case.must_not_match}/")
    views = [w.view for w in result["widgets"] if w.source_tool_call.startswith(SHARE_TOOL)]
    if case.view and case.view not in views:
        problems.append(f"expected the {case.view!r} view, widgets had {views or 'no share widget'}")
    problems += check_response(text, result["scope_notes"], share_answer=True)
    problems += check_units(text, [w.summary for w in result["widgets"] if w.summary])  # a Gt figure written with Mt (a live answer said 434.9 Mt for the US's 434.9 Gt)
    print(f"\n=== {case.id}: {case.prompt}\n  classification={result['classification']} tools={tools} views={views}")
    print(f"  notes={len(result['scope_notes'])} widgets={len(result['widgets'])} links={[l.route for l in result.get('follow_up_links', [])]}\n  answer: {text[:700]}")
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
