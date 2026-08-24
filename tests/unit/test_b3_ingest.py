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
from marketdata.domain.enums import IdentifierType, PriceType
from marketdata.storage.database import create_db_engine, create_session_factory
from marketdata.storage.models import InstrumentIdentifierRow, InstrumentQuoteRow, InstrumentRow
from marketdata.storage.object_store import LocalFileObjectStorage
from marketdata.storage.repositories import resolve_instrument_id

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "b3"


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


@pytest.mark.db
def test_b3_ingest_is_idempotent_and_gated(db_session, tmp_path) -> None:
    from marketdata.ingestion.b3 import ingest_b3

    price = _nested_zip(
        "SPRE260824.zip",
        "BVBG.186.01_sample.xml",
        (FIXTURES / "price_report.xml").read_bytes(),
    )
    master = _nested_zip(
        "IN260824.zip",
        "BVBG.028.02_sample.xml",
        (FIXTURES / "instrument_master.xml").read_bytes(),
    )
    derivatives = _nested_zip(
        "SPRD260824.zip",
        "BVBG.187.01_sample.xml",
        (FIXTURES / "derivatives_price_report.xml").read_bytes(),
    )
    storage = LocalFileObjectStorage(tmp_path)
    first = ingest_b3(
        db_session,
        reference_date=date(2026, 8, 24),
        storage=storage,
        price_payload=price,
        master_payload=master,
        derivatives_payload=derivatives,
    )
    db_session.commit()
    assert int(first["inserted"]) + int(first["updated"]) + int(first["skipped"]) >= 1

    instrument_id = resolve_instrument_id(db_session, "PETR4")
    assert instrument_id is not None
    quote = db_session.scalar(
        select(InstrumentQuoteRow)
        .where(
            InstrumentQuoteRow.instrument_id == instrument_id,
            InstrumentQuoteRow.reference_date == date(2026, 8, 24),
            InstrumentQuoteRow.price_type == PriceType.LAST.value,
        )
        .order_by(InstrumentQuoteRow.revision.desc())
    )
    assert quote is not None
    assert Decimal(quote.value) == Decimal("42.11")

    types = set(
        db_session.scalars(
            select(InstrumentIdentifierRow.identifier_type).where(
                InstrumentIdentifierRow.instrument_id == instrument_id
            )
        )
    )
    assert IdentifierType.TICKER.value in types
    assert IdentifierType.B3_SECURITY_ID.value in types
    assert IdentifierType.ISIN.value in types

    di_id = resolve_instrument_id(db_session, "DI1F27")
    assert di_id is not None
    di_quote = db_session.scalar(
        select(InstrumentQuoteRow)
        .where(
            InstrumentQuoteRow.instrument_id == di_id,
            InstrumentQuoteRow.reference_date == date(2026, 8, 24),
            InstrumentQuoteRow.price_type == PriceType.OFFICIAL_SETTLEMENT.value,
        )
        .order_by(InstrumentQuoteRow.revision.desc())
    )
    assert di_quote is not None
    assert Decimal(di_quote.value) == Decimal("89656.53")
    assert Decimal(di_quote.value) != Decimal("13.81")
    assert di_quote.unit == "PU"
    assert di_quote.extra.get("AdjstdQtTax") == "13.789"
    di_instrument = db_session.get(InstrumentRow, di_id)
    assert di_instrument is not None
    assert di_instrument.asset_class == "future"
    assert di_instrument.maturity_date == date(2027, 1, 4)
    di_types = set(
        db_session.scalars(
            select(InstrumentIdentifierRow.identifier_type).where(
                InstrumentIdentifierRow.instrument_id == di_id
            )
        )
    )
    assert IdentifierType.TICKER.value in di_types
    assert IdentifierType.B3_SECURITY_ID.value in di_types
    assert IdentifierType.ISIN.value in di_types
    assert resolve_instrument_id(db_session, "BGIF27C1234") is None
    assert resolve_instrument_id(db_session, "WINQ26") is None
    assert (tmp_path / "raw" / "b3" / "year=2026" / "month=08" / "bvbg187_2026-08-24.zip").exists()

    second = ingest_b3(
        db_session,
        reference_date=date(2026, 8, 24),
        storage=storage,
        price_payload=price,
        master_payload=master,
        derivatives_payload=derivatives,
    )
    assert second["inserted"] == 0
    assert int(second["skipped"]) >= 1
    db_session.commit()

    client = TestClient(create_app())
    visible = client.get("/v1/quotes/PETR4", params={"source": "b3"})
    assert visible.status_code == 200
    body = visible.json()
    assert body["quotes"]
    assert body["quotes"][0]["price_type"] == "LAST"
    assert Decimal(body["quotes"][0]["price"]) == Decimal("42.11")
    assert body["quotes"][0]["source"] == "b3"

    settlement = client.get("/v1/quotes/DI1F27", params={"source": "b3"})
    assert settlement.status_code == 200
    settlement_body = settlement.json()
    assert settlement_body["quotes"]
    assert settlement_body["quotes"][0]["price_type"] == "OFFICIAL_SETTLEMENT"
    assert Decimal(settlement_body["quotes"][0]["price"]) == Decimal("89656.53")
    assert settlement_body["quotes"][0]["source"] == "b3"
    assert settlement_body["quotes"][0]["unit"] == "PU"
