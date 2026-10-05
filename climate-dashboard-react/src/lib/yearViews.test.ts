import { describe, expect, it } from 'vitest';
import type { WorldMapTimeSeries } from '../api/types';
import { countryValuesForYear, moversForYear } from './yearViews';

// 1989..2000 so the 1990 baseline is inside the series
const years = Array.from({ length: 12 }, (_, i) => 1989 + i);
const SERIES: WorldMapTimeSeries = {
  iso_codes: ['CHN', 'USA', 'DEU', 'SSD'],
  countries: ['China', 'United States', 'Germany', 'South Sudan'],
  years,
  // China doubles 1990 -> 2000, USA +10 %, Germany -20 %, South Sudan has no value before 1995
  values: years.map((y) => [y === 1990 ? 2000 : 2000 + (y - 1990) * 200, 5000 * (y === 1990 ? 1 : 1 + (y - 1990) * 0.01), y === 1990 ? 1000 : 1000 - (y - 1990) * 20, y >= 1995 ? 4 : null]),
  value_range: [0, 5500],
};

describe('countryValuesForYear', () => {
  it('lists the selected countries\' CO₂ for the year, largest first, leaving out those with no value', () => {
    expect(countryValuesForYear(SERIES, ['Germany', 'China', 'South Sudan'], 1992)).toEqual([
      { country: 'China', value: 2400 },
      { country: 'Germany', value: 960 },
    ]);
    expect(countryValuesForYear(SERIES, ['South Sudan'], 1996)).toEqual([{ country: 'South Sudan', value: 4 }]);
  });
  it('ignores countries that are not selected or not in the series, and a year outside it', () => {
    expect(countryValuesForYear(SERIES, ['Atlantis'], 1992)).toEqual([]);
    expect(countryValuesForYear(SERIES, ['China'], 1850)).toEqual([]);
  });
});

describe('moversForYear', () => {
  it('measures each country from 1990 to the year, biggest growth first', () => {
    const m = moversForYear(SERIES, ['China', 'United States', 'Germany'], 2000)!;
    expect(m.map((r) => r.country)).toEqual(['China', 'United States', 'Germany']);
    expect(m[0]).toMatchObject({ co2Base: 2000, co2Year: 4000, absoluteChange: 2000, pctChange: 100 });
    expect(m[1].pctChange).toBeCloseTo(10);
    expect(m[2]).toMatchObject({ co2Base: 1000, co2Year: 800, absoluteChange: -200, pctChange: -20 });
  });
  it('is null for years up to the 1990 baseline, where there is nothing to measure', () => {
    expect(moversForYear(SERIES, ['China'], 1990)).toBeNull();
    expect(moversForYear(SERIES, ['China'], 1989)).toBeNull();
  });
  it('is null when the series does not reach back to the baseline', () => {
    expect(moversForYear({ ...SERIES, years: years.slice(3), values: SERIES.values.slice(3) }, ['China'], 2000)).toBeNull();
  });
  it('leaves out a country with no value in the year or no baseline, as the API does', () => {
    expect(moversForYear(SERIES, ['China', 'South Sudan'], 1994)!.map((r) => r.country)).toEqual(['China']); // South Sudan had no 1990 value
    expect(moversForYear(SERIES, ['South Sudan'], 2000)).toEqual([]);
  });
  it('moving the year changes the measurement and the order can change with it', () => {
    expect(moversForYear(SERIES, ['China', 'Germany'], 1992)![0]).toMatchObject({ country: 'China', pctChange: 20 });
  });
});
