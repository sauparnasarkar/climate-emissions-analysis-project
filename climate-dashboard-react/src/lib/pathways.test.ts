import { describe, expect, it } from 'vitest';
import type { CorrelationScenarioTemperatureResponse } from '../api/correlationTypes';
import { SCENARIO_TEMPERATURE } from '../test/scenarioFixtures';
import { buildPathways } from './pathways';

const withSpread = (spread: unknown) => ({ ...SCENARIO_TEMPERATURE, spread }) as unknown as CorrelationScenarioTemperatureResponse;

describe('buildPathways', () => {
  it('reads the horizon year\'s emissions and implied temperature for the three scenarios, in a fixed order', () => {
    const p = buildPathways(SCENARIO_TEMPERATURE)!;
    expect(p.year).toBe(2040);
    expect(p.cards.map((c) => [c.name, c.emissionsMt, c.levelC])).toEqual([['BAU', 44877, 1.78], ['Moderate', 29000, 1.72], ['Aggressive', 20791, 1.67]]);
    expect(p.cards.map((c) => c.method)).toEqual(['ETS trend, 40 covered countries', '−2% a year from 2025', '−5% a year from 2025']);
  });

  it('writes the one-line reading from the published facts', () => {
    expect(buildPathways(SCENARIO_TEMPERATURE)!.summary).toBe('By 2040 the pathways diverge 2.2× in annual emissions, yet their implied temperatures differ by only 0.11 °C, because 78–83% of the 2040 implied level is warming already observed.');
  });

  it('has no sentence when the API published no facts (the pathways do not diverge enough), but still the cards', () => {
    const p = buildPathways(withSpread({ reading_note_facts: null, reading_note_omitted_reason: 'ratio 1.1 below 1.25' }))!;
    expect(p.summary).toBeNull();
    expect(p.cards).toHaveLength(3);
  });

  it('leaves out the already-observed clause when its range is missing', () => {
    const p = buildPathways(withSpread({ reading_note_facts: { emissions_ratio: 2, gap_end_c: 0.1 } }))!;
    expect(p.summary).toBe('By 2040 the pathways diverge 2.0× in annual emissions, yet their implied temperatures differ by only 0.10 °C.');
  });

  it('is null (the section is omitted) without a response, without rows, or when a scenario lacks its horizon figures', () => {
    expect(buildPathways(null)).toBeNull();
    expect(buildPathways(undefined)).toBeNull();
    expect(buildPathways({ ...SCENARIO_TEMPERATURE, scenarios: {} } as unknown as CorrelationScenarioTemperatureResponse)).toBeNull();
    const broken = { ...SCENARIO_TEMPERATURE, scenarios: { ...SCENARIO_TEMPERATURE.scenarios, Moderate: [{ year: 2040 }] } } as unknown as CorrelationScenarioTemperatureResponse;
    expect(buildPathways(broken)).toBeNull();
  });
});
