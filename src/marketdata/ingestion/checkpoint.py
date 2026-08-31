from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date

from marketdata.storage.object_store import ObjectStorage


@dataclass(frozen=True)
class BackfillCheckpoint:
    provider: str
    start: str
    end: str
    last_completed: str | None  # ISO date or "YYYY-MM" or "YYYY" depending on provider
    status: str  # running | succeeded | failed


def checkpoint_key(provider: str) -> str:
    return f"state/backfill/{provider}.json"


def load_checkpoint(store: ObjectStorage, provider: str) -> BackfillCheckpoint | None:
    key = checkpoint_key(provider)
    if not store.exists(key):
        return None
    payload = json.loads(store.retrieve(key).decode("utf-8"))
    return BackfillCheckpoint(**payload)


def save_checkpoint(store: ObjectStorage, checkpoint: BackfillCheckpoint) -> None:
    store.store(
        checkpoint_key(checkpoint.provider),
        json.dumps(asdict(checkpoint), indent=2).encode("utf-8"),
        content_type="application/json",
    )


def _as_range_token(value: date | str) -> str:
    return value.isoformat() if isinstance(value, date) else value


def should_resume(
    checkpoint: BackfillCheckpoint | None,
    start: date | str,
    end: date | str,
    *,
    resume: bool = True,
    force: bool = False,
) -> bool:
    """Return True when backfill should continue after ``last_completed``.

    Resume when ``resume`` is true, ``force`` is false, a checkpoint exists, and
    its stored ``start``/``end`` match the requested range. Differing ranges
    start fresh. ``force`` always starts fresh.
    """
    if checkpoint is None or force or not resume:
        return False
    return checkpoint.start == _as_range_token(start) and checkpoint.end == _as_range_token(end)


def _completed_token(value: date | str | None) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, date) else value


def effective_last_completed(
    checkpoint: BackfillCheckpoint | None,
    start: date | str,
    end: date | str,
    db_last: date | str | None,
    *,
    resume: bool = True,
    force: bool = False,
) -> str | None:
    """Return the later of a matching checkpoint and a persisted max date.

    GitHub-hosted runners are ephemeral, so ``state/backfill/*.json`` is often
    missing. ``db_last`` is ``max(reference_date)`` already stored for that
    source in ``[start, end]``. A newer checkpoint still wins (weekends and
    empty days are checkpointed without quotes). ``--force`` / ``resume=False``
    ignore both and start at ``start``.
    """
    if force or not resume:
        return None
    file_last = None
    if should_resume(checkpoint, start, end, resume=True, force=False):
        file_last = checkpoint.last_completed if checkpoint is not None else None
    candidates = [token for token in (file_last, _completed_token(db_last)) if token]
    if not candidates:
        return None
    return max(candidates)
