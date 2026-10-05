import { describe, expect, it } from 'vitest';
import type { CorrelationGhgCompositionResponse } from '../api/correlationTypes';
import { COMPOSITION } from '../test/climateFixtures';
import { buildComposition } from './gasComposition';

describe('buildComposition', () => {
  it('builds per-gas series in MtCO₂e and per-year shares, with a fixed colour per gas', () => {
    const c = buildComposition(COMPOSITION)!;
    expect(c.years).toEqual([1970, 2000, 2024]);
    expect(c.gases.map((g) => [g.id, g.short])).toEqual([['co2', 'CO₂'], ['ch4', 'CH₄'], ['n2o', 'N₂O'], ['fgas', 'F-gas']]);
    expect(new Set(c.gases.map((g) => g.color)).size).toBe(4);
    expect(c.mt[0]).toEqual([15000, 26000, 37974]);
    expect(c.shares[2][0]).toBeCloseTo(75.08, 1);
    c.shares.forEach((row) => expect(row.reduce((a, b) => a + b, 0)).toBeCloseTo(100, 6));
    expect(c.excludedIncompleteYears).toEqual([2025]);
    expect(c.basis).toMatch(/AR5 100-year/);
  });

  it('carries the API\'s reconciliation of the gas sum against PRIMAP-hist\'s own national total, per year and overall', () => {
    const c = buildComposition(COMPOSITION)!;
    expect(c.residualPct).toEqual([0.052, 0.052, 0.052]);
    expect(c.reconciliation).toEqual({ maxAbsResidualPct: 0.213, tolerancePct: 1 });
    expect(buildComposition({ ...COMPOSITION, reconciliation: null })!.reconciliation).toBeNull();
  });

  it('keeps only the caveats that belong beside the chart, leaving licences and sources to the methodology', () => {
    const c = buildComposition(COMPOSITION)!;
    expect(c.caveats).toHaveLength(2); // the trailing-year exclusion is stated from excluded_incomplete_years, not repeated here
    expect(c.caveats.join(' ')).not.toMatch(/licence|composite|Trailing years/i);
  });

  it('skips a year in which any gas lacks a value instead of filling zero, and is null with fewer than two usable years', () => {
    const broken = JSON.parse(JSON.stringify(COMPOSITION)) as CorrelationGhgCompositionResponse;
    broken.years[1].values[1].mtco2e = null;
    expect(buildComposition(broken)!.years).toEqual([1970, 2024]);
    broken.years[2].values[0].share_pct = null;
    expect(buildComposition(broken)).toBeNull();
    expect(buildComposition(null)).toBeNull();
    expect(buildComposition({ ...COMPOSITION, gases: [] })).toBeNull();
  });
});
