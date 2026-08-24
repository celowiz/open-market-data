from marketdata.api.access import source_allows_public_api
from marketdata.domain.enums import RedistributionPolicy


def test_gated_source_is_hidden_even_if_flag_true_with_unknown_policy() -> None:
    assert (
        source_allows_public_api(
            public_api_enabled=True,
            redistribution_policy=RedistributionPolicy.UNKNOWN.value,
        )
        is False
    )


def test_b3_api_only_flags_are_public() -> None:
    assert (
        source_allows_public_api(
            public_api_enabled=True,
            redistribution_policy=RedistributionPolicy.API_ONLY.value,
        )
        is True
    )


def test_no_redistribution_flag_off_is_not_public() -> None:
    assert (
        source_allows_public_api(
            public_api_enabled=False,
            redistribution_policy=RedistributionPolicy.NO_REDISTRIBUTION.value,
        )
        is False
    )


def test_cvm_style_source_is_public() -> None:
    assert (
        source_allows_public_api(
            public_api_enabled=True,
            redistribution_policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION.value,
        )
        is True
    )
