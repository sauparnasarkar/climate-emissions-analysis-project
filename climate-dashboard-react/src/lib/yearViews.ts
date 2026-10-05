import { BASELINE_YEAR } from '../constants';
import type { WorldMapTimeSeries } from '../api/types';

// By Country, Top Movers and % Change for any page year, computed from the columnar series the map already holds (every country's annual CO₂
// from 1970) instead of one API request per year (ENHANCEMENTS.md decision 64). The definitions are the API's /overview ones: the bar is each
// selected country's CO₂ in the year, largest first; a mover's change is measured from the 1990 baseline, in absolute Mt and in %.

export interface CountryValue {
  country: string;
  value: number;
}

export interface Mover {
  country: string;
  co2Base: number;
  co2Year: number;
  absoluteChange: number;
  pctChange: number;
}

function column(series: WorldMapTimeSeries, names: string[], year: number): Array<{ country: string; value: number | null }> | null {
  const row = series.years.indexOf(year);
  if (row < 0) return null;
  const wanted = new Set(names);
  return series.countries.flatMap((country, i) => (wanted.has(country) ? [{ country, value: series.values[row][i] ?? null }] : []));
}

/** The selected countries' CO₂ (Mt) in `year`, largest first; countries with no value that year are left out. Empty if the year is outside the series. */
export function countryValuesForYear(series: WorldMapTimeSeries, names: string[], year: number): CountryValue[] {
  return (column(series, names, year) ?? [])
    .filter((c): c is CountryValue => c.value !== null)
    .sort((a, b) => b.value - a.value);
}

/** Each selected country's change from the baseline year to `year`, biggest growth first. Null when there is nothing to measure: the year is not
 * after the baseline (the baseline is 1990 -- years up to it grey the section out) or either year is outside the series. Countries lacking a value or a
 * non-zero baseline in either year are left out, as the API drops them. */
export function moversForYear(series: WorldMapTimeSeries, names: string[], year: number, baseYear: number = BASELINE_YEAR): Mover[] | null {
  if (year <= baseYear) return null;
  const base = column(series, names, baseYear);
  const now = column(series, names, year);
  if (!base || !now) return null;
  const baseBy = new Map(base.map((c) => [c.country, c.value]));
  return now
    .flatMap(({ country, value }) => {
      const b = baseBy.get(country);
      if (value === null || b == null || b === 0) return [];
      const absoluteChange = value - b;
      return [{ country, co2Base: b, co2Year: value, absoluteChange, pctChange: (absoluteChange / b) * 100 }];
    })
    .sort((a, b) => b.pctChange - a.pctChange);
}
