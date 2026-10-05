import { describe, expect, it } from 'vitest';
import type { CorrelationEmissionsTemperatureResponse } from '../api/correlationTypes';
import { CONCENTRATION, PAIR, TEMPERATURE } from '../test/climateFixtures';
import { buildClimateSignal } from './climateSignal';
import { buildHeadline } from './headline';

const signal = buildClimateSignal(PAIR, TEMPERATURE, CONCENTRATION)!;
const fossil = (slope: unknown) => ({ ...PAIR, fit: { ...PAIR.fit, slope } }) as unknown as CorrelationEmissionsTemperatureResponse;

describe('buildHeadline', () => {
  it('takes the headline fit from the signal and the fossil-only slope from its own response', () => {
    const h = buildHeadline(signal, fossil(0.797));
    expect(h).toMatchObject({ slope: 0.5196, ciLow: 0.48, ciHigh: 0.559, rSquared: 0.9, start: 1850, end: 2024, nYears: 175, fossilSlope: 0.797 });
  });
  it('has no fossil comparison when that request failed or returned no fit', () => {
    expect(buildHeadline(signal, null).fossilSlope).toBeNull();
    expect(buildHeadline(signal, undefined).fossilSlope).toBeNull();
    expect(buildHeadline(signal, fossil('x')).fossilSlope).toBeNull();
    expect(buildHeadline(signal, { ...PAIR, fit: null }).fossilSlope).toBeNull();
  });
  it('the signal records the years the pair left out', () => {
    expect(signal.omittedYears).toEqual([]);
    const withOmitted = buildClimateSignal({ ...PAIR, omitted_years: [{ year: 1900, reason: 'x' }] }, TEMPERATURE, CONCENTRATION)!;
    expect(withOmitted.omittedYears).toEqual([1900]);
  });
});
