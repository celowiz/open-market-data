from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from marketdata.ingestion.bcb import ingest_bcb
from marketdata.providers.bcb import BcbProvider
from marketdata.storage.models import Base, MarketSeriesObservationRow
from marketdata.storage.object_store import LocalFileObjectStorage


class SGSError(Exception):
    """Stand-in for python-bcb's SGSError."""


class PartialSgsProvider:
    name = "bcb"

    def fetch_series(self, source_series_id: str, *, start: date, end: date):
        del start, end
        if source_series_id == "1":
            raise SGSError("Value(s) not found")
        if source_series_id == "10813":
            return []
        return [(date(2026, 8, 31), Decimal("0.051660"))]


def test_ingest_bcb_skips_missing_sgs_series_and_succeeds(tmp_path) -> None:
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    session = Session(engine)
    try:
        result = ingest_bcb(
            session,
            reference_date=date(2026, 8, 31),
            storage=LocalFileObjectStorage(tmp_path),
            provider=PartialSgsProvider(),
        )
        session.commit()
        assert result["status"]
        assert int(result["inserted"]) + int(result["updated"]) + int(result["skipped"]) >= 1
        assert int(result["series_skipped"]) >= 1
        count = session.scalar(select(func.count()).select_from(MarketSeriesObservationRow))
        assert count >= 1
    finally:
        session.close()
        engine.dispose()


def test_bcb_provider_missing_sgs_values_return_empty(monkeypatch) -> None:
    def boom(*_args, **_kwargs):
        raise SGSError("Value(s) not found")

    monkeypatch.setattr("bcb.sgs.get", boom)
    rows = BcbProvider().fetch_series("1", start=date(2026, 8, 31), end=date(2026, 8, 31))
    assert rows == []
