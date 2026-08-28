from marketdata.config import Settings


def test_settings_defaults_are_local_first() -> None:
    settings = Settings(_env_file=None)
    assert settings.object_storage_backend == "local"
    assert settings.api_v1_prefix == "/v1"
    assert settings.recent_reprocess_days == 90
    assert settings.yahoo_provider_enabled is True
    assert settings.anbima_provider_enabled is False
    assert settings.public_dataset_publication_enabled is False
    assert settings.tesouro_current_titles_only is True
    assert not settings.object_storage_access_key
