from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from typer.testing import CliRunner

from marketdata.api.deps import get_db
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
from marketdata.storage.models import Base, InstrumentQuoteRow, SourceRow
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
        public_api_enabled=True,
        public_dataset_enabled=False,
    )
    yahoo.official = False
    yahoo.redistribution_policy = RedistributionPolicy.UNKNOWN.value
    yahoo.public_api_enabled = True
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
def test_public_coverage_prices_b3_and_yahoo(db_session, tmp_path: Path) -> None:
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
    assert rows["AAPL"]["status"] == "PRICED"
    assert rows["AAPL"]["price"] == "185.64"
    assert rows["AAPL"]["price_type"] == "CLOSE"
    assert body["priced"] == 3


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
def test_scratch_universe_missing_is_404(db_session, tmp_path: Path) -> None:
    _seed_quotes(db_session)
    client = _client(_seed_universe(tmp_path))
    response = client.get(
        "/v1/coverage",
        params={"date": REF.isoformat(), "universe": "scratch"},
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "universe not found"


@pytest.mark.db
def test_scratch_universe_prices_named_csv(db_session, tmp_path: Path) -> None:
    _seed_quotes(db_session)
    config = tmp_path / "config"
    config.mkdir()
    (config / "instruments.scratch.csv").write_text(
        TINY.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    client = _client(tmp_path)
    response = client.get(
        "/v1/coverage",
        params={"date": REF.isoformat(), "universe": "scratch"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["universe"] == "scratch"
    assert body["universe_size"] == 5
    assert body["priced"] == 3


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
def test_cli_public_flag_prices_yahoo(db_session, tmp_path: Path) -> None:
    _seed_quotes(db_session)
    universe = _seed_universe(tmp_path) / "config" / "instruments.example.csv"
    result = runner.invoke(
        cli_app,
        ["coverage", "--date", REF.isoformat(), "--universe", str(universe), "--public"],
    )
    assert result.exit_code == 0, result.output
    assert "AAPL  PRICED  CLOSE  185.64" in result.output
    assert "PETR4  PRICED  LAST  32.51" in result.output


def test_coverage_span_openapi_is_cheap_and_does_not_require_date() -> None:
    spec = TestClient(create_app()).get("/openapi.json").json()
    operation = spec["paths"]["/v1/coverage/span"]["get"]
    params = {item["name"]: item for item in operation["parameters"]}
    assert "date" not in params
    assert params["universe"]["schema"]["default"] == "example"
    assert params["source"].get("required") is not True
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        schema = spec["components"]["schemas"][name]
    assert {
        "universe",
        "universe_size",
        "instruments_with_quotes",
        "min_date",
        "max_date",
        "quote_count",
        "results",
    } <= set(schema["properties"])
    assert "priced" not in schema["properties"]
    item = spec["components"]["schemas"]["CoverageSpanItem"]
    assert {
        "ticker",
        "instrument_id",
        "source",
        "min_date",
        "max_date",
        "quote_count",
    } <= set(item["properties"])


@pytest.mark.db
def test_coverage_span_scratch_returns_min_max_count(db_session, tmp_path: Path) -> None:
    _seed_quotes(db_session)
    config = tmp_path / "config"
    config.mkdir()
    (config / "instruments.scratch.csv").write_text(
        TINY.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    client = _client(tmp_path)
    response = client.get("/v1/coverage/span", params={"universe": "scratch"})
    assert response.status_code == 200
    body = response.json()
    assert body["universe"] == "scratch"
    assert body["universe_size"] == 7
    assert body["instruments_with_quotes"] == 3
    assert body["min_date"] == REF.isoformat()
    assert body["max_date"] == REF.isoformat()
    assert body["quote_count"] == 3
    by_ticker = {row["ticker"]: row for row in body["results"]}
    assert set(by_ticker) == {
        "PETR4",
        "PETR4.SA",
        "DI1F27",
        "AAPL",
        "UNKNOWN1",
        "UNKNOWN1.SA",
        "CVMSTUB",
    }
    assert by_ticker["PETR4"]["source"] == "b3"
    assert by_ticker["PETR4"]["min_date"] == REF.isoformat()
    assert by_ticker["PETR4"]["quote_count"] == 1
    assert by_ticker["PETR4"]["instrument_id"]
    assert by_ticker["PETR4.SA"]["source"] == "yahoo"
    assert by_ticker["PETR4.SA"]["quote_count"] == 0
    assert by_ticker["UNKNOWN1"]["quote_count"] == 0
    assert by_ticker["UNKNOWN1"]["min_date"] is None
    assert by_ticker["CVMSTUB"]["quote_count"] == 0


@pytest.mark.db
def test_coverage_span_source_filter_hides_other_providers(db_session, tmp_path: Path) -> None:
    _seed_quotes(db_session)
    config = tmp_path / "config"
    config.mkdir()
    (config / "instruments.scratch.csv").write_text(
        TINY.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    client = _client(tmp_path)
    response = client.get(
        "/v1/coverage/span",
        params={"universe": "scratch", "source": "b3"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "b3"
    assert body["universe_size"] == 5
    assert body["instruments_with_quotes"] == 2
    by_ticker = {row["ticker"]: row for row in body["results"]}
    assert set(by_ticker) == {"PETR4", "DI1F27", "AAPL", "UNKNOWN1", "CVMSTUB"}
    assert by_ticker["PETR4"]["quote_count"] == 1
    assert by_ticker["DI1F27"]["quote_count"] == 1
    assert by_ticker["AAPL"]["quote_count"] == 0
    assert "PETR4.SA" not in by_ticker


@pytest.mark.db
def test_coverage_span_shows_yahoo_sa_without_colliding_with_b3_petr4(
    db_session, tmp_path: Path
) -> None:
    _seed_quotes(db_session)
    yahoo = db_session.scalar(select(SourceRow).where(SourceRow.name == "yahoo"))
    assert yahoo is not None
    petr_sa = get_or_create_instrument_by_key(
        db_session,
        source_id=yahoo.id,
        source_key="PETR4.SA",
        asset_class=AssetClass.EQUITY,
        instrument_type="equity",
        name="PETR4.SA",
        currency="BRL",
    )
    attach_identifier(
        db_session,
        instrument_id=petr_sa.id,
        identifier_type=IdentifierType.YAHOO_SYMBOL,
        identifier_value="PETR4.SA",
        source_id=yahoo.id,
    )
    attach_identifier(
        db_session,
        instrument_id=petr_sa.id,
        identifier_type=IdentifierType.TICKER,
        identifier_value="PETR4.SA",
        source_id=yahoo.id,
    )
    _ensure_quote(
        db_session,
        instrument_id=petr_sa.id,
        source_id=yahoo.id,
        price_type=PriceType.CLOSE,
        value=Decimal("45.02"),
    )
    db_session.commit()

    config = tmp_path / "config"
    config.mkdir()
    (config / "instruments.scratch.csv").write_text(
        TINY.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    client = _client(tmp_path)
    response = client.get("/v1/coverage/span", params={"universe": "scratch"})
    assert response.status_code == 200
    body = response.json()
    by_ticker = {row["ticker"]: row for row in body["results"]}
    assert by_ticker["PETR4"]["source"] == "b3"
    assert by_ticker["PETR4"]["quote_count"] == 1
    assert by_ticker["PETR4"]["instrument_id"] != str(petr_sa.id)
    assert by_ticker["PETR4.SA"]["source"] == "yahoo"
    assert by_ticker["PETR4.SA"]["quote_count"] == 1
    assert by_ticker["PETR4.SA"]["instrument_id"] == str(petr_sa.id)
    assert body["instruments_with_quotes"] == 4

    yahoo_only = client.get(
        "/v1/coverage/span",
        params={"universe": "scratch", "source": "yahoo"},
    )
    assert yahoo_only.status_code == 200
    yahoo_body = yahoo_only.json()
    yahoo_tickers = {row["ticker"]: row for row in yahoo_body["results"]}
    assert "PETR4" not in yahoo_tickers
    assert yahoo_tickers["PETR4.SA"]["source"] == "yahoo"
    assert yahoo_tickers["PETR4.SA"]["quote_count"] == 1
    assert yahoo_tickers["AAPL"]["quote_count"] == 1


@pytest.mark.db
def test_coverage_span_scratch_missing_is_404(db_session, tmp_path: Path) -> None:
    _seed_quotes(db_session)
    client = _client(_seed_universe(tmp_path))
    response = client.get("/v1/coverage/span", params={"universe": "scratch"})
    assert response.status_code == 404
    assert response.json()["detail"] == "universe not found"


def test_coverage_span_sqlite_lists_yahoo_sa_beside_b3_petr4(tmp_path: Path) -> None:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'span.db'}",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = factory()
    try:
        _seed_quotes(session)
        yahoo = session.scalar(select(SourceRow).where(SourceRow.name == "yahoo"))
        assert yahoo is not None
        petr_sa = get_or_create_instrument_by_key(
            session,
            source_id=yahoo.id,
            source_key="PETR4.SA",
            asset_class=AssetClass.EQUITY,
            instrument_type="equity",
            name="PETR4.SA",
            currency="BRL",
        )
        attach_identifier(
            session,
            instrument_id=petr_sa.id,
            identifier_type=IdentifierType.YAHOO_SYMBOL,
            identifier_value="PETR4.SA",
            source_id=yahoo.id,
        )
        attach_identifier(
            session,
            instrument_id=petr_sa.id,
            identifier_type=IdentifierType.TICKER,
            identifier_value="PETR4.SA",
            source_id=yahoo.id,
        )
        _ensure_quote(
            session,
            instrument_id=petr_sa.id,
            source_id=yahoo.id,
            price_type=PriceType.CLOSE,
            value=Decimal("45.02"),
        )
        session.commit()
    finally:
        session.close()

    def override_db():
        db = factory()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    config = tmp_path / "config"
    config.mkdir()
    (config / "instruments.scratch.csv").write_text(
        TINY.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    app = create_app()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_coverage_config_dir] = lambda: tmp_path
    client = TestClient(app)
    body = client.get("/v1/coverage/span", params={"universe": "scratch"}).json()
    by_ticker = {row["ticker"]: row for row in body["results"]}
    assert by_ticker["PETR4"]["source"] == "b3"
    assert by_ticker["PETR4"]["quote_count"] == 1
    assert by_ticker["PETR4.SA"]["source"] == "yahoo"
    assert by_ticker["PETR4.SA"]["quote_count"] == 1
    assert by_ticker["PETR4"]["instrument_id"] != by_ticker["PETR4.SA"]["instrument_id"]
    yahoo_body = client.get(
        "/v1/coverage/span",
        params={"universe": "scratch", "source": "yahoo"},
    ).json()
    yahoo_tickers = {row["ticker"]: row for row in yahoo_body["results"]}
    assert "PETR4" not in yahoo_tickers
    assert yahoo_tickers["PETR4.SA"]["quote_count"] == 1
    engine.dispose()
