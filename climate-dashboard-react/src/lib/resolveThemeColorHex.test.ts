import { afterEach, describe, expect, it } from 'vitest';
import {
  resolveCategoricalColorHex,
  resolveDivergingScaleReversedHex,
  resolveNoDataColorHex,
  resolveSentimentColorHex,
} from './resolveThemeColorHex';

const POSITIVE_VAR = '--__s9cmpx-chart-sentiment-positive';
const NEGATIVE_VAR = '--__s9cmpx-chart-sentiment-negative';
const FALLBACK_POSITIVE = '#4FD69B';
const FALLBACK_NEGATIVE = '#EA5B62';

afterEach(() => {
  document.documentElement.removeAttribute('style');
  document.documentElement.removeAttribute('data-theme');
  document.body.innerHTML = '';
});

describe('resolveSentimentColorHex', () => {
  it('prefers a [data-theme] element over document.documentElement when both carry the property', () => {
    // Mirrors App.tsx's real layout: data-theme lives on a .app-shell div, not <html> -- the
    // documentElement value here is a deliberate decoy to prove the themed subtree wins.
    document.documentElement.style.setProperty(POSITIVE_VAR, '#000000');
    const shell = document.createElement('div');
    shell.setAttribute('data-theme', 'analytics');
    shell.style.setProperty(POSITIVE_VAR, '#3ecf95');
    document.body.appendChild(shell);

    expect(resolveSentimentColorHex('positive')).toBe('#3ecf95');
  });

  it('falls back to document.documentElement when no [data-theme] element exists', () => {
    document.documentElement.style.setProperty(NEGATIVE_VAR, '#f36b84');

    expect(resolveSentimentColorHex('negative')).toBe('#f36b84');
  });

  it('falls back to the hardcoded hex when the custom property resolves empty', () => {
    // Neither documentElement nor any [data-theme] element defines the variable.
    expect(resolveSentimentColorHex('positive')).toBe(FALLBACK_POSITIVE);
    expect(resolveSentimentColorHex('negative')).toBe(FALLBACK_NEGATIVE);
  });

  it('reads the correct variable per direction, not the same one for both', () => {
    document.documentElement.style.setProperty(POSITIVE_VAR, '#111111');
    document.documentElement.style.setProperty(NEGATIVE_VAR, '#222222');

    expect(resolveSentimentColorHex('positive')).toBe('#111111');
    expect(resolveSentimentColorHex('negative')).toBe('#222222');
  });
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
