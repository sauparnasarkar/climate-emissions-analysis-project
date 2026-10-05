import { useEffect, useState } from 'react';

/** The element's rendered height in px (0 until it exists or where it can't be measured), kept current as it resizes -- e.g. a sticky row that
 * wraps to a second line at narrow widths. Takes the element itself (from a callback ref), so it also works for an element that mounts late. */
export function useElementHeight(el: HTMLElement | null): number {
  const [height, setHeight] = useState(0);
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
