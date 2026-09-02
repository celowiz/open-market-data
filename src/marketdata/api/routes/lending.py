from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from marketdata.api.deps import get_db
from marketdata.domain.errors import decimal_json
from marketdata.storage.models import LendingSnapshotRow, SourceRow
from marketdata.storage.repositories import resolve_instrument_id

router = APIRouter()


class LendingSnapshotResponse(BaseModel):
    ticker: str
    date: date
    snapshot_type: str
    qty: str | None = None
    avg_rate: str | None = None
    contracts: int | None = None
    avg_price: str | None = None
    balance_brl: str | None = None
    market: str | None = None
    source: str


class LendingResponse(BaseModel):
    identifier: str
    snapshots: list[LendingSnapshotResponse]


def _decimal_or_none(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return decimal_json(Decimal(value))


@router.get("/lending/{identifier}", response_model=LendingResponse)
def list_lending(
    identifier: str,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    limit: int = Query(default=90, ge=1, le=500),
    session: Session = Depends(get_db),
) -> LendingResponse:
    ticker = identifier.strip().upper()
    instrument_id = resolve_instrument_id(session, identifier)
    filters = [SourceRow.public_api_enabled.is_(True)]
    if instrument_id is not None:
        filters.append(
            or_(
                LendingSnapshotRow.instrument_id == instrument_id,
                LendingSnapshotRow.ticker == ticker,
            )
        )
    else:
        filters.append(LendingSnapshotRow.ticker == ticker)
    stmt = (
        select(LendingSnapshotRow, SourceRow.name)
        .join(SourceRow, SourceRow.id == LendingSnapshotRow.source_id)
        .where(*filters)
        .order_by(
            LendingSnapshotRow.reference_date.desc(),
            LendingSnapshotRow.snapshot_type.asc(),
        )
        .limit(limit)
    )
    if start is not None:
        stmt = stmt.where(LendingSnapshotRow.reference_date >= start)
    if end is not None:
        stmt = stmt.where(LendingSnapshotRow.reference_date <= end)
    rows = session.execute(stmt).all()
    if not rows:
        raise HTTPException(status_code=404, detail="lending not found")
    return LendingResponse(
        identifier=identifier,
        snapshots=[
            LendingSnapshotResponse(
                ticker=row.ticker,
                date=row.reference_date,
                snapshot_type=row.snapshot_type,
                qty=_decimal_or_none(row.qty),
                avg_rate=_decimal_or_none(row.avg_rate),
                contracts=row.contracts,
                avg_price=_decimal_or_none(row.avg_price),
                balance_brl=_decimal_or_none(row.balance_brl),
                market=row.market,
                source=source_name,
            )
            for row, source_name in rows
        ],
    )
