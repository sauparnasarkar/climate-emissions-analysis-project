import { describe, expect, it } from 'vitest';
import { buildHeadlineSentence, headlineSegmentsToText, type HeadlineSegment } from './overviewHeadline';
import type { MoverRow } from '../api/types';

const SCOPE = 'the top 10 emitters by 2024 output';

function row(country: string, absoluteChange: number | null, pctChange: number | null): MoverRow {
  return { country, co2_1990: null, co2_latest: null, absolute_change: absoluteChange, pct_change: pctChange };
}

function text(headlineMovers: MoverRow[], scope = SCOPE): string | null {
  const segments = buildHeadlineSentence(headlineMovers, scope);
  return segments && headlineSegmentsToText(segments);
}

function countryNames(segments: HeadlineSegment[]): string[] {
  return segments.filter((s): s is Extract<HeadlineSegment, { kind: 'country' }> => s.kind === 'country').map((s) => s.text);
}

describe('buildHeadlineSentence', () => {
  it('returns null for an empty list', () => {
    expect(buildHeadlineSentence([], SCOPE)).toBeNull();
  });

  it('returns null when every row has null figures', () => {
    expect(buildHeadlineSentence([row('China', null, null)], SCOPE)).toBeNull();
  });

  it('excludes rows with null figures rather than coercing them to 0', () => {
    const sentence = text([
      row('China', 8000, 250),
      row('India', null, null),
      row('USA', -500, -10),
    ]);
    expect(sentence).not.toContain('India');
  });

  it('produces the spec-verified example (SPEC.md §5.18.5, top 10 emitters by 2024 output)', () => {
    const sentence = text([
      row('China', 9806, 250),
      row('India', 1900, 452),
      row('United States', 400, -4),
      row('United Kingdom', -200, -48),
      row('Germany', -180, -46),
    ]);
    expect(sentence).toBe(
      'Among the top 10 emitters by 2024 output, China has grown the most in absolute terms (+9,806 MtCO₂), while India has the fastest growth rate (+452.0%). ' +
        'United States has stayed comparatively flat (-4.0%), while United Kingdom and Germany show the steepest declines (-48.0%, -46.0%).',
    );
  });

  it('prepends the caller-supplied scope clause to the front of the sentence', () => {
    const sentence = text([
      row('China', 9806, 250),
      row('India', 1900, 452),
      row('United States', 400, -4),
      row('United Kingdom', -200, -48),
    ]);
    expect(sentence).toMatch(/^Among the top 10 emitters by 2024 output, /);
  });

  it('never repeats "since 1990" inline -- the caller\'s eyebrow label already carries the timeframe', () => {
    const distinctLeaders = text([
      row('China', 9806, 250),
      row('India', 1900, 452),
      row('United States', 400, -4),
      row('United Kingdom', -200, -48),
    ]);
    expect(distinctLeaders?.toLowerCase()).not.toContain('since 1990');

    const collapsedLeader = text([
      row('China', 8000, 250),
      row('India', 1900, 100),
      row('United States', 400, 8),
      row('United Kingdom', -200, -35),
    ]);
    expect(collapsedLeader?.toLowerCase()).not.toContain('since 1990');
  });

  it('collapses to one clause when the absolute and rate growth leaders are the same country', () => {
    const sentence = text([
      row('China', 8000, 250),
      row('India', 1900, 100),
      row('United States', 400, 8),
      row('United Kingdom', -200, -35),
    ]);
    expect(sentence).toContain('China has grown the most, both in absolute terms');
    expect(sentence?.match(/China/g)).toHaveLength(1);
  });

  it('drops the decline clause entirely when there are no decliners', () => {
    const sentence = text([
      row('China', 8000, 250),
      row('India', 1900, 320),
      row('United States', 400, 8),
      row('Brazil', 100, 5),
    ]);
    expect(sentence).not.toMatch(/decline/);
    expect(sentence?.endsWith('%).')).toBe(true);
  });

  it('uses singular wording for exactly one decliner', () => {
    const sentence = text([
      row('China', 8000, 250),
      row('India', 1900, 320),
      row('United States', 400, 8),
      row('United Kingdom', -200, -35),
    ]);
    expect(sentence).toContain('United Kingdom shows the steepest decline (-35.0%).');
    expect(sentence).not.toContain('and');
  });

  it('suppresses only the "most stable" clause below the minimum selection size, keeping the rest', () => {
    const sentence = text([
      row('China', 8000, 250),
      row('India', 1900, 320),
      row('UK', -200, -35),
    ]);
    expect(sentence).not.toMatch(/stayed comparatively flat/);
    expect(sentence).toContain('China has grown the most');
    expect(sentence).toContain('UK shows the steepest decline');
  });

  it('breaks ties deterministically by keeping the first tied element in input order', () => {
    const rows = [row('Alpha', 1000, 50), row('Beta', 1000, 50), row('Gamma', -100, -5), row('Delta', -50, -2)];
    const first = text(rows);
    const second = text(rows);
    expect(first).toBe(second);
    expect(first).toContain('Alpha has grown the most, both in absolute terms');
  });

  it('tags every country name as its own "country" segment, in the order they appear', () => {
    const segments = buildHeadlineSentence([
      row('China', 9806, 250),
      row('India', 1900, 452),
      row('United States', 400, -4),
      row('United Kingdom', -200, -48),
      row('Germany', -180, -46),
    ], SCOPE);
    expect(segments).not.toBeNull();
    expect(countryNames(segments!)).toEqual(['China', 'India', 'United States', 'United Kingdom', 'Germany']);
  });

  it('collapses to a single country segment (not two) when the same country tops both growth clauses', () => {
    const segments = buildHeadlineSentence([
      row('China', 8000, 250),
      row('India', 1900, 100),
      row('United States', 400, 8),
      row('United Kingdom', -200, -35),
    ], SCOPE);
    expect(countryNames(segments!).filter((name) => name === 'China')).toHaveLength(1);
  });

  it('tags an increase (more emissions) as "negative" sentiment and a decrease as "positive"', () => {
    const segments = buildHeadlineSentence([
      row('China', 9806, 250),
      row('India', 1900, 452),
      row('United States', 400, -4),
      row('United Kingdom', -200, -48),
      row('Germany', -180, -46),
    ], SCOPE);
    const values = segments!.filter((s): s is Extract<HeadlineSegment, { kind: 'value' }> => s.kind === 'value');

    // China's absolute change (+9,806) and India's growth rate (+452.0%) are both increases.
    expect(values.find((s) => s.text.includes('9,806'))?.sentiment).toBe('negative');
    expect(values.find((s) => s.text.includes('452.0'))?.sentiment).toBe('negative');
    // United States' -4.0% and United Kingdom/Germany's declines are decreases.
    expect(values.find((s) => s.text === '-4.0%')?.sentiment).toBe('positive');
    expect(values.find((s) => s.text === '-48.0%')?.sentiment).toBe('positive');
    expect(values.find((s) => s.text === '-46.0%')?.sentiment).toBe('positive');
  });
});
