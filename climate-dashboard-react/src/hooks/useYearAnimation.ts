import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'design-system';

export interface UseYearAnimationOptions {
  minYear: number;
  maxYear: number;
  /** Milliseconds per year step. */
  intervalMs?: number;
}

export interface UseYearAnimationResult {
  currentYear: number;
  isPlaying: boolean;
  /** Resumes from currentYear, or restarts from minYear if playback already finished at maxYear. */
  play: () => void;
  pause: () => void;
  toggle: () => void;
  /** Always pauses, then jumps straight to `year` (manual scrubbing). */
  seek: (year: number) => void;
  reducedMotion: boolean;
}

/**
 * Drives the Overview page's animated-choropleth year (SPEC.md §5.17). Autoplays on mount
 * unless the user has `prefers-reduced-motion` set, in which case it's pinned at `maxYear`
 * with playback disabled entirely -- manual scrubbing via `seek` still works either way, since
 * that's a deliberate, user-initiated action rather than an unprompted animation.
 */
export function useYearAnimation({ minYear, maxYear, intervalMs = 600 }: UseYearAnimationOptions): UseYearAnimationResult {
  const reducedMotion = useReducedMotion();
  const [currentYear, setCurrentYear] = useState(reducedMotion ? maxYear : minYear);
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
        if (year >= maxYear) {
          setIsPlaying(false);
          return year;
        }
        return year + 1;
      });
    }, intervalMs);
    return () => clearInterval(id);
  }, [isPlaying, reducedMotion, maxYear, intervalMs]);

  const play = () => {
    if (reducedMotion) return;
    if (currentYearRef.current >= maxYear) setCurrentYear(minYear);
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
