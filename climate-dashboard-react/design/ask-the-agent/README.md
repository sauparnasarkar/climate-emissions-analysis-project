# Handoff: Ask the Agent redesign (with Area 2 climate outcomes)

## Overview
Redesign of the Ask the Agent page in the Climate Analytics Platform (`sauparnasarkar/climate-emissions-analysis-project`, React app in `climate-dashboard-react/`). It covers the empty state, the answer layout, and how agent answers reuse the Area 2 climate-outcome and correlation work (see `design_handoff_area2_climate_context/`).

## About the design files
`Ask the Agent Redesign.dc.html` is a **design reference built in HTML**, not production code. Recreate it in the existing React app with its components, chart library, theme tokens and agent data flow. Don't copy the markup. Open the file in a browser with `support.js` next to it. It's a pan/zoom canvas: artboard 0 (notes), A1–A3 (desktop, dark), M1–M3 (mobile 390px, dark).

## Fidelity
High-fidelity for layout, hierarchy, copy and colour roles. Chart data is partly mock (see Data). Mocks are dark only; **ship both themes** using the existing Light/Dark toggle and the app's theme tokens. Hex values below are for reference; map them to tokens.

## Screens

### A1 / M1: Empty state
- **Title:** "Ask about emissions and climate outcomes" (desktop 30px/600; mobile 24px/600).
- **Subtitle:** "Answers from emissions data for 1990–2024, global temperature and CO₂ records, and the platform's forecasts. Every chart shows its source." (15.5px, muted, max-width 680px, centred).
- **Input:** its own field, max-width 960px, min-height 64px, radius 12px, surface `#1b2a4a`, 1px border `#3d5580`. Placeholder "Ask about emissions, warming or pathways…". Send button 40×40 (44×44 on mobile), radius 8px, accent fill, "↑", `aria-label="Send"`. **Focus ring wraps the whole field** (1px accent border + 3px accent at 22% opacity), never an inner rectangle on the text input. Hint below: "Enter to send · Shift + Enter for a new line" (12px, muted; hidden on mobile).
- **Prompts sit below the field, outside it.** Default layout: three columns, one category each, two prompts per column (gap 16px). Column label mono 11px, letter-spacing .06em, muted. Card: surface `#1b2a4a`, 1px border `#2c3e63`, radius 10px, padding 14px 16px, min-height 84px, 14px/1.45 text, "→" bottom-right; hover = accent border. Clicking a card sends the prompt.
  - **HISTORICAL TRENDS:** "What are China's historical emissions trends, and how do they compare to the other top 10 emitters?" · "How have India's emissions grown compared with other countries?"
  - **CLIMATE OUTCOMES** (NEW tag): "Show the relationship between cumulative emissions and warming." · "How do temperature outcomes vary based on different emissions pathways?"
  - **FORECASTS:** "What are the top 10 forecasted emitters in 2040?" · "How do today's top 10 emitters compare with the projected top 10 in 2040?"
- **Alternative (Tweaks → Grid 2×3):** 2 columns × 3 rows, category label inside each card, rows ordered Historical → Climate outcomes → Forecasts. Either is acceptable; the three-column grouping is recommended.
- Desktop: block centred vertically in the main area. Mobile: one column, grouped by category label, cards min-height 56px.

### A2 / M2: Answer, historical trends (China prompt)
Content column max-width 900px, gap 22px. Order:
1. "+ New question" button, top-right.
2. Category label (mono 11px) + **question as H2** (24px/600; mobile 19px).
3. **Lead paragraph with figures** (16px/1.65), key figures bold. The lead must state numbers, not adjectives.
4. **KPI row, 3 cards**, each labelled with the year: "CO₂ emissions · 2024" 12,289 Mt (sub "Largest of 218 countries") · "Per capita · 2024" 8.66 t (sub with comparison) · "Change vs 2023" +1.0% (sub "4.9× the 1990 level"). Value 28px/600, tabular numerals.
5. **Line chart** "CO₂ emissions of the top 10 emitters, 1990–2024": the subject country highlighted (accent, 2.75px), the other nine grey (`#56688c`, 1.3px), direct end labels for the subject and the next two largest. Hover names any line. No 10-colour legend.
6. **Horizontal bar chart** "Top 10 emitters, 2024": one colour, subject country in accent, values right-aligned. Subtitle states the top-10 share (71%).
7. **Source/scope line under every chart** (12px, muted), e.g. "Source: OWID CO₂, 1990–2024 · territorial emissions". State whether land use is included.
8. **Deep links:** "Open in Historical Trends →", "Open China in Country Profile →", opening the dashboard with the same countries and years.
- Removed from the current build: the duplicate single-country trend chart, the diverging −10k…+10k colour scale on positive bars, "--" in titles, plain "CO2" (use CO₂).
- **Year:** always default to the latest data year (2024), the same as the dashboard. The current build shows 2020.

### A3 / M3: Answer, climate outcomes (pathways prompt)
Same structure as A2, plus:
- Warning chip under the question: "ILLUSTRATIVE · IMPLIED OUTCOMES, NOT CLIMATE-MODEL PROJECTIONS" (mono 11px, amber text on amber 12% bg; use the theme-aware amber token from the Area 2 accessibility fix).
- Lead: "By 2040 the platform's three emissions pathways imply 1.68–1.79 °C of warming above 1850–1900. Annual emissions in 2040 differ 2.2× between them, but the implied temperatures differ by only 0.11 °C, because 78% of the 2040 level (1.39 °C) was already reached by 2024. The pathways change only the warming still to come: the Aggressive pathway adds 28% less of it than BAU." Numbers filled from pipeline output (same template as the Correlation module's reading note, decision 43).
- Three scenario cards with 3px top border in the series colour (BAU `#FFB54D`, Moderate `#5FD8F7`, Aggressive `#5AB4AC` on dark): 1.79 / 1.73 / 1.68 °C in 2040, sub "46,647 / 30,400 / 21,611 MtCO₂ a year".
- Chart "Implied temperature by pathway, 2015–2040": implied history line to the white "1.39 °C in 2024" anchor, three pathways after it, end labels with values. Same component as the Correlation module's Scenarios chart 2.
- **"How this is calculated" card:** Slope used 0.520 °C per 1,000 GtCO₂ (95% CI 0.480–0.559), 1850–2024, total CO₂ incl. land use · IPCC for comparison AR6 0.45 (0.27–0.63) · Gases CO₂ only. Line: "A relationship in observed data, not a climate model…". Berkeley Earth vintage caveat. On mobile this card is collapsed by default (48px row, ▾).
- Deep links: "Open in Climate Correlation →" (`/climate-correlation#scenarios`), "Open in Scenario Comparison →".

### Answers for "Show the relationship between cumulative emissions and warming"
Not mocked separately. Use the same answer structure, with the Correlation module's **Global relationship** scatter and stat card (0.520 slope, CI, R², AR6 strip, fossil + cement 0.797 comparison), its caption, and a link to `/climate-correlation#relationship`.

### Sticky input and follow-ups (all answers)
- Input moves to a bar pinned to the bottom of the viewport (top border `#2c3e63`, page background), placeholder "Ask a follow-up…".
- Up to three follow-up prompt chips above it (13px, 1px border `#3d5580`, radius 16px). Mobile: one row, scrolls sideways, chip height 36px inside a 44px tap row.
- Follow-ups move the user from emissions toward climate outcomes, e.g. "How has global CO₂ tracked warming since 1850?". Tweaks → `followUps` hides them for comparison.

## Rules for agent answers (Area 2)
- Climate answers reuse the Correlation module's figures, components and caveats. The agent doesn't run its own temperature calculation.
- Pathway temperatures come from the module's `#scenarios` translation (1.39 °C anchor, 0.520 slope, 40-country coverage, rest of world held at its 2024 share).
- IPCC 0.45 (0.27–0.63) is a comparison only, never the slope used.
- **No warming is attributed to any country.** Country answers may link to global climate context only.
- Don't correlate annual emissions with annual temperature.
- Copy uses "correlation", "context", "implied", "illustrative"; never implies a causal or climate model.

## Interactions & state
- `messages[]` (question, category, answer blocks), `pending`, `error`. Answer blocks: lead text, KPI set, chart specs, source lines, deep links, follow-ups.
- Loading: show the question heading immediately, then a skeleton for lead and charts. Error: inline message with "Try again", the input keeps the text.
- Prompt cards and follow-up chips send immediately. "+ New question" clears the thread and returns to the empty state.
- Deep links carry state in the URL (countries, year range, section hash).
- Keyboard: Enter sends, Shift + Enter new line; send button disabled (not hidden) when the field is empty.

## Design tokens (dark, from `analytics.css`; map to tokens)
Page `#121e35` · header `#1e2f52` · sidebar `#172544` · card `#1b2a4a` · border `#2c3e63` · outline `#3d5580` · chart panel `#0f1a2e` · chart grid `#22324f` · text strong `#f1f5fb` · body `#d7e0f0` · muted `#a9b7cf` (use the retuned shared muted token once that change lands) · accent `#5FD8F7` · amber text `#FFC774` on `rgba(255,181,77,.12)` · NEW tag `#7be0a0`.
Type: H1 30px/600 · question H2 24px/600 · card title 16px/600 · KPI 28px/600 · body 16px/1.65 · caption 12px · labels mono 11px, letter-spacing .06em. Radius: field 12px, cards 10px, buttons 8px, chips 16px, tags 3px. Use the app's font stack (mocks use Inter + JetBrains Mono).

## Data
As given (read from pipeline): 12,289 Mt, 8.66 t, +1.0%, 71%, scenario temperatures and emissions, 1.39 °C anchor, 0.11 °C gap, 78%, 28%, slope and CI. **Mock:** country series, the 2.5× and "nearly fivefold" ratios, per-capita comparisons (US 14.2 t, world 4.7 t), other countries' 2024 values.

## Files
- `Ask the Agent Redesign.dc.html`: design reference (artboards 0, A1–A3, M1–M3).
- `support.js`: runtime for the HTML reference only. Don't port it.
- Related: `design_handoff_area2_climate_context/` for the Correlation module components reused here.
