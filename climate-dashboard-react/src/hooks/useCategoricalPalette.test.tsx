import { act, render } from '@testing-library/react';
import { useRef } from 'react';
import { describe, expect, it } from 'vitest';
import { FALLBACK_PALETTE, useCategoricalPalette } from './useCategoricalPalette';

let seen: string[] = [];
function Probe() {
  const ref = useRef<HTMLDivElement>(null);
  seen = useCategoricalPalette(ref);
  return <div data-theme="analytics" ref={ref} style={{ ['--__s9cmpx-chart-categorical-default-02' as string]: ' #112233 ' }} />;
}

describe('useCategoricalPalette', () => {
  it('reads the theme tokens it can see and falls back to SyChart\'s palette for the rest', () => {
    render(<Probe />);
    expect(seen).toHaveLength(10);
    // jsdom resolves inline custom properties, so slot 2 is the token (trimmed) and the others are the fallbacks.
    expect(seen[1]).toBe('#112233');
    expect(seen[0]).toBe(FALLBACK_PALETTE[0]);
  });

  it('re-reads when the theme attribute changes', async () => {
    const { container } = render(<Probe />);
    const el = container.firstElementChild as HTMLElement;
    el.style.setProperty('--__s9cmpx-chart-categorical-default-02', '#445566');
    await act(async () => {
      el.setAttribute('data-theme', 'analytics-bright-tidewater');
      await Promise.resolve();
    });
    expect(seen[1]).toBe('#445566');
  });
});
