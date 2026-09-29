// Shared by the Overview's flat map and the landing page's globe, so both paint identical colours.
// Sequential pale-yellow -> orange -> deep-maroon magnitude scale for the world map, distinct
// from the % Change chart's and Scenario Comparison's shared brown/teal diverging convention
// below it (A6 -- Claude Design theme-adherence review) -- two visually distinct conventions,
// sequential magnitude vs. diverging above/below, each used for one concept. Those two diverging
// charts don't use SyChart's own default stop order, though -- both pass an explicit colorScale
// from resolveDivergingScaleReversedHex, which swaps low/high so an increase (bad) lands on
// brown and a decrease (good) lands on teal; see that function's comment for why. A future
// diverging-scale chart added here should decide deliberately, not copy SyChart's default.
// 9 stops (ColorBrewer's YlOrRd), not 3 -- colorRange is pinned across the whole 1990-2024
// animation (SPEC.md §5.17.2) and most countries, most years, sit in the same middle band of
// that fixed range, where a coarse 3-stop scale interpolates almost linearly and reads as
// near-identical shades of orange. More stops means more perceptually distinct color at the
// values that actually vary year to year, making the 1990-vs-2024 difference easier to read at
// a glance without touching colorRange itself (which must stay the true global min/max, per
// §5.17.2 -- narrowing or padding it would re-introduce the per-frame-renormalization problem
// that prop exists to prevent).
export const MAGNITUDE_SCALE: Array<[number, string]> = [
  [0, '#ffffcc'],
  [0.125, '#ffeda0'],
  [0.25, '#fed976'],
  [0.375, '#feb24c'],
  [0.5, '#fd8d3c'],
  [0.625, '#fc4e2a'],
  [0.75, '#e31a1c'],
  [0.875, '#bd0026'],
  [1, '#800026'],
];
