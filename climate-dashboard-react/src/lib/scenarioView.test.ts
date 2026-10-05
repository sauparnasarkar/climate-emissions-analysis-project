import { describe, expect, it } from 'vitest';
import type { CorrelationEmissionsTemperatureResponse, CorrelationScenarioTemperatureResponse } from '../api/correlationTypes';
import { PAIR } from '../test/climateFixtures';
import { SCENARIO_TEMPERATURE } from '../test/scenarioFixtures';
import { buildScenarioView } from './scenarioView';

// fossil cumulative with steps of 36,000 then 38,598.5 Mt: annual = the step
const years = Array.from({ length: 12 }, (_, i) => 2013 + i);
const FOSSIL = { ...PAIR, points: years.reduce<Array<{ year: number; cumulative_emissions: number; temperature: number }>>((acc, year, i) => [...acc, { year, cumulative_emissions: (acc[i - 1]?.cumulative_emissions ?? 1_700_000) + (year === 2024 ? 38598.5 : 36000), temperature: 1 }], []) } as unknown as CorrelationEmissionsTemperatureResponse;
const TEMP = years.map((year) => ({ year, value: 1 + (year - 2013) * 0.05 }));
const MEAN = years.slice(4).map((year) => ({ year, value: 1.2 + (year - 2017) * 0.02 }));

describe('buildScenarioView', () => {
  const v = buildScenarioView(SCENARIO_TEMPERATURE, FOSSIL, TEMP, MEAN)!;

  it('takes the pathways\' emissions (Gt) and implied temperature from the response, in a fixed scenario order', () => {
    expect(v.pathways.map((p) => p.name)).toEqual(['BAU', 'Moderate', 'Aggressive']);
    expect(v.pathways[0].emissions).toHaveLength(16); // a value for every year 2025..2040
    expect(v.pathways[0].emissions[0]).toEqual({ year: 2025, value: 38.953 });
    expect(v.pathways[0].emissions.at(-1)).toEqual({ year: 2040, value: 44.877 });
    expect(v.pathways[2].temperature.at(-1)).toEqual({ year: 2040, value: 1.67 });
    expect([v.startYear, v.lastObservedYear, v.horizon]).toEqual([2025, 2024, 2040]);
  });

  it('builds observed annual emissions as the step of the cumulative World series, for the decade up to the last observed year, in Gt', () => {
    expect(v.observedEmissions.map((p) => p.year)).toEqual([2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]);
    expect(v.observedEmissions[0].value).toBeCloseTo(36);
    expect(v.observedEmissions.at(-1)!.value).toBeCloseTo(38.5985);
  });

  it('limits the observed temperature to the same decade and carries the anchor the pathways start from', () => {
    expect(v.observedTemperature[0].year).toBe(2015);
    expect(v.observedMean5y[0].year).toBe(2017);
    expect(v.anchor).toEqual({ year: 2024, value: 1.3902 });
  });

  it('measures the gap between the highest and lowest implied temperature in the horizon year', () => {
    expect(v.horizonGapC).toBeCloseTo(0.11, 6); // 1.78 - 1.67
    const one = { ...SCENARIO_TEMPERATURE, scenarios: { BAU: SCENARIO_TEMPERATURE.scenarios.BAU } } as unknown as CorrelationScenarioTemperatureResponse;
    expect(buildScenarioView(one, FOSSIL, TEMP, MEAN)).toBeNull(); // a scenario set short of three is not a usable comparison
  });

  it('passes the API\'s reading note and prescribed labels through verbatim', () => {
    expect(v.readingNote).toBe(SCENARIO_TEMPERATURE.reading_note);
    expect(v.labels).toContain('Illustrative analytical translations, not formal climate-model projections');
    expect(v.labels).toHaveLength(4);
  });

  it('states the assumptions from the response (slope, rest-of-world share, land use)', () => {
    expect(v.assumptions.slope).toBeCloseTo(0.5196);
    expect(v.assumptions.slopeUnit).toBe('°C per 1,000 GtCO2');
    expect(v.assumptions.restOfWorldPct).toBeCloseTo(10.68, 1);
    expect(v.assumptions.restOfWorldYear).toBe(2024);
    expect(v.assumptions.landUseGt).toBeCloseTo(4.658);
    expect(v.assumptions.landUseWindow).toEqual([2020, 2024]);
  });

  it('has no reading note when the API published none, and leaves missing observed history empty rather than zero', () => {
    const quiet = buildScenarioView({ ...SCENARIO_TEMPERATURE, reading_note: null } as unknown as CorrelationScenarioTemperatureResponse, null, [], [])!;
    expect(quiet.readingNote).toBeNull();
    expect(quiet.observedEmissions).toEqual([]);
    expect(quiet.observedTemperature).toEqual([]);
    expect(quiet.pathways).toHaveLength(3);
  });

  it('skips a year the cumulative series does not follow consecutively instead of inventing a step', () => {
    const gap = { ...FOSSIL, points: FOSSIL.points.filter((p) => p.year !== 2020) } as unknown as CorrelationEmissionsTemperatureResponse;
    const years2 = buildScenarioView(SCENARIO_TEMPERATURE, gap, [], [])!.observedEmissions.map((p) => p.year);
    expect(years2).not.toContain(2020);
    expect(years2).not.toContain(2021); // its step would span two years
  });

  it('is null when any pathway does not cover every year from its start to the horizon, in emissions and in temperature', () => {
    const rows = SCENARIO_TEMPERATURE.scenarios as unknown as Record<string, Array<Record<string, unknown>>>;
    const make = (mut: (s: Record<string, Array<Record<string, unknown>>>) => void) => {
      const s = JSON.parse(JSON.stringify(rows)) as Record<string, Array<Record<string, unknown>>>;
      mut(s);
      return { ...SCENARIO_TEMPERATURE, scenarios: s } as unknown as CorrelationScenarioTemperatureResponse;
    };
    // only the horizon row for every scenario: three single dots, not pathways
    expect(buildScenarioView(make((s) => { for (const k of Object.keys(s)) s[k] = s[k].filter((r) => r.year === 2040); }), FOSSIL, TEMP, MEAN)).toBeNull();
    // a missing intermediate year: the line would be drawn straight across it
    expect(buildScenarioView(make((s) => { s.BAU = s.BAU.filter((r) => r.year !== 2031); }), FOSSIL, TEMP, MEAN)).toBeNull();
    expect(buildScenarioView(make((s) => { s.Moderate[5].headline = {}; }), FOSSIL, TEMP, MEAN)).toBeNull();
    // one scenario lacks its start-year row
    expect(buildScenarioView(make((s) => { s.Moderate = s.Moderate.filter((r) => r.year !== 2025); }), FOSSIL, TEMP, MEAN)).toBeNull();
    // one scenario's start row has no emissions value; another's has no implied level
    expect(buildScenarioView(make((s) => { delete s.BAU[0].global_fossil_mt; }), FOSSIL, TEMP, MEAN)).toBeNull();
    expect(buildScenarioView(make((s) => { s.Aggressive[0].headline = {}; }), FOSSIL, TEMP, MEAN)).toBeNull();
    expect(buildScenarioView(SCENARIO_TEMPERATURE, FOSSIL, TEMP, MEAN)).not.toBeNull(); // the complete output is unaffected
  });

  it('is null when the scenario output is unusable', () => {
    expect(buildScenarioView(null, FOSSIL, TEMP, MEAN)).toBeNull();
    expect(buildScenarioView({ ...SCENARIO_TEMPERATURE, scenarios: {} } as unknown as CorrelationScenarioTemperatureResponse, FOSSIL, TEMP, MEAN)).toBeNull();
  });
});
