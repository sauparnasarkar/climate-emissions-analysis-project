import { useCallback, useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'design-system';

/** Seconds a banner stays up before auto-rotating (ENHANCEMENTS.md decision 59). */
export const CAROUSEL_DWELL_MS = 8000;

export interface UseCarouselOptions {
  count: number;
  dwellMs?: number;
}

export interface UseCarouselResult {
  index: number;
  /** The user's intent: auto-rotate is on (the button reads "Pause"). Hover/focus/hidden-tab pauses are temporary and not reflected. */
  autoplay: boolean;
  goTo: (i: number) => void;
  next: () => void;
  prev: () => void;
  pause: () => void;
  play: () => void;
  /** Spread on the carousel region: pauses while the pointer is over it or focus is inside it. */
  regionHandlers: {
    onMouseEnter: () => void;
    onMouseLeave: () => void;
    onFocusCapture: () => void;
    onBlurCapture: (e: React.FocusEvent) => void;
  };
}

/**
 * Rate-limited carousel autoplay (ENHANCEMENTS.md decision 59; requirements §2.1 "carefully rate-limited"):
 * - advances every `dwellMs`, and stops after one full cycle (every slide shown once), holding on the last;
 * - any manual action (arrows, tabs, keys, the Pause button) stops it until the user presses Play;
 * - pauses while the pointer is over the carousel or focus is inside it, and while the browser tab is hidden;
 * - starts stopped under `prefers-reduced-motion`.
 */
export function useCarousel({ count, dwellMs = CAROUSEL_DWELL_MS }: UseCarouselOptions): UseCarouselResult {
  const reducedMotion = useReducedMotion();
  const [index, setIndex] = useState(0);
  const [stopped, setStopped] = useState(reducedMotion);
  // Pointer-over and focus-inside are tracked separately: leaving with the pointer while focus is still inside (or the
  // reverse) must not let a slide disappear under someone who is still interacting with it.
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const [tabHidden, setTabHidden] = useState(() => typeof document !== 'undefined' && document.hidden);
  // Auto advances since autoplay (re)started; a full cycle is count - 1 of them.
  const advances = useRef(0);

  useEffect(() => {
    if (reducedMotion) setStopped(true);
  }, [reducedMotion]);

  useEffect(() => {
    const onVisibility = () => setTabHidden(document.hidden);
    document.addEventListener('visibilitychange', onVisibility);
    return () => document.removeEventListener('visibilitychange', onVisibility);
  }, []);

  const running = !stopped && !hovered && !focused && !tabHidden && count > 1;
  useEffect(() => {
    if (!running) return;
    const id = setTimeout(() => {
      advances.current += 1;
      setIndex((i) => (i + 1) % count);
      if (advances.current >= count - 1) setStopped(true);
    }, dwellMs);
    return () => clearTimeout(id);
  }, [running, index, dwellMs, count]);

  const goTo = useCallback((i: number) => {
    setStopped(true);
    setIndex(((i % count) + count) % count);
  }, [count]);
  const next = useCallback(() => goTo(index + 1), [goTo, index]);
  const prev = useCallback(() => goTo(index - 1), [goTo, index]);
  const pause = useCallback(() => setStopped(true), []);
  const play = useCallback(() => {
    advances.current = 0;
    setStopped(false);
  }, []);

  const regionHandlers = {
    onMouseEnter: () => setHovered(true),
    onMouseLeave: () => setHovered(false),
    onFocusCapture: () => setFocused(true),
    // Focus moving between two controls inside the region is not leaving it.
    onBlurCapture: (e: React.FocusEvent) => {
      if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setFocused(false);
    },
  };

  return { index, autoplay: !stopped, goTo, next, prev, pause, play, regionHandlers };
}
