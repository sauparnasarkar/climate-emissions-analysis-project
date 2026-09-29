import type { MoverRow, WorldMapTimeSeries } from '../api/types';
import { pickHeadlineFacts } from './overviewHeadline';

/** Thousands-separated integer, e.g. 12,289. */
export function fmtInt(n: number): string {
  return Math.round(n).toLocaleString('en-US');
}

/** Signed one-decimal percent with a true minus sign, e.g. +452.5% / −45.7%. */
export function fmtPct(n: number): string {
  return `${n >= 0 ? '+' : '−'}${Math.abs(n).toFixed(1)}%`;
}

/** Signed integer with a true minus sign, e.g. +9,806. */
export function fmtSigned(n: number): string {
  return `${n >= 0 ? '+' : '−'}${fmtInt(Math.abs(n))}`;
}

export type StoryKind = 'largest-rise' | 'fastest-growth' | 'steepest-decline';

export interface Story {
  kind: StoryKind;
  country: string;
  /** The headline figure, pre-formatted (e.g. "+9,806" MtCO₂, "+452.5%", "−45.7%"). */
  headline: string;
  /** Direction of the change, for colouring (a decline is the favourable one). */
  sentiment: 'increase' | 'decrease';
  /** Emissions at the first/last year, when the API has them. */
  from: number | null;
  to: number | null;
  /** Per-year series (aligned to WorldMapTimeSeries.years; null = no data that year). */
  series: Array<number | null>;
}

/**
 * The landing page's "stories": who added the most, who grew fastest, who cut the most, among the
 * headline movers. Uses the *same* selection rules as the Overview's headline sentence
 * (`pickHeadlineFacts`), so the two can never name different countries for the same claim. A card
 * is omitted when its claim isn't true of the data (no rise / no decline at all).
 */
export function pickStories(headlineMovers: MoverRow[], map: WorldMapTimeSeries): Story[] {
  const facts = pickHeadlineFacts(headlineMovers);
  if (!facts) return [];
  const byCountry = new Map(headlineMovers.map((m) => [m.country, m]));
  const seriesOf = (country: string): Array<number | null> => {
    const k = map.countries.indexOf(country);
    return k < 0 ? [] : map.years.map((_, i) => map.values[i]?.[k] ?? null);
  };
  const make = (kind: StoryKind, country: string, headline: string, sentiment: Story['sentiment']): Story => {
    const m = byCountry.get(country);
    return { kind, country, headline, sentiment, from: m?.co2_1990 ?? null, to: m?.co2_latest ?? null, series: seriesOf(country) };
  };

  const stories: Story[] = [];
  if (facts.absGrower.absoluteChange > 0) {
    stories.push(make('largest-rise', facts.absGrower.country, fmtSigned(facts.absGrower.absoluteChange), 'increase'));
  }
  if (facts.pctGrower.pctChange > 0) {
    stories.push(make('fastest-growth', facts.pctGrower.country, fmtPct(facts.pctGrower.pctChange), 'increase'));
  }
  const steepest = facts.decliners[0];
  if (steepest) stories.push(make('steepest-decline', steepest.country, fmtPct(steepest.pctChange), 'decrease'));
  return stories;
}

/** SVG path for a sparkline in a `width`×`height` box. Null points break the line; a flat series draws mid-height. */
export function sparklinePath(values: Array<number | null>, width = 300, height = 64, pad = 4): string {
  const present = values.filter((v): v is number => v != null);
  if (present.length < 2) return '';
  const lo = Math.min(...present);
  const hi = Math.max(...present);
  const span = hi - lo;
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  let pen = false;
  return values
    .map((v, i) => {
      if (v == null) { pen = false; return ''; }
      const y = span === 0 ? height / 2 : height - pad - ((v - lo) / span) * (height - 2 * pad);
      const cmd = pen ? 'L' : 'M';
      pen = true;
      return `${cmd}${(i * step).toFixed(1)},${y.toFixed(1)}`;
    })
    .filter(Boolean)
    .join(' ');
}

export const RACE_SIZE = 10;

export interface RaceModel {
  years: number[];
  /** Every country that is in the top RACE_SIZE in *any* year, sorted by name -- a stable row set so a
   * country keeps its DOM node (and can animate) as its rank changes. */
  countries: string[];
  /** values[yearIdx][countryIdx]; missing data counts as 0. */
  values: number[][];
  /** Largest value anywhere in the race -- the fixed bar scale. */
  maxValue: number;
}

export function buildRaceModel(map: WorldMapTimeSeries): RaceModel {
  const set = new Set<string>();
  map.years.forEach((_, i) => {
    map.countries
      .map((c, k) => [c, map.values[i]?.[k] ?? 0] as const)
      .sort((a, b) => b[1] - a[1])
      .slice(0, RACE_SIZE)
      .forEach(([c]) => set.add(c));
  });
  const countries = Array.from(set).sort();
  const idx = countries.map((c) => map.countries.indexOf(c));
  const values = map.years.map((_, i) => idx.map((k) => map.values[i]?.[k] ?? 0));
  const maxValue = Math.max(0, ...values.flat());
  return { years: map.years, countries, values, maxValue };
}

export interface RaceRow {
  country: string;
  value: number;
  /** 0-based rank among the race's countries this year. */
  rank: number;
  /** Whether the row is in this year's top RACE_SIZE (others are parked off-screen). */
  inTop: boolean;
}

export interface RaceFrame {
  year: number;
  /** In the model's stable country order (not rank order). */
  rows: RaceRow[];
  /** Sum of this year's top RACE_SIZE. */
  topTotal: number;
}

export function raceFrame(model: RaceModel, yearIdx: number): RaceFrame {
  const i = Math.max(0, Math.min(model.years.length - 1, yearIdx));
  const vals = model.values[i] ?? [];
  const order = vals.map((v, k) => [v, k] as const).sort((a, b) => b[0] - a[0]);
  const rankOf = new Map(order.map(([, k], r) => [k, r]));
  const rows = model.countries.map((country, k) => {
    const rank = rankOf.get(k) ?? model.countries.length;
    return { country, value: vals[k] ?? 0, rank, inTop: rank < RACE_SIZE };
  });
  const topTotal = rows.filter((r) => r.inTop).reduce((s, r) => s + r.value, 0);
  return { year: model.years[i], rows, topTotal };
}

/** The top RACE_SIZE's share of the year's world total, as a whole percent; null if the total is unusable. */
export function raceShare(topTotal: number, worldTotal: number | undefined): number | null {
  return worldTotal && worldTotal > 0 ? Math.round((topTotal / worldTotal) * 100) : null;
}
