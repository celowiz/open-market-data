from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from uuid import UUID
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from marketdata.api.main import create_app
from marketdata.config import get_settings
from marketdata.domain.enums import IdentifierType, PriceType
from marketdata.storage.database import create_db_engine, create_session_factory
from marketdata.storage.models import (
    InstrumentIdentifierRow,
    InstrumentQuoteRow,
    InstrumentRow,
    QualityEventRow,
    SourceRow,
)
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


def _equity_payloads() -> tuple[bytes, bytes, bytes]:
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
    return price, master, derivatives


@pytest.mark.db
def test_b3_credit_ingest_last_not_reference_and_absence(db_session, tmp_path) -> None:
    from marketdata.ingestion.b3 import ingest_b3

    price, master, derivatives = _equity_payloads()
    trades = (FIXTURES / "otc_trades.json").read_bytes()
    instruments = (FIXTURES / "otc_instruments.json").read_bytes()
    storage = LocalFileObjectStorage(tmp_path)
    result = ingest_b3(
        db_session,
        reference_date=date(2026, 8, 21),
        storage=storage,
        price_payload=price,
        master_payload=master,
        derivatives_payload=derivatives,
        credit_trades_payload=trades,
        credit_master_payload=instruments,
    )
    db_session.commit()
    assert int(result["inserted"]) + int(result["updated"]) + int(result["skipped"]) >= 1

    petr_id = resolve_instrument_id(db_session, "PETR4")
    assert petr_id is not None
    petr_quote = db_session.scalar(
        select(InstrumentQuoteRow).where(
            InstrumentQuoteRow.instrument_id == petr_id,
            InstrumentQuoteRow.price_type == PriceType.LAST.value,
        )
    )
    assert petr_quote is not None
    assert Decimal(petr_quote.value) == Decimal("42.11")

    di_id = resolve_instrument_id(db_session, "DI1F27")
    assert di_id is not None
    di_quote = db_session.scalar(
        select(InstrumentQuoteRow).where(
            InstrumentQuoteRow.instrument_id == di_id,
            InstrumentQuoteRow.price_type == PriceType.OFFICIAL_SETTLEMENT.value,
        )
    )
    assert di_quote is not None
    assert Decimal(di_quote.value) == Decimal("89656.53")

    jall_id = resolve_instrument_id(db_session, "JALL14")
    assert jall_id is not None
    assert resolve_instrument_id(db_session, "BRJALLDBS036") == jall_id
    jall = db_session.get(InstrumentRow, jall_id)
    assert jall is not None
    assert jall.asset_class == "credit"
    assert jall.instrument_type == "debenture"
    jall_quote = db_session.scalar(
        select(InstrumentQuoteRow)
        .where(
            InstrumentQuoteRow.instrument_id == jall_id,
            InstrumentQuoteRow.reference_date == date(2026, 8, 21),
            InstrumentQuoteRow.price_type == PriceType.LAST.value,
        )
        .order_by(InstrumentQuoteRow.revision.desc())
    )
    assert jall_quote is not None
    assert Decimal(jall_quote.value) == Decimal("1133.31")
    assert Decimal(jall_quote.value) != Decimal("9999.00")
    assert jall_quote.unit == "BRL"
    assert isinstance(jall_quote.value, Decimal)
    assert jall_quote.extra.get("BusinessClass") == "EXTRAGRUPO"
    quotes_for_jall = list(
        db_session.scalars(
            select(InstrumentQuoteRow).where(InstrumentQuoteRow.instrument_id == jall_id)
        )
    )
    assert len(quotes_for_jall) == 1

    assert resolve_instrument_id(db_session, "CDB123") is None
    assert resolve_instrument_id(db_session, "VIRG24") is not None
    assert resolve_instrument_id(db_session, "CRA0240086L") is not None

    silent_id = resolve_instrument_id(db_session, "SILENT1")
    assert silent_id is not None
    silent = db_session.get(InstrumentRow, silent_id)
    assert silent is not None
    assert silent.asset_class == "credit"
    assert silent.maturity_date == date(2029, 5, 20)
    silent_quote = db_session.scalar(
        select(InstrumentQuoteRow).where(InstrumentQuoteRow.instrument_id == silent_id)
    )
    assert silent_quote is None
    event = db_session.scalar(
        select(QualityEventRow).where(
            QualityEventRow.instrument_id == silent_id,
            QualityEventRow.event_type == "NO_PUBLIC_PRICE",
        )
    )
    assert event is not None
    assert event.severity == "INFO"
    assert event.extra.get("reference_date") == "2026-08-21"

    source = db_session.scalar(select(SourceRow).where(SourceRow.name == "b3"))
    assert source is not None
    assert source.redistribution_policy == "API_ONLY"
    assert source.public_api_enabled is True
    assert source.public_dataset_enabled is False

    assert (
        tmp_path / "raw" / "b3" / "year=2026" / "month=08" / "otc_trades_2026-08-21.json"
    ).exists()
    assert (
        tmp_path / "raw" / "b3" / "year=2026" / "month=08" / "otc_instruments_2026-08-21.json"
    ).exists()

    second = ingest_b3(
        db_session,
        reference_date=date(2026, 8, 21),
        storage=storage,
        price_payload=price,
        master_payload=master,
        derivatives_payload=derivatives,
        credit_trades_payload=trades,
        credit_master_payload=instruments,
    )
    db_session.commit()
    assert int(second["skipped"]) >= 1
    events = list(
        db_session.scalars(
            select(QualityEventRow).where(
                QualityEventRow.instrument_id == silent_id,
                QualityEventRow.event_type == "NO_PUBLIC_PRICE",
            )
        )
    )
    assert len(events) == 1

    client = TestClient(create_app())
    visible = client.get("/v1/quotes/JALL14", params={"source": "b3"})
    assert visible.status_code == 200
    body = visible.json()
    assert body["quotes"]
    assert body["quotes"][0]["price_type"] == "LAST"
    assert Decimal(body["quotes"][0]["price"]) == Decimal("1133.31")
    assert body["quotes"][0]["source"] == "b3"

    by_isin = client.get("/v1/quotes/BRJALLDBS036", params={"source": "b3"})
    assert by_isin.status_code == 200
    assert by_isin.json()["quotes"]


@pytest.mark.db
def test_b3_credit_empty_trades_skips_absence_events(db_session, tmp_path) -> None:
    from marketdata.ingestion.b3 import ingest_b3

    price, master, derivatives = _equity_payloads()
    empty_trades = b'{"name":"ConsolidatedRecords","columns":[],"values":[]}'
    instruments = (FIXTURES / "otc_instruments.json").read_bytes()
    result = ingest_b3(
        db_session,
        reference_date=date(2026, 8, 21),
        storage=LocalFileObjectStorage(tmp_path),
        price_payload=price,
        master_payload=master,
        derivatives_payload=derivatives,
        credit_trades_payload=empty_trades,
        credit_master_payload=instruments,
    )
    db_session.commit()
    assert result["status"] == "succeeded"
    silent_id = resolve_instrument_id(db_session, "SILENT1")
    assert silent_id is not None
    assert (
        db_session.scalar(
            select(InstrumentQuoteRow).where(InstrumentQuoteRow.instrument_id == silent_id)
        )
        is None
    )
    run_id = UUID(str(result["run_id"]))
    assert (
        db_session.scalar(
            select(QualityEventRow).where(
                QualityEventRow.ingestion_run_id == run_id,
                QualityEventRow.event_type == "NO_PUBLIC_PRICE",
            )
        )
        is None
    )
