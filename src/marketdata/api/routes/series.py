from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from marketdata.api.deps import get_db
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


def _series_by_code(session: Session, code: str) -> MarketSeriesRow:
    row = session.scalar(select(MarketSeriesRow).where(MarketSeriesRow.code == code))
    if row is None:
        row = session.scalar(
            select(MarketSeriesRow).where(MarketSeriesRow.source_series_id == code)
        )
    if row is None:
        raise HTTPException(status_code=404, detail="series not found")
    return row


@router.get("/series/{code}/observations", response_model=SeriesHistoryResponse)
def series_observations(
    code: str,
    session: Session = Depends(get_db),
    date_filter: date | None = Query(default=None, alias="date"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> SeriesHistoryResponse:
    series = _series_by_code(session, code)
    stmt = select(MarketSeriesObservationRow).where(
        MarketSeriesObservationRow.series_id == series.id
    )
    if date_filter is not None:
        stmt = stmt.where(MarketSeriesObservationRow.reference_date == date_filter)
    rows = session.scalars(
        stmt.order_by(
            MarketSeriesObservationRow.reference_date.desc(),
            MarketSeriesObservationRow.revision.desc(),
        ).limit(limit)
    ).all()
    source = session.get(SourceRow, series.source_id)
    observations = [
        SeriesObservationResponse(
            series=series.code,
            date=row.reference_date,
            value=decimal_json(Decimal(row.value)),
            unit=series.unit,
            source=source.name if source else "bcb",
            revision=row.revision,
        )
        for row in rows
    ]
    return SeriesHistoryResponse(series=series.code, unit=series.unit, observations=observations)
