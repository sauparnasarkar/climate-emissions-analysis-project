import { describe, expect, it } from 'vitest';
import type { CorrelationEmissionsTemperatureResponse } from '../api/correlationTypes';
import { HEADLINE_PAIR, PAIR } from '../test/climateFixtures';
import { buildDerivation } from './derivation';

const without = (...keys: string[]) => {
  const ctx = { ...(HEADLINE_PAIR.fit_context as Record<string, unknown>) };
  keys.forEach((k) => delete ctx[k]);
  return { ...HEADLINE_PAIR, fit_context: ctx } as unknown as CorrelationEmissionsTemperatureResponse;
};

describe('buildDerivation', () => {
  const d = buildDerivation(HEADLINE_PAIR)!;

  it('reads the regression from the fit and the response\'s own descriptions of x and y', () => {
    expect(d.regression).toMatchObject({ start: 1850, end: 2024, n: 175, unit: '°C per 1,000 GtCO2', method: 'OLS with intercept; Newey-West (HAC) standard errors' });
    expect(d.regression.slope).toBeCloseTo(0.51959, 5);
    expect(d.regression.xName).toMatch(/cumulative total anthropogenic CO2 since 1850/);
    expect(d.regression.methodology).toMatch(/analog to the IPCC's TCRE/);
  });

  it('reads the uncertainty: OLS vs HAC error, autocorrelation, the API\'s own lag rule and the bandwidth table', () => {
    expect(d.uncertainty).toMatchObject({ maxlags: 8, lag1: 0.5501525115901242 });
    expect(d.uncertainty!.seHac! > d.uncertainty!.seOls!).toBe(true);
    expect(d.uncertainty!.rule).toBe('maxlags = floor(1.5 * n^(1/3)); Bartlett kernel; 95% CI from the HAC standard error (normal)');
    expect(d.uncertainty!.sensitivity.map((s) => s.maxlags)).toEqual([4, 8, 16]);
  });

  it('reads the land-use scaling and weight scan (with its own note), the bootstrap, block lengths, holdouts and the API\'s stability summary', () => {
    expect(d.sensitivity!.landUseScale.map((s) => s.scale)).toEqual([0.7, 1, 1.3]);
    expect(d.sensitivity!.weightScan!.rows).toHaveLength(2);
    expect(d.sensitivity!.weightScan!.note).toMatch(/not to choose a weight/);
    expect(d.stability!.bootstrap).toMatchObject({ blockYears: 10, low: 0.47284201673187126 });
    expect(d.stability!.blockSensitivity.map((b) => b.blockYears)).toEqual([5, 10]);
    expect(d.stability!.holdouts.map((h) => h.split)).toEqual([1980, 2010]);
    expect(d.stability!.summary).toMatch(/Estimated from later start years \(1850, 1900, 1950, 1970\)/);
    expect(d.stability!.note).toBe('These are published as measured; no pass/fail judgement is made.');
  });

  it('reads the AR6 reference and comparison, and the attribution entries in the API\'s order', () => {
    expect(d.ar6).toMatchObject({ best: 0.45, low: 0.27, high: 0.63, within: true, overlaps: true });
    expect(d.ar6!.ratio).toBeCloseTo(1.1546, 3);
    expect(d.attribution.map((a) => a.series)).toEqual(['owid_world_co2_annual', 'temperature_anomaly_annual']);
    expect(d.attribution[0].citations).toHaveLength(2);
    expect(d.attribution[0].note).toMatch(/Land-use CO2 data originates/);
    expect(d.attribution[1].license).toMatch(/^CC BY-NC 4\.0 International/);
  });

  it('never reads the fit-quality note, whose wording waits for the owner (decision 41)', () => {
    expect(JSON.stringify(d)).not.toMatch(/HELD FOR THE OWNER/);
  });

  it('leaves out a part whose data is missing, instead of showing blanks', () => {
    expect(buildDerivation(without('stability'))!.stability).toBeNull();
    expect(buildDerivation(without('ar6_reference'))!.ar6).toBeNull();
    expect(buildDerivation(without('land_use_sensitivity', 'land_use_weight_scan'))!.sensitivity).toBeNull();
    expect(buildDerivation(without('hac_sensitivity', 'fit'))!.uncertainty).toBeNull();
    const nothing = buildDerivation({ ...HEADLINE_PAIR, attribution: [] })!;
    expect(nothing.attribution).toEqual([]);
  });

  it('skips a holdout without its error and a block length without an interval', () => {
    const ctx = JSON.parse(JSON.stringify(HEADLINE_PAIR.fit_context));
    ctx.stability.holdouts[0] = { split_year: 1980, unavailable: 'needs at least 20 training and 5 test years' };
    delete ctx.stability.block_length_sensitivity[0].ci95;
    const d2 = buildDerivation({ ...HEADLINE_PAIR, fit_context: ctx } as unknown as CorrelationEmissionsTemperatureResponse)!;
    expect(d2.stability!.holdouts.map((h) => h.split)).toEqual([2010]);
    expect(d2.stability!.blockSensitivity.map((b) => b.blockYears)).toEqual([10]);
  });

  it('is null when the fit is incomplete (no label, unit or window)', () => {
    expect(buildDerivation(null)).toBeNull();
    expect(buildDerivation(PAIR)).toBeNull(); // the plain pair fixture has no fit label
    expect(buildDerivation({ ...HEADLINE_PAIR, fit: { ...HEADLINE_PAIR.fit, unit: '' } } as unknown as CorrelationEmissionsTemperatureResponse)).toBeNull();
  });
});
