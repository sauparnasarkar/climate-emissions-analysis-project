import math

from fastapi import APIRouter, HTTPException

from ..constants import COUNTRIES
from ..data_loaders import (
    DataNotFoundError,
    load_ets_parameters,
    load_feature_importance,
    load_features,
    load_forecasts,
    load_model_comparison,
)
from ..schemas import (
    EtsParameterRow,
    EtsParametersResponse,
    FeatureImportanceResponse,
    FeatureImportanceRow,
    ForecastCountryResponse,
    ForecastSummaryResponse,
    ForecastSummaryRow,
    ModelComparisonResponse,
)

router = APIRouter()


def _nan_to_none(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def _snake_case(col: str) -> str:
    return col.strip().lower().replace("-", "_").replace(" ", "_")


# Static routes must be declared before /forecasts/{country} — otherwise Starlette
# would match e.g. "summary" as a {country} path value first.


@router.get("/forecasts/summary", response_model=ForecastSummaryResponse)
def get_forecast_summary():
    try:
        df_forecasts = load_forecasts()
        df = load_features()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    rows = []
    for c in COUNTRIES:
        fc = df_forecasts[df_forecasts["country"] == c].set_index("year")["mean"]
        actual_2020 = df[(df["country"] == c) & (df["year"] == 2020)]["co2"].values
        if len(actual_2020) == 0:
            continue
        a2020 = float(actual_2020[0])
        f2040 = fc.get(2040, float("nan"))
        rows.append(
            ForecastSummaryRow(
                country=c,
                forecast_2030=_nan_to_none(round(fc.get(2030, float("nan")), 1)),
                forecast_2035=_nan_to_none(round(fc.get(2035, float("nan")), 1)),
                forecast_2040=_nan_to_none(round(f2040, 1)),
                actual_2020=round(a2020, 1),
                pct_change_2020_2040=_nan_to_none(round((f2040 - a2020) / a2020 * 100, 1)),
            )
        )

    # Descending by forecast_2040, with missing values sorted last (matches
    # pandas' sort_values(..., ascending=False) na_position="last" default).
    rows.sort(key=lambda r: -r.forecast_2040 if r.forecast_2040 is not None else float("inf"))
    return ForecastSummaryResponse(rows=rows)


@router.get("/forecasts/model-comparison", response_model=ModelComparisonResponse)
def get_model_comparison():
    try:
        df_model_cmp = load_model_comparison()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    columns = [_snake_case(c) for c in df_model_cmp.columns]
    rows = []
    for _, row in df_model_cmp.iterrows():
        rows.append({_snake_case(c): _nan_to_none(row[c]) for c in df_model_cmp.columns})

    return ModelComparisonResponse(columns=columns, rows=rows)


@router.get("/forecasts/ets-parameters", response_model=EtsParametersResponse)
def get_ets_parameters():
    try:
        df_ets_params = load_ets_parameters()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    rows = [
        EtsParameterRow(country=r["country"], alpha=r["alpha"], beta_star=r["beta_star"], phi=r["phi"])
        for _, r in df_ets_params.iterrows()
    ]
    return EtsParametersResponse(rows=rows)


@router.get("/forecasts/feature-importance", response_model=FeatureImportanceResponse)
def get_feature_importance():
    try:
        df_feat_imp = load_feature_importance()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    df_sorted = df_feat_imp.sort_values("importance")
    rows = [FeatureImportanceRow(feature=r["feature"], importance=r["importance"]) for _, r in df_sorted.iterrows()]
    return FeatureImportanceResponse(rows=rows)


@router.get("/forecasts/{country}", response_model=ForecastCountryResponse)
def get_forecast(country: str):
    if country not in COUNTRIES:
        raise HTTPException(status_code=404, detail=f"Unknown country: {country}")

    try:
        df_forecasts = load_forecasts()
        df = load_features()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    fc_c = df_forecasts[df_forecasts["country"] == country].sort_values("year")
    hist_c = df[(df["country"] == country) & (df["year"] <= 2018)].sort_values("year")
    hold_c = df[(df["country"] == country) & (df["year"] > 2018)].sort_values("year")

    return ForecastCountryResponse(
        country=country,
        hist_years=hist_c["year"].tolist(),
        hist_co2=[_nan_to_none(v) for v in hist_c["co2"].tolist()],
        holdout_years=hold_c["year"].tolist(),
        holdout_co2=[_nan_to_none(v) for v in hold_c["co2"].tolist()],
        forecast_years=fc_c["year"].tolist(),
        forecast_mean=fc_c["mean"].tolist(),
        ci_upper=fc_c["ci_upper"].tolist(),
        ci_lower=fc_c["ci_lower"].tolist(),
    )
