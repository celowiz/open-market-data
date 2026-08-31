from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from marketdata.config import get_settings
from marketdata.domain.enums import AssetClass, PriceType, RedistributionPolicy
from marketdata.storage.database import create_db_engine, create_session_factory
from marketdata.storage.models import InstrumentQuoteRow
from marketdata.storage.repositories import get_or_create_instrument_by_key, get_or_create_source

STABLE_DATE = date(2026, 8, 24)


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


def _insert_stable_petr4_last(session) -> None:
    source = get_or_create_source(
        session,
        name="b3",
        display_name="B3",
        official=True,
        homepage="https://www.b3.com.br/",
        documentation_url="https://www.b3.com.br/",
        data_license="UNKNOWN",
        redistribution_policy=RedistributionPolicy.NO_REDISTRIBUTION,
        public_api_enabled=True,
        public_dataset_enabled=False,
    )
    instrument = get_or_create_instrument_by_key(
        session,
        source_id=source.id,
        source_key="PETR4",
        asset_class=AssetClass.EQUITY,
        instrument_type="STOCK",
        name="PETR4",
        currency="BRL",
    )
    session.add(
        InstrumentQuoteRow(
            id=uuid4(),
            instrument_id=instrument.id,
            reference_date=STABLE_DATE,
            value=Decimal("42.11"),
            currency="BRL",
            unit="BRL",
            price_type=PriceType.LAST.value,
            source_id=source.id,
            is_official=True,
            retrieved_at=datetime.now(UTC),
            revision=1,
            quality_status="ok",
        )
    )


@pytest.mark.db
def test_instrument_quotes_identity_unique_is_enforced(db_session) -> None:
    _insert_stable_petr4_last(db_session)
    db_session.flush()
    _insert_stable_petr4_last(db_session)
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


@pytest.mark.db
def test_instrument_quotes_identity_can_be_reinserted_after_prior_db_test(db_session) -> None:
    """Would UniqueViolation if a previous db test leaked PETR4 LAST 2026-08-24."""
    _insert_stable_petr4_last(db_session)
    db_session.flush()
