import { describe, expect, it } from 'vitest';
import { buildHeadlineSentence } from './overviewHeadline';
import type { MoverRow } from '../api/types';

function row(country: string, absoluteChange: number | null, pctChange: number | null): MoverRow {
  return { country, co2_1990: null, co2_latest: null, absolute_change: absoluteChange, pct_change: pctChange };
}

describe('buildHeadlineSentence', () => {
  it('returns null for an empty list', () => {
    expect(buildHeadlineSentence([])).toBeNull();
  });

  it('returns null when every row has null figures', () => {
    expect(buildHeadlineSentence([row('China', null, null)])).toBeNull();
  });

  it('excludes rows with null figures rather than coercing them to 0', () => {
    const sentence = buildHeadlineSentence([
      row('China', 8000, 250),
      row('India', null, null),
      row('USA', -500, -10),
    ]);
    expect(sentence).not.toContain('India');
  });

  it('produces the spec-verified example (SPEC.md §5.18.1, Featured 10 default selection)', () => {
    const sentence = buildHeadlineSentence([
      row('China', 9806, 250),
      row('India', 1900, 452),
      row('United States', 400, -4),
      row('United Kingdom', -200, -48),
      row('Germany', -180, -46),
    ]);
    expect(sentence).toBe(
      'China has grown the most in absolute terms (+9,806 MtCO₂), while India has the fastest growth rate (+452.0%). ' +
        'United States has stayed comparatively flat (-4.0%), while United Kingdom and Germany show the steepest declines (-48.0%, -46.0%).',
    );
  });

  it('never repeats "since 1990" inline -- the caller\'s eyebrow label already carries the timeframe', () => {
    const distinctLeaders = buildHeadlineSentence([
      row('China', 9806, 250),
      row('India', 1900, 452),
      row('United States', 400, -4),
      row('United Kingdom', -200, -48),
    ]);
    expect(distinctLeaders?.toLowerCase()).not.toContain('since 1990');

    const collapsedLeader = buildHeadlineSentence([
      row('China', 8000, 250),
      row('India', 1900, 100),
      row('United States', 400, 8),
      row('United Kingdom', -200, -35),
    ]);
    expect(collapsedLeader?.toLowerCase()).not.toContain('since 1990');
  });

  it('collapses to one clause when the absolute and rate growth leaders are the same country', () => {
    const sentence = buildHeadlineSentence([
      row('China', 8000, 250),
      row('India', 1900, 100),
      row('United States', 400, 8),
      row('United Kingdom', -200, -35),
    ]);
    expect(sentence).toContain('China has grown the most, both in absolute terms');
    expect(sentence?.match(/China/g)).toHaveLength(1);
  });

  it('drops the decline clause entirely when there are no decliners', () => {
    const sentence = buildHeadlineSentence([
      row('China', 8000, 250),
      row('India', 1900, 320),
      row('United States', 400, 8),
      row('Brazil', 100, 5),
    ]);
    expect(sentence).not.toMatch(/decline/);
    expect(sentence?.endsWith('%).')).toBe(true);
  });

  it('uses singular wording for exactly one decliner', () => {
    const sentence = buildHeadlineSentence([
      row('China', 8000, 250),
      row('India', 1900, 320),
      row('United States', 400, 8),
      row('United Kingdom', -200, -35),
    ]);
    expect(sentence).toContain('United Kingdom shows the steepest decline (-35.0%).');
    expect(sentence).not.toContain('and');
  });

  it('suppresses only the "most stable" clause below the minimum selection size, keeping the rest', () => {
    const sentence = buildHeadlineSentence([
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
    const first = buildHeadlineSentence(rows);
    const second = buildHeadlineSentence(rows);
    expect(first).toBe(second);
    expect(first).toContain('Alpha has grown the most, both in absolute terms');
  });
});
