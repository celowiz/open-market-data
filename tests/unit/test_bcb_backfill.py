from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from marketdata.domain.enums import QualityStatus, RedistributionPolicy
from marketdata.ingestion.bcb import backfill_bcb
from marketdata.ingestion.checkpoint import BackfillCheckpoint, save_checkpoint
from marketdata.providers.bcb import SGS_SERIES, chunk_date_range
from marketdata.storage.models import (
    Base,
    InstrumentQuoteRow,
    MarketSeriesObservationRow,
    MarketSeriesRow,
)
from marketdata.storage.object_store import LocalFileObjectStorage
from marketdata.storage.repositories import get_or_create_source

BACKFILL_START = date(2000, 1, 1)
BACKFILL_END = date(2026, 1, 1)


class FakeBcbProvider:
    name = "bcb"

    def __init__(self, value: Decimal = Decimal("0.051660")) -> None:
        self.calls: list[tuple[str, date, date]] = []
        self._value = value

    def fetch_series(
        self,
        source_series_id: str,
        *,
        start: date,
        end: date,
    ) -> list[tuple[date, Decimal]]:
        self.calls.append((source_series_id, start, end))
        return [(start, self._value)]


class BoomBcbProvider:
    name = "bcb"

    def fetch_series(self, source_series_id: str, *, start: date, end: date) -> list:
        raise AssertionError("HTTP fetch must not run when observations are injected")


def _sqlite_session() -> Session:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return Session(engine)


def _safe_series_code(code: str) -> str:
    return code.replace(":", "_")


def test_chunk_date_range_respects_ten_years_on_26_year_span() -> None:
    chunks = chunk_date_range(BACKFILL_START, BACKFILL_END, years=10)
    assert chunks[0][0] == BACKFILL_START
    assert chunks[-1][1] == BACKFILL_END
    assert all((chunk_end - chunk_start).days <= 3650 for chunk_start, chunk_end in chunks)
    assert len(chunks) >= 3


def test_backfill_bcb_fetches_per_series_times_chunks_not_per_day(tmp_path) -> None:
    session = _sqlite_session()
    storage = LocalFileObjectStorage(tmp_path)
    provider = FakeBcbProvider()
    chunks = chunk_date_range(BACKFILL_START, BACKFILL_END, years=10)

    result = backfill_bcb(
        session,
        start=BACKFILL_START,
        end=BACKFILL_END,
        storage=storage,
        provider=provider,
    )
    session.commit()

    expected_calls = len(SGS_SERIES) * len(chunks)
    calendar_days = (BACKFILL_END - BACKFILL_START).days + 1
    assert len(provider.calls) == expected_calls
    assert len(provider.calls) < calendar_days
    assert {call[0] for call in provider.calls} == {series_id for _, series_id, _, _ in SGS_SERIES}
    for _series_id, chunk_start, chunk_end in provider.calls:
        assert (chunk_end - chunk_start).days <= 3650
        assert chunk_start >= BACKFILL_START
        assert chunk_end <= BACKFILL_END
    assert int(result["inserted"]) == expected_calls


def test_backfill_bcb_persists_decimal_not_float(tmp_path) -> None:
    session = _sqlite_session()
    storage = LocalFileObjectStorage(tmp_path)
    value = Decimal("0.051660")
    provider = FakeBcbProvider(value=value)

    backfill_bcb(
        session,
        start=date(2026, 1, 1),
        end=date(2026, 1, 1),
        storage=storage,
        provider=provider,
    )
    session.commit()

    rows = session.scalars(select(MarketSeriesObservationRow)).all()
    assert rows
    for row in rows:
        assert isinstance(row.value, Decimal)
        assert not isinstance(row.value, float)
        assert row.value == value


def test_backfill_bcb_does_not_write_instrument_quotes(tmp_path) -> None:
    session = _sqlite_session()
    storage = LocalFileObjectStorage(tmp_path)

    backfill_bcb(
        session,
        start=date(2026, 1, 1),
        end=date(2026, 1, 1),
        storage=storage,
        provider=FakeBcbProvider(),
    )
    session.commit()

    quote_count = session.scalar(select(func.count()).select_from(InstrumentQuoteRow))
    assert quote_count == 0


def test_backfill_bcb_injected_observations_skip_http(tmp_path) -> None:
    session = _sqlite_session()
    storage = LocalFileObjectStorage(tmp_path)
    observations = [
        (
            "BCB:CDI_DAILY",
            "12",
            "CDI",
            "percent_per_day",
            date(2026, 8, 21),
            Decimal("0.051660"),
        )
    ]

    result = backfill_bcb(
        session,
        start=date(2026, 8, 1),
        end=date(2026, 8, 31),
        storage=storage,
        provider=BoomBcbProvider(),
        observations=observations,
    )
    session.commit()

    assert int(result["inserted"]) == 1
    rows = session.scalars(select(MarketSeriesObservationRow)).all()
    assert len(rows) == 1
    assert isinstance(rows[0].value, Decimal)
    assert rows[0].value == Decimal("0.051660")


def test_backfill_bcb_stores_raw_json_per_series_chunk(tmp_path) -> None:
    session = _sqlite_session()
    storage = LocalFileObjectStorage(tmp_path)
    start = date(2000, 1, 1)
    end = date(2015, 1, 1)
    chunks = chunk_date_range(start, end, years=10)

    backfill_bcb(
        session,
        start=start,
        end=end,
        storage=storage,
        provider=FakeBcbProvider(),
    )

    for code, _series_id, _name, _unit in SGS_SERIES:
        for chunk_start, chunk_end in chunks:
            key = (
                f"raw/bcb/backfill/{_safe_series_code(code)}/"
                f"{chunk_start.isoformat()}_{chunk_end.isoformat()}.json"
            )
            assert storage.exists(key), key


def test_backfill_bcb_resume_skips_chunks_through_last_completed(tmp_path) -> None:
    session = _sqlite_session()
    storage = LocalFileObjectStorage(tmp_path)
    chunks = chunk_date_range(BACKFILL_START, BACKFILL_END, years=10)
    first_end = chunks[0][1]
    save_checkpoint(
        storage,
        BackfillCheckpoint(
            provider="bcb",
            start=BACKFILL_START.isoformat(),
            end=BACKFILL_END.isoformat(),
            last_completed=first_end.isoformat(),
            status="running",
        ),
    )
    provider = FakeBcbProvider()

    backfill_bcb(
        session,
        start=BACKFILL_START,
        end=BACKFILL_END,
        storage=storage,
        provider=provider,
        resume=True,
    )

    remaining = chunks[1:]
    assert len(provider.calls) == len(SGS_SERIES) * len(remaining)
    assert all(chunk_end > first_end for _series_id, _start, chunk_end in provider.calls)


def test_backfill_bcb_recent_observation_does_not_skip_earlier_chunks(tmp_path) -> None:
    """Daily ingest writes a recent date; that must not skip historical chunks."""
    session = _sqlite_session()
    storage = LocalFileObjectStorage(tmp_path)
    chunks = chunk_date_range(BACKFILL_START, BACKFILL_END, years=10)
    source = get_or_create_source(
        session,
        name="bcb",
        display_name="BCB",
        official=True,
        homepage="https://www.bcb.gov.br/",
        documentation_url="https://www.bcb.gov.br/",
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
            reference_date=BACKFILL_END,
            value=Decimal("0.05"),
            source_id=source.id,
            retrieved_at=datetime.now(UTC),
            revision=1,
            quality_status=QualityStatus.OK.value,
        )
    )
    session.commit()
    provider = FakeBcbProvider()
    backfill_bcb(
        session,
        start=BACKFILL_START,
        end=BACKFILL_END,
        storage=storage,
        provider=provider,
        resume=True,
    )
    assert len(provider.calls) == len(SGS_SERIES) * len(chunks)


def test_backfill_bcb_commits_completed_chunk_if_later_chunk_fails(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'bcb.db'}", future=True)
    Base.metadata.create_all(engine)
    session = Session(engine)
    chunks = chunk_date_range(BACKFILL_START, BACKFILL_END, years=10)
    first_end = chunks[0][1]

    class BoomAfterFirstChunk:
        name = "bcb"

        def fetch_series(self, source_series_id: str, *, start: date, end: date) -> list:
            if start > first_end:
                raise RuntimeError("chunk 2 failed")
            return [(start, Decimal("0.051660"))]

    with pytest.raises(RuntimeError, match="chunk 2 failed"):
        backfill_bcb(
            session,
            start=BACKFILL_START,
            end=BACKFILL_END,
            storage=LocalFileObjectStorage(tmp_path),
            provider=BoomAfterFirstChunk(),
        )

    other = Session(engine)
    try:
        count = other.scalar(select(func.count()).select_from(MarketSeriesObservationRow))
        assert count == len(SGS_SERIES)
    finally:
        other.close()
        session.close()
        engine.dispose()
