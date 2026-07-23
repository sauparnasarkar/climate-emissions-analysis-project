import io

import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..data_loaders import DataNotFoundError, load_filtered
from ..schemas import ExplorerDataResponse, ExplorerMetaResponse, ModelComparisonResponse

router = APIRouter()


def _select_columns(df: pd.DataFrame, requested: list[str] | None) -> pd.DataFrame:
    """Absent/empty `requested` means "all columns" — an explicit API default distinct from
    any one UI's own default selection (e.g. app.py's Data Explorer page pre-selects a
    representative subset itself, rather than the API deciding that for every consumer).
    Any requested name that isn't a real column is silently dropped rather than erroring —
    kept forgiving, consistent with this being an exploratory browsing endpoint."""
    if not requested:
        return df
    known = [c for c in requested if c in df.columns]
    return df[known] if known else df


def _filter(
    countries: list[str] | None,
    year_min: int | None,
    year_max: int | None,
    columns: list[str] | None,
) -> pd.DataFrame:
    try:
        df = load_filtered()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    if countries:
        df = df[df["country"].isin(countries)]
    if year_min is not None:
        df = df[df["year"] >= year_min]
    if year_max is not None:
        df = df[df["year"] <= year_max]

    return _select_columns(df, columns)


def _to_rows(df: pd.DataFrame) -> list[dict]:
    # Bulk NaN -> None so every dtype's missing values serialize as valid JSON null,
    # matching this API's existing per-value _nan_to_none convention (bulk version, since
    # this endpoint's column set is user-selected and arbitrary rather than a fixed schema).
    return df.where(pd.notnull(df), None).to_dict("records")


@router.get("/explorer/meta", response_model=ExplorerMetaResponse)
def get_explorer_meta():
    try:
        df = load_filtered()
    except DataNotFoundError as e:
        raise HTTPException(status_code=503, detail=e.message)

    return ExplorerMetaResponse(
        countries=sorted(df["country"].unique().tolist()),
        columns=df.columns.tolist(),
        year_min=int(df["year"].min()),
        year_max=int(df["year"].max()),
    )


@router.get("/explorer/data", response_model=ExplorerDataResponse)
def get_explorer_data(
    countries: list[str] | None = Query(default=None),
    year_min: int | None = Query(default=None),
    year_max: int | None = Query(default=None),
    columns: list[str] | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=500),
):
    df = _filter(countries, year_min, year_max, columns)
    total_rows = len(df)
    start = (page - 1) * page_size
    page_df = df.iloc[start : start + page_size]

    return ExplorerDataResponse(
        columns=page_df.columns.tolist(),
        rows=_to_rows(page_df),
        total_rows=total_rows,
        page=page,
        page_size=page_size,
    )


@router.get("/explorer/summary", response_model=ModelComparisonResponse)
def get_explorer_summary(
    countries: list[str] | None = Query(default=None),
    year_min: int | None = Query(default=None),
    year_max: int | None = Query(default=None),
    columns: list[str] | None = Query(default=None),
):
    df = _filter(countries, year_min, year_max, columns)
    summary = df.describe(include="all").reset_index().rename(columns={"index": "statistic"})

    return ModelComparisonResponse(
        columns=summary.columns.tolist(),
        rows=_to_rows(summary),
    )


@router.get("/explorer/download")
def download_explorer_data(
    countries: list[str] | None = Query(default=None),
    year_min: int | None = Query(default=None),
    year_max: int | None = Query(default=None),
    columns: list[str] | None = Query(default=None),
):
    df = _filter(countries, year_min, year_max, columns)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)

    return StreamingResponse(
        buffer,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ghg_filtered_export.csv"},
    )
