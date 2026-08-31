from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from marketdata.domain.enums import (
    AssetClass,
    PriceType,
    QualityStatus,
    RedistributionPolicy,
)
from marketdata.ingestion.checkpoint import (
    BackfillCheckpoint,
    checkpoint_key,
    effective_last_completed,
    load_checkpoint,
    save_checkpoint,
    should_resume,
)
from marketdata.storage.models import (
    Base,
    InstrumentQuoteRow,
    InstrumentRow,
    MarketSeriesObservationRow,
    MarketSeriesRow,
)
from marketdata.storage.object_store import LocalFileObjectStorage, ObjectStorageError
from marketdata.storage.repositories import (
    get_or_create_source,
    max_observation_reference_date,
    max_quote_reference_date,
)


def test_save_and_load_checkpoint_round_trip(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    checkpoint = BackfillCheckpoint(
        provider="cvm",
        start="2018-01-01",
        end="2026-08-24",
        last_completed="2018-03",
        status="running",
    )

    save_checkpoint(store, checkpoint)

    loaded = load_checkpoint(store, "cvm")
    assert loaded == checkpoint
    assert store.exists("state/backfill/cvm.json")
    assert store.exists(checkpoint_key("cvm"))


def test_load_checkpoint_missing_key_returns_none(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    assert load_checkpoint(store, "tesouro") is None


def test_checkpoint_key_never_contains_parent_escape() -> None:
    key = checkpoint_key("bcb")
    assert ".." not in key
    assert key == "state/backfill/bcb.json"


def test_local_object_storage_rejects_parent_escape_via_store(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    with pytest.raises(ObjectStorageError, match="unsafe object key"):
        store.store("../secret", b"nope")
    with pytest.raises(ObjectStorageError, match="unsafe object key"):
        store.exists("state/backfill/../secret.json")


def test_should_resume_when_range_matches() -> None:
    checkpoint = BackfillCheckpoint(
        provider="b3",
        start="2024-01-01",
        end="2026-08-24",
        last_completed="2024-02-01",
        status="running",
    )
    assert should_resume(checkpoint, date(2024, 1, 1), date(2026, 8, 24)) is True
    assert should_resume(checkpoint, "2024-01-01", "2026-08-24", resume=True) is True


def test_should_resume_false_when_range_differs() -> None:
    checkpoint = BackfillCheckpoint(
        provider="yahoo",
        start="2020-01-01",
        end="2024-12-31",
        last_completed="2021-06-01",
        status="running",
    )
    assert should_resume(checkpoint, "2022-01-01", "2024-12-31") is False


def test_should_resume_false_when_force_or_disabled() -> None:
    checkpoint = BackfillCheckpoint(
        provider="tesouro",
        start="2002-01-01",
        end="2026-08-24",
        last_completed="2010-01-01",
        status="running",
    )
    assert should_resume(checkpoint, "2002-01-01", "2026-08-24", force=True) is False
    assert should_resume(checkpoint, "2002-01-01", "2026-08-24", resume=False) is False
    assert should_resume(None, "2002-01-01", "2026-08-24") is False


def test_effective_last_completed_uses_db_when_checkpoint_missing() -> None:
    assert (
        effective_last_completed(
            None,
            date(2024, 1, 1),
            date(2024, 12, 31),
            date(2024, 5, 10),
        )
        == "2024-05-10"
    )


def test_effective_last_completed_checkpoint_wins_if_newer() -> None:
    checkpoint = BackfillCheckpoint(
        provider="b3",
        start="2024-01-01",
        end="2024-12-31",
        last_completed="2024-05-15",
        status="running",
    )
    assert (
        effective_last_completed(
            checkpoint,
            "2024-01-01",
            "2024-12-31",
            date(2024, 5, 10),
        )
        == "2024-05-15"
    )


def test_effective_last_completed_db_wins_if_newer_than_checkpoint() -> None:
    checkpoint = BackfillCheckpoint(
        provider="b3",
        start="2024-01-01",
        end="2024-12-31",
        last_completed="2024-03-01",
        status="running",
    )
    assert (
        effective_last_completed(
            checkpoint,
            "2024-01-01",
            "2024-12-31",
            date(2024, 5, 10),
        )
        == "2024-05-10"
    )


def test_effective_last_completed_empty_db_starts_at_range_start() -> None:
    assert effective_last_completed(None, date(2024, 1, 1), date(2024, 12, 31), None) is None


def test_effective_last_completed_ignores_stale_checkpoint_range() -> None:
    checkpoint = BackfillCheckpoint(
        provider="b3",
        start="2023-01-01",
        end="2023-12-31",
        last_completed="2023-12-31",
        status="running",
    )
    assert (
        effective_last_completed(
            checkpoint,
            "2024-01-01",
            "2024-12-31",
            date(2024, 4, 1),
        )
        == "2024-04-01"
    )


def test_effective_last_completed_force_or_disabled_ignores_db() -> None:
    checkpoint = BackfillCheckpoint(
        provider="b3",
        start="2024-01-01",
        end="2024-12-31",
        last_completed="2024-05-15",
        status="running",
    )
    assert (
        effective_last_completed(
            checkpoint,
            "2024-01-01",
            "2024-12-31",
            date(2024, 5, 10),
            force=True,
        )
        is None
    )
    assert (
        effective_last_completed(
            None,
            "2024-01-01",
            "2024-12-31",
            date(2024, 5, 10),
            resume=False,
        )
        is None
    )


def _sqlite_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_quote(session: Session, *, source_name: str, reference_date: date) -> None:
    source = get_or_create_source(
        session,
        name=source_name,
        display_name=source_name.upper(),
        official=True,
        homepage="https://example.test/",
        documentation_url="https://example.test/",
        data_license="UNKNOWN",
        redistribution_policy=RedistributionPolicy.API_ONLY,
        public_api_enabled=True,
        public_dataset_enabled=False,
    )
    instrument = InstrumentRow(
        id=uuid4(),
        asset_class=AssetClass.EQUITY.value,
        instrument_type="listed",
        name="PETR4",
        currency="BRL",
    )
    session.add(instrument)
    session.flush()
    session.add(
        InstrumentQuoteRow(
            id=uuid4(),
            instrument_id=instrument.id,
            reference_date=reference_date,
            value=Decimal("32.51"),
            currency="BRL",
            unit="BRL",
            price_type=PriceType.LAST.value,
            source_id=source.id,
            is_official=True,
            retrieved_at=datetime.now(UTC),
            revision=1,
            quality_status=QualityStatus.OK.value,
        )
    )
    session.commit()


def test_max_quote_reference_date_returns_max_in_range() -> None:
    session = _sqlite_session()
    _seed_quote(session, source_name="b3", reference_date=date(2024, 3, 1))
    _seed_quote(session, source_name="b3", reference_date=date(2024, 5, 10))
    _seed_quote(session, source_name="b3", reference_date=date(2023, 12, 29))
    _seed_quote(session, source_name="cvm", reference_date=date(2024, 8, 1))

    assert max_quote_reference_date(
        session, "b3", start=date(2024, 1, 1), end=date(2024, 12, 31)
    ) == date(2024, 5, 10)


def test_max_quote_reference_date_empty_db_returns_none() -> None:
    session = _sqlite_session()
    assert (
        max_quote_reference_date(session, "b3", start=date(2024, 1, 1), end=date(2024, 12, 31))
        is None
    )


def test_max_observation_reference_date_returns_max_in_range() -> None:
    session = _sqlite_session()
    source = get_or_create_source(
        session,
        name="bcb",
        display_name="BCB",
        official=True,
        homepage="https://example.test/",
        documentation_url="https://example.test/",
        data_license="UNKNOWN",
        redistribution_policy=RedistributionPolicy.PUBLIC,
        public_api_enabled=True,
        public_dataset_enabled=True,
    )
    series = MarketSeriesRow(
        id=uuid4(),
        code="BCB:CDI_DAILY",
        source_series_id="12",
        name="CDI",
        source_id=source.id,
        unit="percent_per_day",
    )
    session.add(series)
    session.flush()
    session.add(
        MarketSeriesObservationRow(
            id=uuid4(),
            series_id=series.id,
            reference_date=date(2010, 1, 1),
            value=Decimal("0.05"),
            source_id=source.id,
            retrieved_at=datetime.now(UTC),
            revision=1,
            quality_status=QualityStatus.OK.value,
        )
    )
    session.commit()

    assert max_observation_reference_date(
        session, "bcb", start=date(2000, 1, 1), end=date(2026, 1, 1)
    ) == date(2010, 1, 1)
    assert (
        max_observation_reference_date(session, "bcb", start=date(2011, 1, 1), end=date(2026, 1, 1))
        is None
    )
