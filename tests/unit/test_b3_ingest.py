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
from marketdata.storage.models import InstrumentIdentifierRow, InstrumentQuoteRow
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
    storage = LocalFileObjectStorage(tmp_path)
    first = ingest_b3(
        db_session,
        reference_date=date(2026, 8, 24),
        storage=storage,
        price_payload=price,
        master_payload=master,
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

    second = ingest_b3(
        db_session,
        reference_date=date(2026, 8, 24),
        storage=storage,
        price_payload=price,
        master_payload=master,
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
