// Fixed copy for the Area 2 climate-context surfaces (requirements doc §2.3/§2.4, SPEC.md §5.26).
// One place, so the guardrail wording cannot drift between the landing page, the Overview and the
// Correlation module. Figures never live here -- every number on screen comes from API output.

/** Overview anchors the Landing and the in-page jump links point at (one constant, so a link and its target cannot drift). */
export const CLIMATE_SIGNAL_ANCHOR = 'climate-signal';
export const RELATIONSHIP_ANCHOR = 'relationship';

export const CAUSAL_CHAIN = ['Emissions', 'Concentration', 'Radiative forcing', 'Temperature anomaly'] as const;

/** Radiative forcing is copy-only: no value, no chart, no endpoint (decision 2). */
export const FORCING_CONCEPT_ONLY =
  'More CO₂ in the air traps more outgoing heat. This link is described here, not calculated: the platform holds no forcing dataset.';

export const NOT_A_CLIMATE_MODEL = 'Shown as context from observed data; not a climate model.';

export const NO_COUNTRY_ATTRIBUTION =
  "Shares describe each country's part of cumulative emissions. No country series is regressed against temperature, and no warming is attributed to a country.";

export const SCENARIO_LABEL = 'Illustrative · implied outcomes, not projections';

/** The 1970+ PRIMAP-hist view is never called TCRE (decision 35 / requirements §1.3.1). */
export const ALL_GAS_TAG = 'Recent all-gas relationship · not TCRE';

/** Module anchors (one constant each, so the jump links and their targets cannot drift). */
export const CAUSAL_CHAIN_ANCHOR = 'causal-chain';
export const GLOBAL_RELATIONSHIP_ANCHOR = 'global-relationship';

/** The IPCC AR6 transient climate response to cumulative emissions, °C per 1,000 GtCO₂ (best estimate and very-likely range): fixed comparison copy
 * (ENHANCEMENTS.md decision 40, owner decision D), the same figures the API's methodology note quotes. Everything else in the module is read from the API. */
export const AR6_TCRE = { best: 0.45, low: 0.27, high: 0.63 } as const;
