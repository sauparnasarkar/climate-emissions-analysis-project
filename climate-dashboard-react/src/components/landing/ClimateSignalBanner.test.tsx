import { describe, expect, it } from 'vitest';
import { CLIMATE_BANNER_STYLES } from './ClimateSignalBanner';

describe('ClimateSignalBanner phone layout (decision 72)', () => {
  it('shows two figure cards and drops the Forecasts link there', () => {
    expect(CLIMATE_BANNER_STYLES).toMatch(/@media \(max-width: 640px\)/);
    expect(CLIMATE_BANNER_STYLES).not.toMatch(/display: contents|order: [56]/); // order is in the markup, not painted over it
    expect(CLIMATE_BANNER_STYLES).toMatch(/\.climate-banner__metrics > div:nth-child\(3\) \{ display: none; \}/);
    expect(CLIMATE_BANNER_STYLES).toMatch(/\.climate-banner__forecasts \{ display: none; \}/);
  });
});
