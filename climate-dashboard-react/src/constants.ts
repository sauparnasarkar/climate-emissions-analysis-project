// TS mirror of api/constants.py — single source of truth for the frontend.
//
// FEATURED_COUNTRIES/EXPANDED_COUNTRIES are no longer hardcoded here — they're
// data-driven now (data/selected_countries.json), fetched via GET /api/countries
// (see api/client.ts's listCountries() and hooks/useCountries.ts).

// Mirrors api/constants.py's MAX_SELECTED_COUNTRIES — shared by every capped MultiSelect
// (Historical Trends, Overview) so the two never drift.
export const MAX_SELECTED_COUNTRIES = 10;

// Same numeric convention as MAX_SELECTED_COUNTRIES above (a chart with more than 10 series
// stops being readable), but a distinct constant since it governs a different concern:
// render-time chart legibility for agent-driven widgets (WidgetRenderer.tsx), not picker
// input. The agent can call a tool with an arbitrary explicit country list -- unlike every
// MultiSelect on this dashboard, there's no upstream picker enforcing a cap before the data
// reaches the chart.
export const MAX_CHART_SERIES = 10;

export const GAS_COLUMNS: Record<string, string> = {
  co2: 'CO₂',
  methane: 'Methane (CH₄)',
  nitrous_oxide: 'Nitrous Oxide (N₂O)',
};

// The design handoff for the Bright/Dark toggle flagged a prior SCENARIO_COLORS hex map as a
// theme risk, but that map's per-scenario colors were never actually consumed by any chart --
// ScenarioComparisonPage.tsx renders one panel per scenario, each colored by *country* via
// SyChart's own default categorical palette, which already resolves correctly per theme. Only
// the scenario names themselves are needed elsewhere (panel titles, radio labels), so this
// stays a plain, theme-independent list rather than dead per-theme hex values.
export const SCENARIO_PANELS = ['BAU', 'Moderate', 'Aggressive'] as const;

// Shared increase/decrease convention: a decrease in emissions is good, an increase is bad --
// used wherever a value's direction maps to an emissions outcome, as opposed to a plain
// positive/negative-number convention. Colored via the same colorblind-safe brown/teal
// diverging pair every CO2-direction chart in this app uses (Claude Design theme-adherence
// review round 2) -- `--__s9cmpx-static-text-sentiment-diverging-positive/-negative` is that
// pair's light-background-text-tuned counterpart, published specifically because the dark-
// panel `--__s9cmpx-chart-diverging-low/-high` hexes (see `resolveDivergingEndpointHex`/
// `resolveDivergingScaleReversedHex` in `lib/resolveThemeColorHex.ts`, used by every chart)
// read too pale against a light card to use directly here.
//
// For plain DOM/CSS `style` props (theme-aware, resolved by the browser) -- these two usages
// (TierSummaryPanel's % Chg. column, OverviewHeadline's narrative sentence) are plain text on
// a light card, not Plotly chart props, so `var(...)` resolves live in CSS with no JS-side
// getComputedStyle step needed.
export const POSITIVE_COLOR = 'var(--__s9cmpx-static-text-sentiment-diverging-positive, #1D726B)';
export const NEGATIVE_COLOR = 'var(--__s9cmpx-static-text-sentiment-diverging-negative, #7D5B12)';
