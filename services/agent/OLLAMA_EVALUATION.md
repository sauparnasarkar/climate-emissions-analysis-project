# Local LLM Evaluation (Ollama) — `services/agent`

**Status:** local experiment, not a settled decision. `qwen2.5:14b-ctx8k` is live as an active
trial on the deployed instance; Claude Sonnet 5 remains CLAUDE.md's documented production model
and stays one plist edit away as the fallback. See `LLM_PROVIDER=ollama` in
[`src/agent/llm.py`](src/agent/llm.py) for the switch itself.

## Why

The deployed agent's public endpoint runs on a Mac Mini with 16GB RAM. Running a local Ollama
model instead of the Anthropic API removes per-query API cost, at the cost of local inference
speed and (as this evaluation found) real correctness risk that varies sharply by model choice.

## Models tried, in order

| Model | Verdict | Key finding |
|---|---|---|
| `qwen2.5-coder:7b` | **Rejected outright** | `bind_tools()` never populated `AIMessage.tool_calls` — tool-call JSON came back as plain text content instead of a structured call. On an off-topic query it fabricated a call to a tool that was never bound. Not a prompt-tuning problem; structurally broken for this graph's tool-calling path. |
| `llama3.1:8b` | **Rejected after full-battery testing** | Passed initial spot-checks, but a 30-case guardrail battery plus testing against the real production starter prompts exposed a reliable bug: list-typed tool arguments were serialized as Python-repr strings (`"['China']"` instead of a real JSON array `["China"]`), breaking every multi-country tool (`get_historical_emissions`, `get_forecast_comparison`, `compare_scenarios_across_countries`). All 4 of the real starter prompts from `climate-dashboard-react`'s `AgentPage.tsx` failed under this model — 0/4. Also picked the wrong tool for forecast-year queries and made duplicate tool calls in the same turn. |
| `qwen2.5:14b` → `qwen2.5:14b-ctx8k` | **Adopted (trial)** | Fixed the list-serialization bug outright — real JSON arrays every time. Full 30-case battery: **30/30 correct, 0 errors**, matching Anthropic's own 30/30 on the identical battery. The base `qwen2.5:14b` (Ollama's default 4096-token context) genuinely *stalled* on a compound query — sat at ~0.2% CPU for 4+ minutes with zero progress, occupying Ollama's single inference slot (`-np 1`) until the runner process was manually killed. Root cause: the larger multi-round tool-schema payload was hitting the context ceiling. A custom `qwen2.5:14b-ctx8k` model tag (`ollama create ... num_ctx: 8192`) resolved the stall completely — same query then completed in ~2m13s with correct data. A `qwen2.5:14b-ctx12k` variant was also evaluated; total battery time was statistically identical to `ctx8k` (20m4.84s vs. 20m9.69s) with no clear win, so the deployed instance stayed on `ctx8k`. |

## Correctness vs. Anthropic (`claude-sonnet-5`)

Essentially tied on the same 30-case battery (5 off_topic, 5 opinion, 5 general_climate, 5
boundary/adversarial cases, 10 data_query cases, 4 real starter prompts, plus 6 more compound/
boundary cases) — both `qwen2.5:14b-ctx8k` and Anthropic hit 30/30 on guardrail classification,
boundary cases, and tool selection. Anthropic showed richer behavior on the hardest compound
queries (used more tools per turn, correctly flagged when a specific figure wasn't isolated in a
given pull rather than asserting confidently), but `qwen2.5:14b-ctx8k` reached functionally
correct answers too.

## The real, unclosed gap: latency, not correctness

| | Anthropic | `qwen2.5:14b-ctx8k` |
|---|---|---|
| 30-case battery, total wall time | 6m35s | 20m10s |
| Avg per query | ~13s | ~40s |
| Slowest single query observed | a few seconds | up to ~250s (on the `ctx12k` variant) |

Roughly **3x slower** across the board. Ollama's single inference slot (`-np 1`) means one slow
request blocks every other request behind it — a real availability risk for a public,
unauthenticated endpoint that Anthropic's hosted API doesn't share. `num_parallel` (Ollama's
concurrency knob) turned out to be a server-wide `OLLAMA_NUM_PARALLEL` environment variable, not
settable per-model the way `num_ctx` is via `ollama create` — confirmed empirically, not assumed.
Increasing it was deliberately not pursued: expected usage is one interactive user at a time, and
raising parallel slots roughly doubles KV-cache memory per slot on an already-tight 16GB host.

## Follow-on fixes that came out of this testing

All merged to `main`:

- **PR #170** — `ui_selection_node` now surfaces partial tool-call failures into `scope_notes`
  (using each `ToolCallRecord`'s plain-language `progress_label`, never a raw tool name) instead
  of silently answering from half the data when only some of a turn's tool calls fail.
- **PR #171** — `services/mcp-server` tool docstrings (`get_historical_emissions`,
  `get_gas_composition_by_decade`, `get_forecast_comparison`, `compare_scenarios_across_countries`)
  now explicitly require full country names, not ISO codes — root cause of one class of resolution
  failures seen under both `llama3.1:8b` and `qwen2.5:14b`.
- **PR #172** — a 150-second per-call timeout on the Ollama branch of `get_llm()`, sized off a
  real timed battery run, so a future stall degrades to a bounded, logged failure instead of an
  indefinite hang.
- **PR #173** — per-query `trace_id` and node/tool timing logs (`src/agent/tracing.py`), which
  is what later let a slow query be diagnosed directly from server logs — confirming that LLM
  generation, not tool/API call volume, is where time actually goes on a local model.

## Where things stand

`qwen2.5:14b-ctx8k` is live on the deployed instance as an active trial — correctness-equivalent
to Anthropic on this evaluation's battery, materially slower in wall-clock time. Anthropic stays
one plist edit away (`LLM_PROVIDER=anthropic` in `com.ghgemissions.agent.plist`, then
`launchctl bootout`/`bootstrap` to reload) as the fallback for client demos or if the trial
doesn't hold up under real traffic.
