from typing import Protocol, runtime_checkable


@runtime_checkable
class MarketDataProvider(Protocol):
    """Source adapter contract. Fetch/parse/normalize arrive with real providers."""

    name: str
