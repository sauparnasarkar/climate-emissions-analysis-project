import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { buildClimateSignal, latestValue, type ClimateSignal } from '../lib/climateSignal';
import { useAsync } from './useAsync';

export interface ClimateSignalData {
  signal: ClimateSignal | null;
  /** Latest trailing 5-year mean temperature anomaly */
  mean5y: { value: number; year: number } | null;
  /** True once the request has finished (either way) or `waitMs` has passed: a page can wait for it, bounded, before it renders. */
  settled: boolean;
  /** True only once the request has actually finished (answer or failure) -- not on the timeout. A deep link to a section that only exists with the data waits for this. */
  done: boolean;
}

/** The climate-context data the Overview shows beside the emissions figures (Area 2): the headline pair, the latest temperature and
 * concentration, and the 5-year mean. `signal` is null when anything is missing or the request failed, so a page leaves the climate
 * pieces out instead of showing gaps or zeros. A late answer after `waitMs` is still used (the page already has its anchors). */
export function useClimateSignal(waitMs = 3000): ClimateSignalData {
  const query = useAsync(async () => {
    const [pair, temperature, mean5y, concentration] = await Promise.all([
      api.correlationEmissionsTemperature(),
      api.correlationTemperature({ baseline: '1850_1900' }),
      api.correlationTemperature({ view: 'mean5y', baseline: '1850_1900' }),
      api.correlationConcentration(),
    ]);
    const signal = buildClimateSignal(pair, temperature, concentration);
    return signal ? { signal, mean5y: latestValue(mean5y.points) } : null;
  }, []);
  const [timedOut, setTimedOut] = useState(false);
  useEffect(() => {
    if (!query.loading) return;
    const id = setTimeout(() => setTimedOut(true), waitMs);
    return () => clearTimeout(id);
  }, [query.loading, waitMs]);
  return { signal: query.data?.signal ?? null, mean5y: query.data?.mean5y ?? null, settled: !query.loading || timedOut, done: !query.loading };
}
