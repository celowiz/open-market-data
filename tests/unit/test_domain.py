from decimal import Decimal

import pytest
from pydantic import ValidationError

from marketdata.domain import (
    InstrumentQuote,
    InvalidFinancialValueError,
    PriceType,
    RedistributionPolicy,
    Source,
    exact_decimal,
)


def test_exact_decimal_rejects_float() -> None:
    with pytest.raises(InvalidFinancialValueError):
        exact_decimal(1.23)  # type: ignore[arg-type]


def test_exact_decimal_accepts_str() -> None:
    assert exact_decimal("32.51") == Decimal("32.51")


def test_instrument_quote_rejects_float_price() -> None:
    with pytest.raises((InvalidFinancialValueError, ValidationError)):
        InstrumentQuote(
            instrument_id="abc",
            reference_date="2026-08-21",
            value=32.51,  # type: ignore[arg-type]
            price_type=PriceType.LAST,
            source_name="b3",
        )


def test_instrument_quote_keeps_decimal() -> None:
    quote = InstrumentQuote(
        instrument_id="abc",
        reference_date="2026-08-21",
        value="32.51",
        price_type=PriceType.FUND_NAV,
        source_name="cvm",
        is_official=True,
    )
    assert quote.value == Decimal("32.51")
    assert quote.price_type is PriceType.FUND_NAV


def test_source_public_api_requires_policy_and_flag() -> None:
    blocked = Source(
        name="yahoo",
        display_name="Yahoo Finance",
        official=False,
        redistribution_policy=RedistributionPolicy.UNKNOWN,
        ingestion_enabled=True,
        public_api_enabled=True,
        public_dataset_enabled=True,
    )
    assert blocked.allows_public_api() is False
    assert blocked.allows_public_dataset() is False

    allowed = Source(
        name="cvm",
        display_name="CVM",
        official=True,
        redistribution_policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION,
        ingestion_enabled=True,
        public_api_enabled=True,
        public_dataset_enabled=True,
    )
    assert allowed.allows_public_api() is True
    assert allowed.allows_public_dataset() is True
