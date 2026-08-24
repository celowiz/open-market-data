from decimal import Decimal
from typing import Any


class DomainError(Exception):
    """Base error for domain-rule violations."""


class InvalidFinancialValueError(DomainError):
    """Raised when a financial value would lose exact decimal semantics."""


def exact_decimal(value: Decimal | int | str) -> Decimal:
    """Coerce a financial value to Decimal, rejecting binary floats."""
    if isinstance(value, float):
        raise InvalidFinancialValueError(
            "binary float values are not allowed for financial amounts"
        )
    if isinstance(value, Decimal):
        return value
    return Decimal(value)


def decimal_json(value: Decimal) -> str:
    """Serialize a Decimal without binary float conversion."""
    return format(value, "f")


def json_ready(value: Any) -> Any:
    if isinstance(value, Decimal):
        return decimal_json(value)
    return value
