// TS mirror of api/constants.py — single source of truth for the frontend.
//
// FEATURED_COUNTRIES/EXPANDED_COUNTRIES are no longer hardcoded here — they're
// data-driven now (data/selected_countries.json), fetched via GET /api/countries
// (see api/client.ts's listCountries() and hooks/useCountries.ts).

// Mirrors api/constants.py's MAX_SELECTED_COUNTRIES — shared by every capped MultiSelect
// (Historical Trends, Overview) so the two never drift.
export const MAX_SELECTED_COUNTRIES = 10;

export const GAS_COLUMNS: Record<string, string> = {
  co2: 'CO₂',
  methane: 'Methane (CH₄)',
  nitrous_oxide: 'Nitrous Oxide (N₂O)',
};

export const SCENARIO_COLORS: Record<string, string> = {
  BAU: '#3950c4',
  Moderate: '#d19e27',
  Aggressive: '#87ca65',
};

// Shared increase/decrease convention: a decrease in emissions is good (green), an increase
// is bad (crimson) — used wherever a value's direction maps to an emissions outcome, as
// opposed to a plain positive/negative-number convention.
//
// Two forms are needed: `var(...)` for plain DOM/CSS `style` props (theme-aware, resolved by
// the browser), and a literal hex fallback for chart color props (SyChart's `color`/
// `pointColors` are passed straight into Plotly's own color parser, which can't resolve CSS
// custom properties — it silently renders black rather than falling back).
export const POSITIVE_COLOR = 'var(--__s9cmpx-static-text-sentiment-positive, #187254)';
export const NEGATIVE_COLOR = 'var(--__s9cmpx-static-text-sentiment-negative, #8d1a2a)';
export const POSITIVE_COLOR_HEX = '#187254';
export const NEGATIVE_COLOR_HEX = '#8d1a2a';
