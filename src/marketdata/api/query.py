from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import HTTPException
from sqlalchemy import Select
from sqlalchemy.orm import Session

DEFAULT_HISTORY_LIMIT = 500
MAX_HISTORY_LIMIT = 5000


@dataclass(frozen=True)
class HistoryWindow:
    start: date | None
    end: date | None


def parse_history_window(
    *,
    start: date | None = None,
    end: date | None = None,
    date_filter: date | None = None,
    cursor: date | None = None,
) -> HistoryWindow:
    if start is not None and end is not None and start > end:
        raise HTTPException(status_code=422, detail="start must be on or before end")
    if date_filter is not None:
        if start is not None and start != date_filter:
            raise HTTPException(
                status_code=422, detail="date must be consistent with start and end"
            )
        if end is not None and end != date_filter:
            raise HTTPException(
                status_code=422, detail="date must be consistent with start and end"
            )
        start = date_filter
        end = date_filter
    if cursor is not None:
        end = cursor if end is None else min(end, cursor)
    return HistoryWindow(start=start, end=end)


def apply_history_window(stmt: Select[Any], column: Any, window: HistoryWindow) -> Select[Any]:
    if window.start is not None:
        stmt = stmt.where(column >= window.start)
    if window.end is not None:
        stmt = stmt.where(column <= window.end)
    return stmt


def paginate_by_date[T](
    rows: Sequence[T],
    *,
    limit: int,
    date_of: Callable[[T], date],
) -> tuple[list[T], date | None]:
    if not rows:
        return [], None
    if len(rows) <= limit:
        return list(rows), None
    overflow_date = date_of(rows[limit])
    page = [row for row in rows[:limit] if date_of(row) != overflow_date]
    if not page:
        first_date = date_of(rows[0])
        page = [row for row in rows if date_of(row) == first_date]
        older = [row for row in rows if date_of(row) != first_date]
        return page, date_of(older[0]) if older else None
    return page, overflow_date


def load_history_page(
    session: Session,
    stmt: Select[Any],
    *,
    date_attr: str,
    distinct_on: tuple[Any, ...],
    order_by: tuple[Any, ...],
    limit: int,
) -> tuple[list[Any], date | None]:
    page_stmt = stmt.distinct(*distinct_on).order_by(*order_by).limit(limit + 1)
    rows = list(session.scalars(page_stmt).all())
    return paginate_by_date(rows, limit=limit, date_of=lambda row: getattr(row, date_attr))
