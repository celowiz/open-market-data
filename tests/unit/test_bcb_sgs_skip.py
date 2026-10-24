from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from marketdata.ingestion.bcb import ingest_bcb
from marketdata.providers.bcb import BcbProvider, parse_sgs_json
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

    monkeypatch.setattr("bcb.sgs.get_json", boom)
    rows = BcbProvider().fetch_series("1", start=date(2026, 8, 31), end=date(2026, 8, 31))
    assert rows == []


def test_bcb_provider_empty_200_payload_returns_empty(monkeypatch) -> None:
    """SGS sometimes answers HTTP 200 with ``[]`` before the day's value is published.

    python-bcb 0.4.0 ``sgs.get`` crashed on that with ``KeyError: "None of ['Date'] ..."``
    (Ingest BCB failures 2026-10-13..22).
    """
    monkeypatch.setattr("bcb.sgs.get_json", lambda *_a, **_k: "[]")
    rows = BcbProvider().fetch_series("12", start=date(2026, 10, 22), end=date(2026, 10, 22))
    assert rows == []


def test_bcb_provider_parses_sgs_json(monkeypatch) -> None:
    payload = '[{"data":"22/10/2026","valor":"0.050788"},{"data":"23/10/2026","valor":""}]'
    monkeypatch.setattr("bcb.sgs.get_json", lambda *_a, **_k: payload)
    rows = BcbProvider().fetch_series("11", start=date(2026, 10, 22), end=date(2026, 10, 23))
    assert rows == [(date(2026, 10, 22), Decimal("0.050788"))]


def test_parse_sgs_json_handles_error_and_empty_payloads() -> None:
    assert parse_sgs_json("") == []
    assert parse_sgs_json("null") == []
    assert parse_sgs_json('{"erro":{"statusCode":404,"detail":"Value(s) not found"}}') == []
    assert parse_sgs_json(b'[{"data":"01/10/2026","valor":"5.4321"}]') == [
        (date(2026, 10, 1), Decimal("5.4321"))
    ]
