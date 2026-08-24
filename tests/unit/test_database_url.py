from marketdata.storage.urls import normalize_database_url


def test_normalize_database_url_selects_psycopg3() -> None:
    assert (
        normalize_database_url("postgresql://user:pass@localhost/db")
        == "postgresql+psycopg://user:pass@localhost/db"
    )
    assert (
        normalize_database_url("postgres://user:pass@localhost/db")
        == "postgresql+psycopg://user:pass@localhost/db"
    )
    already = "postgresql+psycopg://user:pass@localhost/db"
    assert normalize_database_url(already) == already
