import io
import zipfile
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from marketdata.config import get_settings
from marketdata.ingestion.cvm import ingest_cvm
from marketdata.providers.cvm import CvmProvider
from marketdata.storage.database import create_db_engine, create_session_factory
from marketdata.storage.object_store import LocalFileObjectStorage

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "cvm"


class _FakeResponse:
    def __init__(self, content: bytes, url: str) -> None:
        self.content = content
        self.status_code = 200
        self.headers = {"content-type": "application/zip"}
        self.request = type("Req", (), {"url": url})()


class _FakeCvm(CvmProvider):
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def fetch_month(self, year: int, month: int, *, client=None) -> _FakeResponse:
        return _FakeResponse(self._payload, self.month_url(year, month))


def _zip_from_csv(path: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(path.name, path.read_bytes())
    return buffer.getvalue()


@pytest.fixture
def db_session():
    settings = get_settings()
    if not settings.database_url:
        pytest.skip("DATABASE_URL is not configured")
    factory = create_session_factory(create_db_engine(settings))
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.mark.db
def test_cvm_ingest_is_idempotent(db_session, tmp_path) -> None:
    payload = _zip_from_csv(FIXTURES / "ingest.csv")
    provider = _FakeCvm(payload)
    storage = LocalFileObjectStorage(tmp_path)
    first = ingest_cvm(
        db_session,
        reference_date=date(2026, 8, 3),
        lookback_days=0,
        storage=storage,
        provider=provider,
    )
    db_session.commit()
    second = ingest_cvm(
        db_session,
        reference_date=date(2026, 8, 3),
        lookback_days=0,
        storage=storage,
        provider=provider,
    )
    assert int(first["inserted"]) + int(first["updated"]) + int(first["skipped"]) >= 1
    assert second["inserted"] == 0
    assert int(second["skipped"]) >= 1

    from marketdata.api.main import create_app

    client = TestClient(create_app())
    response = client.get("/v1/funds/88888888000188/quotes", params={"date": "2026-08-03"})
    assert response.status_code == 200
    body = response.json()
    from decimal import Decimal

    assert body["quotes"][0]["price_type"] == "FUND_NAV"
    assert Decimal(body["quotes"][0]["price"]) == Decimal("1.23456789")
    assert body["quotes"][0]["official"] is True
