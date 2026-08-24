from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from marketdata.api.access import instrument_visible_on_public_api, public_quotes_stmt
from marketdata.api.deps import get_db
from marketdata.api.routes.funds import QuoteResponse, _to_quote
from marketdata.storage.models import InstrumentQuoteRow
from marketdata.storage.repositories import resolve_instrument_id

router = APIRouter()


class QuotesResponse(BaseModel):
    instrument_id: str
    identifier: str
    quotes: list[QuoteResponse]


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
    session: Session = Depends(get_db),
    date_filter: date | None = Query(default=None, alias="date"),
    price_type: str | None = Query(default=None),
    source: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
) -> QuotesResponse:
    instrument_id = _visible_instrument(session, identifier, source)
    stmt = public_quotes_stmt(instrument_id, source_name=source)
    if date_filter is not None:
        stmt = stmt.where(InstrumentQuoteRow.reference_date == date_filter)
    if price_type is not None:
        stmt = stmt.where(InstrumentQuoteRow.price_type == price_type)
    stmt = stmt.order_by(
        InstrumentQuoteRow.reference_date.desc(),
        InstrumentQuoteRow.price_type,
        InstrumentQuoteRow.revision.desc(),
    )
    rows = session.scalars(stmt.limit(limit)).all()
    return QuotesResponse(
        instrument_id=str(instrument_id),
        identifier=identifier,
        quotes=[_to_quote(session, row) for row in rows],
    )


@router.get("/quotes/{identifier}/latest", response_model=QuoteResponse)
def latest_quote(
    identifier: str,
    session: Session = Depends(get_db),
    price_type: str | None = Query(default=None),
    source: str | None = Query(default=None),
) -> QuoteResponse:
    instrument_id = _visible_instrument(session, identifier, source)
    stmt = public_quotes_stmt(instrument_id, source_name=source)
    if price_type is not None:
        stmt = stmt.where(InstrumentQuoteRow.price_type == price_type)
    row = session.scalar(
        stmt.order_by(InstrumentQuoteRow.reference_date.desc(), InstrumentQuoteRow.revision.desc())
    )
    if row is None:
        raise HTTPException(status_code=404, detail="quote not found")
    return _to_quote(session, row)
