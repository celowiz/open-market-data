from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from marketdata.api.deps import get_db
from marketdata.storage.models import EventRow
from marketdata.storage.repositories import resolve_instrument_id

router = APIRouter()


class EventResponse(BaseModel):
    ticker: str
    source: str
    event_type: str
    occurred_at: datetime
    headline: str
    url: str | None = None
    external_id: str


class EventsResponse(BaseModel):
    identifier: str
    events: list[EventResponse]


@router.get("/events/{identifier}", response_model=EventsResponse)
def list_events(
    identifier: str,
    event_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    session: Session = Depends(get_db),
) -> EventsResponse:
    ticker = identifier.strip().upper()
    instrument_id = resolve_instrument_id(session, identifier)
    stmt = select(EventRow).order_by(EventRow.occurred_at.desc()).limit(limit)
    if instrument_id is not None:
        stmt = stmt.where(
            or_(EventRow.instrument_id == instrument_id, EventRow.ticker == ticker)
        )
    else:
        stmt = stmt.where(EventRow.ticker == ticker)
    if event_type:
        stmt = stmt.where(EventRow.event_type == event_type)
    rows = session.scalars(stmt).all()
    if not rows:
        raise HTTPException(status_code=404, detail="events not found")
    return EventsResponse(
        identifier=identifier,
        events=[
            EventResponse(
                ticker=row.ticker,
                source=row.source,
                event_type=row.event_type,
                occurred_at=row.occurred_at,
                headline=row.headline,
                url=row.url,
                external_id=row.external_id,
            )
            for row in rows
        ],
    )
