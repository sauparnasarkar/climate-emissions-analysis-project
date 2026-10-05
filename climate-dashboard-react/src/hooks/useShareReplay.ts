import { useCallback, useEffect, useState } from 'react';
import { SHARE_STEP_MS } from '../lib/shareBars';

/**
 * The Share bars' temporary replay (ENHANCEMENTS.md decision 64): steps one year per `stepMs` from `first` up to `target` (the page year), then
 * returns to the page year by itself. It is temporary -- it never changes the page year -- and ends early when the page year moves (`target`
 * changes) or the page's own Play starts (`cancel`). `replayYear` is the year on screen while it runs, null otherwise.
 */
export function useShareReplay(first: number, target: number, cancel: boolean, stepMs: number = SHARE_STEP_MS) {
  const [replayYear, setReplayYear] = useState<number | null>(null);
  const active = replayYear !== null;

  useEffect(() => {
    setReplayYear(null);
  }, [target, cancel]);

  useEffect(() => {
    if (!active) return;
    const id = setInterval(() => setReplayYear((y) => (y === null || y + 1 > target ? null : y + 1)), stepMs);
    return () => clearInterval(id);
  }, [active, target, stepMs]);

  const start = useCallback(() => {
    if (target > first) setReplayYear(first);
  }, [first, target]);
  const stop = useCallback(() => setReplayYear(null), []);
  return { replayYear, replaying: active, start, stop };
}
