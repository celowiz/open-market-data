from datetime import date
from io import BytesIO
from unittest.mock import MagicMock
from zipfile import ZipFile

import pytest

from marketdata.ingestion.b3 import (
    _is_empty_b3_day_error,
    backfill_b3,
)
from marketdata.ingestion.checkpoint import BackfillCheckpoint, load_checkpoint, save_checkpoint
from marketdata.providers.b3 import B3ParseError, validate_b3_zip
from marketdata.storage.object_store import LocalFileObjectStorage


class _FakeProvider:
    name = "b3"


def _ok_day(**_kwargs) -> dict[str, int | str]:
    return {
        "run_id": "test",
        "inserted": 1,
        "updated": 0,
        "skipped": 0,
        "rejected": 0,
        "artifacts": 1,
        "status": "succeeded",
    }


def test_empty_zip_error_is_skippable_for_backfill_only() -> None:
    buffer = BytesIO()
    with ZipFile(buffer, "w"):
        pass
    with pytest.raises(B3ParseError) as excinfo:
        validate_b3_zip(buffer.getvalue())
    assert _is_empty_b3_day_error(excinfo.value)
    assert not _is_empty_b3_day_error(B3ParseError("ZIP does not contain XML"))
    assert not _is_empty_b3_day_error(ValueError("B3 response is not a usable ZIP"))


def test_backfill_skips_weekends_and_checkpoints(tmp_path, monkeypatch) -> None:
    ingested: list[date] = []

    def fake_day(session, *, reference_date, **kwargs):
        ingested.append(reference_date)
        return _ok_day()

    monkeypatch.setattr("marketdata.ingestion.b3._ingest_b3_day", fake_day)
    slept: list[float] = []
    monkeypatch.setattr("marketdata.ingestion.b3.time.sleep", slept.append)

    storage = LocalFileObjectStorage(tmp_path)
    result = backfill_b3(
        MagicMock(),
        start=date(2026, 8, 21),
        end=date(2026, 8, 24),
        storage=storage,
        provider=_FakeProvider(),
        delay_seconds=0.5,
    )

    assert ingested == [date(2026, 8, 21), date(2026, 8, 24)]
    assert result["status"] == "succeeded"
    assert result["empty_days"] == 0
    assert slept == []
    checkpoint = load_checkpoint(storage, "b3")
    assert checkpoint is not None
    assert checkpoint.provider == "b3"
    assert checkpoint.start == "2026-08-21"
    assert checkpoint.end == "2026-08-24"
    assert checkpoint.last_completed == "2026-08-24"
    assert checkpoint.status == "succeeded"


def test_backfill_skips_empty_zip_without_failing(tmp_path, monkeypatch) -> None:
    def fake_day(session, *, reference_date, **kwargs):
        raise B3ParseError("B3 response is not a usable ZIP")

    monkeypatch.setattr("marketdata.ingestion.b3._ingest_b3_day", fake_day)
    storage = LocalFileObjectStorage(tmp_path)
    result = backfill_b3(
        MagicMock(),
        start=date(2026, 8, 21),
        end=date(2026, 8, 21),
        storage=storage,
        provider=_FakeProvider(),
        delay_seconds=0,
    )
    assert result["status"] == "succeeded"
    assert result["empty_days"] == 1
    checkpoint = load_checkpoint(storage, "b3")
    assert checkpoint is not None
    assert checkpoint.last_completed == "2026-08-21"
    assert checkpoint.status == "succeeded"


def test_backfill_resume_skips_completed_days(tmp_path, monkeypatch) -> None:
    ingested: list[date] = []

    def fake_day(session, *, reference_date, **kwargs):
        ingested.append(reference_date)
        return _ok_day()

    monkeypatch.setattr("marketdata.ingestion.b3._ingest_b3_day", fake_day)
    storage = LocalFileObjectStorage(tmp_path)
    save_checkpoint(
        storage,
        BackfillCheckpoint(
            provider="b3",
            start="2026-08-21",
            end="2026-08-24",
            last_completed="2026-08-21",
            status="running",
        ),
    )
    result = backfill_b3(
        MagicMock(),
        start=date(2026, 8, 21),
        end=date(2026, 8, 24),
        storage=storage,
        provider=_FakeProvider(),
        resume=True,
    )
    assert ingested == [date(2026, 8, 24)]
    assert result["status"] == "succeeded"


def test_backfill_cotahist_opt_in_calls_year_ingest(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("marketdata.ingestion.b3._ingest_b3_day", lambda *a, **k: _ok_day())
    years: list[int] = []

    def fake_cotahist(session, *, year, **kwargs):
        years.append(year)
        return {"inserted": 2, "updated": 0, "skipped": 0, "rejected": 0}

    monkeypatch.setattr("marketdata.ingestion.b3._ingest_cotahist_year", fake_cotahist)
    result = backfill_b3(
        MagicMock(),
        start=date(2024, 12, 31),
        end=date(2025, 1, 2),
        storage=LocalFileObjectStorage(tmp_path),
        provider=_FakeProvider(),
        include_cotahist=True,
    )
    assert years == [2024, 2025]
    assert result["status"] == "succeeded"


def test_backfill_without_cotahist_does_not_fetch_annual_file(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("marketdata.ingestion.b3._ingest_b3_day", lambda *a, **k: _ok_day())

    def fail_cotahist(*_args, **_kwargs):
        raise AssertionError("COTAHIST must stay opt-in")

    monkeypatch.setattr("marketdata.ingestion.b3._ingest_cotahist_year", fail_cotahist)
    result = backfill_b3(
        MagicMock(),
        start=date(2026, 8, 21),
        end=date(2026, 8, 21),
        storage=LocalFileObjectStorage(tmp_path),
        provider=_FakeProvider(),
        include_cotahist=False,
    )
    assert result["status"] == "succeeded"


def test_backfill_hard_error_does_not_checkpoint_failed_day(tmp_path, monkeypatch) -> None:
    def fake_day(session, *, reference_date, **kwargs):
        raise B3ParseError("ZIP does not contain XML")

    monkeypatch.setattr("marketdata.ingestion.b3._ingest_b3_day", fake_day)
    storage = LocalFileObjectStorage(tmp_path)
    with pytest.raises(B3ParseError, match="ZIP does not contain XML"):
        backfill_b3(
            MagicMock(),
            start=date(2026, 8, 21),
            end=date(2026, 8, 21),
            storage=storage,
            provider=_FakeProvider(),
        )
    checkpoint = load_checkpoint(storage, "b3")
    assert checkpoint is not None
    assert checkpoint.status == "failed"
    assert checkpoint.last_completed is None
