from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from marketdata.api.access import instrument_visible_on_public_api, public_quotes_stmt
from marketdata.api.deps import get_db
from marketdata.domain.enums import PriceType
from marketdata.domain.errors import decimal_json
from marketdata.storage.models import InstrumentQuoteRow, RawArtifactRow, SourceRow
from marketdata.storage.repositories import resolve_instrument_id

router = APIRouter()


class QuoteResponse(BaseModel):
    date: date
    price: str
    currency: str | None
    price_type: str
    source: str
    official: bool
    revision: int
    retrieved_at: str | None = None
    raw_artifact_sha256: str | None = None
    unit: str | None = None


class FundQuotesResponse(BaseModel):
    instrument_id: str
    identifier: str
    quotes: list[QuoteResponse]


def _source_name(session: Session, source_id) -> str:
    source = session.get(SourceRow, source_id)
    return source.name if source is not None else "unknown"


def _to_quote(session: Session, row: InstrumentQuoteRow) -> QuoteResponse:
    artifact_sha: str | None = None
    if row.raw_artifact_id is not None:
        artifact = session.get(RawArtifactRow, row.raw_artifact_id)
        if artifact is not None:
            artifact_sha = artifact.sha256
    return QuoteResponse(
        date=row.reference_date,
        price=decimal_json(Decimal(row.value)),
        currency=row.currency,
        price_type=row.price_type,
        source=_source_name(session, row.source_id),
        official=row.is_official,
        revision=row.revision,
        retrieved_at=row.retrieved_at.isoformat() if row.retrieved_at else None,
        raw_artifact_sha256=artifact_sha,
        unit=row.unit,
    )


@router.get("/funds/{identifier}/quotes", response_model=FundQuotesResponse)
def fund_quotes(
    identifier: str,
    session: Session = Depends(get_db),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    date_filter: date | None = Query(default=None, alias="date"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> FundQuotesResponse:
    instrument_id = resolve_instrument_id(session, identifier)
    if instrument_id is None or not instrument_visible_on_public_api(session, instrument_id):
        raise HTTPException(status_code=404, detail="instrument not found")
    stmt = public_quotes_stmt(instrument_id).where(
        InstrumentQuoteRow.price_type == PriceType.FUND_NAV.value,
    )
    if date_filter is not None:
        stmt = stmt.where(InstrumentQuoteRow.reference_date == date_filter)
    if start is not None:
        stmt = stmt.where(InstrumentQuoteRow.reference_date >= start)
    if end is not None:
        stmt = stmt.where(InstrumentQuoteRow.reference_date <= end)
    stmt = stmt.order_by(
        InstrumentQuoteRow.reference_date.desc(), InstrumentQuoteRow.revision.desc()
    )
    rows = session.scalars(stmt.limit(limit)).all()
    # Keep the highest revision per date.
    seen: set[date] = set()
    quotes: list[QuoteResponse] = []
    for row in rows:
        if row.reference_date in seen:
            continue
        seen.add(row.reference_date)
        quotes.append(_to_quote(session, row))
    return FundQuotesResponse(
        instrument_id=str(instrument_id), identifier=identifier, quotes=quotes
    )


@router.get("/funds/{identifier}/quotes/latest", response_model=QuoteResponse)
def fund_latest_quote(identifier: str, session: Session = Depends(get_db)) -> QuoteResponse:
    instrument_id = resolve_instrument_id(session, identifier)
    if instrument_id is None or not instrument_visible_on_public_api(session, instrument_id):
        raise HTTPException(status_code=404, detail="instrument not found")
    row = session.scalar(
        public_quotes_stmt(instrument_id)
        .where(InstrumentQuoteRow.price_type == PriceType.FUND_NAV.value)
        .order_by(InstrumentQuoteRow.reference_date.desc(), InstrumentQuoteRow.revision.desc())
    )
    if row is None:
        raise HTTPException(status_code=404, detail="quote not found")
    return _to_quote(session, row)
