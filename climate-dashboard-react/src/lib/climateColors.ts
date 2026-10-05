import type { Era } from './climateSignal';

// The Area 2 design's series colours for charts drawn on the dark chart panel (both themes): emissions,
// concentration, temperature, and a neutral for the earliest era. The design-system has no tokens for these.
export const ERA_COLORS: Record<Era, string> = { pre1900: '#94B4C0', y1900_1969: '#FFB54D', y1970plus: '#EA5B62' };
export const ERA_LABELS: Record<Era, string> = { pre1900: 'to 1899', y1900_1969: '1900–69', y1970plus: '1970+' };

/** Series colours on the dark chart panel (the design's "on dark" column). */
export const SERIES_ON_DARK = { emissions: '#FFB54D', concentration: '#5FD8F7', temperature: '#EA5B62' } as const;
