from marketdata.providers.bootstrap import register_default_providers
from marketdata.providers.registry import registry


def canonical_source_names() -> frozenset[str]:
    """Source.name values that belong to registered providers.

    Leftover CI rows such as ``b3-api-*`` / ``lying-ds-*`` are not registered
    providers. There is no ``is_test`` column; ``sources.name`` is the identity.
    """
    register_default_providers()
    return frozenset(name.lower() for name in registry.names())


def is_canonical_source_name(name: str) -> bool:
    return name.strip().lower() in canonical_source_names()
