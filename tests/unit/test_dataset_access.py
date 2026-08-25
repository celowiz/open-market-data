from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest

from marketdata.datasets.access import public_dataset_quotes_stmt, source_allows_public_dataset
from marketdata.domain.enums import (
    AssetClass,
    IdentifierType,
    PriceType,
    QualityStatus,
    RedistributionPolicy,
)
from marketdata.storage.models import InstrumentIdentifierRow, InstrumentQuoteRow, InstrumentRow
from marketdata.storage.repositories import get_or_create_source


def test_cvm_style_source_is_dataset_eligible() -> None:
    assert (
        source_allows_public_dataset(
            public_dataset_enabled=True,
            redistribution_policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION.value,
        )
        is True
    )


def test_tesouro_style_source_is_dataset_eligible() -> None:
    assert (
        source_allows_public_dataset(
            public_dataset_enabled=True,
            redistribution_policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION.value,
        )
        is True
    )


def test_bcb_style_source_is_dataset_eligible() -> None:
    assert (
        source_allows_public_dataset(
            public_dataset_enabled=True,
            redistribution_policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION.value,
        )
        is True
    )


def test_public_policy_with_flag_is_dataset_eligible() -> None:
    assert (
        source_allows_public_dataset(
            public_dataset_enabled=True,
            redistribution_policy=RedistributionPolicy.PUBLIC.value,
        )
        is True
    )


def test_b3_api_only_is_not_dataset_eligible() -> None:
    assert (
        source_allows_public_dataset(
            public_dataset_enabled=False,
            redistribution_policy=RedistributionPolicy.API_ONLY.value,
        )
        is False
    )


def test_yahoo_unknown_is_not_dataset_eligible() -> None:
    assert (
        source_allows_public_dataset(
            public_dataset_enabled=False,
            redistribution_policy=RedistributionPolicy.UNKNOWN.value,
        )
        is False
    )


def test_odbl_policy_with_flag_off_is_not_dataset_eligible() -> None:
    assert (
        source_allows_public_dataset(
            public_dataset_enabled=False,
            redistribution_policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION.value,
        )
        is False
    )


def test_lying_api_only_with_flag_on_is_not_dataset_eligible() -> None:
    assert (
        source_allows_public_dataset(
            public_dataset_enabled=True,
            redistribution_policy=RedistributionPolicy.API_ONLY.value,
        )
        is False
    )


def test_unknown_policy_string_is_not_dataset_eligible() -> None:
    assert (
        source_allows_public_dataset(
            public_dataset_enabled=True,
            redistribution_policy="not-a-policy",
        )
        is False
    )


def test_dataset_package_source_does_not_import_provider_libraries() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "marketdata" / "datasets"
    text = "\n".join(path.read_text(encoding="utf-8") for path in root.glob("*.py"))
    lowered = text.lower()
    assert "yfinance" not in lowered
    assert "mercados" not in lowered
    assert "python-bcb" not in lowered
    assert "import bcb" not in lowered
    assert "from bcb" not in lowered


@pytest.fixture
def db_session():
    from marketdata.config import get_settings
    from marketdata.storage.database import create_db_engine, create_session_factory

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


def _add_quote(
    session, *, source, ticker: str | None, cnpj: str | None, price_type: PriceType, value: Decimal
):
    suffix = uuid4().hex[:8]
    instrument = InstrumentRow(
        id=uuid4(),
        asset_class=AssetClass.FUND.value if cnpj else AssetClass.EQUITY.value,
        instrument_type="fund_class" if cnpj else "listed",
        name=ticker or cnpj or suffix,
        currency="BRL",
    )
    session.add(instrument)
    session.flush()
    if ticker is not None:
        session.add(
            InstrumentIdentifierRow(
                id=uuid4(),
                instrument_id=instrument.id,
                identifier_type=IdentifierType.TICKER.value,
                identifier_value=ticker,
                source_id=source.id,
            )
        )
    if cnpj is not None:
        session.add(
            InstrumentIdentifierRow(
                id=uuid4(),
                instrument_id=instrument.id,
                identifier_type=IdentifierType.CNPJ_FUNDO_CLASSE.value,
                identifier_value=cnpj,
                source_id=source.id,
            )
        )
    session.add(
        InstrumentQuoteRow(
            id=uuid4(),
            instrument_id=instrument.id,
            reference_date=date(2026, 8, 21),
            value=value,
            currency="BRL",
            unit="BRL",
            price_type=price_type.value,
            source_id=source.id,
            is_official=True,
            retrieved_at=datetime.now(UTC),
            revision=1,
            quality_status=QualityStatus.OK.value,
        )
    )
    return instrument


@pytest.mark.db
def test_dataset_sql_gate_includes_odbl_and_omits_restricted(db_session) -> None:
    suffix = uuid4().hex[:8]
    cvm = get_or_create_source(
        db_session,
        name=f"cvm-ds-{suffix}",
        display_name="CVM test",
        official=True,
        homepage="https://dados.cvm.gov.br/",
        documentation_url="https://dados.cvm.gov.br/",
        data_license="ODbL-1.0",
        redistribution_policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION,
        public_api_enabled=True,
        public_dataset_enabled=True,
    )
    b3 = get_or_create_source(
        db_session,
        name=f"b3-ds-{suffix}",
        display_name="B3 test",
        official=True,
        homepage="https://www.b3.com.br/",
        documentation_url="https://www.b3.com.br/",
        data_license="UNKNOWN",
        redistribution_policy=RedistributionPolicy.API_ONLY,
        public_api_enabled=True,
        public_dataset_enabled=False,
    )
    yahoo = get_or_create_source(
        db_session,
        name=f"yahoo-ds-{suffix}",
        display_name="Yahoo test",
        official=False,
        homepage="https://finance.yahoo.com/",
        documentation_url="https://finance.yahoo.com/",
        data_license="UNKNOWN",
        redistribution_policy=RedistributionPolicy.UNKNOWN,
        public_api_enabled=False,
        public_dataset_enabled=False,
    )
    lying = get_or_create_source(
        db_session,
        name=f"lying-ds-{suffix}",
        display_name="Lying API_ONLY",
        official=True,
        homepage="https://example.test/",
        documentation_url="https://example.test/",
        data_license="UNKNOWN",
        redistribution_policy=RedistributionPolicy.API_ONLY,
        public_api_enabled=True,
        public_dataset_enabled=True,
    )
    fund = _add_quote(
        db_session,
        source=cvm,
        ticker=None,
        cnpj=f"99{suffix}000153",
        price_type=PriceType.FUND_NAV,
        value=Decimal("1.25"),
    )
    petr = _add_quote(
        db_session,
        source=b3,
        ticker=f"PETR{suffix[:4].upper()}",
        cnpj=None,
        price_type=PriceType.LAST,
        value=Decimal("32.51"),
    )
    aapl = _add_quote(
        db_session,
        source=yahoo,
        ticker=f"AAPL{suffix[:4].upper()}",
        cnpj=None,
        price_type=PriceType.CLOSE,
        value=Decimal("185.64"),
    )
    fake = _add_quote(
        db_session,
        source=lying,
        ticker=f"FAKE{suffix[:4].upper()}",
        cnpj=None,
        price_type=PriceType.LAST,
        value=Decimal("10.00"),
    )
    db_session.commit()
    assert db_session.scalar(public_dataset_quotes_stmt(fund.id).limit(1)) is not None
    assert db_session.scalar(public_dataset_quotes_stmt(petr.id).limit(1)) is None
    assert db_session.scalar(public_dataset_quotes_stmt(aapl.id).limit(1)) is None
    assert db_session.scalar(public_dataset_quotes_stmt(fake.id).limit(1)) is None
