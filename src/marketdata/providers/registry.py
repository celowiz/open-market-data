from marketdata.providers.base import MarketDataProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, MarketDataProvider] = {}

    def register(self, provider: MarketDataProvider) -> None:
        key = provider.name.strip().lower()
        if not key:
            raise ValueError("provider name must not be empty")
        if key in self._providers:
            raise ValueError(f"provider already registered: {provider.name}")
        self._providers[key] = provider

    def get(self, name: str) -> MarketDataProvider:
        try:
            return self._providers[name.strip().lower()]
        except KeyError as exc:
            raise KeyError(f"unknown provider: {name}") from exc

    def names(self) -> list[str]:
        return sorted(provider.name for provider in self._providers.values())


registry = ProviderRegistry()
