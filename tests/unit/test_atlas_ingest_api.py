from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from marketdata.api.main import create_app
from marketdata.config import get_settings
from marketdata.domain.enums import PriceType, RedistributionPolicy
from marketdata.ingestion.config_tables import load_cot_contracts, load_scratch_cusip_map
from marketdata.providers.cftc import parse_cot_rows
from marketdata.providers.edgar import parse_13f_information_table
from marketdata.providers.fred import FredObservation
from marketdata.providers.ibge import parse_sidra_observations
from marketdata.storage.database import create_db_engine, create_session_factory
from marketdata.storage.models import EventRow, InstrumentQuoteRow, LendingSnapshotRow
from marketdata.storage.repositories import (
    get_or_create_source,
    upsert_event,
    upsert_lending_snapshot,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


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
def test_b3_lending_ingest_scratch_only(db_session, monkeypatch) -> None:
    from marketdata.ingestion.b3_lending import ingest_b3_lending

    monkeypatch.setattr(
        "marketdata.ingestion.b3_lending.lending_equity_allowlist",
        lambda: frozenset({"PETR4"}),
    )
    monkeypatch.setattr(
        "marketdata.ingestion.b3_lending.public_publication_storage_configured",
        lambda _settings=None: False,
    )
    result = ingest_b3_lending(
        db_session,
        reference_date=date(2026, 8, 21),
        registered_payload=(FIXTURES / "b3" / "lending_registered.json").read_bytes(),
        open_payload=(FIXTURES / "b3" / "lending_open.json").read_bytes(),
    )
    assert result["status"] == "succeeded"
    assert result["negociosbtb"] == "skipped"
    rows = list(db_session.scalars(select(LendingSnapshotRow)).all())
    assert {row.ticker for row in rows} == {"PETR4"}
    types = {row.snapshot_type for row in rows}
    assert types == {"registered", "open_position"}
    open_row = next(row for row in rows if row.snapshot_type == "open_position")
    assert open_row.qty == Decimal("12000000")


@pytest.mark.db
def test_fred_ingest_persists_reference_quotes(db_session) -> None:
    from marketdata.ingestion.fred import ingest_fred

    observations = [
        FredObservation(series_id="DGS10", reference_date=date(2026, 8, 21), value=Decimal("4.05"))
    ]
    result = ingest_fred(db_session, reference_date=date(2026, 8, 21), observations=observations)
    assert result["inserted"] >= 1
    quote = db_session.scalar(select(InstrumentQuoteRow))
    assert quote is not None
    assert quote.price_type == PriceType.REFERENCE.value
    assert quote.value == Decimal("4.05")


@pytest.mark.db
def test_ibge_ingest_persists_ipca_series(db_session) -> None:
    from marketdata.ingestion.ibge import ingest_ibge

    payload = (FIXTURES / "ibge" / "ipca.json").read_bytes()
    rows = parse_sidra_observations(
        payload=payload,
        code="IBGE:IPCA_MOM",
        source_series_id="1737:63",
        name="IPCA variação mensal",
        unit="percent",
    )
    result = ingest_ibge(db_session, reference_date=date(2026, 8, 1), observations=rows)
    assert result["inserted"] == 1


@pytest.mark.db
def test_cvm_events_ingest_headlines_only(db_session) -> None:
    from marketdata.ingestion.cvm_events import ingest_cvm_events

    result = ingest_cvm_events(
        db_session,
        reference_date=date(2026, 8, 21),
        payload=(FIXTURES / "cvm" / "fato_relevante.csv").read_bytes(),
    )
    assert result["inserted"] == 1
    event = db_session.scalar(select(EventRow))
    assert event is not None
    assert event.ticker == "PETR4"
    assert event.event_type == "fato_relevante"
    assert "pre-sal" in event.headline
    assert event.extra.get("body") is None


@pytest.mark.db
def test_cftc_and_13f_filtered_ingest(db_session) -> None:
    from marketdata.ingestion.cftc import ingest_cftc
    from marketdata.ingestion.edgar import ingest_13f

    cot = parse_cot_rows((FIXTURES / "cftc" / "cot.json").read_bytes(), load_cot_contracts())
    cot_result = ingest_cftc(db_session, reference_date=date(2026, 8, 18), records=cot)
    assert cot_result["inserted"] == 2
    holdings = parse_13f_information_table(
        (FIXTURES / "edgar" / "13f.xml").read_bytes(),
        filer_cik="0001067983",
        filer_name="Berkshire",
        report_date=date(2026, 6, 30),
        cusip_map=load_scratch_cusip_map(),
    )
    f_result = ingest_13f(db_session, reference_date=date(2026, 6, 30), holdings=holdings)
    assert f_result["inserted"] == 1


@pytest.mark.db
def test_lending_events_macro_and_news_hook_api(db_session, monkeypatch) -> None:
    from uuid import uuid4

    from marketdata.storage.models import RawArtifactRow

    source = get_or_create_source(
        db_session,
        name="b3",
        display_name="B3",
        official=True,
        homepage="https://www.b3.com.br/",
        documentation_url="https://www.b3.com.br/",
        data_license="UNKNOWN",
        redistribution_policy=RedistributionPolicy.API_ONLY,
        public_api_enabled=True,
        public_dataset_enabled=False,
    )
    artifact = RawArtifactRow(
        id=uuid4(),
        source_id=source.id,
        source_url="fixture",
        retrieved_at=datetime.now(UTC),
        sha256="a" * 64,
        size_bytes=1,
        storage_uri="memory://x",
        http_status=200,
    )
    db_session.add(artifact)
    db_session.flush()
    upsert_lending_snapshot(
        db_session,
        ticker="PETR4",
        instrument_id=None,
        reference_date=date(2026, 8, 21),
        snapshot_type="open_position",
        source_id=source.id,
        qty=Decimal("12000000"),
        avg_rate=Decimal("0.12"),
        contracts=42,
        avg_price=None,
        balance_brl=None,
        market=None,
        artifact=artifact,
        ingestion_run_id=None,
    )
    upsert_event(
        db_session,
        ticker="PETR4",
        instrument_id=None,
        source="cvm",
        event_type="fato_relevante",
        occurred_at=datetime(2026, 8, 21, tzinfo=UTC),
        headline="Aumento de produção",
        url="https://example.test/fato",
        external_id="cvm-fato:1",
    )
    db_session.commit()

    monkeypatch.setenv("NEWS_HOOK_TOKEN", "secret-token")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "marketdata.api.routes.hooks.get_settings",
        lambda: get_settings(),
    )
    # Recreate settings with token
    from marketdata.config import Settings

    monkeypatch.setattr(
        "marketdata.api.routes.hooks.get_settings",
        lambda: Settings(
            _env_file=None,
            news_hook_token="secret-token",
            database_url=get_settings().database_url,
        ),
    )

    client = TestClient(create_app())
    lending = client.get("/v1/lending/PETR4")
    assert lending.status_code == 200
    body = lending.json()
    qty = body["snapshots"][0]["qty"]
    assert qty is not None and qty.startswith("12000000")
    events = client.get("/v1/events/PETR4")
    assert events.status_code == 200
    assert events.json()["events"][0]["headline"] == "Aumento de produção"
    macro = client.get("/v1/macro")
    assert macro.status_code == 200
    codes = {item["code"] for item in macro.json()["series"]}
    assert "FRED:DGS10" in codes
    denied = client.post(
        "/v1/hooks/news",
        json={
            "ticker": "PETR4",
            "headline": "Wire headline",
            "external_id": "wire-1",
        },
    )
    assert denied.status_code in {401, 503}
    hooked = client.post(
        "/v1/hooks/news",
        headers={"X-News-Hook-Token": "secret-token"},
        json={
            "ticker": "PETR4",
            "headline": "Wire headline",
            "external_id": "wire-1",
        },
    )
    assert hooked.status_code == 200
    assert hooked.json()["status"] in {"inserted", "skipped"}
