import { describe, expect, it } from 'vitest';
import { COUNTRY_SNAPSHOT } from '../test/climateFixtures';
import { shareResponse } from '../test/shareFixtures';
import { buildCountryLines, defaultCountries } from './countryView';

describe('defaultCountries', () => {
  it('starts with the five largest cumulative emitters, in the API\'s ranked order', () => {
    expect(defaultCountries(COUNTRY_SNAPSHOT)).toEqual(['USA', 'CHN', 'RUS', 'DEU', 'GBR']);
    expect(defaultCountries(COUNTRY_SNAPSHOT, 2)).toEqual(['USA', 'CHN']);
    expect(defaultCountries(null)).toEqual([]);
  });
});

describe('buildCountryLines', () => {
  const resp = shareResponse([
    ['USA', 'United States', [[1850, 4, 10], [1851, 4.3, 12]]],
    ['CHN', 'China', [[1850, 1, 1], [1851, 1.1, 1]]],
    ['TWN', 'Taiwan', []],
  ]);
  it('gives one line per country with data, coloured by its place in the selection', () => {
    const l = buildCountryLines(resp)!;
    expect(l.lines.map((x) => x.code)).toEqual(['USA', 'CHN']);
    expect(l.lines[0].points).toEqual([{ year: 1850, share: 4 }, { year: 1851, share: 4.3 }]);
    expect(l.lines[0].color).not.toBe(l.lines[1].color);
    expect(l.cumulativeFrom).toBe(1750);
  });
  it('reports a country with no rows instead of drawing it at zero, and is null with no data at all', () => {
    expect(buildCountryLines(resp)!.missing).toEqual([{ code: 'TWN', name: 'Taiwan' }]);
    expect(buildCountryLines(shareResponse([['TWN', 'Taiwan', []]]))).toBeNull();
    expect(buildCountryLines(null)).toBeNull();
  });
});
