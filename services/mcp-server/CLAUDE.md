# CLAUDE.md — Climate Emissions MCP Server (`services/mcp-server`)

## Scope note

This sub-project is **not internship scope** — see the root [`CLAUDE.md`](../../CLAUDE.md)'s
scope note and [`SPEC.md`](SPEC.md) §1. Like `api/` and `climate-dashboard-react/`, it's a
mentor-built post-internship expansion: Stage 1 of a separate conversational-agent project,
wrapping the REST API in `api/` as hand-curated MCP tools. Don't treat it as an intern
deliverable, and don't imply interns are expected to build or extend it.

## What This Directory Is

An MCP server that wraps the existing `api/` FastAPI backend (documented in the root
`CLAUDE.md`/`SPEC.md`) as a set of hand-curated MCP tools, so that Claude Desktop/Claude Code
(Stage 1) and later a LangGraph agent (Stage 2+) can answer emissions/forecasting questions by
calling these tools rather than the raw REST API.

Full design (architecture decisions, cross-cutting conventions, tool catalog, open items) is in
[`SPEC.md`](SPEC.md) — read that before making design changes here, not just this file.

## Key Design Decisions (see `SPEC.md` for full rationale)

- **HTTP client of `api/`, not a shared library.** No privileged access path — same interface
  any consumer uses. Base URL comes from the `API_BASE_URL` env var (must include the `/api`
  prefix), never hardcoded — production may sit behind `StripDeployPrefixMiddleware`.
- **Hand-curated tools, not auto-converted from OpenAPI.** Forecast/scenario endpoints get
  composed, task-shaped tools (e.g. `get_top_emitters`) that a raw 1:1 conversion wouldn't
  produce. See `SPEC.md` §5 for the full tool catalog.
- **Country resolution guard (`SPEC.md` §3.1) sits in front of every tool taking a
  `country`/`countries` arg** — exact match, then fuzzy match above a threshold, then an
  explicit tool error below it. Never silently drop an unmatched country the way the raw API
  does.
- **`get_historical_emissions` never relies on the API's own omit-`countries` default.** It
  resolves and ranks the scope pool itself and always passes an explicit `countries` list —
  `GET /historical/timeseries`'s built-in default silently ignores `scope` (see `SPEC.md` §4).
  `get_gas_composition_by_decade` is the one exception that *can* rely on the API's
  omit-default, since that endpoint's default already respects `scope`. Don't conflate the two.
- **V1 auth: unauthenticated, localhost only.** `api/` has no auth mechanism today, so no
  token-presenting code is added on this side either — that would be dead code. Real
  service-account auth is a hard prerequisite before any non-local deploy. Do not add
  token-shaped code "for later" — see the root `CLAUDE.md`'s general no-speculative-code stance.
- **V1 infra: `pyproject.toml` only.** Keeps this sub-project's deps (an MCP SDK, `rapidfuzz`)
  isolated from the shared root `requirements.txt` that the notebooks/jupyter also depend on.
  No Dockerfile, no CI job yet — deferred, not omitted (`SPEC.md` §2.1).
- **Scope:** classical/no scope creep beyond `SPEC.md`'s tool catalog — same "don't add
  hypothetical future requirements" convention as the rest of this repo.
- **Operational caveat: a broken `tools/*` module fails silently at startup.** `server.py`
  imports `tools/*` for their `@mcp.tool()` registration side effects; if one of those modules
  raises on import (e.g. a syntax error), `MCPServer` starts anyway with that module's tools
  simply missing, rather than crashing loudly. Acceptable for V1's stateless, locally-run
  design (a missing tool shows up immediately in manual testing) — revisit if this server ever
  runs unattended in a context where nobody would notice a quietly-shrunk tool list.

## When Helping With This Sub-Project

- Reference `SPEC.md` before adding, removing, or changing the shape of a tool.
- Mirror `api/tests/conftest.py`'s fixture pattern for this sub-project's own tests
  (`tests/conftest.py`) — small per-scenario fixture builders, no real/gitignored `data/` CSVs.
- This sub-project makes **no changes to `api/`** — if a fix seems to belong in `api/` instead
  (e.g. an endpoint default that doesn't compose well with a tool), flag it as a separate,
  independent change rather than folding it in here.
- Use the same feature-branch-per-section workflow as the rest of this repo when Claude is
  implementing sections of this sub-project: branch → implement → commit → push → PR → mentor
  review → merge, one section at a time — see root `CLAUDE.md`.
