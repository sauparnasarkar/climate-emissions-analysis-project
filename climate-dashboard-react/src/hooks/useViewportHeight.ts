import { useEffect, useState } from 'react';

/** The window's inner height in px, kept current on resize. Used to size the landing carousel so a banner and its
 * controls fit above the fold on a laptop. */
export function useViewportHeight(): number {
  const [height, setHeight] = useState(() => (typeof window === 'undefined' ? 900 : window.innerHeight));
  useEffect(() => {
    const onResize = () => setHeight(window.innerHeight);
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return height;
}

/** A viewport reading: its width and inner height in px. */
export interface ViewportSize { w: number; h: number }

/** The next stable reading: a rotation (width changed) or a shrink is taken as it is; a height-only growth is ignored. On a phone, Safari's toolbar collapsing
 * while the visitor scrolls makes the inner height grow, and sizing the globe from it would resize the picture under their finger. */
export function nextStableViewport(prev: ViewportSize, next: ViewportSize): ViewportSize {
  if (next.w !== prev.w) return next;
  return next.h < prev.h ? next : prev;
}

/** The inner height with the browser toolbars showing (the small viewport): follows a rotation and any shrink, never a toolbar-collapse growth. */
export function useStableViewportHeight(): number {
  const read = (): ViewportSize => (typeof window === 'undefined' ? { w: 0, h: 900 } : { w: window.innerWidth, h: window.innerHeight });
  const [size, setSize] = useState(read);
  useEffect(() => {
    const onResize = () => setSize((prev) => nextStableViewport(prev, read()));
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  return size.h;
}
