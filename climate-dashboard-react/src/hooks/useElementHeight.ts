import { useEffect, useState } from 'react';

/** The element's rendered height in px, or null until it has been measured (no element yet), kept current as it resizes -- e.g. a sticky row
 * that wraps to a second line at narrow widths. Takes the element itself (from a callback ref), so it also works for an element that mounts late.
 * Null vs a number lets a caller wait for the first measurement before acting on it (a layout can legitimately measure 0, e.g. in jsdom). */
export function useElementHeight(el: HTMLElement | null): number | null {
  const [height, setHeight] = useState<number | null>(null);
  useEffect(() => {
    if (!el) return;
    const measure = () => setHeight(el.getBoundingClientRect().height);
    measure();
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, [el]);
  return height;
}
