// Column names come from the raw OWID dataset (snake_case, e.g. `co2_per_capita`,
// `total_ghg`) or from pre-formatted derived tables (e.g. `Baseline MAE`) -- either way,
// plain title-casing capitalizes only the first letter of each word, mangling any acronym
// into "Co2", "Gdp", "Mae" (Claude Design theme-adherence review, C7 -- Data Explorer's
// headers "read as unfinished"). This list is every acronym this app's own columns are known
// to use; an unlisted word still falls back to plain title-casing rather than guessing.
const ACRONYMS = ['co2', 'ch4', 'n2o', 'ghg', 'gdp', 'gnp', 'gni', 'mae', 'rmse', 'ets', 'iso'];
const ACRONYM_PATTERN = new RegExp(`\\b(${ACRONYMS.join('|')})\\b`, 'gi');

export function humanize(field: string): string {
  const titled = field.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
  return titled.replace(ACRONYM_PATTERN, (match) => match.toUpperCase());
}
