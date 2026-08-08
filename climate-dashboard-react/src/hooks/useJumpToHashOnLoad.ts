import { useEffect, useRef } from 'react';
import { scrollToJumpTarget } from 'design-system';

/**
 * Scrolls to and focuses a `#anchor` already in the URL (a bookmarked/shared jump-nav link,
 * SPEC.md §5.19) once `ready` becomes true -- fires exactly once per page load, not on every
 * subsequent `ready` re-render (e.g. a data refetch triggered by changing the country picker).
 * The browser's own one-shot native hash-scroll on initial page load often fires before a
 * data-loaded page's target section exists in the DOM yet, so this replays the same jump once
 * it does.
 */
export function useJumpToHashOnLoad(ready: boolean, reduceMotion: boolean): void {
  const handled = useRef(false);
  useEffect(() => {
    if (handled.current || !ready) return;
    handled.current = true;
    const hash = window.location.hash.slice(1);
    if (hash) scrollToJumpTarget(hash, { reduceMotion });
    // reduceMotion isn't a dep -- handled.current makes this a one-shot effect, so a later
    // change to reduceMotion could never trigger a second run anyway.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);
}
