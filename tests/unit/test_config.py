from marketdata.config import Settings


def test_settings_defaults_are_local_first() -> None:
    settings = Settings(_env_file=None)
    assert settings.object_storage_backend == "local"
    assert settings.api_v1_prefix == "/v1"
    assert settings.recent_reprocess_days == 90
    assert settings.cvm_provider_enabled is True
    assert settings.b3_provider_enabled is True
    assert settings.tesouro_provider_enabled is True
    assert settings.bcb_provider_enabled is True
    assert settings.yahoo_provider_enabled is False
    assert settings.anbima_provider_enabled is False
    assert settings.fred_provider_enabled is True
    assert settings.fred_api_key == ""
    assert settings.ibge_provider_enabled is True
    assert settings.cftc_provider_enabled is True
    assert settings.edgar_provider_enabled is True
    assert settings.news_hook_token == ""
    assert settings.ingest_universe == ""
    assert settings.b3_equity_universe_path == ""
    assert settings.public_dataset_publication_enabled is False
    assert settings.tesouro_current_titles_only is True
    assert settings.cvm_classes == ""
    assert not settings.object_storage_access_key
