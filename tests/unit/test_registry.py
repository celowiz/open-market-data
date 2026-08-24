import pytest

from marketdata.providers.registry import ProviderRegistry


class FakeProvider:
    name = "fake"


def test_registry_register_and_get() -> None:
    registry = ProviderRegistry()
    registry.register(FakeProvider())
    assert registry.names() == ["fake"]
    assert registry.get("FAKE").name == "fake"


def test_registry_rejects_duplicates() -> None:
    registry = ProviderRegistry()
    registry.register(FakeProvider())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(FakeProvider())


def test_registry_unknown_provider() -> None:
    registry = ProviderRegistry()
    with pytest.raises(KeyError, match="unknown provider"):
        registry.get("cvm")
