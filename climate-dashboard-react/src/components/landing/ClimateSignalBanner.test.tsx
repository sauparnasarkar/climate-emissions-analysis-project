import { describe, expect, it } from 'vitest';
import { CLIMATE_BANNER_STYLES } from './ClimateSignalBanner';

describe('ClimateSignalBanner phone layout (decision 72)', () => {
  it('puts the chart before the buttons on a phone, shows two figure cards and drops the Forecasts link there', () => {
    expect(CLIMATE_BANNER_STYLES).toMatch(/@media \(max-width: 640px\)/);
    expect(CLIMATE_BANNER_STYLES).toMatch(/\.climate-banner__text \{ display: contents !important; \}/);
    expect(CLIMATE_BANNER_STYLES).toMatch(/\.climate-banner__chart \{ order: 5;/);
    expect(CLIMATE_BANNER_STYLES).toMatch(/\.climate-banner__ctas \{ order: 6; \}/);
    expect(CLIMATE_BANNER_STYLES).toMatch(/\.climate-banner__metrics > div:nth-child\(3\) \{ display: none; \}/);
    expect(CLIMATE_BANNER_STYLES).toMatch(/\.climate-banner__forecasts \{ display: none; \}/);
  });
});
