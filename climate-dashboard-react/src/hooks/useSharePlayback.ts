import { useCallback, useEffect, useState } from 'react';
import { SHARE_STEP_MS } from '../lib/shareBars';

/**
 * Year playback for the Share bars (ENHANCEMENTS.md decision 63): user-initiated only, one year per `stepMs`, stops at `max`, and Play from the
 * end replays from `min`. Scrubbing pauses. Until the user plays or scrubs, the year *is* `max` -- so it follows the range as the data arrives
 * (the range is a placeholder until the first response) rather than freezing at whatever `max` was on the first render.
 */
export function useSharePlayback(min: number, max: number, stepMs: number = SHARE_STEP_MS) {
  const [rawYear, setRawYear] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const year = Math.min(Math.max(rawYear ?? max, min), max);

  useEffect(() => {
    if (!playing) return;
    const id = setInterval(() => setRawYear((y) => Math.min(Math.max(y ?? max, min) + 1, max)), stepMs);
    return () => clearInterval(id);
  }, [playing, min, max, stepMs]);
  useEffect(() => {
    if (playing && year >= max) setPlaying(false);
  }, [playing, year, max]);

  const toggle = useCallback(() => {
    if (playing) return setPlaying(false);
    if (year >= max) setRawYear(min);
    setPlaying(true);
  }, [playing, year, min, max]);
  const seek = useCallback((y: number) => {
    setPlaying(false);
    setRawYear(y);
  }, []);
  return { year, playing, toggle, seek };
}
