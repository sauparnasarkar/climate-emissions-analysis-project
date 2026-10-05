import type { CorrelationEmissionsTemperatureResponse } from '../api/correlationTypes';
import type { ClimateSignal } from './climateSignal';

export interface Headline {
  /** °C per 1,000 GtCO₂: total anthropogenic CO₂ (fossil + cement + land-use change), 1850 onward */
  slope: number;
  ciLow: number;
  ciHigh: number;
  rSquared: number | null;
  start: number;
  end: number;
  nYears: number;
  /** The same regression on fossil + cement CO₂ only (the labelled comparison), or null when that request failed */
  fossilSlope: number | null;
}

const num = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);

/** The headline numbers for the module's stat card: the climate signal's fit plus the fossil-only slope from its own request. */
export function buildHeadline(signal: ClimateSignal, fossil: CorrelationEmissionsTemperatureResponse | null | undefined): Headline {
  const { slope, ciLow, ciHigh, rSquared, start, end, nYears } = signal.fit;
  return { slope, ciLow, ciHigh, rSquared, start, end, nYears, fossilSlope: num(fossil?.fit?.slope) };
}
