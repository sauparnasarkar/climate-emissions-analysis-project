import { afterEach, describe, expect, it } from 'vitest';
import {
  resolveCategoricalColorHex,
  resolveDivergingEndpointHex,
  resolveDivergingScaleReversedHex,
  resolveNoDataColorHex,
} from './resolveThemeColorHex';

afterEach(() => {
  document.documentElement.removeAttribute('style');
  document.documentElement.removeAttribute('data-theme');
  document.body.innerHTML = '';
});

describe('resolveCategoricalColorHex', () => {
  it('reads the slot-numbered categorical token', () => {
    document.documentElement.style.setProperty('--__s9cmpx-chart-categorical-default-05', '#abcdef');

    expect(resolveCategoricalColorHex(5, '#000000')).toBe('#abcdef');
  });

  it('falls back when the token resolves empty', () => {
    expect(resolveCategoricalColorHex(5, '#123456')).toBe('#123456');
  });
});

describe('resolveNoDataColorHex', () => {
  it('reads --__s9cmpx-chart-surface-text-weak', () => {
    document.documentElement.style.setProperty('--__s9cmpx-chart-surface-text-weak', '#94b4c0');

    expect(resolveNoDataColorHex('#000000')).toBe('#94b4c0');
  });

  it('falls back when the token resolves empty', () => {
    expect(resolveNoDataColorHex('#6b7280')).toBe('#6b7280');
  });
});

describe('resolveDivergingScaleReversedHex', () => {
  it('puts the diverging-high token at stop 0 and the diverging-low token at stop 1 -- reversed from SyChart\'s own low/mid/high stop order', () => {
    document.documentElement.style.setProperty('--__s9cmpx-chart-diverging-low', '#d8b365');
    document.documentElement.style.setProperty('--__s9cmpx-chart-diverging-mid', '#e5e5e5');
    document.documentElement.style.setProperty('--__s9cmpx-chart-diverging-high', '#5ab4ac');

    expect(resolveDivergingScaleReversedHex()).toEqual([
      [0, '#5ab4ac'],
      [0.5, '#e5e5e5'],
      [1, '#d8b365'],
    ]);
  });

  it('falls back to the literal BrBG triple, still reversed, when no token resolves', () => {
    expect(resolveDivergingScaleReversedHex()).toEqual([
      [0, '#5AB4AC'],
      [0.5, '#E5E5E5'],
      [1, '#D8B365'],
    ]);
  });
});

describe('resolveDivergingEndpointHex', () => {
  it("'positive' (favorable/decrease) reads diverging-high; 'negative' (unfavorable/increase) reads diverging-low", () => {
    document.documentElement.style.setProperty('--__s9cmpx-chart-diverging-low', '#111111');
    document.documentElement.style.setProperty('--__s9cmpx-chart-diverging-high', '#333333');

    expect(resolveDivergingEndpointHex('positive')).toBe('#333333');
    expect(resolveDivergingEndpointHex('negative')).toBe('#111111');
  });

  it('falls back to the literal BrBG endpoints when no token resolves', () => {
    expect(resolveDivergingEndpointHex('positive')).toBe('#5AB4AC');
    expect(resolveDivergingEndpointHex('negative')).toBe('#D8B365');
  });
});
