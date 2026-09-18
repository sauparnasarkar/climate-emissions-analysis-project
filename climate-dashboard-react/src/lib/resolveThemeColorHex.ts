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

// Every sentiment-colored value in this app is drawn INSIDE a chart's dark panel (YoY bars,
// forecast/scenario series), never as plain card text -- `--__s9cmpx-static-text-sentiment-*`
// is tuned for the light card instead and fails contrast there (Claude Design theme-adherence
// review, C1). `--__s9cmpx-chart-sentiment-positive/-negative` is the on-panel counterpart
// published for exactly this case; on `analytics` (whose whole canvas is already dark) it
// aliases straight back to the static pair, so this reads correctly on both themes.
const SENTIMENT_FALLBACK_HEX: Record<'positive' | 'negative', string> = {
  positive: '#4FD69B',
  negative: '#EA5B62',
};

const SENTIMENT_VAR_NAME: Record<'positive' | 'negative', string> = {
  positive: '--__s9cmpx-chart-sentiment-positive',
  negative: '--__s9cmpx-chart-sentiment-negative',
};

export function resolveSentimentColorHex(direction: 'positive' | 'negative'): string {
  return resolveThemeVarHex(SENTIMENT_VAR_NAME[direction], SENTIMENT_FALLBACK_HEX[direction]);
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
