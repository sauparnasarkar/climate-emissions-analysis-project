import { useCallback, useEffect, useState } from 'react';
import { useReducedMotion } from 'design-system';

/** Seconds a banner stays up before auto-rotating (ENHANCEMENTS.md decision 59). */
export const CAROUSEL_DWELL_MS = 10000;

export interface UseCarouselOptions {
  count: number;
  dwellMs?: number;
}

export interface UseCarouselResult {
  index: number;
  /** Whether auto-rotate is on: the Play/Pause button's state, and nothing else. */
  autoplay: boolean;
  goTo: (i: number) => void;
  next: () => void;
  prev: () => void;
  pause: () => void;
  play: () => void;
}

/**
 * Carousel auto-rotate controlled by one thing: the Play/Pause button (ENHANCEMENTS.md decision 59, as amended 2026-10-04).
 * It rotates every `dwellMs` while on; Pause stops it and Play starts it. Moving to a slide by hand (arrows, tabs, ←/→) does
 * not change that state -- the dwell simply starts afresh on the slide you chose. The pointer, focus and the browser tab have no
 * effect. Under `prefers-reduced-motion` it starts paused (an explicit Play is a request for movement).
 */
export function useCarousel({ count, dwellMs = CAROUSEL_DWELL_MS }: UseCarouselOptions): UseCarouselResult {
  const reducedMotion = useReducedMotion();
  const [index, setIndex] = useState(0);
  const [paused, setPaused] = useState(reducedMotion);

  useEffect(() => {
    if (reducedMotion) setPaused(true);
  }, [reducedMotion]);

  const running = !paused && count > 1;
  useEffect(() => {
    if (!running) return;
    const id = setTimeout(() => setIndex((i) => (i + 1) % count), dwellMs);
    return () => clearTimeout(id);
  }, [running, index, dwellMs, count]);

  const goTo = useCallback((i: number) => setIndex(((i % count) + count) % count), [count]);
  const next = useCallback(() => goTo(index + 1), [goTo, index]);
  const prev = useCallback(() => goTo(index - 1), [goTo, index]);
  const pause = useCallback(() => setPaused(true), []);
  const play = useCallback(() => setPaused(false), []);

  return { index, autoplay: !paused, goTo, next, prev, pause, play };
}
