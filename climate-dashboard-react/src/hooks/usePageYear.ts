import { useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useYearAnimation, type UseYearAnimationResult } from './useYearAnimation';

/** The Overview's page year steps by decade and dwells ~1.75 s at each stop (requirements §2.6; ENHANCEMENTS.md decision 64). */
export const PAGE_YEAR_STOP_MS = 1750;
export const PAGE_YEAR_STEP = 10;
const PARAM = 'year';

/** `?year=` as a whole year, or undefined when absent or not a number. */
export function parseYearParam(search: string): number | undefined {
  const raw = new URLSearchParams(search).get(PARAM);
  return raw && /^\d{4}$/.test(raw) ? Number(raw) : undefined;
}

/**
 * The one year the middle of the Overview shares (ENHANCEMENTS.md decision 64): the map, tiers, ranking, ppm card and the sections below.
 * It starts on `?year=` (clamped to the range; an unknown or absent year means the latest), never autoplays -- Play is the user's -- and is kept
 * in the URL (replace, so stepping doesn't fill the back stack; dropped while it is the latest, leaving other params and the hash alone).
 * `years` is null until the series has loaded: the year then follows the range instead of freezing on a placeholder, and the URL is left alone.
 */
export function usePageYear(years: number[] | null): UseYearAnimationResult {
  const { search, hash, pathname } = useLocation();
  const navigate = useNavigate();
  const minYear = years?.[0] ?? 1970;
  const maxYear = years?.[years.length - 1] ?? 1970;
  const anim = useYearAnimation({
    minYear,
    maxYear,
    intervalMs: PAGE_YEAR_STOP_MS,
    stepYears: PAGE_YEAR_STEP,
    autoplay: false,
    initialYear: parseYearParam(search),
  });
  const { currentYear, seek } = anim;
  // The query string this hook last wrote, and the last one it looked at: a change to `search` that is not its own write came from outside
  // (back/forward, or another link to /overview?year=… while this page stays mounted) and must move the year, not be overwritten by it.
  const lastWritten = useRef<string | null>(null);
  const lastSeen = useRef(search);

  useEffect(() => {
    if (!years) return;
    if (search !== lastSeen.current) {
      lastSeen.current = search;
      // The marker is consumed by the first change that follows the write, so a later outside navigation to the same query (after the year has
      // moved on) is not mistaken for it.
      const own = search === lastWritten.current;
      lastWritten.current = null;
      if (!own) {
        const fromUrl = Math.min(Math.max(parseYearParam(search) ?? maxYear, minYear), maxYear);
        if (fromUrl !== currentYear) {
          seek(fromUrl);
          return;
        }
      }
    }
    const params = new URLSearchParams(search);
    const want = currentYear === maxYear ? null : String(currentYear);
    if (params.get(PARAM) === want) return;
    if (want === null) params.delete(PARAM);
    else params.set(PARAM, want);
    const qs = params.toString();
    lastWritten.current = qs ? `?${qs}` : '';
    navigate({ pathname, search: qs ? `?${qs}` : '', hash }, { replace: true });
  }, [years, currentYear, minYear, maxYear, seek, search, hash, pathname, navigate]);

  return anim;
}
