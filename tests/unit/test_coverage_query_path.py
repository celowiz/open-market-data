from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from marketdata.api.deps import get_db
from marketdata.api.main import create_app
from marketdata.api.routes.coverage import get_coverage_config_dir
from marketdata.coverage.csv import UniverseRow
from marketdata.coverage.engine import CoverageMode, evaluate_coverage
from marketdata.coverage.store import SessionCoverageStore
from marketdata.domain.enums import (
    AssetClass,
    IdentifierType,
    MissingReason,
    PriceType,
    QualityStatus,
    RedistributionPolicy,
)
from marketdata.storage.models import (
    Base,
    InstrumentIdentifierRow,
    InstrumentQuoteRow,
    InstrumentRow,
    SourceRow,
)

REF = date(2026, 8, 21)
PRIOR = date(2026, 8, 20)
UNIVERSE_N = 24
SELECT_BUDGET = 12

UNIVERSE_HEADER = (
    "instrument_id,asset_class,ticker,isin,cnpj_fundo_classe,title_type,"
    "maturity_date,exchange,currency,preferred_provider,universe\n"
)


def _memory_session() -> tuple[Session, object]:
    engine = create_engine(
        "sqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    return factory(), engine


def _capture_selects(engine):
    statements: list[str] = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        stripped = statement.lstrip().upper()
        if stripped.startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    return statements


def _seed_source(session: Session) -> SourceRow:
    source = SourceRow(
        id=uuid4(),
        name="b3",
        display_name="B3",
        official=True,
        homepage="https://www.b3.com.br/",
        documentation_url="https://www.b3.com.br/",
        data_license="UNKNOWN",
        redistribution_policy=RedistributionPolicy.API_ONLY.value,
        ingestion_enabled=True,
        public_api_enabled=True,
        public_dataset_enabled=False,
    )
    session.add(source)
    session.flush()
    return source


def _seed_equity(
    session: Session,
    *,
    source: SourceRow,
    ticker: str,
    quote_date: date,
    value: Decimal,
) -> InstrumentRow:
    instrument = InstrumentRow(
        id=uuid4(),
        asset_class=AssetClass.EQUITY.value,
        instrument_type="listed",
        name=ticker,
        currency="BRL",
        exchange="B3",
    )
    session.add(instrument)
    session.flush()
    session.add(
        InstrumentIdentifierRow(
            id=uuid4(),
            instrument_id=instrument.id,
            identifier_type=IdentifierType.TICKER.value,
            identifier_value=ticker,
            source_id=source.id,
        )
    )
    session.add(
        InstrumentQuoteRow(
            id=uuid4(),
            instrument_id=instrument.id,
            reference_date=quote_date,
            value=value,
            currency="BRL",
            unit="BRL",
            price_type=PriceType.LAST.value,
            source_id=source.id,
            is_official=True,
            retrieved_at=datetime.now(UTC),
            revision=1,
            quality_status=QualityStatus.OK.value,
        )
    )
    return instrument


def _universe_rows(tickers: list[str]) -> list[UniverseRow]:
    return [
        UniverseRow(
            instrument_id=None,
            asset_class="equity",
            ticker=ticker,
            isin=None,
            cnpj_fundo_classe=None,
            title_type=None,
            maturity_date=None,
            exchange="B3",
            currency="BRL",
            preferred_provider="b3",
            universe="ibov",
        )
        for ticker in tickers
    ]


def _write_scratch_csv(tmp_path: Path, tickers: list[str]) -> Path:
    config = tmp_path / "config"
    config.mkdir()
    dest = config / "instruments.scratch.csv"
    lines = [UNIVERSE_HEADER]
    for ticker in tickers:
        lines.append(f",equity,{ticker},,,,,B3,BRL,b3,ibov\n")
    dest.write_text("".join(lines), encoding="utf-8")
    return tmp_path


def test_session_coverage_scores_stale_universe_with_bounded_selects() -> None:
    session, engine = _memory_session()
    tickers = [f"T{i:03d}" for i in range(UNIVERSE_N)]
    try:
        source = _seed_source(session)
        for ticker in tickers:
            _seed_equity(
                session,
                source=source,
                ticker=ticker,
                quote_date=PRIOR,
                value=Decimal("10.00"),
            )
        session.commit()
        selects = _capture_selects(engine)
        report = evaluate_coverage(
            _universe_rows(tickers),
            reference_date=REF,
            store=SessionCoverageStore(session),
            mode=CoverageMode.PUBLIC,
            today=REF,
            universe_name="scratch",
        )
    finally:
        session.close()

    assert report.universe_size == UNIVERSE_N
    assert report.priced == 0
    assert report.missing_reason_counts == {MissingReason.STALE.value: UNIVERSE_N}
    assert all(item.staleness == 1 for item in report.results)
    assert len(selects) <= SELECT_BUDGET, (
        f"coverage issued {len(selects)} SELECTs for {UNIVERSE_N} rows; "
        f"expected <= {SELECT_BUDGET} batched queries, not per-row lookups"
    )


def test_session_coverage_prices_latest_revision_in_one_quote_query() -> None:
    session, engine = _memory_session()
    ticker = "PETR4"
    try:
        source = _seed_source(session)
        instrument = _seed_equity(
            session,
            source=source,
            ticker=ticker,
            quote_date=REF,
            value=Decimal("32"),
        )
        session.add(
            InstrumentQuoteRow(
                id=uuid4(),
                instrument_id=instrument.id,
                reference_date=REF,
                value=Decimal("33"),
                currency="BRL",
                unit="BRL",
                price_type=PriceType.LAST.value,
                source_id=source.id,
                is_official=True,
                retrieved_at=datetime.now(UTC),
                revision=2,
                quality_status=QualityStatus.OK.value,
            )
        )
        session.commit()
        selects = _capture_selects(engine)
        report = evaluate_coverage(
            _universe_rows([ticker]),
            reference_date=REF,
            store=SessionCoverageStore(session),
            mode=CoverageMode.PUBLIC,
            today=REF,
            universe_name="scratch",
        )
    finally:
        session.close()

    assert report.priced == 1
    assert report.results[0].price == Decimal("33")
    assert len(selects) <= SELECT_BUDGET


def test_coverage_api_scratch_page_does_not_requery_per_row(tmp_path: Path) -> None:
    session, engine = _memory_session()
    tickers = [f"T{i:03d}" for i in range(UNIVERSE_N)]
    source = _seed_source(session)
    for ticker in tickers:
        _seed_equity(
            session,
            source=source,
            ticker=ticker,
            quote_date=PRIOR,
            value=Decimal("10.00"),
        )
    session.commit()
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    def override_db():
        db = factory()
        try:
            yield db
            db.commit()
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_coverage_config_dir] = lambda: _write_scratch_csv(
        tmp_path, tickers
    )
    client = TestClient(app)
    selects = _capture_selects(engine)
    response = client.get(
        "/v1/coverage",
        params={"date": REF.isoformat(), "universe": "scratch", "limit": 5, "cursor": 0},
    )
    session.close()
    assert response.status_code == 200
    body = response.json()
    assert body["universe"] == "scratch"
    assert body["universe_size"] == UNIVERSE_N
    assert body["priced"] == 0
    assert body["next_cursor"] == 5
    assert len(body["results"]) == 5
    assert body["missing_reason_counts"] == {MissingReason.STALE.value: UNIVERSE_N}
    assert len(selects) <= SELECT_BUDGET, (
        f"GET /v1/coverage issued {len(selects)} SELECTs for {UNIVERSE_N} rows"
    )


def test_coverage_openapi_keeps_universe_pagination_and_summary() -> None:
    spec = TestClient(create_app()).get("/openapi.json").json()
    operation = spec["paths"]["/v1/coverage"]["get"]
    params = {item["name"]: item for item in operation["parameters"]}
    assert params["date"]["required"] is True
    assert params["universe"]["schema"]["enum"] == ["example", "operator", "scratch"]
    assert params["universe"]["schema"]["default"] == "example"
    assert params["limit"]["schema"]["default"] == 100
    assert params["limit"]["schema"]["maximum"] == 1000
    assert params["cursor"]["schema"]["default"] == 0
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    if "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].rsplit("/", 1)[-1]]
    assert {
        "date",
        "universe",
        "mode",
        "universe_size",
        "priced",
        "priced_pct",
        "missing_reason_counts",
        "results",
        "next_cursor",
    } <= set(schema["properties"])
