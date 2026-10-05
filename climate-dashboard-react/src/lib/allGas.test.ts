import { describe, expect, it } from 'vitest';
import type { CorrelationEmissionsTemperatureResponse } from '../api/correlationTypes';
import { ALL_GAS_PAIR, PAIR } from '../test/climateFixtures';
import { buildAllGas } from './allGas';

describe('buildAllGas', () => {
  it('reads the fit, interval, window and stability from the response, with the points in GtCO₂e', () => {
    const a = buildAllGas(ALL_GAS_PAIR)!;
    expect(a).toMatchObject({ slope: 0.5793, ciLow: 0.5327, ciHigh: 0.6259, rSquared: 0.9165, start: 1970, end: 2024, nYears: 55, unit: '°C per 1,000 GtCO2e' });
    expect(a.label).toMatch(/^Recent all-gas relationship/);
    expect(a.points.map((p) => p.gt)).toEqual([900.769, 1500, 2300]);
    expect(a.points.every((p) => p.era === 'y1970plus')).toBe(true);
    expect(a.bootstrap).toEqual({ low: 0.5393, high: 0.619, blockYears: 10 });
    expect(a.stabilitySummary).toMatch(/10-year blocks/);
    expect(a.omittedYears).toEqual([2025]);
    expect(a.line.x0).toBeCloseTo(900.769);
    expect(a.line.y1).toBeGreaterThan(a.line.y0);
  });

  it('is null for anything but the PRIMAP all-gas view with a complete fit', () => {
    expect(buildAllGas(null)).toBeNull();
    expect(buildAllGas(undefined)).toBeNull();
    expect(buildAllGas(PAIR)).toBeNull(); // the long-run CO₂ response is not this view
    expect(buildAllGas({ ...ALL_GAS_PAIR, fit: null } as unknown as CorrelationEmissionsTemperatureResponse)).toBeNull();
    expect(buildAllGas({ ...ALL_GAS_PAIR, fit: { ...ALL_GAS_PAIR.fit, ci95_hac: [] } } as unknown as CorrelationEmissionsTemperatureResponse)).toBeNull();
    expect(buildAllGas({ ...ALL_GAS_PAIR, points: [] })).toBeNull();
  });

  it('is null when any of the fit\'s own metadata is missing (R², unit, label) instead of substituting frontend wording', () => {
    for (const field of ['r_squared', 'unit', 'label']) {
      const fit = { ...ALL_GAS_PAIR.fit } as Record<string, unknown>;
      delete fit[field];
      expect(buildAllGas({ ...ALL_GAS_PAIR, fit } as unknown as CorrelationEmissionsTemperatureResponse), field).toBeNull();
      expect(buildAllGas({ ...ALL_GAS_PAIR, fit: { ...fit, [field]: '' } } as unknown as CorrelationEmissionsTemperatureResponse), `${field} empty`).toBeNull();
    }
  });

  it('tolerates a missing stability block (no bootstrap, no summary)', () => {
    const a = buildAllGas({ ...ALL_GAS_PAIR, fit_context: {} } as unknown as CorrelationEmissionsTemperatureResponse)!;
    expect(a.bootstrap).toBeNull();
    expect(a.stabilitySummary).toBeNull();
  });
});
