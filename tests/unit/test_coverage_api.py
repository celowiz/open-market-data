from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from typer.testing import CliRunner

from marketdata.api.main import create_app
from marketdata.api.routes.coverage import get_coverage_config_dir
from marketdata.cli.main import app as cli_app
from marketdata.config import get_settings
from marketdata.domain.enums import (
    AssetClass,
    IdentifierType,
    PriceType,
    QualityStatus,
    RedistributionPolicy,
)
from marketdata.storage.database import create_db_engine, create_session_factory
from marketdata.storage.models import InstrumentQuoteRow
from marketdata.storage.repositories import (
    attach_identifier,
    get_or_create_instrument_by_key,
    get_or_create_source,
)

REF = date(2026, 8, 21)
TINY = Path(__file__).resolve().parents[1] / "fixtures" / "coverage" / "universe.tiny.csv"
runner = CliRunner()


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


def _seed_universe(tmp_path: Path) -> Path:
    config = tmp_path / "config"
    config.mkdir()
    dest = config / "instruments.example.csv"
    dest.write_text(TINY.read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def _ensure_quote(
    session, *, instrument_id, source_id, price_type: PriceType, value: Decimal
) -> None:
    existing = session.scalar(
        select(InstrumentQuoteRow.id).where(
            InstrumentQuoteRow.instrument_id == instrument_id,
            InstrumentQuoteRow.reference_date == REF,
            InstrumentQuoteRow.source_id == source_id,
            InstrumentQuoteRow.price_type == price_type.value,
        )
    )
    if existing is not None:
        return
    session.add(
        InstrumentQuoteRow(
            id=uuid4(),
            instrument_id=instrument_id,
            reference_date=REF,
            value=value,
            currency="BRL" if price_type is not PriceType.CLOSE else "USD",
            unit="BRL" if price_type is not PriceType.CLOSE else "USD",
            price_type=price_type.value,
            source_id=source_id,
            is_official=price_type is not PriceType.CLOSE,
            retrieved_at=datetime.now(UTC),
            revision=1,
            quality_status=QualityStatus.OK.value,
        )
    )


def _seed_quotes(session) -> None:
    b3 = get_or_create_source(
        session,
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
    b3.public_api_enabled = True
    b3.redistribution_policy = RedistributionPolicy.API_ONLY.value
    b3.public_dataset_enabled = False
    yahoo = get_or_create_source(
        session,
        name="yahoo",
        display_name="Yahoo Finance",
        official=False,
        homepage="https://finance.yahoo.com/",
        documentation_url="https://finance.yahoo.com/",
        data_license="UNKNOWN",
        redistribution_policy=RedistributionPolicy.UNKNOWN,
        public_api_enabled=False,
        public_dataset_enabled=False,
    )
    yahoo.official = False
    yahoo.redistribution_policy = RedistributionPolicy.UNKNOWN.value
    yahoo.public_api_enabled = False
    yahoo.public_dataset_enabled = False
    yahoo.ingestion_enabled = True

    petr = get_or_create_instrument_by_key(
        session,
        source_id=b3.id,
        source_key="PETR4",
        asset_class=AssetClass.EQUITY,
        instrument_type="listed",
        name="PETR4",
        currency="BRL",
    )
    attach_identifier(
        session,
        instrument_id=petr.id,
        identifier_type=IdentifierType.TICKER,
        identifier_value="PETR4",
        source_id=b3.id,
    )
    _ensure_quote(
        session,
        instrument_id=petr.id,
        source_id=b3.id,
        price_type=PriceType.LAST,
        value=Decimal("32.51"),
    )

    di1 = get_or_create_instrument_by_key(
        session,
        source_id=b3.id,
        source_key="DI1F27",
        asset_class=AssetClass.FUTURE,
        instrument_type="future",
        name="DI1F27",
        currency="BRL",
    )
    attach_identifier(
        session,
        instrument_id=di1.id,
        identifier_type=IdentifierType.TICKER,
        identifier_value="DI1F27",
        source_id=b3.id,
    )
    _ensure_quote(
        session,
        instrument_id=di1.id,
        source_id=b3.id,
        price_type=PriceType.OFFICIAL_SETTLEMENT,
        value=Decimal("98642.12"),
    )

    aapl = get_or_create_instrument_by_key(
        session,
        source_id=yahoo.id,
        source_key="AAPL",
        asset_class=AssetClass.EQUITY,
        instrument_type="stock",
        name="AAPL",
        currency="USD",
    )
    attach_identifier(
        session,
        instrument_id=aapl.id,
        identifier_type=IdentifierType.YAHOO_SYMBOL,
        identifier_value="AAPL",
        source_id=yahoo.id,
    )
    attach_identifier(
        session,
        instrument_id=aapl.id,
        identifier_type=IdentifierType.TICKER,
        identifier_value="AAPL",
        source_id=yahoo.id,
    )
    _ensure_quote(
        session,
        instrument_id=aapl.id,
        source_id=yahoo.id,
        price_type=PriceType.CLOSE,
        value=Decimal("185.64"),
    )
    session.commit()


def _client(tmp_path: Path) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_coverage_config_dir] = lambda: tmp_path
    return TestClient(app)


def _by_instrument(payload: dict) -> dict:
    return {row["instrument"]: row for row in payload["results"]}


@pytest.mark.db
def test_public_coverage_prices_b3_and_restricts_yahoo(db_session, tmp_path: Path) -> None:
    _seed_quotes(db_session)
    client = _client(_seed_universe(tmp_path))
    response = client.get("/v1/coverage", params={"date": REF.isoformat()})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "public"
    assert body["universe"] == "example"
    assert body["universe_size"] == 5
    rows = _by_instrument(body)
    assert rows["PETR4"]["status"] == "PRICED"
    assert rows["PETR4"]["price"] == "32.51"
    assert rows["PETR4"]["price_type"] == "LAST"
    assert rows["DI1F27"]["status"] == "PRICED"
    assert rows["DI1F27"]["price_type"] == "OFFICIAL_SETTLEMENT"
    assert Decimal(rows["DI1F27"]["price"]) == Decimal("98642.12")
    assert rows["AAPL"]["status"] == "RESTRICTED"
    assert rows["AAPL"]["missing_reason"] == "REDISTRIBUTION_RESTRICTED"
    assert rows["AAPL"]["price"] is None
    assert body["priced"] == 2


@pytest.mark.db
def test_coverage_has_no_yahoo_route(db_session, tmp_path: Path) -> None:
    _seed_quotes(db_session)
    client = _client(_seed_universe(tmp_path))
    assert client.get("/v1/yahoo").status_code == 404


@pytest.mark.db
def test_operator_universe_missing_is_404(db_session, tmp_path: Path) -> None:
    _seed_quotes(db_session)
    client = _client(_seed_universe(tmp_path))
    response = client.get(
        "/v1/coverage",
        params={"date": REF.isoformat(), "universe": "operator"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "universe not found"


@pytest.mark.db
def test_cli_local_counts_yahoo_close(db_session, tmp_path: Path) -> None:
    _seed_quotes(db_session)
    universe = _seed_universe(tmp_path) / "config" / "instruments.example.csv"
    result = runner.invoke(
        cli_app,
        ["coverage", "--date", REF.isoformat(), "--universe", str(universe)],
    )
    assert result.exit_code == 0, result.output
    assert "AAPL  PRICED  CLOSE  185.64" in result.output
    assert "PETR4  PRICED  LAST  32.51" in result.output
    assert "DI1F27  PRICED  OFFICIAL_SETTLEMENT" in result.output


@pytest.mark.db
def test_cli_public_flag_restricts_yahoo(db_session, tmp_path: Path) -> None:
    _seed_quotes(db_session)
    universe = _seed_universe(tmp_path) / "config" / "instruments.example.csv"
    result = runner.invoke(
        cli_app,
        ["coverage", "--date", REF.isoformat(), "--universe", str(universe), "--public"],
    )
    assert result.exit_code == 0, result.output
    assert "AAPL  RESTRICTED" in result.output
    assert "REDISTRIBUTION_RESTRICTED" in result.output
    assert "185.64" not in result.output.split("AAPL")[1].split("\n")[0]
