from datetime import date

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
from marketdata.api.routes.funds import QuoteResponse, _latest_public_quote, quotes_from_joined_rows
from marketdata.api.span import load_instrument_spans
from marketdata.storage.models import InstrumentQuoteRow
from marketdata.storage.repositories import resolve_instrument_id

router = APIRouter()


class QuotesResponse(BaseModel):
    instrument_id: str
    identifier: str
    quotes: list[QuoteResponse]
    next_cursor: date | None = None
    first_quote_date: date | None = None
    last_quote_date: date | None = None
    quote_count: int | None = None


def _visible_instrument(session: Session, identifier: str, source_name: str | None):
    instrument_id = resolve_instrument_id(session, identifier)
    if instrument_id is None or not instrument_visible_on_public_api(
        session, instrument_id, source_name=source_name
    ):
        raise HTTPException(status_code=404, detail="instrument not found")
    return instrument_id


@router.get("/quotes/{identifier}", response_model=QuotesResponse)
@router.get("/quotes/{identifier}/history", response_model=QuotesResponse)
def list_quotes(
    identifier: str,
    date_filter: date | None = Query(default=None, alias="date"),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    cursor: date | None = Query(default=None),
    price_type: str | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_HISTORY_LIMIT, ge=1, le=MAX_HISTORY_LIMIT),
    session: Session = Depends(get_db),
) -> QuotesResponse:
    window = parse_history_window(start=start, end=end, date_filter=date_filter, cursor=cursor)
    instrument_id = _visible_instrument(session, identifier, source)
    stmt = public_quotes_with_provenance_stmt(instrument_id, source_name=source)
    stmt = apply_history_window(stmt, InstrumentQuoteRow.reference_date, window)
    if price_type is not None:
        stmt = stmt.where(InstrumentQuoteRow.price_type == price_type)
    rows, next_cursor = load_history_result_rows(
        session,
        stmt,
        date_of=lambda row: row[0].reference_date,
        distinct_on=(InstrumentQuoteRow.reference_date, InstrumentQuoteRow.price_type),
        order_by=(
            InstrumentQuoteRow.reference_date.desc(),
            InstrumentQuoteRow.price_type.asc(),
            InstrumentQuoteRow.revision.desc(),
            InstrumentQuoteRow.id.asc(),
        ),
        limit=limit,
    )
    span = load_instrument_spans(session, [instrument_id], source_name=source).get(instrument_id)
    return QuotesResponse(
        instrument_id=str(instrument_id),
        identifier=identifier,
        quotes=quotes_from_joined_rows(rows),
        next_cursor=next_cursor,
        first_quote_date=span.min_date if span is not None else None,
        last_quote_date=span.max_date if span is not None else None,
        quote_count=span.quote_count if span is not None else 0,
    )


@router.get("/quotes/{identifier}/latest", response_model=QuoteResponse)
def latest_quote(
    identifier: str,
    session: Session = Depends(get_db),
    price_type: str | None = Query(default=None),
    source: str | None = Query(default=None),
) -> QuoteResponse:
    instrument_id = _visible_instrument(session, identifier, source)
    return _latest_public_quote(session, instrument_id, source_name=source, price_type=price_type)
