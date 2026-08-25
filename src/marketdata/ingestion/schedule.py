from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

SAO_PAULO = ZoneInfo("America/Sao_Paulo")
B3_EOD_READY = time(21, 0)


def b3_ingest_reference_date(now: datetime | None = None) -> date:
    """B3 daily ingest date in America/Sao_Paulo.

    If local time is 21:00 or later, use today; otherwise use yesterday.
    Walk backward across Saturday/Sunday. Holidays are not skipped.
    """
    instant = datetime.now(tz=SAO_PAULO) if now is None else now
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=SAO_PAULO)
    else:
        instant = instant.astimezone(SAO_PAULO)
    candidate = instant.date()
    if instant.time() < B3_EOD_READY:
        candidate -= timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate


if __name__ == "__main__":
    print(b3_ingest_reference_date().isoformat())
