import { useEffect } from 'react';
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
  const { currentYear } = anim;

  useEffect(() => {
    if (!years) return;
    const params = new URLSearchParams(search);
    const want = currentYear === maxYear ? null : String(currentYear);
    if (params.get(PARAM) === want) return;
    if (want === null) params.delete(PARAM);
    else params.set(PARAM, want);
    const qs = params.toString();
    navigate({ pathname, search: qs ? `?${qs}` : '', hash }, { replace: true });
  }, [years, currentYear, maxYear, search, hash, pathname, navigate]);

  return anim;
}
