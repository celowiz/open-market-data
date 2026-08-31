from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from marketdata.api.access import (
    instrument_visible_on_public_api,
    public_quotes_with_provenance_stmt,
)
from marketdata.api.deps import get_db
from marketdata.api.query import (
    DEFAULT_HISTORY_LIMIT,
    MAX_HISTORY_LIMIT,
    apply_history_window,
    load_history_result_rows,
    parse_history_window,
)
from marketdata.domain.enums import PriceType
from marketdata.domain.errors import decimal_json
from marketdata.storage.models import InstrumentQuoteRow
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


def quote_from_parts(
    row: InstrumentQuoteRow, source_name: str, artifact_sha: str | None
) -> QuoteResponse:
    return QuoteResponse(
        date=row.reference_date,
        price=decimal_json(Decimal(row.value)),
        currency=row.currency,
        price_type=row.price_type,
        source=source_name or "unknown",
        official=row.is_official,
        revision=row.revision,
        retrieved_at=row.retrieved_at.isoformat() if row.retrieved_at else None,
        raw_artifact_sha256=artifact_sha,
        unit=row.unit,
    )


def quotes_from_joined_rows(rows: list[Any]) -> list[QuoteResponse]:
    return [quote_from_parts(quote, source_name, sha) for quote, source_name, sha in rows]


def _latest_public_quote(
    session: Session,
    instrument_id: UUID,
    *,
    source_name: str | None = None,
    price_type: str | None = None,
) -> QuoteResponse:
    stmt = public_quotes_with_provenance_stmt(instrument_id, source_name=source_name)
    if price_type is not None:
        stmt = stmt.where(InstrumentQuoteRow.price_type == price_type)
    joined = session.execute(
        stmt.order_by(
            InstrumentQuoteRow.reference_date.desc(), InstrumentQuoteRow.revision.desc()
        ).limit(1)
    ).first()
    if joined is None:
        raise HTTPException(status_code=404, detail="quote not found")
    quote, source_name_value, sha = joined
    return quote_from_parts(quote, source_name_value, sha)


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
    stmt = public_quotes_with_provenance_stmt(instrument_id).where(
        InstrumentQuoteRow.price_type == PriceType.FUND_NAV.value,
    )
    stmt = apply_history_window(stmt, InstrumentQuoteRow.reference_date, window)
    rows, next_cursor = load_history_result_rows(
        session,
        stmt,
        date_of=lambda row: row[0].reference_date,
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
        quotes=quotes_from_joined_rows(rows),
        next_cursor=next_cursor,
    )


@router.get("/funds/{identifier}/quotes/latest", response_model=QuoteResponse)
def fund_latest_quote(identifier: str, session: Session = Depends(get_db)) -> QuoteResponse:
    instrument_id = resolve_instrument_id(session, identifier)
    if instrument_id is None or not instrument_visible_on_public_api(session, instrument_id):
        raise HTTPException(status_code=404, detail="instrument not found")
    return _latest_public_quote(session, instrument_id, price_type=PriceType.FUND_NAV.value)
