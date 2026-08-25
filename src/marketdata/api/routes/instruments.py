from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from marketdata.api.access import source_row_allows_public_api
from marketdata.api.deps import get_db
from marketdata.storage.models import (
    InstrumentIdentifierRow,
    InstrumentQuoteRow,
    InstrumentRow,
    SourceRow,
)

router = APIRouter()

DEFAULT_INSTRUMENT_LIMIT = 20
MAX_INSTRUMENT_LIMIT = 100


class InstrumentSearchItem(BaseModel):
    instrument_id: str
    name: str
    asset_class: str
    identifiers: list[str]


class InstrumentsResponse(BaseModel):
    instruments: list[InstrumentSearchItem]


def require_search_q(q: str = Query(default="")) -> str:
    stripped = q.strip()
    if not stripped:
        raise HTTPException(status_code=400, detail="q is required")
    return stripped


def _ilike_contains(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _visible_instrument_ids():
    return (
        select(InstrumentQuoteRow.instrument_id)
        .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
        .where(SourceRow.public_api_enabled.is_(True))
        .distinct()
    )


def _public_identifier_values(session: Session, instrument_id) -> list[str]:
    rows = session.execute(
        select(InstrumentIdentifierRow.identifier_value, InstrumentIdentifierRow.source_id)
        .where(InstrumentIdentifierRow.instrument_id == instrument_id)
        .order_by(InstrumentIdentifierRow.identifier_value)
    ).all()
    values: list[str] = []
    seen: set[str] = set()
    for value, source_id in rows:
        if source_id is not None:
            source = session.get(SourceRow, source_id)
            if source is None or not source_row_allows_public_api(source):
                continue
        if value not in seen:
            seen.add(value)
            values.append(value)
    return values


@router.get("/instruments", response_model=InstrumentsResponse)
def search_instruments(
    q: str = Depends(require_search_q),
    limit: int = Query(default=DEFAULT_INSTRUMENT_LIMIT, ge=1, le=MAX_INSTRUMENT_LIMIT),
    session: Session = Depends(get_db),
) -> InstrumentsResponse:
    pattern = _ilike_contains(q)
    matching_ids = (
        select(InstrumentRow.id)
        .outerjoin(
            InstrumentIdentifierRow,
            InstrumentIdentifierRow.instrument_id == InstrumentRow.id,
        )
        .where(
            InstrumentRow.id.in_(_visible_instrument_ids()),
            or_(
                InstrumentRow.name.ilike(pattern, escape="\\"),
                InstrumentIdentifierRow.identifier_value.ilike(pattern, escape="\\"),
            ),
        )
        .distinct()
    )
    stmt = (
        select(InstrumentRow)
        .where(InstrumentRow.id.in_(matching_ids))
        .order_by(InstrumentRow.name, InstrumentRow.id)
        .limit(limit)
    )
    instruments = session.scalars(stmt).all()
    return InstrumentsResponse(
        instruments=[
            InstrumentSearchItem(
                instrument_id=str(instrument.id),
                name=instrument.name,
                asset_class=instrument.asset_class,
                identifiers=_public_identifier_values(session, instrument.id),
            )
            for instrument in instruments
        ]
    )
