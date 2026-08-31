from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from marketdata.api.access import source_row_allows_public_api
from marketdata.api.deps import get_db
from marketdata.api.query import (
    DEFAULT_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
    apply_history_window,
    load_history_page,
    parse_history_window,
)
from marketdata.domain.errors import decimal_json
from marketdata.storage.models import MarketSeriesObservationRow, MarketSeriesRow, SourceRow

router = APIRouter()


class SeriesObservationResponse(BaseModel):
    series: str
    date: date
    value: str
    unit: str
    source: str
    revision: int


class SeriesHistoryResponse(BaseModel):
    series: str
    unit: str
    observations: list[SeriesObservationResponse]
    next_cursor: date | None = None


def _series_with_source(session: Session, code: str) -> tuple[MarketSeriesRow, SourceRow]:
    joined = session.execute(
        select(MarketSeriesRow, SourceRow)
        .join(SourceRow, SourceRow.id == MarketSeriesRow.source_id)
        .where(MarketSeriesRow.code == code)
    ).first()
    if joined is None:
        joined = session.execute(
            select(MarketSeriesRow, SourceRow)
            .join(SourceRow, SourceRow.id == MarketSeriesRow.source_id)
            .where(MarketSeriesRow.source_series_id == code)
        ).first()
    if joined is None or not source_row_allows_public_api(joined[1]):
        raise HTTPException(status_code=404, detail="series not found")
    return joined[0], joined[1]


def _to_observation(
    series: MarketSeriesRow, row: MarketSeriesObservationRow, source_name: str
) -> SeriesObservationResponse:
    return SeriesObservationResponse(
        series=series.code,
        date=row.reference_date,
        value=decimal_json(Decimal(row.value)),
        unit=series.unit,
        source=source_name,
        revision=row.revision,
    )


@router.get("/series/{code}/latest", response_model=SeriesObservationResponse)
def series_latest(code: str, session: Session = Depends(get_db)) -> SeriesObservationResponse:
    series, source = _series_with_source(session, code)
    row = session.scalar(
        select(MarketSeriesObservationRow)
        .where(MarketSeriesObservationRow.series_id == series.id)
        .order_by(
            MarketSeriesObservationRow.reference_date.desc(),
            MarketSeriesObservationRow.revision.desc(),
        )
        .limit(1)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="observation not found")
    return _to_observation(series, row, source.name)


@router.get("/series/{code}/observations", response_model=SeriesHistoryResponse)
def series_observations(
    code: str,
    date_filter: date | None = Query(default=None, alias="date"),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    cursor: date | None = Query(default=None),
    limit: int = Query(default=DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT),
    session: Session = Depends(get_db),
) -> SeriesHistoryResponse:
    window = parse_history_window(start=start, end=end, date_filter=date_filter, cursor=cursor)
    series, source = _series_with_source(session, code)
    stmt = select(MarketSeriesObservationRow).where(
        MarketSeriesObservationRow.series_id == series.id
    )
    stmt = apply_history_window(stmt, MarketSeriesObservationRow.reference_date, window)
    rows, next_cursor = load_history_page(
        session,
        stmt,
        date_attr="reference_date",
        distinct_on=(MarketSeriesObservationRow.reference_date,),
        order_by=(
            MarketSeriesObservationRow.reference_date.desc(),
            MarketSeriesObservationRow.revision.desc(),
            MarketSeriesObservationRow.id.asc(),
        ),
        limit=limit,
    )
    return SeriesHistoryResponse(
        series=series.code,
        unit=series.unit,
        observations=[_to_observation(series, row, source.name) for row in rows],
        next_cursor=next_cursor,
    )
