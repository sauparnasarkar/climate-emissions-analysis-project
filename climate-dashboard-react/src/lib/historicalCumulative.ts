import type { HistoricalCumulativeResponse } from '../api/types';

// Chart series for the Historical Trends Cumulative and Share-of-world views (SPEC.md §5.28). Pure so the
// Rest-of-world arithmetic and the stacking order are unit-tested without rendering a chart.

export const REST_OF_WORLD = 'Rest of world';
// A fixed neutral (not a theme token): the chart panel is dark in every theme, and this has to read as "everyone else"
// against any categorical series colour.
export const REST_OF_WORLD_COLOR = '#6F8793';

const MT_PER_GT = 1000;

export interface CumulativeChartSeries {
  name: string;
  x: number[];
  y: Array<number | null>;
  kind: 'area' | 'line';
  color?: string;
}

const lastValue = (values: Array<number | null>): number => {
  for (let i = values.length - 1; i >= 0; i--) {
    const v = values[i];
    if (v != null) return v;
  }
  return 0;
};

/**
 * Stacked areas in GtCO₂, largest accumulated total at the bottom (each country keeps its picker-order colour), with a grey Rest of world on top so the full height
 * is the World total. A country with no value in a year (before its record starts) adds nothing to the stack; Rest of
 * world is World minus what is shown, floored at zero, and null where World itself has no value.
 */
export function cumulativeAreaSeries(data: HistoricalCumulativeResponse, palette: readonly string[]): CumulativeChartSeries[] {
  // Colour by picker position (data.series is in request order), the same slot SyChart gives that country in the Annual and
  // Share views, so a country keeps its colour when the view switches even though this view re-orders the stack by size.
  const slot = new Map(data.series.map((s, i) => [s.name, palette[i % palette.length]]));
  const ordered = [...data.series].sort((a, b) => lastValue(b.cumulative_co2) - lastValue(a.cumulative_co2));
  const shown = data.years.map((_, i) => ordered.reduce((sum, s) => sum + (s.cumulative_co2[i] ?? 0), 0));
  const countries = ordered.map((s) => ({
    name: s.name,
    x: data.years,
    y: s.cumulative_co2.map((v) => (v == null ? 0 : v / MT_PER_GT)),
    kind: 'area' as const,
    color: slot.get(s.name),
  }));
  const rest: CumulativeChartSeries = {
    name: REST_OF_WORLD,
    x: data.years,
    y: data.world_cumulative_co2.map((w, i) => (w == null ? null : Math.max(0, w - shown[i]) / MT_PER_GT)),
    kind: 'area',
    color: REST_OF_WORLD_COLOR,
  };
  return [...countries, rest];
}

/** One line per country: its share of the world's cumulative CO₂ (percent), in the picker's order. Rest of world is omitted: it would flatten every other line. */
export function shareLineSeries(data: HistoricalCumulativeResponse): CumulativeChartSeries[] {
  return data.series.map((s) => ({ name: s.name, x: data.years, y: s.share_of_world_cumulative, kind: 'line' as const }));
}
