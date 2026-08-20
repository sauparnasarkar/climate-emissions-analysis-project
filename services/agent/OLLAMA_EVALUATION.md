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

## Ollama's automatic prompt caching (vs. Anthropic's explicit `cache_control`)

Prompted by an Anthropic Console billing alert about low prompt-cache hit rate on the
Anthropic path (which already marks `agent_node`'s system+tools prefix with `cache_control` —
see `graph.py`'s `_timed_node`/`agent_node` comments), the natural follow-up question was
whether Ollama has anything equivalent. It does, but the mechanism and guarantees are
different, confirmed by reading `~/.ollama/logs/server.log` on the Mac Mini directly rather
than assumed from documentation:

- **Automatic, not explicit.** Ollama's runner (`llama-server`) keeps up to 32 "context
  checkpoints" and matches each new prompt against them by longest-common-prefix similarity —
  `context checkpoints enabled, max = 32, min spacing = 8192`. There is no `cache_control`-style
  flag to mark something as cacheable; it's opportunistic based on whatever's still resident.
- **Confirmed real, with a measured before/after pair from live traffic:**

  | | Total prompt | Tokens actually re-evaluated | Wall time |
  |---|---|---|---|
  | Cache **miss** | ~4,117 tokens | ~3,983 (nearly all) | 36.8s |
  | Cache **hit** (`f_keep = 0.987`) | 5,975 tokens | 1,969 (only the new part) | 20.7s |

  Reprocessing that second prompt's full 5,975 tokens from scratch at the same ~10ms/token rate
  would have cost roughly 63s instead of the 20.7s it actually took — a genuine ~40s saving on
  that one call. Repeated hits in the 90-99% keep range (`0.914`, `0.917`, `0.926`, `0.962`,
  `0.996`, `0.999`) turned up in the same log, alongside plenty of near-zero misses
  (`f_keep = 0.001-0.049`) — a real, recurring effect, not a one-off.
- **Inconsistent by nature, not guaranteed.** Whether a given call benefits depends on whether
  something similar enough is still one of the 7 (at the time of checking) stored checkpoints
  when it arrives — unlike Anthropic's `cache_control`, which deterministically caches a marked
  block for its TTL.
- **No visibility from the API.** There's no field analogous to Anthropic's
  `cache_read_input_tokens`/`cache_creation_input_tokens` — confirmed via Ollama's own open
  GitHub issue ([ollama/ollama#8008](https://github.com/ollama/ollama/issues/8008)) requesting
  exactly this. The only way to observe it is reading the raw runner log directly, as done here.
- **Real memory cost.** The prompt cache itself was observed holding 3-5GB (capped at 8GB via
  `--cache-ram`) on top of `qwen2.5:14b-ctx8k`'s own ~9-10GB resident footprint, on a 16GB host.
  Worth monitoring; no memory pressure or crashes observed so far.

No action taken or needed — this runs automatically and is already a real, if inconsistent,
contributor to why some LLM calls in the timing logs (`src/agent/tracing.py`, see below) are
markedly faster than others of similar prompt size.

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
