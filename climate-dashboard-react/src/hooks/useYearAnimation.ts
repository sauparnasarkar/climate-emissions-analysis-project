import { useEffect, useMemo, useRef, useState, type RefObject } from 'react';
import { useReducedMotion } from 'design-system';
import { computeAutoplayStops } from '../lib/yearStops';

export interface UseYearAnimationOptions {
  minYear: number;
  maxYear: number;
  /** Milliseconds dwelt at each autoplay stop (see computeAutoplayStops -- not one per year). */
  intervalMs?: number;
  /** Years between autoplay stops (default 5). */
  stepYears?: number;
  /** When given, autoplay starts the first time this element scrolls into view instead of on mount --
   * so a globe/map further down a page (or on a phone, below the fold) isn't already several steps
   * through its animation by the time anyone sees it. Never starts if the user has already pressed
   * Play/Pause or scrubbed, and never for reduced motion. Falls back to starting on mount where
   * IntersectionObserver doesn't exist. */
  startWhenVisible?: RefObject<Element | null>;
  /** When false the animation is held paused (and never auto-starts) without counting as the user driving it --
   * e.g. a carousel slide that isn't showing. Turning it back on lets a not-yet-user-driven autoplay start/resume
   * (waiting for `startWhenVisible` again). Default true. */
  enabled?: boolean;
  /** When false nothing plays until the user presses Play: no autoplay on mount or on scroll-into-view (`startWhenVisible` is ignored), and the
   * year is `initialYear`, else the latest, until the user moves it -- following `maxYear` as the range arrives rather than freezing at the
   * placeholder a not-yet-loaded range had on the first render. For a year the page shares and keeps in the URL. Default true. */
  autoplay?: boolean;
  /** Year to start on instead of the first stop (or the latest, with `autoplay: false`); clamped to the range. */
  initialYear?: number;
}

/** Default autoplay step: every 5 years (minYear, minYear+5, ..., then maxYear). */
const DEFAULT_STEP_YEARS = 5;

export interface UseYearAnimationResult {
  currentYear: number;
  isPlaying: boolean;
  /** Resumes from currentYear, or restarts from the first stop if playback already finished at maxYear. */
  play: () => void;
  pause: () => void;
  toggle: () => void;
  /** Always pauses, then jumps straight to `year` (manual scrubbing, any year -- not stop-aligned). */
  seek: (year: number) => void;
  reducedMotion: boolean;
}

/**
 * Drives the animated-choropleth / globe year (SPEC.md §5.17). Autoplays on mount unless the user
 * has `prefers-reduced-motion` set, in which case it starts pinned at `maxYear` and does NOT
 * autoplay -- but Play still works. Reduced motion is about *unrequested* movement: the user
 * pressing Play (like scrubbing with `seek`) is a deliberate, user-initiated action, and disabling
 * it left iPhone users with Reduce Motion on (a common setting) with a permanently dead button.
 * Consumers still use `reducedMotion` to tone down the *kind* of motion (no globe spin, no colour
 * blending -- years just step).
 */
export function useYearAnimation({ minYear, maxYear, intervalMs = 1800, stepYears = DEFAULT_STEP_YEARS, startWhenVisible: startWhenVisibleOption, enabled = true, autoplay = true, initialYear }: UseYearAnimationOptions): UseYearAnimationResult {
  const startWhenVisible = autoplay ? startWhenVisibleOption : undefined;
  const reducedMotion = useReducedMotion();
  const stops = useMemo(() => computeAutoplayStops(minYear, maxYear, stepYears), [minYear, maxYear, stepYears]);
  // null = "the latest": with `autoplay: false` the year follows maxYear until the user moves it (see the option's doc comment).
  const [rawYear, setRawYear] = useState<number | null>(initialYear ?? (autoplay ? (reducedMotion ? maxYear : stops[0]) : null));
  const currentYear = Math.min(Math.max(rawYear ?? maxYear, minYear), maxYear);
  // Decided once, on first render: wait for the element only if a ref was given AND the browser can tell us.
  const deferAutoplay = useRef(Boolean(startWhenVisible) && typeof IntersectionObserver !== 'undefined');
  // Any deliberate Play/Pause/scrub means "the user is driving" -- a late scroll-into-view must not override it.
  const userDriven = useRef(false);
  const [isPlaying, setIsPlaying] = useState(autoplay && !reducedMotion && !deferAutoplay.current);
  // Avoids a stale-closure read of currentYear inside the interval callback below without
  // needing currentYear itself in the effect's dependency array (which would tear down and
  // recreate the interval every single tick).
  const currentYearRef = useRef(currentYear);
  currentYearRef.current = currentYear;

  // If the OS setting turns on mid-session (useReducedMotion is live-subscribed), stop whatever is
  // playing right away; the year is left where it is (the user can still scrub or press Play).
  useEffect(() => {
    if (reducedMotion) setIsPlaying(false);
  }, [reducedMotion]);

  // Held paused while disabled. Deliberately not `userDriven`: when it is enabled again an autoplay the user never
  // touched may start/resume (the observer effect below re-arms on `enabled`).
  useEffect(() => {
    if (!enabled) setIsPlaying(false);
  }, [enabled]);

  useEffect(() => {
    if (!isPlaying) return;
    const id = setInterval(() => {
      setRawYear((raw) => {
        const year = Math.min(Math.max(raw ?? maxYear, minYear), maxYear);
        // The next stop strictly after wherever we currently are -- not "the next index in
        // stops" -- so resuming Play after a manual seek to a non-stop year (e.g. 2015) advances
        // to the next decade boundary after that (2020), rather than replaying a stop already
        // passed or skipping arbitrarily.
        const next = stops.find((s) => s > year);
        return next ?? year;
      });
    }, intervalMs);
    return () => clearInterval(id);
  }, [isPlaying, stops, intervalMs, minYear, maxYear]);

  // Stops playback the instant the final stop is reached, rather than waiting one more full
  // dwell period to notice -- the animation has visibly finished; Play/Pause should reflect
  // that immediately. Separate from the ticking effect above so this also correctly no-ops
  // playback for a degenerate single-stop range (minYear === maxYear) without needing a tick.
  useEffect(() => {
    if (currentYear === stops[stops.length - 1]) setIsPlaying(false);
  }, [currentYear, stops]);

  // First time the element is (mostly) on screen: begin the autoplay from the first stop.
  useEffect(() => {
    const el = startWhenVisible?.current;
    if (!deferAutoplay.current || !el || reducedMotion || !enabled) return;
    const io = new IntersectionObserver(
      (entries) => {
        if (!entries.some((e) => e.isIntersecting)) return;
        io.disconnect();
        // Not once it has already played through: re-showing a finished animation must not restart the timer and spin
        // at the last year (the completion effect only runs when the year changes).
        if (!userDriven.current && currentYearRef.current < maxYear) setIsPlaying(true);
      },
      { threshold: 0.2 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [startWhenVisible, reducedMotion, enabled, maxYear]);

  const play = () => {
    if (!enabled) return;
    userDriven.current = true;
    if (currentYearRef.current >= maxYear) setRawYear(stops[0]);
    setIsPlaying(true);
  };
  const pause = () => {
    userDriven.current = true;
    setIsPlaying(false);
  };
  const toggle = () => (isPlaying ? pause() : play());
  const seek = (year: number) => {
    userDriven.current = true;
    setIsPlaying(false);
    setRawYear(Math.max(minYear, Math.min(maxYear, year)));
  };

  return { currentYear, isPlaying, play, pause, toggle, seek, reducedMotion };
}
