import type { CorrelationCountryShareResponse } from '../api/correlationTypes';

type P = [year: number, stock: number, flow: number | null];
export const shareResponse = (series: Array<[code: string, name: string, points: P[]]>): CorrelationCountryShareResponse =>
  ({
    schema_version: 1, generated_at: null, note: '', caveats: [], attribution: [], source_vintage: null, name: 'n', method: 'm', source: 'owid_co2', gas_scope: 'co2',
    label: 'OWID fossil + cement CO2', unit: 'Mt CO2', mode: 'series', year: null, limit: null, start_year: Math.min(...series.flatMap(([, , points]) => points.map(([year]) => year)), 9999), end_year: 2024, coverage: [1850, 2024], cumulative_from: 1750,
    total_cumulative_mt: null, annual_total_mt: null, rows: [], denominator: null, reconciliation: null, details: {}, notes: [],
    series: series.map(([country, name, points]) => ({ country, name, points: points.map(([year, share_pct, annual_share_pct]) => ({ year, cumulative_mt: 1, share_pct, annual_mt: null, annual_share_pct })) })),
  }) as CorrelationCountryShareResponse;
