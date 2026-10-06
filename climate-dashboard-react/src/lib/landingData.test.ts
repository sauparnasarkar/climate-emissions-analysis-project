import { describe, expect, it } from 'vitest';
import type { MoverRow, WorldMapTimeSeries } from '../api/types';
import { buildHeadlineSentence, headlineSegmentsToText } from './overviewHeadline';
import { buildRaceModel, fmtInt, fmtPct, fmtSigned, growthPhrase, latestTopShare, pickStories, raceFrame, raceShare, sparklinePath } from './landingData';

const mover = (country: string, from: number | null, to: number | null): MoverRow => ({
  country,
  co2_1990: from,
  co2_latest: to,
  absolute_change: from != null && to != null ? to - from : null,
  pct_change: from != null && to != null && from ? ((to - from) / from) * 100 : null,
});

const MAP: WorldMapTimeSeries = {
  iso_codes: ['AAA', 'BBB', 'CCC', 'DDD'],
  countries: ['Alpha', 'Beta', 'Gamma', 'Delta'],
  years: [1990, 1991, 1992],
  // Beta overtakes Alpha in 1992; Delta only enters the top 2 in 1990; Gamma has a gap in 1991.
  values: [
    [100, 50, 10, 90],
    [100, 80, null, 20],
    [100, 300, 12, 15],
  ],
  value_range: [1, 300],
};

describe('formatters', () => {
  it('uses true minus signs and grouped integers', () => {
    expect(fmtInt(12289.4)).toBe('12,289');
    expect(fmtPct(452.52)).toBe('+452.5%');
    expect(fmtPct(-45.74)).toBe('−45.7%');
    expect(fmtSigned(9806)).toBe('+9,806');
    expect(fmtSigned(-289)).toBe('−289');
  });
});

describe('pickStories', () => {
  const movers = [mover('Alpha', 100, 100), mover('Beta', 50, 300), mover('Gamma', 10, 12), mover('Delta', 90, 15)];

  it('picks largest rise, fastest growth and steepest decline with their figures and series', () => {
    const stories = pickStories(movers, MAP);
    expect(stories.map((s) => [s.kind, s.country])).toEqual([
      ['largest-rise', 'Beta'],
      ['fastest-growth', 'Beta'],
      ['steepest-decline', 'Delta'],
    ]);
    expect(stories[0].headline).toBe('+250');
    expect(stories[1].headline).toBe('+500.0%');
    expect(stories[2].headline).toBe('−83.3%');
    expect(stories[0]).toMatchObject({ from: 50, to: 300, sentiment: 'increase' });
    expect(stories[2].sentiment).toBe('decrease');
    expect(stories[1].series).toEqual([50, 80, 300]);
    expect(stories[2].series).toEqual([90, 20, 15]);
  });

  it('names the same countries as the Overview headline sentence (shared selection rules)', () => {
    const sentence = headlineSegmentsToText(buildHeadlineSentence(movers, 'x')!);
    const stories = pickStories(movers, MAP);
    for (const s of stories) expect(sentence).toContain(s.country);
  });

  it('omits the decline card when nothing declined, and any rise card when nothing rose', () => {
    expect(pickStories([mover('A', 10, 20), mover('B', 10, 15)], MAP).map((s) => s.kind)).toEqual(['largest-rise', 'fastest-growth']);
    expect(pickStories([mover('A', 20, 10), mover('B', 30, 15)], MAP).map((s) => s.kind)).toEqual(['steepest-decline']);
  });

  it('ignores rows with null figures and returns [] when none are usable', () => {
    expect(pickStories([mover('A', null, null)], MAP)).toEqual([]);
    expect(pickStories([mover('A', null, 5), mover('B', 10, 5)], MAP).map((s) => s.country)).toEqual(['B']);
  });

  it('tolerates a country missing from the map series (empty series, no crash)', () => {
    expect(pickStories([mover('Nowhere', 10, 20)], MAP)[0].series).toEqual([]);
  });
});

describe('sparklinePath', () => {
  it('scales to the box, first point at x=0 and last at x=width', () => {
    const p = sparklinePath([0, 10], 300, 64, 4);
    expect(p).toBe('M0.0,60.0 L300.0,4.0');
  });
  it('breaks the line at nulls, draws flat series mid-height, and yields nothing for < 2 points', () => {
    expect(sparklinePath([1, null, 3], 100, 50, 0)).toBe('M0.0,50.0 M100.0,0.0');
    expect(sparklinePath([5, 5, 5], 100, 40)).toBe('M0.0,20.0 L50.0,20.0 L100.0,20.0');
    expect(sparklinePath([1], 100, 40)).toBe('');
    expect(sparklinePath([null, null])).toBe('');
  });
});

describe('race', () => {
  const model = buildRaceModel(MAP);

  it('keeps a stable, name-sorted row set of every country that was ever in the top 10', () => {
    expect(model.countries).toEqual(['Alpha', 'Beta', 'Delta', 'Gamma']);
    expect(model.maxValue).toBe(300);
    expect(model.values[1]).toEqual([100, 80, 20, 0]); // Gamma's gap counts as 0
  });

  it('ranks per year, so the ordering really changes between frames', () => {
    const rank = (yearIdx: number) => Object.fromEntries(raceFrame(model, yearIdx).rows.map((r) => [r.country, r.rank]));
    expect(rank(0)).toMatchObject({ Alpha: 0, Delta: 1, Beta: 2, Gamma: 3 });
    expect(rank(2)).toMatchObject({ Beta: 0, Alpha: 1, Delta: 2, Gamma: 3 });
  });

  it('marks only the top RACE_SIZE as visible and sums them; clamps out-of-range years', () => {
    const f = raceFrame(model, 99);
    expect(f.year).toBe(1992);
    expect(f.rows.every((r) => r.inTop)).toBe(true); // 4 countries < 10
    expect(f.topTotal).toBe(300 + 100 + 12 + 15);
  });

  it('computes the share of the world total, null when the total is unusable', () => {
    expect(raceShare(71, 100)).toBe(71);
    expect(raceShare(50, 0)).toBeNull();
    expect(raceShare(50, undefined)).toBeNull();
  });

  it('latestTopShare is the same figure the race heading shows for its last frame (decision 79: banner and heading change together)', () => {
    const totals = [300, 400, 500];
    const lastFrame = raceFrame(model, 2);
    expect(latestTopShare(MAP, totals)).toBe(raceShare(lastFrame.topTotal, totals[2]));
    expect(latestTopShare(MAP, totals)).toBe(Math.round((427 / 500) * 100));
    expect(latestTopShare(MAP, [])).toBeNull();
    expect(latestTopShare({ ...MAP, years: [], values: [] }, totals)).toBeNull();
  });
});

describe('growthPhrase', () => {
  it('words the change since the baseline: more than doubled, more than two-thirds, else the plain percentage', () => {
    expect(growthPhrase(120)).toBe('more than doubled');
    expect(growthPhrase(100)).toBe('more than doubled');
    expect(growthPhrase(68.6)).toBe('grown by more than two-thirds');
    expect(growthPhrase(66.7)).toBe('grown by more than two-thirds');
    expect(growthPhrase(66.6)).toBe('grown by 67%');
    expect(growthPhrase(12.4)).toBe('grown by 12%');
  });
});
