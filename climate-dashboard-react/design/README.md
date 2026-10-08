# Design references

HTML design references from the designer's handoffs. **They are references, not code:** recreate them in the
React app with its own components, chart library and theme tokens (each handoff's `README.md` says so too).
Nothing here is imported, bundled, linted or tested — `src/` is the only app source, and `.oxlintrc.json`
ignores this folder.

| Folder | Handoff | Received | Drives |
|---|---|---|---|
| `area2-climate-context/` | Area 2 climate context layer (landing, Overview, Correlation module) | 2026-10-04, final design 2026-10-08 | Release 21 Section 2 (built) |
| `ask-the-agent/` | Ask the Agent redesign with Area 2 climate outcomes | 2026-10-08 | Release 21 Section 3, steps 3.4–3.5 (decisions 102–109 in the root `ENHANCEMENTS.md`) |

## How to view one
Open the `.dc.html` in a browser with `support.js` beside it (a pan/zoom canvas of artboards). `support.js` is the
design tool's generated viewer runtime — it loads React 18.3.1 and Babel from unpkg and compiles the page's own
code, so it needs network access and **must not be served as part of the app or ported**. The copy in both
folders is byte-identical.

## Read these before building from a handoff
- **Their figures are not current.** Both READMEs and mocks predate the Berkeley Earth high-resolution
  migration (root `ENHANCEMENTS.md` decision 83): they show a slope of 0.520 (CI 0.480–0.559), a fossil-only
  comparison of 0.797, a 2024 anchor of 1.39 °C and 2040 levels of 1.79/1.73/1.68 °C. The pipeline now gives
  0.486 (0.442–0.530), 0.749, 1.32 °C and 1.68/1.64/1.58 °C. The mocks also say "Berkeley Earth vintage caveat",
  now the preliminary-release note. **Every number on a page comes from the data, never from a mock**
  (decision 109).
- **Each README lists which values are mock** — replace those with pipeline output.
- **Where a handoff and a recorded decision disagree, the decision wins.** The Ask-the-Agent handoff's
  "clicking a prompt card sends it" is not adopted (prompt cards prefill, decision 102), and its
  `/climate-correlation#relationship` should be `#global-relationship` (decision 107).
