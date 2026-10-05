import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import type { CorrelationEmissionsTemperatureResponse } from '../api/correlationTypes';
import { buildClimateSignal, latestValue, spliceInfo, yearValues, type ClimateSignal, type SpliceInfo, type YearValue } from '../lib/climateSignal';
import { useAsync } from './useAsync';

export interface ClimateSignalData {
  signal: ClimateSignal | null;
  /** Latest trailing 5-year mean temperature anomaly */
  mean5y: { value: number; year: number } | null;
  /** The annual and trailing-5-year-mean temperature anomaly series (nulls dropped), available on their own even when `signal` is null */
  temperatureSeries: YearValue[];
  mean5ySeries: YearValue[];
  /** The concentration record's documented splice, available on its own even when `signal` is null */
  splice: SpliceInfo | null;
  /** The headline pair response itself (its fit and fit_context), available on its own even when `signal` is null */
  headline: CorrelationEmissionsTemperatureResponse | null;
  /** True once the request has finished (either way) or `waitMs` has passed: a page can wait for it, bounded, before it renders. */
  settled: boolean;
  /** True only once the request has actually finished (answer or failure) -- not on the timeout. A deep link to a section that only exists with the data waits for this. */
  done: boolean;
}

/** The climate-context data the pages show beside the emissions figures (Area 2): the headline pair, the latest temperature and concentration, and the
 * 5-year mean. `signal` is null when the pair, the temperature or the concentration is missing, so a page leaves the climate pieces out instead of showing
 * gaps or zeros. A late answer after `waitMs` is still used (the page already has its anchors).
 *
 * The four requests are independent: the annual and 5-year-mean temperature series are exposed on their own, so a page that wants only those (the
 * correlation module's country view) reuses these answers instead of asking again, and still has them when the signal as a whole is unavailable. */
export function useClimateSignal(waitMs = 3000): ClimateSignalData {
  const pair = useAsync(async () => api.correlationEmissionsTemperature(), []);
  const temperature = useAsync(async () => api.correlationTemperature({ baseline: '1850_1900' }), []);
  // Optional: only the 5-year-mean figure uses it, so its failure must not take the signal (and every page built on it) down.
  const mean5y = useAsync(async () => api.correlationTemperature({ view: 'mean5y', baseline: '1850_1900' }), []);
  const concentration = useAsync(async () => api.correlationConcentration(), []);

  const signal = useMemo(
    () => (pair.data && temperature.data && concentration.data ? buildClimateSignal(pair.data, temperature.data, concentration.data) : null),
    [pair.data, temperature.data, concentration.data],
  );
  const temperatureSeries = useMemo(() => (temperature.data ? yearValues(temperature.data.points) : []), [temperature.data]);
  const mean5ySeries = useMemo(() => (mean5y.data ? yearValues(mean5y.data.points) : []), [mean5y.data]);
  const mean5yLatest = useMemo(() => (mean5y.data ? latestValue(mean5y.data.points) : null), [mean5y.data]);

  const splice = useMemo(() => spliceInfo(concentration.data?.details?.splice), [concentration.data]);

  const loading = pair.loading || temperature.loading || mean5y.loading || concentration.loading;
  const [timedOut, setTimedOut] = useState(false);
  useEffect(() => {
    if (!loading) return;
    const id = setTimeout(() => setTimedOut(true), waitMs);
    return () => clearTimeout(id);
  }, [loading, waitMs]);
  return { signal, mean5y: signal ? mean5yLatest : null, temperatureSeries, mean5ySeries, splice, headline: pair.data ?? null, settled: !loading || timedOut, done: !loading };
}
