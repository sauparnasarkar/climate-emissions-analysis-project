"""Canonical methodology text (SPEC.md §3.3).

Single source for get_methodology_notes (SPEC.md §5, added in Step 3) and every tool's
scope_note wording (SPEC.md §3.2, added in Step 3 via trimming.py) -- neither should
duplicate its own description of the expanded-scope criteria, ETS(A,Ad,N), or the model
comparison set. A future documentation change should only need to happen here.
"""

from __future__ import annotations

FORECASTING_METHODOLOGY = (
    "Forecasts use ETS(A,Ad,N) -- Holt's Damped Trend (statsmodels ExponentialSmoothing, "
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
    "learning only (Linear Regression, Random Forest, ETS) -- no Prophet (inappropriate for "
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
    "expanded": "Expanded scope — coverage ≥ natural gap threshold, ≥100 Mt latest-year CO2",
    "sovereign": "Sovereign scope — every country with a real ISO-3 code",
}


def methodology_notes() -> dict[str, str]:
    return {
        "forecasting_methodology": FORECASTING_METHODOLOGY,
        "model_comparison": MODEL_COMPARISON_SET,
        "data_provenance": DATA_PROVENANCE,
        "scope_criteria": SCOPE_CRITERIA,
    }
