from marketdata.api.canonical_sources import (
    canonical_source_names,
    is_canonical_source_name,
)
from marketdata.providers.bootstrap import register_default_providers


def test_canonical_source_names_are_registered_providers() -> None:
    register_default_providers()
    names = canonical_source_names()
    expected = {"b3", "bcb", "cftc", "cvm", "edgar", "fred", "ibge", "tesouro", "yahoo"}
    assert names == frozenset(expected)
    assert is_canonical_source_name("b3")
    assert is_canonical_source_name("B3")
    assert not is_canonical_source_name("b3-api-1a2828de")
    assert not is_canonical_source_name("lying-ds-ffff")
    assert not is_canonical_source_name("cvm-ds-abcd")
