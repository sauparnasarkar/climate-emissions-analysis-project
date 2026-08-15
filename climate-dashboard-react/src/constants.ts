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
// For plain DOM/CSS `style` props (theme-aware, resolved by the browser). Chart color props
// (SyChart's `color`/`pointColors`) can't resolve `var(...)` at all -- see
// `lib/resolveThemeColorHex.ts`'s `resolveSentimentColorHex` for that case instead of using
// these directly, since a hardcoded hex here would be wrong the moment a non-default theme
// (or a future theme toggle) is active.
export const POSITIVE_COLOR = 'var(--__s9cmpx-static-text-sentiment-positive, #187254)';
export const NEGATIVE_COLOR = 'var(--__s9cmpx-static-text-sentiment-negative, #8d1a2a)';
