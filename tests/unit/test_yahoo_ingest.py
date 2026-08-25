from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from marketdata.api.main import create_app
from marketdata.config import get_settings
from marketdata.domain.enums import IdentifierType, PriceType, RedistributionPolicy
from marketdata.ingestion.b3 import ingest_b3
from marketdata.ingestion.yahoo import ingest_yahoo
from marketdata.providers.yahoo import YahooQuoteRecord
from marketdata.storage.database import create_db_engine, create_session_factory
from marketdata.storage.models import InstrumentIdentifierRow, InstrumentQuoteRow, SourceRow
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
    assert source.public_api_enabled is False
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
def test_yahoo_quotes_are_omitted_from_public_api_while_b3_petr4_remains(
    db_session, tmp_path
) -> None:
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
    hidden = client.get("/v1/quotes/AAPL")
    assert hidden.status_code == 404
    assert hidden.json()["detail"] == "instrument not found"
    hidden_source = client.get("/v1/quotes/AAPL", params={"source": "yahoo"})
    assert hidden_source.status_code == 404

    visible = client.get("/v1/quotes/PETR4")
    assert visible.status_code == 200
    body = visible.json()
    assert body["quotes"]
    assert body["quotes"][0]["price_type"] == "LAST"
    assert body["quotes"][0]["source"] == "b3"
    assert Decimal(body["quotes"][0]["price"]) == Decimal("42.11")

    visible_b3 = client.get("/v1/quotes/PETR4", params={"source": "b3"})
    assert visible_b3.status_code == 200
    assert visible_b3.json()["quotes"]
