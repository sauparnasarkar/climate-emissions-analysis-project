// SyChart's `color`/`pointColors`/`noDataColor` props are passed straight into Plotly's own
// color parser, which can't resolve CSS custom properties (`var(...)`) at all -- it silently
// renders black rather than falling back. Callers that need a theme-aware color inside a
// Plotly series must resolve the CSS variable to its actual computed hex first, against
// whichever theme is currently active on the document -- App.tsx's Bright/Dark toggle changes
// `data-theme` at runtime, so this reads the live value rather than assuming a fixed theme.
function resolveThemeVarHex(varName: string, fallback: string): string {
  if (typeof document === 'undefined') return fallback;
  // App.tsx sets `data-theme` (whichever of Bright/Dark is active) on its own `.app-shell`
  // root div, not on `<html>` -- resolving against `document.documentElement` would silently
  // read the un-themed (light) default values instead, since that attribute scopes the CSS
  // custom property overrides to its own subtree.
  const themedRoot = document.querySelector('[data-theme]') ?? document.documentElement;
  const resolved = getComputedStyle(themedRoot).getPropertyValue(varName).trim();
  return resolved || fallback;
}

// `slot` is 1-9, matching SyChart's own `--__s9cmpx-chart-categorical-default-0N` tokens --
// use this instead of a hardcoded literal so a chart color tracks the active theme's series
// palette (Claude Design theme-adherence review, C3).
export function resolveCategoricalColorHex(slot: number, fallback: string): string {
  return resolveThemeVarHex(`--__s9cmpx-chart-categorical-default-0${slot}`, fallback);
}

// No design-system token exists yet for "no-data" specifically, so this reuses
// `--__s9cmpx-chart-surface-text-weak` -- already published per theme, already contrast-
// validated against that theme's dark chart panel (it's what SyChart uses for axis labels),
// and visually distinct from the yellow-to-maroon magnitude ramp it sits alongside (Claude
// Design theme-adherence review, C4).
export function resolveNoDataColorHex(fallback: string): string {
  return resolveThemeVarHex('--__s9cmpx-chart-surface-text-weak', fallback);
}

// SyChart's own `DEFAULT_CONTINUOUS_SCALE` (ColorBrewer "BrBG" brown/grey/teal, A6) -- kept
// byte-for-byte in sync with design-system's SyChart.tsx since this resolves the *same*
// published `--__s9cmpx-chart-diverging-low/-mid/-high` tokens, just re-ordered below.
const DIVERGING_LOW_FALLBACK_HEX = '#D8B365';
const DIVERGING_MID_FALLBACK_HEX = '#E5E5E5';
const DIVERGING_HIGH_FALLBACK_HEX = '#5AB4AC';

/**
 * SyChart's default diverging scale positions "low" at the bottom of the *value* range and
 * "high" at the top -- correct for a scale with no inherent sentiment, but Overview's %
 * Change-by-country bars and the Scenario Comparison treemap both feed it signed deltas where
 * positive means "emissions rose" (bad) and negative means "emissions fell" (good). Left at
 * SyChart's default stop order, brown (index 0) lands on decrease and teal (index 1) lands on
 * increase -- the same slot positions the old literal green/crimson scale used (green=low=
 * decrease, crimson=high=increase), so nothing about *which value goes where* changed when A6
 * swapped in this CVD-safe hue pair. But the swap flipped the *intuitive* reading: teal reads
 * as calm/positive to most viewers and brown as dull/negative, backwards from "an increase in
 * emissions should be a negative signal." This reverses the stop order (high, mid, low) so
 * brown lands on increase/bad and teal lands on decrease/good instead -- the exact same
 * colorblind-safe BrBG hues C5/A6 chose, not a reintroduction of red/green.
 */
export function resolveDivergingScaleReversedHex(): Array<[number, string]> {
  const low = resolveThemeVarHex('--__s9cmpx-chart-diverging-low', DIVERGING_LOW_FALLBACK_HEX);
  const mid = resolveThemeVarHex('--__s9cmpx-chart-diverging-mid', DIVERGING_MID_FALLBACK_HEX);
  const high = resolveThemeVarHex('--__s9cmpx-chart-diverging-high', DIVERGING_HIGH_FALLBACK_HEX);
  return [
    [0, high],
    [0.5, mid],
    [1, low],
  ];
}

/**
 * The same reversed-diverging pair as `resolveDivergingScaleReversedHex`, but as two bare
 * hex endpoints rather than a 3-stop colorScale array -- for a chart that colors discrete
 * `pointColors` off the sign of each value (Country Profile's YoY bars) instead of feeding a
 * continuous `colorValues` gradient. Kept as the *same* brown/teal pair as the other two
 * diverging charts (not the separate literal red/green `--__s9cmpx-chart-sentiment-*` tokens)
 * so all three CO2-direction charts in this app agree visually, not just directionally.
 * 'positive' here means the *emissions* direction is favorable (a decrease -- teal), 'negative'
 * unfavorable (an increase -- brown), matching every other diverging-direction convention in
 * this file, not a bare positive/negative-number convention.
 */
export function resolveDivergingEndpointHex(direction: 'positive' | 'negative'): string {
  return direction === 'positive'
    ? resolveThemeVarHex('--__s9cmpx-chart-diverging-high', DIVERGING_HIGH_FALLBACK_HEX)
    : resolveThemeVarHex('--__s9cmpx-chart-diverging-low', DIVERGING_LOW_FALLBACK_HEX);
}
