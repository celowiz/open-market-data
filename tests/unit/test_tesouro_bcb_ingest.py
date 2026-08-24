from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from marketdata.config import get_settings
from marketdata.ingestion.bcb import ingest_bcb
from marketdata.ingestion.tesouro import ingest_tesouro
from marketdata.storage.database import create_db_engine, create_session_factory
from marketdata.storage.object_store import LocalFileObjectStorage

TESOURO_CSV = Path(__file__).resolve().parents[1] / "fixtures" / "tesouro" / "sample.csv"


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
def test_tesouro_and_bcb_ingest(db_session, tmp_path) -> None:
    storage = LocalFileObjectStorage(tmp_path)
    tesouro = ingest_tesouro(
        db_session,
        reference_date=date(2026, 8, 21),
        storage=storage,
        csv_text=TESOURO_CSV.read_text(encoding="utf-8"),
    )
    assert tesouro["inserted"] + tesouro["skipped"] + tesouro["updated"] >= 1
    observations = [
        ("BCB:CDI_DAILY", "12", "CDI", "percent_per_day", date(2026, 8, 21), Decimal("0.051660"))
    ]
    bcb = ingest_bcb(
        db_session,
        reference_date=date(2026, 8, 21),
        storage=storage,
        observations=observations,
    )
    assert bcb["inserted"] + bcb["skipped"] + bcb["updated"] >= 1
    db_session.commit()

    from marketdata.api.main import create_app

    client = TestClient(create_app())
    quotes = client.get(
        "/v1/quotes/LTN:2029-01-01", params={"date": "2026-08-21", "price_type": "PU_BASE"}
    )
    assert quotes.status_code == 200
    assert quotes.json()["quotes"]
    series = client.get("/v1/series/BCB:CDI_DAILY/observations", params={"date": "2026-08-21"})
    assert series.status_code == 200
    assert series.json()["observations"]
