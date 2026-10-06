import { useEffect, useState } from 'react';

/** Whether a media query currently matches, kept current as it changes (e.g. a phone-width viewport). False where `matchMedia` does not exist. */
export function useMediaQuery(query: string): boolean {
  const get = () => (typeof window !== 'undefined' && typeof window.matchMedia === 'function' ? window.matchMedia(query).matches : false);
  const [matches, setMatches] = useState(get);
  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return;
    const mq = window.matchMedia(query);
    const onChange = () => setMatches(mq.matches);
    onChange();
    mq.addEventListener?.('change', onChange);
    return () => mq.removeEventListener?.('change', onChange);
  }, [query]);
  return matches;
}

/** A phone turned sideways: wider than 768 px but at most ~430 px tall (tablets and desktop windows are taller). ENHANCEMENTS.md decision 74. */
export const PHONE_LANDSCAPE_QUERY = '(orientation: landscape) and (max-height: 500px)';

/** The phone breakpoint of the Area 2 navigation (ENHANCEMENTS.md decision 69). */
export const PHONE_QUERY = '(max-width: 640px)';

/** Tablets and below: the landing page's one-column breakpoint (1100 px), widened to 1440 px for touch screens so an iPad Pro in landscape (1376 px) counts too while a laptop window that wide does not. Where the top nav collapses behind a menu button too. */
export const TABLET_QUERY = '(max-width: 1100px), (max-width: 1440px) and (pointer: coarse)';
