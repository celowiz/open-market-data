from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from marketdata.api.main import create_app
from marketdata.config import get_settings
from marketdata.domain.enums import (
    AssetClass,
    IdentifierType,
    PriceType,
    QualityStatus,
    RedistributionPolicy,
)
from marketdata.storage.database import create_db_engine, create_session_factory
from marketdata.storage.models import InstrumentIdentifierRow, InstrumentQuoteRow, InstrumentRow
from marketdata.storage.repositories import get_or_create_source


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
def test_quotes_api_hides_gated_source(db_session) -> None:
    ticker = f"GATE{uuid4().hex[:8].upper()}"
    source = get_or_create_source(
        db_session,
        name=f"gated-{ticker.lower()}",
        display_name="Gated test source",
        official=True,
        homepage="https://example.test/",
        documentation_url="https://example.test/",
        data_license="UNKNOWN",
        redistribution_policy=RedistributionPolicy.NO_REDISTRIBUTION,
        public_api_enabled=False,
        public_dataset_enabled=False,
    )
    instrument = InstrumentRow(
        id=uuid4(),
        asset_class=AssetClass.EQUITY.value,
        instrument_type="stock",
        name=ticker,
        currency="BRL",
    )
    db_session.add(instrument)
    db_session.flush()
    db_session.add(
        InstrumentIdentifierRow(
            id=uuid4(),
            instrument_id=instrument.id,
            identifier_type=IdentifierType.TICKER.value,
            identifier_value=ticker,
            source_id=source.id,
        )
    )
    db_session.add(
        InstrumentQuoteRow(
            id=uuid4(),
            instrument_id=instrument.id,
            reference_date=date(2026, 8, 21),
            value=Decimal("32.51"),
            currency="BRL",
            unit="BRL",
            price_type=PriceType.LAST.value,
            source_id=source.id,
            is_official=True,
            retrieved_at=datetime.now(UTC),
            revision=1,
            quality_status=QualityStatus.OK.value,
        )
    )
    db_session.commit()

    client = TestClient(create_app())
    response = client.get(f"/v1/quotes/{ticker}")
    assert response.status_code == 404
    assert response.json()["detail"] == "instrument not found"
