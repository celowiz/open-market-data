from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, or_, select
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
    sources: list[str] = []


class InstrumentsResponse(BaseModel):
    instruments: list[InstrumentSearchItem]
    next_cursor: str | None = None


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _parse_cursor(cursor: str | None) -> UUID | None:
    stripped = _optional_text(cursor)
    if stripped is None:
        return None
    try:
        return UUID(stripped)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="cursor must be an instrument_id") from exc


def _ilike_contains(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _visible_instrument_ids(*, source_name: str | None = None):
    stmt = (
        select(InstrumentQuoteRow.instrument_id)
        .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
        .where(SourceRow.public_api_enabled.is_(True))
    )
    if source_name is not None:
        stmt = stmt.where(SourceRow.name == source_name)
    return stmt.distinct()


def _matching_instrument_ids(*, q: str):
    pattern = _ilike_contains(q)
    return (
        select(InstrumentRow.id)
        .outerjoin(
            InstrumentIdentifierRow,
            InstrumentIdentifierRow.instrument_id == InstrumentRow.id,
        )
        .where(
            or_(
                InstrumentRow.name.ilike(pattern, escape="\\"),
                InstrumentIdentifierRow.identifier_value.ilike(pattern, escape="\\"),
            )
        )
        .distinct()
    )


def _public_identifier_values_by_instrument(
    session: Session, instrument_ids: list[UUID]
) -> dict[UUID, list[str]]:
    result: dict[UUID, list[str]] = {instrument_id: [] for instrument_id in instrument_ids}
    if not instrument_ids:
        return result
    rows = session.execute(
        select(
            InstrumentIdentifierRow.instrument_id,
            InstrumentIdentifierRow.identifier_value,
            InstrumentIdentifierRow.source_id,
        )
        .where(InstrumentIdentifierRow.instrument_id.in_(instrument_ids))
        .order_by(InstrumentIdentifierRow.identifier_value)
    ).all()
    source_ids = {source_id for _, _, source_id in rows if source_id is not None}
    sources_by_id: dict[UUID, SourceRow] = {}
    if source_ids:
        for source in session.scalars(select(SourceRow).where(SourceRow.id.in_(source_ids))):
            sources_by_id[source.id] = source
    seen: dict[UUID, set[str]] = {instrument_id: set() for instrument_id in instrument_ids}
    for instrument_id, value, source_id in rows:
        if source_id is not None:
            source = sources_by_id.get(source_id)
            if source is None or not source_row_allows_public_api(source):
                continue
        if value not in seen[instrument_id]:
            seen[instrument_id].add(value)
            result[instrument_id].append(value)
    return result


def _public_source_names_by_instrument(
    session: Session, instrument_ids: list[UUID]
) -> dict[UUID, list[str]]:
    result: dict[UUID, list[str]] = {instrument_id: [] for instrument_id in instrument_ids}
    if not instrument_ids:
        return result
    rows = session.execute(
        select(InstrumentQuoteRow.instrument_id, SourceRow.name)
        .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
        .where(
            InstrumentQuoteRow.instrument_id.in_(instrument_ids),
            SourceRow.public_api_enabled.is_(True),
        )
        .distinct()
        .order_by(InstrumentQuoteRow.instrument_id, SourceRow.name)
    ).all()
    for instrument_id, name in rows:
        if name not in result[instrument_id]:
            result[instrument_id].append(name)
    return result


def _keyset_after(name: str, instrument_id: UUID):
    return or_(
        InstrumentRow.name > name,
        and_(InstrumentRow.name == name, InstrumentRow.id > instrument_id),
    )


@router.get("/instruments", response_model=InstrumentsResponse)
def search_instruments(
    q: str = Query(default=""),
    source: str | None = Query(default=None),
    asset_class: str | None = Query(default=None),
    cursor: str | None = Query(default=None),
    limit: int = Query(default=DEFAULT_INSTRUMENT_LIMIT, ge=1, le=MAX_INSTRUMENT_LIMIT),
    session: Session = Depends(get_db),
) -> InstrumentsResponse:
    query = _optional_text(q)
    source_name = _optional_text(source)
    asset_class_name = _optional_text(asset_class)
    cursor_id = _parse_cursor(cursor)

    stmt = (
        select(InstrumentRow)
        .where(InstrumentRow.id.in_(_visible_instrument_ids(source_name=source_name)))
        .order_by(InstrumentRow.name, InstrumentRow.id)
    )
    if query is not None:
        stmt = stmt.where(InstrumentRow.id.in_(_matching_instrument_ids(q=query)))
    if asset_class_name is not None:
        stmt = stmt.where(InstrumentRow.asset_class == asset_class_name)
    if cursor_id is not None:
        cursor_row = session.get(InstrumentRow, cursor_id)
        if cursor_row is None:
            raise HTTPException(status_code=400, detail="cursor is invalid")
        stmt = stmt.where(_keyset_after(cursor_row.name, cursor_row.id))

    rows = list(session.scalars(stmt.limit(limit + 1)).all())
    page = rows[:limit]
    next_cursor = str(page[-1].id) if len(rows) > limit else None
    instrument_ids = [instrument.id for instrument in page]
    identifiers = _public_identifier_values_by_instrument(session, instrument_ids)
    sources = _public_source_names_by_instrument(session, instrument_ids)
    return InstrumentsResponse(
        instruments=[
            InstrumentSearchItem(
                instrument_id=str(instrument.id),
                name=instrument.name,
                asset_class=instrument.asset_class,
                identifiers=identifiers[instrument.id],
                sources=sources[instrument.id],
            )
            for instrument in page
        ],
        next_cursor=next_cursor,
    )
