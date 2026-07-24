import { api } from '../api/client';
import { useAsync } from './useAsync';

/** {featured, expanded} — used by every page with a country picker, so pickers can search
 * the full ~40-country expanded set while still defaulting to the 10 curated countries. */
export function useCountries() {
  return useAsync(() => api.listCountries(), []);
}
