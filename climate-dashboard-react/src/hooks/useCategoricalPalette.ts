import { useLayoutEffect, useState, type RefObject } from 'react';

// SyChart's own fallback palette (design-system chartMath.ts FALLBACK_PALETTE), used until the theme's tokens resolve and
// in jsdom, which has no computed custom properties.
export const FALLBACK_PALETTE = ['#7accf5', '#e66066', '#d19e27', '#87ca65', '#fed26a', '#be8cd7', '#3950c4', '#a333a1', '#46b7b7', '#c42338'];

const sameColors = (a: string[], b: string[]) => a.length === b.length && a.every((c, i) => c === b[i]);

/**
 * The active theme's 10-slot categorical chart palette, resolved the way SyChart resolves it (--__s9cmpx-chart-categorical-default-NN
 * against the element's computed style), so a page that must reorder series can still give each one the colour SyChart would have
 * given it by position elsewhere. Re-reads when the nearest [data-theme] ancestor changes theme.
 */
export function useCategoricalPalette(ref: RefObject<HTMLElement | null>): string[] {
  const [palette, setPalette] = useState<string[]>(FALLBACK_PALETTE);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const read = () => {
      const cs = getComputedStyle(el);
      const next = FALLBACK_PALETTE.map(
        (fb, i) => cs.getPropertyValue(`--__s9cmpx-chart-categorical-default-${String(i + 1).padStart(2, '0')}`).trim() || fb,
      );
      setPalette((prev) => (sameColors(prev, next) ? prev : next));
    };
    read();
    const host = el.closest('[data-theme]');
    if (!host) return;
    const observer = new MutationObserver(read);
    observer.observe(host, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, [ref]);

  return palette;
}
