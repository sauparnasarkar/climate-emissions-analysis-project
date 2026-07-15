// TS mirror of api/constants.py — single source of truth for the frontend.

export const COUNTRIES = [
  'China', 'United States', 'India', 'Russia', 'Japan',
  'Germany', 'Brazil', 'United Kingdom', 'South Africa', 'Australia',
] as const;

export type Country = (typeof COUNTRIES)[number];

export const GAS_COLUMNS: Record<string, string> = {
  co2: 'CO₂',
  methane: 'Methane (CH₄)',
  nitrous_oxide: 'Nitrous Oxide (N₂O)',
};

export const SCENARIO_COLORS: Record<string, string> = {
  BAU: '#3950c4',
  Moderate: '#d19e27',
  Aggressive: '#87ca65',
};
