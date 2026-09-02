from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from marketdata.api.main import create_app
from marketdata.config import get_settings
from marketdata.domain.enums import IdentifierType, PriceType, RedistributionPolicy
from marketdata.ingestion.b3 import ingest_b3
from marketdata.ingestion.yahoo import ingest_yahoo
from marketdata.providers.yahoo import YahooQuoteRecord
from marketdata.storage.database import create_db_engine, create_session_factory
from marketdata.storage.models import (
    Base,
    InstrumentIdentifierRow,
    InstrumentQuoteRow,
    SourceRow,
)
from marketdata.storage.object_store import LocalFileObjectStorage
from marketdata.storage.repositories import resolve_instrument_id

B3_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "b3"


def _nested_zip(outer_name: str, inner_name: str, xml: bytes) -> bytes:
    inner_buffer = BytesIO()
    with ZipFile(inner_buffer, "w") as inner:
        inner.writestr(inner_name, xml)
    outer_buffer = BytesIO()
    with ZipFile(outer_buffer, "w") as outer:
        outer.writestr(outer_name, inner_buffer.getvalue())
    return outer_buffer.getvalue()


@pytest.fixture
def db_session():
    settings = get_settings()
    if not settings.database_url:
        pytest.skip("DATABASE_URL is not configured")
    factory = create_session_factory(create_db_engine(settings))
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _aapl_close() -> YahooQuoteRecord:
    return YahooQuoteRecord(
        symbol="AAPL",
        reference_date=date(2026, 8, 21),
        value=Decimal("185.64"),
        currency="USD",
    )


@pytest.mark.db
def test_yahoo_ingest_persists_unofficial_close(db_session, tmp_path) -> None:
    storage = LocalFileObjectStorage(tmp_path)
    first = ingest_yahoo(
        db_session,
        reference_date=date(2026, 8, 21),
        symbols=["AAPL"],
        storage=storage,
        history_rows=[_aapl_close()],
    )
    db_session.commit()
    assert int(first["inserted"]) + int(first["updated"]) + int(first["skipped"]) >= 1

    instrument_id = resolve_instrument_id(db_session, "AAPL")
    assert instrument_id is not None
    quote = db_session.scalar(
        select(InstrumentQuoteRow)
        .where(
            InstrumentQuoteRow.instrument_id == instrument_id,
            InstrumentQuoteRow.reference_date == date(2026, 8, 21),
            InstrumentQuoteRow.price_type == PriceType.CLOSE.value,
        )
        .order_by(InstrumentQuoteRow.revision.desc())
    )
    assert quote is not None
    assert quote.price_type == PriceType.CLOSE.value
    assert quote.is_official is False
    assert Decimal(quote.value) == Decimal("185.64")
    assert quote.extra.get("source_field") == "Close"

    types = set(
        db_session.scalars(
            select(InstrumentIdentifierRow.identifier_type).where(
                InstrumentIdentifierRow.instrument_id == instrument_id
            )
        )
    )
    assert IdentifierType.YAHOO_SYMBOL.value in types
    assert IdentifierType.SOURCE_ID.value in types
    assert IdentifierType.TICKER.value in types

    source = db_session.scalar(select(SourceRow).where(SourceRow.name == "yahoo"))
    assert source is not None
    assert source.official is False
    assert source.redistribution_policy == RedistributionPolicy.UNKNOWN.value
    assert source.public_api_enabled is True
    assert source.public_dataset_enabled is False
    assert source.ingestion_enabled is True
    assert (tmp_path / "raw" / "yahoo" / "year=2026" / "month=08" / "AAPL-2026-08-21.json").exists()

    second = ingest_yahoo(
        db_session,
        reference_date=date(2026, 8, 21),
        symbols=["AAPL"],
        storage=storage,
        history_rows=[_aapl_close()],
    )
    assert second["inserted"] == 0
    assert int(second["skipped"]) >= 1
    db_session.commit()
    latest = db_session.scalar(
        select(InstrumentQuoteRow)
        .where(
            InstrumentQuoteRow.instrument_id == instrument_id,
            InstrumentQuoteRow.price_type == PriceType.CLOSE.value,
        )
        .order_by(InstrumentQuoteRow.revision.desc())
    )
    assert latest is not None
    assert Decimal(latest.value) == Decimal("185.64")


@pytest.mark.db
def test_yahoo_quotes_are_visible_on_public_api_alongside_b3_petr4(db_session, tmp_path) -> None:
    storage = LocalFileObjectStorage(tmp_path)
    ingest_yahoo(
        db_session,
        reference_date=date(2026, 8, 21),
        symbols=["AAPL"],
        storage=storage,
        history_rows=[_aapl_close()],
    )
    price = _nested_zip(
        "SPRE260824.zip",
        "BVBG.186.01_sample.xml",
        (B3_FIXTURES / "price_report.xml").read_bytes(),
    )
    master = _nested_zip(
        "IN260824.zip",
        "BVBG.028.02_sample.xml",
        (B3_FIXTURES / "instrument_master.xml").read_bytes(),
    )
    ingest_b3(
        db_session,
        reference_date=date(2026, 8, 24),
        storage=storage,
        price_payload=price,
        master_payload=master,
    )
    db_session.commit()

    client = TestClient(create_app())
    visible = client.get("/v1/quotes/AAPL")
    assert visible.status_code == 200
    apple = visible.json()
    assert apple["quotes"]
    assert apple["quotes"][0]["price_type"] == "CLOSE"
    assert apple["quotes"][0]["source"] == "yahoo"
    assert Decimal(apple["quotes"][0]["price"]) == Decimal("185.64")

    by_source = client.get("/v1/quotes/AAPL", params={"source": "yahoo"})
    assert by_source.status_code == 200
    assert by_source.json()["quotes"]

    petr4 = client.get("/v1/quotes/PETR4")
    assert petr4.status_code == 200
    body = petr4.json()
    assert body["quotes"]
    assert body["quotes"][0]["price_type"] == "LAST"
    assert body["quotes"][0]["source"] == "b3"
    assert Decimal(body["quotes"][0]["price"]) == Decimal("42.11")

    visible_b3 = client.get("/v1/quotes/PETR4", params={"source": "b3"})
    assert visible_b3.status_code == 200
    assert visible_b3.json()["quotes"]


class _PartialYahooProvider:
    name = "yahoo"

    def fetch_history(self, symbol: str, *, start, end):
        del start, end
        if symbol == "MISSING.SA":
            raise RuntimeError("No data found for MISSING.SA")
        return [
            YahooQuoteRecord(
                symbol=symbol,
                reference_date=date(2026, 8, 21),
                value=Decimal("42.11"),
                currency="BRL",
                price_type=PriceType.CLOSE,
                source_field="Close",
            ),
            YahooQuoteRecord(
                symbol=symbol,
                reference_date=date(2026, 8, 21),
                value=Decimal("40.00"),
                currency="BRL",
                price_type=PriceType.ADJUSTED_CLOSE,
                source_field="Adj Close",
            ),
        ]


@pytest.mark.db
def test_yahoo_ingest_skips_missing_symbol_and_persists_adj_close_column(
    db_session, tmp_path
) -> None:
    storage = LocalFileObjectStorage(tmp_path)
    result = ingest_yahoo(
        db_session,
        reference_date=date(2026, 8, 21),
        symbols=["PETR4.SA", "MISSING.SA"],
        storage=storage,
        provider=_PartialYahooProvider(),
    )
    db_session.commit()
    assert result["status"]
    assert int(result["inserted"]) + int(result["updated"]) + int(result["skipped"]) >= 2

    instrument_id = resolve_instrument_id(db_session, "PETR4.SA")
    assert instrument_id is not None
    close = db_session.scalar(
        select(InstrumentQuoteRow).where(
            InstrumentQuoteRow.instrument_id == instrument_id,
            InstrumentQuoteRow.price_type == PriceType.CLOSE.value,
        )
    )
    adj = db_session.scalar(
        select(InstrumentQuoteRow).where(
            InstrumentQuoteRow.instrument_id == instrument_id,
            InstrumentQuoteRow.price_type == PriceType.ADJUSTED_CLOSE.value,
        )
    )
    assert close is not None
    assert Decimal(close.value) == Decimal("42.11")
    assert close.extra.get("source_field") == "Close"
    assert adj is not None
    assert Decimal(adj.value) == Decimal("40.00")
    assert adj.extra.get("source_field") == "Adj Close"
    assert resolve_instrument_id(db_session, "MISSING.SA") is None

    yahoo_petr = TestClient(create_app()).get("/v1/quotes/PETR4.SA")
    assert yahoo_petr.status_code == 200
    assert yahoo_petr.json()["quotes"][0]["source"] == "yahoo"


def test_ingest_yahoo_missing_symbol_does_not_fail_sqlite_job(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'yahoo.db'}", future=True)
    Base.metadata.create_all(engine)
    session = Session(engine, autoflush=False)
    try:
        result = ingest_yahoo(
            session,
            reference_date=date(2026, 8, 21),
            symbols=["PETR4.SA", "MISSING.SA"],
            storage=LocalFileObjectStorage(tmp_path),
            provider=_PartialYahooProvider(),
        )
        session.commit()
        assert int(result["inserted"]) >= 2
        assert int(result["symbols_skipped"]) >= 1
        assert int(result["mapped"]) == 2
        assert int(result["fetched"]) == 1
        assert int(result["persisted"]) >= 2
        count = session.scalar(select(func.count()).select_from(InstrumentQuoteRow))
        assert count >= 2
    finally:
        session.close()
        engine.dispose()


class _EmptyYahooProvider:
    name = "yahoo"

    def fetch_history(self, symbol: str, *, start, end):
        del symbol, start, end
        return []


def test_yahoo_ingest_fails_when_mapped_equities_persist_nothing_on_weekday(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'yahoo-empty.db'}", future=True)
    Base.metadata.create_all(engine)
    session = Session(engine, autoflush=False)
    try:
        with pytest.raises(RuntimeError, match="mapped 2 equities but persisted 0"):
            ingest_yahoo(
                session,
                reference_date=date(2026, 8, 31),
                symbols=["PETR4.SA", "VALE3.SA"],
                storage=LocalFileObjectStorage(tmp_path),
                provider=_EmptyYahooProvider(),
            )
    finally:
        session.close()
        engine.dispose()


def test_yahoo_ingest_warns_but_succeeds_when_weekend_history_is_empty(
    tmp_path, caplog: pytest.LogCaptureFixture
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'yahoo-weekend.db'}", future=True)
    Base.metadata.create_all(engine)
    session = Session(engine, autoflush=False)
    try:
        with caplog.at_level("WARNING"):
            result = ingest_yahoo(
                session,
                reference_date=date(2026, 8, 30),
                symbols=["PETR4.SA", "VALE3.SA"],
                storage=LocalFileObjectStorage(tmp_path),
                provider=_EmptyYahooProvider(),
            )
        session.commit()
        assert result["status"]
        assert int(result["mapped"]) == 2
        assert int(result["fetched"]) == 0
        assert int(result["persisted"]) == 0
        assert int(result["symbols_skipped"]) == 2
        assert "persisted 0" in caplog.text
    finally:
        session.close()
        engine.dispose()
