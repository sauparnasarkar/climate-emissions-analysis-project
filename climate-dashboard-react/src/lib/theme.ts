import { createContext, useContext } from 'react';

// Origin-scoped localStorage key -- labs.syena.io hosts more than one app (this one and
// the India Allocation Monitor), so a generic key like "theme" would risk colliding with
// another app's own choice if they ever shared storage semantics. Same convention as that
// app's own THEME_STORAGE_KEY.
export const THEME_STORAGE_KEY = 'ghg-emissions-analysis-theme';

export type AppTheme = 'analytics-bright-signal-tidewater' | 'analytics';

export const ThemeContext = createContext<AppTheme>('analytics-bright-signal-tidewater');

export function useTheme(): AppTheme {
  return useContext(ThemeContext);
}

// Per-theme scenario colors -- SCENARIO_COLORS' flat hex values were tuned for the dark
// `analytics` chart panel; #3950c4 in particular is a deep indigo that reads as dark-on-dark
// on Tidewater's own dark #061E28 panel. No existing design-system token expresses "a
// hex per scenario", so this stays an explicit small constant map here, same pattern
// CHART_SIGN_COLORS uses in the India Allocation Monitor for its own analogous problem.
export const SCENARIO_COLORS: Record<AppTheme, Record<'BAU' | 'Moderate' | 'Aggressive', string>> = {
  analytics: { BAU: '#3950c4', Moderate: '#d19e27', Aggressive: '#87ca65' },
  'analytics-bright-signal-tidewater': { BAU: '#58C8F0', Moderate: '#FFB84D', Aggressive: '#7FE0D0' },
};
