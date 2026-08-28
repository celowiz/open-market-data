from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "development"
    log_level: str = "INFO"
    app_timezone: str = "America/Sao_Paulo"

    database_url: str = ""
    database_pool_size: int = 5
    database_max_overflow: int = 10
    database_pool_timeout: int = 30
    database_pool_recycle: int = 300

    object_storage_backend: str = "local"
    local_storage_path: Path = Path("./data")
    object_storage_endpoint: str = ""
    object_storage_bucket: str = ""
    object_storage_access_key: str = ""
    object_storage_secret_key: str = ""
    object_storage_region: str = "auto"

    http_user_agent: str = "open-market-data"
    http_timeout_seconds: int = 30
    http_max_retries: int = 3

    recent_reprocess_days: int = Field(default=90)
    ingestion_max_concurrency: int = 4
    ingest_universe: str = ""
    b3_equity_universe_path: str = ""

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_v1_prefix: str = "/v1"
    api_docs_enabled: bool = True

    cors_allowed_origins: str = ""
    public_api_base_url: str = ""
    public_data_base_url: str = ""

    public_dataset_publication_enabled: bool = False
    public_dataset_format: str = "parquet"

    coverage_config_dir: Path = Path(".")

    cvm_provider_enabled: bool = True
    b3_provider_enabled: bool = True
    tesouro_provider_enabled: bool = True
    bcb_provider_enabled: bool = True
    yahoo_provider_enabled: bool = True
    anbima_provider_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
