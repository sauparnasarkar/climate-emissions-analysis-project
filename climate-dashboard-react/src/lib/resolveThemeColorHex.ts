// SyChart's `color`/`pointColors` props are passed straight into Plotly's own color parser,
// which can't resolve CSS custom properties (`var(...)`) at all -- it silently renders black
// rather than falling back. Callers that need a sentiment color inside a Plotly series must
// resolve the CSS variable to its actual computed hex first, against whichever theme is
// currently active on the document (this app forces `data-theme="analytics"`, but this stays
// correct even if a theme toggle is added later).
const FALLBACK_HEX: Record<'positive' | 'negative', string> = {
  positive: '#187254',
  negative: '#8d1a2a',
};

const VAR_NAME: Record<'positive' | 'negative', string> = {
  positive: '--__s9cmpx-static-text-sentiment-positive',
  negative: '--__s9cmpx-static-text-sentiment-negative',
};

export function resolveSentimentColorHex(direction: 'positive' | 'negative'): string {
  if (typeof document === 'undefined') return FALLBACK_HEX[direction];
  // App.tsx sets `data-theme="analytics"` on its own `.app-shell` root div, not on
  // `<html>` -- resolving against `document.documentElement` would silently read the
  // un-themed (light) default values instead, since that attribute scopes the CSS
  // custom property overrides to its own subtree.
  const themedRoot = document.querySelector('[data-theme]') ?? document.documentElement;
  const resolved = getComputedStyle(themedRoot).getPropertyValue(VAR_NAME[direction]).trim();
  return resolved || FALLBACK_HEX[direction];
}
