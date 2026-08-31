from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from marketdata.storage.models import InstrumentQuoteRow, RawArtifactRow, SourceRow


def source_allows_public_api(*, public_api_enabled: bool, redistribution_policy: str) -> bool:
    _ = redistribution_policy
    return public_api_enabled


def source_row_allows_public_api(row: SourceRow) -> bool:
    return source_allows_public_api(
        public_api_enabled=row.public_api_enabled,
        redistribution_policy=row.redistribution_policy,
    )


def _public_quote_filters(instrument_id: UUID, *, source_name: str | None):
    filters = [
        InstrumentQuoteRow.instrument_id == instrument_id,
        SourceRow.public_api_enabled.is_(True),
    ]
    if source_name is not None:
        filters.append(SourceRow.name == source_name)
    return filters


def public_quotes_stmt(
    instrument_id: UUID, *, source_name: str | None = None
) -> Select[tuple[InstrumentQuoteRow]]:
    return (
        select(InstrumentQuoteRow)
        .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
        .where(*_public_quote_filters(instrument_id, source_name=source_name))
    )


def public_quotes_with_provenance_stmt(
    instrument_id: UUID, *, source_name: str | None = None
) -> Select[Any]:
    """One statement: quote row + source name + artifact sha256 (LEFT JOIN)."""
    return (
        select(InstrumentQuoteRow, SourceRow.name, RawArtifactRow.sha256)
        .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
        .outerjoin(RawArtifactRow, RawArtifactRow.id == InstrumentQuoteRow.raw_artifact_id)
        .where(*_public_quote_filters(instrument_id, source_name=source_name))
    )


def public_quote_exists_stmt(
    instrument_id: UUID, *, source_name: str | None = None
) -> Select[tuple[UUID]]:
    return (
        select(InstrumentQuoteRow.id)
        .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
        .where(*_public_quote_filters(instrument_id, source_name=source_name))
        .limit(1)
    )


def instrument_visible_on_public_api(
    session: Session,
    instrument_id: UUID,
    *,
    source_name: str | None = None,
) -> bool:
    return (
        session.scalar(public_quote_exists_stmt(instrument_id, source_name=source_name)) is not None
    )


def series_source_visible_on_public_api(session: Session, source_id: UUID) -> bool:
    row = session.get(SourceRow, source_id)
    return row is not None and source_row_allows_public_api(row)
