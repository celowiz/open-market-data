from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from marketdata.ingestion.schedule import b3_ingest_reference_date

BRT = ZoneInfo("America/Sao_Paulo")


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        # Monday 21:00 BRT → that Monday (EOD files are expected).
        (datetime(2026, 8, 24, 21, 0, tzinfo=BRT), date(2026, 8, 24)),
        # Monday 20:59 BRT → Sunday, then skip weekend to Friday.
        (datetime(2026, 8, 24, 20, 59, 59, tzinfo=BRT), date(2026, 8, 21)),
        # GitHub ingest-b3 cron: Tuesday 00:00 UTC = Monday 21:00 BRT.
        (datetime(2026, 8, 25, 0, 0, tzinfo=UTC), date(2026, 8, 24)),
        # Saturday 00:00 UTC = Friday 21:00 BRT.
        (datetime(2026, 8, 29, 0, 0, tzinfo=UTC), date(2026, 8, 28)),
        # Saturday morning BRT still maps to Friday.
        (datetime(2026, 8, 29, 10, 0, tzinfo=BRT), date(2026, 8, 28)),
        # Sunday after the cutoff is still a weekend → Friday.
        (datetime(2026, 8, 30, 22, 0, tzinfo=BRT), date(2026, 8, 28)),
        # Friday before 21:00 → Thursday.
        (datetime(2026, 8, 28, 20, 0, tzinfo=BRT), date(2026, 8, 27)),
        # Naive clock is treated as America/Sao_Paulo local time.
        (datetime(2026, 8, 24, 21, 0), date(2026, 8, 24)),
    ],
)
def test_b3_ingest_reference_date(now: datetime, expected: date) -> None:
    assert b3_ingest_reference_date(now) == expected
