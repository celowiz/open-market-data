def normalize_database_url(url: str) -> str:
    """Use psycopg3 when the URL omits an explicit SQLAlchemy driver."""
    if url.startswith("postgresql+"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    return url
