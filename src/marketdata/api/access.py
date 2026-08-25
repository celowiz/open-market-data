from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from marketdata.storage.models import InstrumentQuoteRow, SourceRow


def source_allows_public_api(*, public_api_enabled: bool, redistribution_policy: str) -> bool:
    _ = redistribution_policy
    return public_api_enabled


def source_row_allows_public_api(row: SourceRow) -> bool:
    return source_allows_public_api(
        public_api_enabled=row.public_api_enabled,
        redistribution_policy=row.redistribution_policy,
    )


def public_quotes_stmt(
    instrument_id: UUID, *, source_name: str | None = None
) -> Select[tuple[InstrumentQuoteRow]]:
    stmt = (
        select(InstrumentQuoteRow)
        .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
        .where(
            InstrumentQuoteRow.instrument_id == instrument_id,
            SourceRow.public_api_enabled.is_(True),
        )
    )
    if source_name is not None:
        stmt = stmt.where(SourceRow.name == source_name)
    return stmt


def instrument_visible_on_public_api(
    session: Session,
    instrument_id: UUID,
    *,
    source_name: str | None = None,
) -> bool:
    return (
        session.scalar(public_quotes_stmt(instrument_id, source_name=source_name).limit(1))
        is not None
    )


def series_source_visible_on_public_api(session: Session, source_id: UUID) -> bool:
    row = session.get(SourceRow, source_id)
    return row is not None and source_row_allows_public_api(row)
