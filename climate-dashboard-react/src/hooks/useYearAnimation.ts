import { useEffect, useMemo, useRef, useState } from 'react';
import { useReducedMotion } from 'design-system';

export interface UseYearAnimationOptions {
  minYear: number;
  maxYear: number;
  /** Milliseconds dwelt at each autoplay stop (see computeDecadeStops -- not one per year). */
  intervalMs?: number;
}

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
 * Autoplay stops: minYear, then every decade boundary after it, then maxYear (if maxYear isn't
 * already a decade boundary). Year-over-year change is gradual enough that stepping through
 * every single year makes the trend hard to notice; jumping decade to decade makes it obvious
 * at a glance, which is the point of the animation. Manual scrubbing (`seek`) is unaffected --
 * it always allows any year in [minYear, maxYear], not just these stops.
 */
function computeDecadeStops(minYear: number, maxYear: number): number[] {
  const stops = [minYear];
  for (let year = Math.ceil((minYear + 1) / 10) * 10; year < maxYear; year += 10) {
    stops.push(year);
  }
  if (stops[stops.length - 1] !== maxYear) stops.push(maxYear);
  return stops;
}

/**
 * Drives the Overview page's animated-choropleth year (SPEC.md §5.17). Autoplays on mount
 * unless the user has `prefers-reduced-motion` set, in which case it's pinned at `maxYear`
 * with playback disabled entirely -- manual scrubbing via `seek` still works either way, since
 * that's a deliberate, user-initiated action rather than an unprompted animation.
 */
export function useYearAnimation({ minYear, maxYear, intervalMs = 1800 }: UseYearAnimationOptions): UseYearAnimationResult {
  const reducedMotion = useReducedMotion();
  const stops = useMemo(() => computeDecadeStops(minYear, maxYear), [minYear, maxYear]);
  const [currentYear, setCurrentYear] = useState(reducedMotion ? maxYear : stops[0]);
  const [isPlaying, setIsPlaying] = useState(!reducedMotion);
  // Avoids a stale-closure read of currentYear inside the interval callback below without
  // needing currentYear itself in the effect's dependency array (which would tear down and
  // recreate the interval every single tick).
  const currentYearRef = useRef(currentYear);
  currentYearRef.current = currentYear;

  // If the OS setting changes mid-session (useReducedMotion is live-subscribed), stop
  // playback immediately and snap to the static, fully-scrubbable end state.
  useEffect(() => {
    if (reducedMotion) {
      setIsPlaying(false);
      setCurrentYear(maxYear);
    }
  }, [reducedMotion, maxYear]);

  useEffect(() => {
    if (!isPlaying || reducedMotion) return;
    const id = setInterval(() => {
      setCurrentYear((year) => {
        // The next stop strictly after wherever we currently are -- not "the next index in
        // stops" -- so resuming Play after a manual seek to a non-stop year (e.g. 2015) advances
        // to the next decade boundary after that (2020), rather than replaying a stop already
        // passed or skipping arbitrarily.
        const next = stops.find((s) => s > year);
        return next ?? year;
      });
    }, intervalMs);
    return () => clearInterval(id);
  }, [isPlaying, reducedMotion, stops, intervalMs]);

  // Stops playback the instant the final stop is reached, rather than waiting one more full
  // dwell period to notice -- the animation has visibly finished; Play/Pause should reflect
  // that immediately. Separate from the ticking effect above so this also correctly no-ops
  // playback for a degenerate single-stop range (minYear === maxYear) without needing a tick.
  useEffect(() => {
    if (currentYear === stops[stops.length - 1]) setIsPlaying(false);
  }, [currentYear, stops]);

  const play = () => {
    if (reducedMotion) return;
    if (currentYearRef.current >= maxYear) setCurrentYear(stops[0]);
    setIsPlaying(true);
  };
  const pause = () => setIsPlaying(false);
  const toggle = () => (isPlaying ? pause() : play());
  const seek = (year: number) => {
    setIsPlaying(false);
    setCurrentYear(Math.max(minYear, Math.min(maxYear, year)));
  };

  return { currentYear, isPlaying, play, pause, toggle, seek, reducedMotion };
}
