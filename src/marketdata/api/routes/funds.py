from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from marketdata.api.access import instrument_visible_on_public_api, public_quotes_stmt
from marketdata.api.deps import get_db
from marketdata.api.query import (
    DEFAULT_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
    apply_history_window,
    load_history_page,
    parse_history_window,
)
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
    next_cursor: date | None = None


def quote_responses(session: Session, rows: list[InstrumentQuoteRow]) -> list[QuoteResponse]:
    if not rows:
        return []
    source_ids = {row.source_id for row in rows}
    artifact_ids = {row.raw_artifact_id for row in rows if row.raw_artifact_id is not None}
    sources = {
        source.id: source.name
        for source in session.scalars(select(SourceRow).where(SourceRow.id.in_(source_ids)))
    }
    artifacts: dict[object, str] = {}
    if artifact_ids:
        artifacts = {
            artifact.id: artifact.sha256
            for artifact in session.scalars(
                select(RawArtifactRow).where(RawArtifactRow.id.in_(artifact_ids))
            )
        }
    return [
        QuoteResponse(
            date=row.reference_date,
            price=decimal_json(Decimal(row.value)),
            currency=row.currency,
            price_type=row.price_type,
            source=sources.get(row.source_id, "unknown"),
            official=row.is_official,
            revision=row.revision,
            retrieved_at=row.retrieved_at.isoformat() if row.retrieved_at else None,
            raw_artifact_sha256=(
                artifacts.get(row.raw_artifact_id) if row.raw_artifact_id is not None else None
            ),
            unit=row.unit,
        )
        for row in rows
    ]


def _to_quote(session: Session, row: InstrumentQuoteRow) -> QuoteResponse:
    return quote_responses(session, [row])[0]


@router.get("/funds/{identifier}/quotes", response_model=FundQuotesResponse)
def fund_quotes(
    identifier: str,
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    date_filter: date | None = Query(default=None, alias="date"),
    cursor: date | None = Query(default=None),
    limit: int = Query(default=DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT),
    session: Session = Depends(get_db),
) -> FundQuotesResponse:
    window = parse_history_window(start=start, end=end, date_filter=date_filter, cursor=cursor)
    instrument_id = resolve_instrument_id(session, identifier)
    if instrument_id is None or not instrument_visible_on_public_api(session, instrument_id):
        raise HTTPException(status_code=404, detail="instrument not found")
    stmt = public_quotes_stmt(instrument_id).where(
        InstrumentQuoteRow.price_type == PriceType.FUND_NAV.value,
    )
    stmt = apply_history_window(stmt, InstrumentQuoteRow.reference_date, window)
    rows, next_cursor = load_history_page(
        session,
        stmt,
        date_attr="reference_date",
        distinct_on=(InstrumentQuoteRow.reference_date,),
        order_by=(
            InstrumentQuoteRow.reference_date.desc(),
            InstrumentQuoteRow.revision.desc(),
            InstrumentQuoteRow.id.asc(),
        ),
        limit=limit,
    )
    return FundQuotesResponse(
        instrument_id=str(instrument_id),
        identifier=identifier,
        quotes=quote_responses(session, rows),
        next_cursor=next_cursor,
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
