# Handoff: Area 2 Climate Context Layer, Section 2 Frontend (Release 21)

## ⚑ Build from the final design (supersedes the option tables below)
`Area 2 Final Design.dc.html` is the final pass, checked against the requirements doc (`climate_analytics_area2_requirements.docx`, rev. 2026-10-02, §2.1–2.6). Build from it. Option IDs (1a–3b) mentioned below refer to earlier explorations that are not included in this package; the final file and this README are the spec.

Artboards: **L1** Landing desktop (dark) · **L2** Landing mobile, both banners (light) · **O1** Overview desktop (light) · **O2** Overview mobile (dark) · **M1** Temperature & GHG Correlation module (light). Each has a SPEC NOTES column; these notes are part of the spec.

Changes from the earlier options:
- Banner 1 subhead uses the "chain reaction" wording; its primary CTA goes to `/overview#climate-signal`. "Explore the data" and "Forecasts to 2043" are secondary actions.
- Overview order: #climate-signal → #relationship → #top-emitters → #share → #by-country → #percent-change → #pathways.
- KPI strip: emissions · change since baseline (index, 1990 = 100) · concentration · temperature. Every KPI has an ⓘ baseline panel showing baseline year, reference, formula, source range and excluded years (§2.5).
- "Why emissions matter" (same treatment as the existing "Since 1990" card) states the full chain, the ocean–climate note and the global vs country distinction.
- The top-5 **leading-emitter ranking** for all countries is back beside the map, synced to year and to the Absolute/Cumulative mode (§2.2 block 3, §2.6).
- Pathways closes the page with links to Forecasts, Scenario Comparison and the module.
- Module sections: Causal chain (diagram + prose + "not modelled" list) · Long-run relationship (headline) · Recent all-gas relationship 1970+ (PRIMAP-hist, tagged NOT TCRE, with a data-quality note) · Gas composition (stacked area + selected-year bar) · Country responsibility · Scenarios · Methodology & sources (sources table, baselines table, series differences, two global totals, 1959 splice, derivation accordion).
- Every chart has a "Purpose:" line (§2.3).

### Page year (one control for the middle of the Overview)
- A sticky **Year** control sits at the right of the anchor bar: a select over the decade stops (1970, 1980, 1990, 2000, 2010, 2020, 2024) plus ▶ Play at ~1.75 s per stop. The map's decade stops and Play change the **same** value. The existing map slider still scrubs single years. Default 2024; kept in the URL (`/overview?year=2010#share`).
- Follows the page year: map, summary tiers, leading-emitter ranking, CO₂ ppm card, Share, By Country, Top Movers, % Change. Each section header shows a year badge.
- Doesn't follow it: Climate signal KPIs (always the latest year), the relationship chart (full series), Pathways (2025–2040).
- **Share:** the slider is removed. "▶ Replay 1970 → {year}" animates at ~0.25 s per year, then returns to the page year. While it runs the readout is marked "replaying · temporary" and nothing else on the page changes. Changing the page year or pressing Play cancels a replay.
- **By Country:** the existing bar chart, titled "CO₂ Emissions by Country ({year})" and re-sorted for that year. Top Movers are measured "1990 → {year}".
- **% Change:** the existing diverging bar chart, titled "CO₂ % Change by Country, 1990–{year}", with the axis rescaling per year. For years ≤1990, the chart and Top Movers grey out with a status prompt: "The baseline is 1990… choose 2000 or later."
- Mobile: the page year is the first chip in the sticky chip row; tapping it opens a bottom sheet with the stops and Play.
- Mock data: the per-decade values for the 10 selected countries in By Country and % Change are illustrative, except the 2024 values, which match the live site.

Decisions (confirmed by the owner 2026-10-04):
- A. Headline = total CO₂ incl. land use (0.520), per decision 40. Fossil + cement (0.797) is the comparison. The requirements doc §1.3.1/§2.4 still say fossil + cement and need amending.
- B. IPCC comparator: 0.45 best estimate within the AR6 0.27–0.63 range.
- C. Keep the top-5 leading-emitter ranking for all countries beside the map (doc §2.2 block 3).
- D. §1.3.2 lag analysis is out of scope; don't build it.

Mock values in the final file (replace with pipeline output): R² 0.91, the all-gas slope, gas shares, country shares over time, rankings before 2024, and tier values for non-2024 years.

### Update 2026-10-08: Landing mobile (L2) and Banner 2 subtitle
- **Banner 2 subtitle (desktop and mobile):** "Global CO₂ emissions have grown by more than two-thirds since 1990, and the 10 largest emitters now account for 71% of the total." The 71% must come from the same source as the Top 10 section heading, so both update together.
- **Mobile order, both banners:** eyebrow → headline → one line of copy → picture with its caption → figures → CTAs.
- **Banner 1 mobile:** the temperature chart moves above the two figure cards (+1.62 °C, 427 ppm), which sit directly under it.
- **Banner 2 mobile:** the globe follows the copy, capped at ~62% of viewport height so Play and the year slider stay with it. The "2024 · 37,398 MtCO₂ · all countries" readout is the globe's caption (see the Globe `caption` slot below). The 37,398 and "40 countries in the Expanded set" stats are dropped on mobile; the figures are +68.6% since 1990 and 71% from the top 10 emitters.
- **Carousel controls on mobile** sit in the page flow under the CTAs. A floating pill must not cover the chart or globe; if it stays floating, pad each banner by the pill's height.
- **Globe caption (design-system PR):** add an optional `caption` prop to `Globe`, rendered as a `<figcaption>` inside its `<figure>`, directly under the canvas and before the legend/controls. Not `aria-live` during playback; announce the year only on pause or manual slider moves. The caption doesn't count toward the height cap. If the PR can't merge before release, keep the current order, record it as a temporary deviation in decision 79 with a link to the PR.

### Shared muted-text colour (accessibility follow-up)
Retune the shared muted-text token per theme so it reaches ≥4.5:1 on the most tinted surface it's used on (page background, baseline chips, map controls). The remaining violation is in **dark**, which needs a lighter value. Then remove the Area 2 scoped muted variable and the jump-links workaround, run the contrast check on every page in both themes, and share before/after screenshots of two or three muted-text-heavy pages for sign-off. The amber, link and landmark fixes stay as they are.

---

## Product name
The header title changes from "GHG Emissions Analytics" (landing) / "GHG Emissions Analytics Platform" (inner pages) to **Climate Analytics Platform** everywhere: landing nav, inner-page header, browser tab titles (e.g. "Overview — Climate Analytics Platform"), footer, and meta/OG tags.

## Overview
Frontend designs for Area 2 of the GHG Emissions Analytics Platform (`sauparnasarkar/climate-emissions-analysis-project`, see `SPEC.md` §5.26 and `ENHANCEMENTS.md` Release 21, phases 2.1–2.6). The work adds climate context (atmospheric CO₂ concentration and global temperature anomaly) next to the existing emissions data, plus correlation-driven storytelling:

- **Landing (2.1):** a two-banner hero ("Climate signal" + existing hero) and a four-step "emissions → concentration → forcing → temperature" band.
- **Overview (2.2, 2.6):** new *Climate signal*, *Share* and *Pathways* sections; the existing *Map* section gains decade stops, an Absolute/Cumulative toggle and a global CO₂ ppm card.
- **Temperature & GHG Correlation module (2.4, 2.5):** new page combining the global relationship, scenarios, country view, causal chain and methodology.

## About the design files
`Area 2 Final Design.dc.html` is a **design reference built in HTML**, not production code. Recreate these designs inside the existing React app (`climate-dashboard-react/`) using its components, chart library, routing, theme system and data hooks. Don't copy the markup. Open the file in a browser (keep `support.js` next to it). It's a pan/zoom canvas of labelled artboards (0, L1, L2, O1, O2, M1). Several options are interactive (carousel, tabs, decade stops, chart toggles, accordion).

## Fidelity
**High-fidelity for layout, hierarchy, copy and colour roles. Chart data is mock.**
- Colours come from the design-system themes `analytics.css` (dark) and `analytics-bright-tidewater.css` (light). Map them to the app's existing theme tokens; don't hard-code hex values.
- Mocks alternate light and dark across options. **Every surface must ship in both themes** using the existing Light/Dark toggle.
- Font: mocks use Inter. Use the app's existing font stack.
- Globe and choropleth are drawn as striped placeholders. Use the existing `Globe` and choropleth components with the new behaviour described below.
- All chart curves are illustrative. Figures marked **[doc]** below come from SPEC/ENHANCEMENTS and must be read from pipeline output, never hard-coded. Figures marked **[mock]** are invented and must be replaced with real outputs.

## Decisions made with the user (which option to build)
| Surface | Build | Notes |
|---|---|---|
| Landing | **1a or 1b** (user's choice; they can be combined: 1a carousel + 1b shared-timeline band) | |
| Overview | **2a** page flow, with **3a Map changes** and **2b Share (stock vs flow) animated** | The 1c top-5 ranking beside the map is **removed** (it duplicated By Country) |
| Correlation module | **1e + 1f combined into one page** | Causal chain and Methodology need fuller designs (see §Open items) |

---

## Screens / Views

### Global shell (unchanged)
Existing header (logo, "GHG Emissions Analytics Platform", Light/Dark segmented toggle, "✦ Ask the Agent" button) and left sidebar (Home · EXPLORATION: Overview, Historical Trends, Country Profile, Data Explorer, **Climate Correlation [NEW tag]** · PROJECTION: Forecasts, Scenario Comparison). Add the **Climate Correlation** nav item to both sidebar and landing top nav. NEW tag: mono 10px, bg `#E4F6EC`, text `#0F7A47`, radius 3px.

Page convention (existing): one scrolling page per route, with a row of in-page anchor links under the H1 (`/overview#map`). Anchor row: 15px, muted; active = strong text, weight 600, 2px bottom border in primary.

Card convention (light): white surface, radius 8px, 3px top border in the series colour, padding 16px 18px. Dark: surface `#1e2f52`, 1px border `#2c3e63`, radius 8px.

Baseline chip (2.5, required on every figure): mono 11px, bg `#ECF1F3` (light), padding 3px 6px, radius 3px, e.g. "Baseline 1990 · OWID".

---

### 1. Landing (Phase 2.1). Options 1a / 1b

#### Option 1a: Carousel + four-step cards
- Top nav 64px, horizontal padding 48px.
- **Carousel region** (`role="region" aria-roledescription="carousel"`), padding 56px 48px 28px. Each slide is a 2-column grid `5fr / 6fr`, gap 56px, min-height 470px.
  - **Slide 1 "Climate signal":** eyebrow "CLIMATE SIGNAL · BERKELEY EARTH × OWID · 1850–2024" (13px, 600, letter-spacing .08em). H1 54px/1.06 bold: "Warming has risen in step with cumulative CO₂." Body 18px/1.6: "Over 175 years of observations, every 1,000 GtCO₂ of cumulative emissions coincides with about **0.52 °C** of warming (95% CI 0.480–0.559). Read as context from the data, not as a climate model." CTAs: primary "Explore the correlation" (→ module), secondary outline "How this number was derived" (→ module #methodology). Right: scatter chart card (see Shared charts → Scatter).
  - **Slide 2 "Where CO₂ comes from":** the existing hero copy unchanged, with the Globe on the right (400px circle).
  - **Controls bar** (top border, padding-top 18px): prev/next 36px square buttons; tab buttons "01 Climate signal", "02 Where CO₂ comes from" (selected = white bg, dark text); right-aligned hint "Auto-rotate off · focus and use ← → to switch".
  - **No auto-rotation.** ←/→ keys switch slides when the region has focus. Slides are `role="group" aria-roledescription="slide" aria-label="1 of 2: …"`.
- **Four-step band** (surface bg, padding 56px 48px 60px). H2 38px "From emissions to warming"; sub 17px "Four links, measured from the same data foundation. The third is explained, not modelled." Grid `1fr 20px 1fr 20px .85fr 20px 1fr` with "→" separators.
  - 01 EMISSIONS: **37,398 MtCO₂** [doc], "Fossil and cement CO₂ in 2024, all countries.", sparkline 1850–2024, link "See on the Overview →".
  - 02 CONCENTRATION: **424.6 ppm** [doc], "Atmospheric CO₂, 2024. +49% on 1850." Sparkline with dashed vertical at 1959; caption "Ice core to 1958 · Mauna Loa from 1959".
  - 03 RADIATIVE FORCING: **dashed border card, no number, no chart**. "Concept only" + "More CO₂ in the air traps more outgoing heat. This link is described here, not calculated: the platform holds no forcing dataset."
  - 04 TEMPERATURE: **+1.62 °C** [doc], "2024, above the 1850–1900 average." Caption "Berkeley Earth file of Jan 2025 · ~0.1 °C unreconciled".
  - Step label: mono 11px, letter-spacing .08em, series colour. Value 32px/600.

#### Option 1b: Tabbed switcher + shared-timeline band
- Grid `280px / 1fr`, gap 24px, padding 40px 48px. Left: vertical `tablist` (eyebrow "FEATURED · 2 STORIES"; each tab 16px 18px, radius 8px; selected = white bg + border, title in primary). Note: "Never rotates on its own. Arrow keys move between stories."
- Right panel white, padding 40px, min-height 470px. Slide 1 hero number: "0.52" 104px bold + " °C" 48px primary; "of warming per 1,000 GtCO₂ emitted" 20px; body text citing AR6 0.27–0.63; chips "95% CI 0.480–0.559" (neutral) and "Not a climate model" (warning: bg `#FFF6E6`, text `#8A5A00`). Scatter on dark chart bg.
- **Band "Four links, one timeline":** rows `230px / 1fr / 170px`, divider lines `#E5EEF1`. Each row: number + name + source (left), sparkline 60px tall on a **shared 1850–2024 x-axis** (middle), latest value 24px/600 + caption (right). Forcing row is a dashed box with explanatory text and "no series". Concentration row labels the 1959 splice. Shared axis ticks: 1850, 1900, 1950, 2000, 2024.

#### Globe behaviour (decision 12)
Continuous rotation 1970 → 2024 with a smoothly advancing year counter; colours change over time; **values, legend and labels hidden while playing, revealed on pause**. Respect `prefers-reduced-motion` (start paused).

---

### 2. Overview (Phases 2.2 + 2.6). Build 2a + 3a Map + animated 2b Share

Anchor row: **Climate signal · Map · Share · Pathways · By Country · % Change**. By Country and % Change are the existing sections, unchanged.

#### 2.1 Climate signal (`#climate-signal`, new)
- 4-up KPI grid (gap 14px). Each card: label 13px muted, value 28px/600 + unit 14px, delta 13px, baseline chip.
  1. CO₂ emissions · 2024: 37,398 MtCO₂, "+68.6% since 1990" [doc], chip "Baseline 1990 · OWID". Top border emissions colour.
  2. CO₂ concentration · 2024: 424.6 ppm, "+49% vs pre-industrial", chip "Baseline 1850 · NOAA + Law Dome". Top border concentration colour.
  3. Temperature anomaly · 2024: +1.62 °C, "5-year mean 1.39 °C" [doc], chip "vs 1850–1900 · Berkeley Earth". Top border temperature colour.
  4. Cumulative CO₂ since 1850: ≈2,610 GtCO₂ [mock], "Fossil, cement + land use", chip "Full OWID history".
- Row `2fr / 1fr`:
  - **Dual-axis chart** "CO₂ emissions and temperature anomaly, 1970–2024": bars = annual fossil+cement GtCO₂ (left axis 0–40), line = anomaly °C (right axis 0–1.5, 2.5px). Caption: "Two series on separate axes. Shown together as context; this chart does not establish cause." Option 1d adds a segmented toggle **Over time / Against cumulative CO₂** that swaps in the Scatter chart. Recommended.
  - **"Why emissions matter" card** (styled like the existing "Since 1990" card): 18px/1.55 text: "Since 1970, annual CO₂ emissions have risen +151% and the temperature anomaly by about 1.2 °C. Warming tracks the **cumulative** total, so every year of emissions adds to it, even when annual output stops growing." Link "Open the Correlation module →". Figures must be generated from data.
- Map, ranking or choropleth must **not** appear in this section.

#### 2.2 Map (`#map`, existing, upgraded). See option 3a spec below
Row `1.75fr / 1fr`.
- **Map card:** title + **segmented toggle (`role="radiogroup"`)**:
  - **Absolute**: "Annual MtCO₂". Title "CO₂ Emissions by Country ({year})". Choropleth = that year's annual emissions.
  - **Cumulative**: "Since 1850, GtCO₂". Title "Cumulative CO₂ Emissions by Country, 1850–{year}". Choropleth = running total. Uses its own colour scale (don't reuse the annual bins).
  - Choropleth 320px tall, selected countries outlined.
  - Controls: "▶ Play decades" primary button; decade stop buttons **1970 1980 1990 2000 2010 2020 2024** (selected = primary fill); hint "or drag the year slider, year by year". Play advances stops every **~1.5–2 s**. The existing year slider stays and scrubs single years. Map, side card and ppm card stay in sync.
- **Side card** (existing All / Expanded / Selected summary, replacing the 1c top-5 list):
  - Three tiers: **All Countries (218)**, **Expanded (Coverage + ≥100 Mt) (40)**, **Selected (10)**. Each tier: name 14px/600; columns `Countries | CO₂ | change`.
  - Absolute mode: CO₂ ({year}) in MtCO₂ + "% chg. since 1990". 2024 values in the mock: 37,398 / +68.6% [doc]; 34,477 / +75.1% and 25,324 / +76.5% [mock].
  - Cumulative mode: "Cumulative 1850–{year}" in GtCO₂ + "Share of world total" (%).
  - Positive change uses the warning text colour (`#8A5A00` light); negative uses teal (`#1D726B`).
  - **New bottom panel: "Atmospheric CO₂ · {year}"** (bg `#F3F8FA` light / `#182746` dark), label "GLOBAL" mono 10px. Value 26px/600 "{ppm} ppm" + "+{Δ} ppm (+{%}) since 1850" (baseline 285.2 ppm in 1850). Sparkline 1850–2024 with a dashed line at the 1959 splice and a marker + drop line at the current year. Caption: "Law Dome ice core to 1958 · NOAA Mauna Loa from 1959. One global value: concentration is not split by country." The value is the same in both toggle modes (it's a stock already). Reference values: 1970 325.68, 1980 338.91, 1990 354.45, 2000 369.71, 2010 389.90, 2020 414.21, 2024 424.61.

#### 2.3 Share of cumulative emissions (`#share`, new). Build 2b, animated
- Controls row (from 2a): Measure segmented **CO₂ · OWID / CO₂ · PRIMAP-hist / All GHGs · PRIMAP-hist**; Countries = the page's existing selected set; right-aligned chip "Baseline: full history 1850–2024 · national sum, bunkers excluded".
- Card (dark mock: surface `#1e2f52`), title "Who emitted the stock, and who emits now".
- **Two 100% stacked horizontal bars**, 44px tall, 2px gap between segments, radius 4px, label column 150px:
  - **The stock**: cumulative share 1850–{year}.
  - **The flow**: annual share in {year}.
  - Segments = selected countries in a **fixed colour per country shared by both bars**, then "Rest of world" (neutral `#31476e` dark / `#BDD3DB` light). Inline label "US 24.3%" when the segment is ≥ ~5% wide; abbreviate narrow ones; hide labels under ~3%. Legend below.
  - 2024 mock values: stock US 24.3, China 15.0, Russia 6.8, Germany 5.4, UK 4.4, Japan 3.9, India 3.4, others 3.2, RoW 33.6. Flow China 32.9, US 13.1, India 8.5, Russia 4.8 … [mock]. Read from data.
- **Animation (new, user request): share over time from 1970.**
  - Year control under the bars: ▶ Play / ❚❚ Pause, a 1970–2024 slider, and a large current-year readout (e.g. 32px/600) beside the title.
  - Play steps one year at a time, **~250 ms per year** (≈14 s total), and ends at 2024. Segment widths tween with `transition: width 250ms linear` (or equivalent in the chart lib). Segment **order stays fixed** (sorted by 2024 cumulative share) so colours don't jump.
  - Labels and % values update each frame. Optional ghost tick at each country's 1970 position to show the shift.
  - Reduced motion: no autoplay; slider jumps directly.
  - The stock bar uses cumulative 1850–{year}, so 1970 already contains pre-1970 history.
- Footnote: "Same 10 selected countries in both bars, same colours. Shares describe contribution to emissions; no warming is attributed to a country." Optional link "Country view in the Correlation module →".
- 2a's alternative (ranked cumulative bars + cumulative-vs-2024 dumbbell) is **not** selected; keep for reference only.

#### 2.4 Where the pathways lead (`#pathways`, new)
Badge "ILLUSTRATIVE · IMPLIED OUTCOMES" (warning chip). Two treatments; 2a is the default for light, 2b's for dark. Pick one and theme it:
- **2a:** grid `1fr 1fr 1fr 1.35fr`. Three scenario cards (top border BAU `#B07A10` / Moderate `#0A6E8C` / Aggressive `#1D726B`): name, method ("ETS(A,Ad,N) trend, all 40 countries", "−2% a year from 2025", "−5% a year from 2025"), "Implied temperature, 2040" **1.79 / 1.73 / 1.68 °C** [doc] at 30px/600, mini table "Emissions 2040: 46,647 / 30,400 / 21,611 Mt" [doc] and "Added 2025–40 (Gt)" [mock]. Fourth card: implied-temperature line chart 2015–2040 with the "1.39 °C today" anchor.
- **2b:** paired small multiples (Annual emissions GtCO₂ | Implied temperature °C) with captions "**2.2×** apart by 2040" / "**0.11 °C** apart by 2040", plus a "2040 at a glance" table and a breakdown bar: "1.39 °C already observed (78%)" vs "+0.40 still to come".
- Footer: "Emissions in 2040 differ 2.2× between BAU and Aggressive; implied temperatures differ by 0.11 °C because 78% of the 2040 level is warming already observed. Pathways start from the 2024 observed total. Rest of world held at its 2024 share." Link "Full scenarios in the Correlation module →".

---

### 3. Temperature & GHG Correlation module (Phases 2.4 + 2.5). 1e + 1f combined
New route (e.g. `/climate-correlation`). H1 "Temperature & GHG Correlation". Anchor row: **Causal chain · Global relationship · Country view · Scenarios · Methodology**. Intro 16px/1.55, max-width 880px: "Emissions raise atmospheric CO₂, which traps heat and warms the planet. This module reads that chain from observations. It is descriptive: correlation is shown as context, not as proof of cause."

**Causal chain** (1e strip, to be expanded): 4 equal cells in one bordered container: 1 EMISSIONS, 2 CONCENTRATION ("About half stays in the air: 285 ppm in 1850, 424.6 in 2024."), 3 FORCING · CONCEPT (diagonal-hatch background, "Not calculated here."), 4 TEMPERATURE.

**Global relationship** (1e), row `1.55fr / 1fr`:
- Scatter "Temperature anomaly vs cumulative CO₂, 1850–2024" (see Shared charts). Caption: "Each dot is one year. Dashed line: OLS fit. The 1970+ all-gas view (PRIMAP-hist) is a separate chart and is not called TCRE."
- Stat card "Warming per 1,000 GtCO₂": **0.520 °C** 46px/700; key-value grid: 95% CI (Newey–West HAC) 0.480–0.559 [doc]; R² 0.91 [mock]; Years 1850–2024 (175); Fossil + cement only 0.797 [doc]. **AR6 range strip**: axis 0.20–0.90, band 0.27–0.63 (primary at 55% opacity), white marker at 0.520, emissions-colour marker at 0.797, mono 11px labels.
- Baseline card (2.5): Reference 1850–1900 mean; Formula `ΔT = T − mean(T₁₈₅₀–₁₉₀₀)` (mono); Range 1850–2024; Excluded none. Warning text: "Berkeley Earth file dated Jan 2025; its 2024 value differs from the Jan 2026 report by ~0.1 °C (unreconciled)."

**Country view** (1f bottom): two cards side by side: "Share of cumulative CO₂ since 1850, %" (multi-line, 5 of 40 countries, editable selection, end-of-line labels) and "Global temperature anomaly, °C" (annual thin line at 45% opacity + 5-yr mean 2.2px). Info banner (bg `#E1F0F5`, text `#0A6E8C`): "Shares describe each country's part of cumulative emissions. No country series is regressed against temperature, and no warming is attributed to a country."

**Scenarios** (1f): title "Implied temperature by scenario, 2025–2040" + warning chip "ILLUSTRATIVE · IMPLIED OUTCOMES, NOT PROJECTIONS". Grid `1fr 1fr 290px`:
1. "1 · Annual emissions" (GtCO₂, "large divergence"): observed 2015–2024 + three pathways from 2025, dashed vertical at 2025 labelled "2025 start ≈ 2024 observed". Legend with 2040 values.
2. "2 · Implied temperature" (°C vs 1850–1900, "small divergence"): annual observed dots, 5-yr mean line, pathways, white anchor dot "1.39 °C anchor" at 2024, bracket at 2040 labelled "0.11 °C".
3. "Reading note · generated from the output" card (top border emissions colour), 14px/1.6. **Template text, numbers filled from pipeline output** (decision 43): "Scenarios diverge sharply in annual emissions by 2040 (46,647 vs 21,611 Mt a year, 2.2×), but the implied temperatures differ by only 0.11 °C. 2025–2040 is a short window against the 175 years of emissions already accumulated, and 78% of the 2040 implied level (1.39 °C) is warming already observed by 2024, before any scenario begins. What the scenarios change is only the emissions still to come: relative to the 0.40 °C of additional warming, the Aggressive pathway adds 28% less than BAU. The gap widens every year the pathways stay apart (0.015 °C in 2030, 0.053 °C in 2035)."
- Footnote: "40 covered countries, fossil + cement CO₂. Rest of world held at its 2024 share of the global total: global = covered ÷ (1 − RoW share). Translation uses slope × Δcumulative from 2024."

**Methodology** (1e "How this number was derived"): accordion in a card; header "How this number was derived" + "Every figure below is read from the pipeline output". Rows: mono number, title, +/− icon; one open at a time (first open by default); `aria-expanded`. Body 14px/1.6, indent 66px, max-width 900px. Steps:
1. What is regressed on what. 2. Uncertainty (Newey–West HAC, maxlags ⌊1.5·n^(1/3)⌋, bandwidth sensitivity table). 3. How sensitive the slope is (windows from 1850/1900/1950/1970; land-use scaling). 4. Stability (seeded residual block bootstrap, block-length sensitivity, four decade holdouts). 5. Comparison with the IPCC range (AR6 0.27–0.63). 6. Data, licences and attribution (OWID, GCP land use, Berkeley Earth CC BY-NC 4.0, NOAA GML, Law Dome). 7. What this is not.
Full body copy is in the HTML file (`stepsRaw` in the logic class).

---

## Shared charts
- **Scatter (temperature vs cumulative CO₂):** x = cumulative total anthropogenic CO₂ since 1850 (0–2,700 GtCO₂, ticks every 500), y = °C above 1850–1900 (−0.4 to 1.8, ticks 0/0.5/1/1.5). One dot per year, r=3, 85% opacity, coloured by era: **to 1899** neutral, **1900–1969** emissions colour, **1970+** temperature colour. OLS fit as a dashed 1.5px line. Label the 2024 point "2024 · +1.62 °C". Legend top-right. Caption must say correlation, not proof of cause.
- **Sparklines:** 2px stroke, no axes, `vector-effect: non-scaling-stroke`; concentration sparkline always shows the 1959 splice.
- Light theme puts charts on a dark chart panel (`#061E28`, grid `#123544`, tick text `#94B4C0`), matching the current app's charts.

## Interactions & behaviour
- Carousel/tabs (Landing): manual only, ←/→ keyboard, no autoplay.
- Overview anchor row: scroll to section; update hash.
- Map: Absolute/Cumulative toggle swaps choropleth metric, title, side-card columns. Decade Play ~1.5–2 s/stop; slider scrubs years; all synced.
- Share: Play animates 1970→2024 at ~250 ms/year; Pause; scrub slider; fixed segment order.
- Overview chart toggle (1d): Over time ↔ Against cumulative CO₂, with title and caption swapping.
- Methodology accordion: single-open.
- All animations honour `prefers-reduced-motion`.
- Hover: chart tooltips per the app's existing chart tooltip pattern (year, value, unit, baseline).
- Loading/empty: reuse existing skeletons. If climate series fail to load, hide concentration/temperature cards rather than showing zeros.

## State
- Landing: `activeSlide: 0|1`.
- Overview: `chartView: 'time'|'cumulative'`, `mapMode: 'absolute'|'cumulative'`, `mapYear`, `mapPlaying`, `shareMeasure: 'owid_co2'|'primap_co2'|'primap_ghg'`, `shareYear` (1970–2024), `sharePlaying`; selected countries from existing global state.
- Module: `openMethodStep`, country-view selection (default 5 of 40).
- Data: annual + cumulative emissions by country (OWID, PRIMAP-hist), global CO₂ ppm (Law Dome + NOAA), Berkeley Earth anomaly + 5-yr mean, regression outputs (slope, CI, R², fossil-only slope), scenario outputs (emissions + implied temperature 2025–2040), generated reading-note figures.

## Design tokens (from design-system themes)
**Dark (analytics.css):** page `#121e35` · surface `#1e2f52` · strong `#28406c` · selected nav `#31476e` · border `#2c3e63` · chart panel `#182746` · chart grid `#263757` · outline `#3d5580` · text strong `#ffffff` · body `#d7e0f0` · secondary `#b9c6dd` · muted `#8fa2c4` · primary button `#2d9cbd` · accent/active `#50c7e0` · warning chip bg `#453516`.
**Light (analytics-bright-tidewater.css):** page `#DCE8ED` · surface `#ffffff` · subtle `#F3F8FA` · chip `#ECF1F3` · border `#C7D9E0` · divider `#E5EEF1` · dashed `#BDD3DB` · header `#06222D` · text strong `#071C24` · body/heading `#3C5460` · muted `#5C7683` · primary `#0A6E8C` · selected nav bg `#E4F2F8` · info bg `#E1F0F5` · warning bg `#FFF6E6` / text `#8A5A00` · NEW tag `#E4F6EC`/`#0F7A47` · chart panel `#061E28` / grid `#123544` / tick `#94B4C0`.
**Series roles:**
| Role | Dark | Light (UI) | On dark chart |
|---|---|---|---|
| Emissions / BAU | `#e5b955` | `#B07A10` (text `#8A5A00`) | `#FFB54D` |
| Concentration / Moderate | `#5ecbf5` | `#0A6E8C` | `#5FD8F7` |
| Temperature | `#f2637e` | `#B3261E` | `#EA5B62` |
| Aggressive | `#5AB4AC` | `#1D726B` | `#5AB4AC` |
| Pre-1900 / neutral | `#8fa2c4` | `#5C7683` | `#94B4C0` |
Country palette (Share): US `#5FD8F7`, China `#FFB54D`, Russia `#c89cff`, Germany `#7791F8`, UK `#F263F2`, Japan `#ff8f6b`, India `#D7E740`, others `#5AB4AC`. Reuse the app's existing country palette if one exists.
**Type:** H1 34px/600 (pages), 54px/700 (landing hero); H2 22px/600 (sections), 36–38px/700 (landing bands); card title 17px/600; KPI 28–32px/600; body 14–18px; caption 12px; eyebrow/step labels mono 11px, letter-spacing .06–.08em. Tabular numerals for all figures.
**Spacing/radius:** card padding 16–22px; grid gaps 14–16px (Overview), 24–56px (Landing); page padding 28–40px; radius 8px cards, 6px chart panels/segmented, 4px buttons/chips, 3px tags.

## Copy guardrails (from SPEC)
- Always "correlation", "context", "implied", "illustrative". Never imply a causal model or a climate model.
- Radiative forcing is **copy-only**: no value, no chart.
- Never attribute warming to a country.
- The PRIMAP 1970+ all-gas chart is not called TCRE.
- Every figure shows its baseline (2.5).

## Open items
- Causal chain and Methodology need full-section designs (sources and licences table, per-module baseline table, 1959 splice and overlap gap, why the two global totals differ, 1970+ all-gas view).
- Replace all [mock] figures with pipeline output.

## Files
- `Area 2 Final Design.dc.html`: the final design (artboards 0, L1, L2, O1, O2, M1). Open in a browser; requires `support.js` alongside.
- `support.js`: runtime for the HTML reference only. Don't port it.
- Source requirements: `SPEC.md` §5.26, `ENHANCEMENTS.md` Release 21 (in the repo).
- Theme sources: `sauparnasarkar/design-system` → `src/styles/themes/analytics.css`, `analytics-bright-tidewater.css`.
