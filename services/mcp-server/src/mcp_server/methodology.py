"""Canonical methodology text (SPEC.md §3.3).

Single source for get_methodology_notes (SPEC.md §5, §5.1) and every tool's
scope_note wording (SPEC.md §3.2, added in Step 3 via trimming.py) -- neither should
duplicate its own description of the expanded-scope criteria, ETS(A,Ad,N), the model
comparison set, or (Area 2, `CLIMATE_METHODOLOGY` below) the climate-context methodology. A future documentation change should only
need to happen here.
"""

from __future__ import annotations

FORECASTING_METHODOLOGY = (
    "Forecasts use ETS(A,Ad,N) – Holt's Damped Trend (statsmodels ExponentialSmoothing, "
    "trend='add', damped_trend=True, seasonal=None). The damped trend prevents unbounded "
    "long-range extrapolation and better captures emissions slowdowns in developed countries "
    "(e.g. UK, Germany) than an undamped trend or ARIMA would. Deep learning and LLM-based "
    "forecasting approaches are intentionally out of scope for this project."
)

MODEL_COMPARISON_SET = (
    "Backtested against a 1990-2018 train / 2019-2023 test split (capturing the 2020 "
    "COVID-19 emissions dip in the test set) across five models: Naive baseline, Linear "
    "Regression, Random Forest per-country, Random Forest pooled (trained on all countries "
    "at once with a country_encoded feature), and ETS(A,Ad,N)."
)

DATA_PROVENANCE = (
    "All figures derive from Our World in Data's owid-co2-data.csv. Classical machine "
    "learning only (Linear Regression, Random Forest, ETS) – no Prophet (inappropriate for "
    "annual data), no deep learning, no LLM-based forecasting."
)

SCOPE_CRITERIA = (
    "'Featured' is the original 10 hardcoded countries (China, USA, India, Russia, Japan, "
    "Germany, Brazil, UK, South Africa, Australia). 'Expanded' (~40 countries) is a "
    "data-driven set selected by data-quality coverage and emissions-materiality thresholds. "
    "'Sovereign' is every real country in the dataset (~218), distinguished from OWID's "
    "aggregate/grouping rows (continents, income groups, EU, etc.) by having a real ISO-3 "
    "code."
)

# Human-readable label per scope, used by trimming.py's scope_note (SPEC.md §3.2) so the
# wording is identical everywhere a scope_note appears rather than re-described per tool.
SCOPE_LABELS = {
    "featured": "Featured scope — the original 10 curated countries",
    "expanded": "Expanded scope — coverage ≥ natural gap threshold, ≥100 Mt latest-year CO₂",
    "sovereign": "Sovereign scope — every country with a real ISO-3 code",
}


def methodology_notes() -> dict[str, str]:
    return {
        "forecasting_methodology": FORECASTING_METHODOLOGY,
        "model_comparison": MODEL_COMPARISON_SET,
        "data_provenance": DATA_PROVENANCE,
        "scope_criteria": SCOPE_CRITERIA,
    }


# --- Area 2 climate-context text (SPEC.md §5.1; root ENHANCEMENTS.md decisions 4, 15, 40, 83) -----
# Static wording only. Every number (slope, CI, R², stability, land-use sensitivity) is read from
# the API at call time by get_methodology_notes(topic="climate") and never typed here, so this
# text cannot drift from the published figures.

CLIMATE_METHODOLOGY = {
    "climate_chain": (
        "Emissions (annual flows) -> atmospheric concentration (the accumulated stock, in ppm) -> "
        "radiative forcing (the heat-trapping effect of that stock) -> temperature anomaly "
        "(deviation from a reference period). Radiative forcing is a conceptual link only here: "
        "no forcing dataset, calculation or endpoint exists. This platform does not model "
        "carbon-cycle feedbacks, ocean heat uptake or ocean thermal lag."
    ),
    "headline_long_run_relationship": (
        "Ordinary least squares of the Berkeley Earth global temperature anomaly (1850-1900 "
        "reference) on cumulative OWID total anthropogenic CO₂ since 1850 (fossil fuel, cement "
        "and land-use change; OWID's World series, which includes international aviation and "
        "shipping). A simplified, data-driven analog to the IPCC's TCRE (AR6 best estimate about "
        "0.45 °C per 1,000 GtCO₂, very likely range 0.27–0.63), not a restatement of it: it also "
        "absorbs warming from non-CO₂ gases and aerosols that varies with CO₂, uses one observed "
        "climate history rather than a multi-model ensemble, and depends on uncertain land-use "
        "estimates. The confidence interval uses Newey-West (HAC) standard errors because plain "
        "OLS errors are too narrow for autocorrelated annual series. Fossil + cement only is the "
        "labelled secondary variant."
    ),
    "recent_all_gas_relationship": (
        "A separate, secondary relationship: PRIMAP-hist cumulative national total GHG in CO₂e "
        "(AR5 GWP-100, excluding land use and international aviation/shipping) from 1970 against "
        "the same temperature series. It is a descriptive regression and is never called TCRE and "
        "never compared with the AR6 range."
    ),
    "country_share": (
        "Country responsibility is shown as cumulative share of emissions: a country's cumulative "
        "emissions divided by the national sum over all countries (international aviation and "
        "shipping excluded, so shares sum to 100% of territorial emissions; this differs by design "
        "from the World series used in the headline regression). It describes where emissions "
        "occurred. It is not an estimate of any country's contribution to warming, and no "
        "country's emissions are regressed against the global temperature series."
    ),
    "scenario_temperature_translation": (
        "An illustrative, partial-coverage translation, not a climate-model projection: the "
        "BAU/Moderate/Aggressive pathways apply to the covered country set only; the rest of the "
        "world is held at its last-observed share of the global total; land-use CO₂ is held flat "
        "after the last observed year; the OWID CO₂ headline slope converts added cumulative "
        "emissions to implied temperature, with a second line from the fossil-only slope. The "
        "output depends on the regression period, the emissions source and these assumptions."
    ),
    "source_reconciliation": (
        "OWID/GCP and PRIMAP-hist CO₂ are deliberately not forced to agree: scope boundaries, "
        "treatment of international bunker fuels, treatment of cement and process emissions, "
        "methodology and data-vintage differences all produce expected directional differences. "
        "The 5-8% figure in the requirements was estimated against EDGAR and has not yet been "
        "re-measured for PRIMAP-hist, so do not quote it as a measured PRIMAP-hist figure."
    ),
    "licences_and_attribution": (
        "PRIMAP-hist is CC BY-NC-SA 4.0 (non-commercial, attribution required; the maintainer "
        "confirmed this is authoritative, 2026-10-08). Berkeley Earth's high-resolution annual "
        "file is a preliminary release, not yet peer reviewed; values may be revised. NOAA GML "
        "Mauna Loa and the Law Dome ice-core record are spliced at 1959 (the splice year and the "
        "measured overlap gap are published with the series). EDGAR is not published (its "
        "fuel-combustion CO₂ is IEA data under CC BY-NC-ND 4.0)."
    ),
    "not_a_climate_model": (
        "Everything here is descriptive analysis of observed series. Correlation and regression "
        "show long-run co-movement and are not proof of cause; climate outcomes depend on many "
        "physical processes. This is not an Earth-system or integrated assessment model, and "
        "global temperature must not be attributed to any single country from its emissions."
    ),
}

# The order the headline derivation is told in (decision 42); the figures come from the API.
HEADLINE_DERIVATION_OUTLINE = [
    "1. What is regressed on what, and why total anthropogenic CO₂ (the fossil-only result beside it).",
    "2. Uncertainty: HAC standard errors and why plain errors are too narrow, with the bandwidth sensitivity.",
    "3. Sensitivity: estimation window and land-use scaling.",
    "4. Stability: residual bootstrap (not a pairs bootstrap) and decade holdouts; in-sample vs out-of-sample.",
    "5. Comparison to the IPCC AR6 range, and why the figures differ.",
    "6. Data, licences and attribution; the Berkeley preliminary-release note.",
    "7. What this is not: not a climate model; correlation, not proof of cause.",
]
