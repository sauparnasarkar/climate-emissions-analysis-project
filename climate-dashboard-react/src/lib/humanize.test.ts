import { describe, expect, it } from 'vitest';
import { humanize } from './humanize';

describe('humanize', () => {
  it('title-cases snake_case OWID column names', () => {
    expect(humanize('population')).toBe('Population');
    expect(humanize('co2_per_capita')).toBe('CO2 Per Capita');
    expect(humanize('total_ghg')).toBe('Total GHG');
  });

  it('uppercases known acronyms that plain title-casing would mangle', () => {
    expect(humanize('gdp')).toBe('GDP');
    expect(humanize('co2')).toBe('CO2');
    expect(humanize('ghg_intensity')).toBe('GHG Intensity');
  });

  it('leaves already-spaced, mixed-case column names intact', () => {
    // model_comparison.csv's own headers -- not snake_case at all.
    expect(humanize('Baseline MAE')).toBe('Baseline MAE');
    expect(humanize('RF-PC RMSE')).toBe('RF-PC RMSE');
  });

  it('does not uppercase words that merely contain an acronym as a substring', () => {
    expect(humanize('gdppc')).toBe('Gdppc');
  });
});
