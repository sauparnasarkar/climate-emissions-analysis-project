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

/** The phone breakpoint of the Area 2 navigation (ENHANCEMENTS.md decision 69). */
export const PHONE_QUERY = '(max-width: 640px)';
