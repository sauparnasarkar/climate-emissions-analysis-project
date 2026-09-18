import { useLayoutEffect, useState } from 'react';
import { useTheme } from '../lib/theme';

/**
 * Re-resolves a `resolveThemeColorHex.ts` color every time the Bright/Dark toggle flips,
 * correctly this time -- calling a resolver directly in a render body (the pattern every
 * caller used before this hook existed) reads `getComputedStyle` against the LIVE DOM, but
 * React's render phase runs before the commit that actually flips `data-theme` on
 * `.app-shell`. On a theme change, that read races the commit and returns the OUTGOING
 * theme's value; since nothing then triggers a second render, the color stays one toggle
 * behind until the next flip (invisible in an eyeballed screenshot when the two themes'
 * hexes happen to be similarly bright -- caught only by comparing the resolved hex, not the
 * pixels, before/after a live toggle).
 *
 * `useLayoutEffect` runs synchronously after the commit that updates `data-theme`, so the
 * re-resolve there reads the correct value and (via `setHex`) forces the one corrective
 * re-render before the browser paints -- no visible flicker.
 */
export function useThemeColorHex(resolve: () => string): string {
  const theme = useTheme();
  const [hex, setHex] = useState(resolve);
  useLayoutEffect(() => {
    setHex(resolve());
    // Deliberately keyed on `theme` alone, not `resolve` (a fresh closure every render) --
    // the resolved value only ever actually changes when the theme does.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [theme]);
  return hex;
}
