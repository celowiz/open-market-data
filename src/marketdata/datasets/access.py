from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from marketdata.domain.enums import PUBLIC_DATASET_POLICIES, RedistributionPolicy
from marketdata.storage.models import (
    InstrumentQuoteRow,
    MarketSeriesObservationRow,
    SourceRow,
)

PUBLIC_DATASET_POLICY_VALUES = tuple(policy.value for policy in PUBLIC_DATASET_POLICIES)


def source_allows_public_dataset(
    *, public_dataset_enabled: bool, redistribution_policy: str
) -> bool:
    try:
        policy = RedistributionPolicy(redistribution_policy)
    except ValueError:
        return False
    return public_dataset_enabled and policy in PUBLIC_DATASET_POLICIES


def source_row_allows_public_dataset(row: SourceRow) -> bool:
    return source_allows_public_dataset(
        public_dataset_enabled=row.public_dataset_enabled,
        redistribution_policy=row.redistribution_policy,
    )


def dataset_eligible_sources_stmt() -> Select[tuple[SourceRow]]:
    return select(SourceRow).where(
        SourceRow.public_dataset_enabled.is_(True),
        SourceRow.redistribution_policy.in_(PUBLIC_DATASET_POLICY_VALUES),
    )


def public_dataset_quotes_stmt(
    instrument_id: UUID | None = None, *, source_name: str | None = None
) -> Select[tuple[InstrumentQuoteRow]]:
    stmt = (
        select(InstrumentQuoteRow)
        .join(SourceRow, SourceRow.id == InstrumentQuoteRow.source_id)
        .where(
            SourceRow.public_dataset_enabled.is_(True),
            SourceRow.redistribution_policy.in_(PUBLIC_DATASET_POLICY_VALUES),
        )
    )
    if instrument_id is not None:
        stmt = stmt.where(InstrumentQuoteRow.instrument_id == instrument_id)
    if source_name is not None:
        stmt = stmt.where(SourceRow.name == source_name)
    return stmt


def public_dataset_observations_stmt() -> Select[tuple[MarketSeriesObservationRow]]:
    return (
        select(MarketSeriesObservationRow)
        .join(SourceRow, SourceRow.id == MarketSeriesObservationRow.source_id)
        .where(
            SourceRow.public_dataset_enabled.is_(True),
            SourceRow.redistribution_policy.in_(PUBLIC_DATASET_POLICY_VALUES),
        )
    )


def source_visible_on_public_dataset(session: Session, source_id: UUID) -> bool:
    row = session.get(SourceRow, source_id)
    return row is not None and source_row_allows_public_dataset(row)
