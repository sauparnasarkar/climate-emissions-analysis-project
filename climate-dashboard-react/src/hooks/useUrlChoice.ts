import { useCallback, useMemo } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';

/**
 * A single choice kept in one query param (e.g. `?gas=methane`), validated against a fixed list of
 * options so a hand-edited or stale URL can never inject an unknown value into an API call. The same
 * conventions as `useSelectedCountry` (the other single-value URL hook):
 * - absent or unrecognised -> `fallback`
 * - the setter rewrites only this param, uses replace (so tweaking a control does not fill the back
 *   stack), keeps the hash and every other param, and drops the param while the choice equals
 *   `fallback`, so the default view keeps a clean URL.
 * Values are matched exactly (they are identifiers, not display text), but case-insensitively.
 */
export function useUrlChoice(param: string, options: readonly string[], fallback: string): [string, (next: string) => void] {
  const { search, hash, pathname } = useLocation();
  const navigate = useNavigate();

  const value = useMemo(() => {
    const raw = new URLSearchParams(search).get(param)?.trim().toLowerCase();
    return options.find((o) => o.toLowerCase() === raw) ?? fallback;
  }, [search, param, options, fallback]);

  const setValue = useCallback(
    (next: string) => {
      const params = new URLSearchParams(search);
      params.delete(param);
      if (next !== fallback && options.includes(next)) params.set(param, next);
      const qs = params.toString();
      navigate({ pathname, search: qs ? `?${qs}` : '', hash }, { replace: true });
    },
    [search, hash, pathname, param, options, fallback, navigate],
  );

  return [value, setValue];
}
