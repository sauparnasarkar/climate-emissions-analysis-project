import { afterEach, describe, expect, it } from 'vitest';
import { resolveSentimentColorHex } from './resolveThemeColorHex';

const POSITIVE_VAR = '--__s9cmpx-static-text-sentiment-positive';
const NEGATIVE_VAR = '--__s9cmpx-static-text-sentiment-negative';
const FALLBACK_POSITIVE = '#187254';
const FALLBACK_NEGATIVE = '#8d1a2a';

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
