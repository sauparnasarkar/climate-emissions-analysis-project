import { useCallback, useEffect, useState } from 'react';
import { useReducedMotion } from 'design-system';

/** Seconds a banner stays up before auto-rotating (ENHANCEMENTS.md decision 59). */
export const CAROUSEL_DWELL_MS = 10000;

export interface UseCarouselOptions {
  count: number;
  dwellMs?: number;
}

export type CarouselDirection = 'forward' | 'back';

export interface UseCarouselResult {
  index: number;
  /** The slide just left, or null before the first move. With `direction` it tells the view which way to slide. */
  previous: number | null;
  /** The way the last move went: Next and auto-rotate are always forward (also when wrapping from the last slide to the first);
   * Previous is back; jumping to a slide by tab goes forward to a later one and back to an earlier one. */
  direction: CarouselDirection;
  /** Whether auto-rotate is on: the Play/Pause button's state, and nothing else. */
  autoplay: boolean;
  goTo: (i: number) => void;
  next: () => void;
  prev: () => void;
  pause: () => void;
  play: () => void;
}

interface Nav {
  index: number;
  previous: number | null;
  direction: CarouselDirection;
}

/**
 * Carousel auto-rotate controlled by one thing: the Play/Pause button (ENHANCEMENTS.md decision 59, as amended 2026-10-04).
 * It rotates every `dwellMs` while on; Pause stops it and Play starts it. Moving to a slide by hand (arrows, tabs, ←/→) does
 * not change that state -- the dwell simply starts afresh on the slide you chose. The pointer, focus and the browser tab have no
 * effect. Under `prefers-reduced-motion` it starts paused (an explicit Play is a request for movement).
 */
export function useCarousel({ count, dwellMs = CAROUSEL_DWELL_MS }: UseCarouselOptions): UseCarouselResult {
  const reducedMotion = useReducedMotion();
  const [nav, setNav] = useState<Nav>({ index: 0, previous: null, direction: 'forward' });
  const [paused, setPaused] = useState(reducedMotion);

  useEffect(() => {
    if (reducedMotion) setPaused(true);
  }, [reducedMotion]);

  const wrap = useCallback((i: number) => ((i % count) + count) % count, [count]);
  const move = useCallback((to: number, direction: CarouselDirection) => {
    setNav((n) => (n.index === to ? n : { index: to, previous: n.index, direction }));
  }, []);

  const running = !paused && count > 1;
  useEffect(() => {
    if (!running) return;
    const id = setTimeout(() => move(wrap(nav.index + 1), 'forward'), dwellMs);
    return () => clearTimeout(id);
  }, [running, nav.index, dwellMs, move, wrap]);

  const goTo = useCallback((i: number) => {
    const to = wrap(i);
    move(to, to > nav.index ? 'forward' : 'back');
  }, [move, wrap, nav.index]);
  const next = useCallback(() => move(wrap(nav.index + 1), 'forward'), [move, wrap, nav.index]);
  const prev = useCallback(() => move(wrap(nav.index - 1), 'back'), [move, wrap, nav.index]);
  const pause = useCallback(() => setPaused(true), []);
  const play = useCallback(() => setPaused(false), []);

  return { index: nav.index, previous: nav.previous, direction: nav.direction, autoplay: !paused, goTo, next, prev, pause, play };
}
