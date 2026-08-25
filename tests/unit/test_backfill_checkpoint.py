from datetime import date

import pytest

from marketdata.ingestion.checkpoint import (
    BackfillCheckpoint,
    checkpoint_key,
    load_checkpoint,
    save_checkpoint,
    should_resume,
)
from marketdata.storage.object_store import LocalFileObjectStorage, ObjectStorageError


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
