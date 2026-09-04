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
