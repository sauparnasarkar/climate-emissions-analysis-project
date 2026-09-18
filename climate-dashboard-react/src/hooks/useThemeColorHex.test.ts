import { renderHook } from '@testing-library/react';
import { createElement, type ReactNode } from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { useThemeColorHex } from './useThemeColorHex';
import { ThemeContext, type AppTheme } from '../lib/theme';

const COLOR_BY_THEME: Record<AppTheme, string> = {
  'analytics-bright-tidewater': '#111111',
  analytics: '#222222',
};

// Mutated by each test, then picked up by Wrapper on the next renderHook `rerender()` call --
// module-level rather than component state so Wrapper's own `data-theme` DOM attribute (and,
// in the real app via that theme's stylesheet, its resolved CSS vars) changes in the SAME
// commit as the surrounding re-render, exactly mirroring App.tsx's `<div data-theme={theme}>`.
// That's what makes this a real regression test for the bug (Claude Design theme-adherence
// review, C4): a resolver called directly in a render body reads this node's PRE-commit
// attribute/style, one render behind.
let currentTheme: AppTheme = 'analytics-bright-tidewater';

function Wrapper({ children }: { children: ReactNode }) {
  return createElement(
    ThemeContext.Provider,
    { value: currentTheme },
    createElement('div', { 'data-theme': currentTheme, style: { '--test-color': COLOR_BY_THEME[currentTheme] } as Record<string, string> }, children),
  );
}

function NoVarWrapper({ children }: { children: ReactNode }) {
  return createElement(ThemeContext.Provider, { value: 'analytics' as AppTheme }, createElement('div', { 'data-theme': 'analytics' }, children));
}

function getResolvedTestColor(fallback: string): string {
  const el = document.querySelector('[data-theme]') ?? document.documentElement;
  const resolved = getComputedStyle(el).getPropertyValue('--test-color').trim();
  return resolved || fallback;
}

afterEach(() => {
  document.body.innerHTML = '';
});

describe('useThemeColorHex', () => {
  it('re-resolves to the new theme value after a live toggle, not the outgoing theme', () => {
    currentTheme = 'analytics-bright-tidewater';
    const { result, rerender } = renderHook(() => useThemeColorHex(() => getResolvedTestColor('#000000')), { wrapper: Wrapper });
    expect(result.current).toBe('#111111');

    currentTheme = 'analytics';
    rerender();
    expect(result.current).toBe('#222222');

    currentTheme = 'analytics-bright-tidewater';
    rerender();
    expect(result.current).toBe('#111111');
  });

  it('falls back to the resolver-provided fallback when no [data-theme] element defines the variable', () => {
    const { result } = renderHook(() => useThemeColorHex(() => getResolvedTestColor('#6b7280')), { wrapper: NoVarWrapper });
    expect(result.current).toBe('#6b7280');
  });
});
