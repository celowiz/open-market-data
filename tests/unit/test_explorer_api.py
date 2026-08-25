from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from marketdata.api.main import create_app
from marketdata.config import Settings, get_settings
from marketdata.domain.enums import (
    AssetClass,
    IdentifierType,
    PriceType,
    QualityStatus,
    RedistributionPolicy,
)
from marketdata.storage.database import create_db_engine, create_session_factory
from marketdata.storage.models import (
    InstrumentIdentifierRow,
    InstrumentQuoteRow,
    InstrumentRow,
    MarketSeriesObservationRow,
    MarketSeriesRow,
)
from marketdata.storage.repositories import get_or_create_source


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


def _client() -> TestClient:
    return TestClient(create_app())


def _cors_client(monkeypatch: pytest.MonkeyPatch, origins: str) -> TestClient:
    monkeypatch.setattr(
        "marketdata.api.main.get_settings",
        lambda: Settings(_env_file=None, cors_allowed_origins=origins),
    )
    return _client()


def _source(session, *, name: str, policy: RedistributionPolicy, public_api: bool):
    return get_or_create_source(
        session,
        name=name,
        display_name=name,
        official=True,
        homepage="https://example.test/",
        documentation_url="https://example.test/",
        data_license="UNKNOWN",
        redistribution_policy=policy,
        public_api_enabled=public_api,
        public_dataset_enabled=False,
    )


def _add_identifier(session, instrument_id, *, identifier_type, value, source_id) -> None:
    session.add(
        InstrumentIdentifierRow(
            id=uuid4(),
            instrument_id=instrument_id,
            identifier_type=identifier_type.value,
            identifier_value=value,
            source_id=source_id,
        )
    )


def _add_quote(
    session,
    *,
    instrument_id,
    source_id,
    reference_date: date,
    value: Decimal,
    price_type: str,
    revision: int = 1,
) -> None:
    session.add(
        InstrumentQuoteRow(
            id=uuid4(),
            instrument_id=instrument_id,
            reference_date=reference_date,
            value=value,
            currency="BRL",
            unit="BRL",
            price_type=price_type,
            source_id=source_id,
            is_official=True,
            retrieved_at=datetime.now(UTC),
            revision=revision,
            quality_status=QualityStatus.OK.value,
        )
    )


def _add_instrument(
    session,
    *,
    ticker: str,
    name: str,
    source,
    asset_class: AssetClass,
    instrument_type: str,
    identifier_type: IdentifierType = IdentifierType.TICKER,
):
    instrument = InstrumentRow(
        id=uuid4(),
        asset_class=asset_class.value,
        instrument_type=instrument_type,
        name=name,
        currency="BRL",
    )
    session.add(instrument)
    session.flush()
    _add_identifier(
        session,
        instrument.id,
        identifier_type=identifier_type,
        value=ticker,
        source_id=source.id,
    )
    return instrument


@pytest.fixture
def explorer_seed(db_session):
    suffix = uuid4().hex[:8].upper()
    b3 = _source(
        db_session,
        name=f"b3-api-{suffix.lower()}",
        policy=RedistributionPolicy.API_ONLY,
        public_api=True,
    )
    yahoo = _source(
        db_session,
        name=f"yahoo-api-{suffix.lower()}",
        policy=RedistributionPolicy.UNKNOWN,
        public_api=True,
    )
    cvm = _source(
        db_session,
        name=f"cvm-api-{suffix.lower()}",
        policy=RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION,
        public_api=True,
    )
    bcb = _source(
        db_session,
        name=f"bcb-api-{suffix.lower()}",
        policy=RedistributionPolicy.PUBLIC,
        public_api=True,
    )

    b3_ticker = f"B3{suffix}"
    b3_instrument = _add_instrument(
        db_session,
        ticker=b3_ticker,
        name=f"Visible B3 Equity {suffix}",
        source=b3,
        asset_class=AssetClass.EQUITY,
        instrument_type="stock",
    )
    _add_quote(
        db_session,
        instrument_id=b3_instrument.id,
        source_id=b3.id,
        reference_date=date(2026, 1, 5),
        value=Decimal("10.00"),
        price_type=PriceType.LAST.value,
        revision=1,
    )
    _add_quote(
        db_session,
        instrument_id=b3_instrument.id,
        source_id=b3.id,
        reference_date=date(2026, 1, 5),
        value=Decimal("10.50"),
        price_type=PriceType.LAST.value,
        revision=2,
    )
    _add_quote(
        db_session,
        instrument_id=b3_instrument.id,
        source_id=b3.id,
        reference_date=date(2026, 1, 6),
        value=Decimal("11.25"),
        price_type=PriceType.LAST.value,
    )
    _add_quote(
        db_session,
        instrument_id=b3_instrument.id,
        source_id=b3.id,
        reference_date=date(2026, 1, 7),
        value=Decimal("12.00"),
        price_type=PriceType.LAST.value,
    )

    yahoo_ticker = f"YH{suffix}"
    yahoo_instrument = _add_instrument(
        db_session,
        ticker=yahoo_ticker,
        name=f"Visible Yahoo Equity {suffix}",
        source=yahoo,
        asset_class=AssetClass.EQUITY,
        instrument_type="stock",
    )
    _add_quote(
        db_session,
        instrument_id=yahoo_instrument.id,
        source_id=yahoo.id,
        reference_date=date(2026, 1, 7),
        value=Decimal("99.99"),
        price_type=PriceType.CLOSE.value,
    )

    fund_id = f"8888{suffix[:10].zfill(10)}"[:14]
    fund = _add_instrument(
        db_session,
        ticker=fund_id,
        name=f"Visible Fund {suffix}",
        source=cvm,
        asset_class=AssetClass.FUND,
        instrument_type="fund",
        identifier_type=IdentifierType.CNPJ,
    )
    for day, nav in (
        (date(2026, 2, 1), Decimal("1.10000000")),
        (date(2026, 2, 2), Decimal("1.20000000")),
        (date(2026, 2, 3), Decimal("1.30000000")),
    ):
        _add_quote(
            db_session,
            instrument_id=fund.id,
            source_id=cvm.id,
            reference_date=day,
            value=nav,
            price_type=PriceType.FUND_NAV.value,
        )

    series_code = f"TEST:CDI_{suffix}"
    series = MarketSeriesRow(
        id=uuid4(),
        code=series_code,
        source_series_id=series_code,
        name=f"Test CDI {suffix}",
        source_id=bcb.id,
        unit="percent_per_day",
        value_semantics="REFERENCE",
    )
    db_session.add(series)
    db_session.flush()
    for day, value in (
        (date(2026, 3, 1), Decimal("0.041000")),
        (date(2026, 3, 2), Decimal("0.042000")),
        (date(2026, 3, 3), Decimal("0.043000")),
    ):
        db_session.add(
            MarketSeriesObservationRow(
                id=uuid4(),
                series_id=series.id,
                reference_date=day,
                value=value,
                source_id=bcb.id,
                retrieved_at=datetime.now(UTC),
                revision=1,
                quality_status=QualityStatus.OK.value,
            )
        )

    empty_code = f"TEST:EMPTY_{suffix}"
    db_session.add(
        MarketSeriesRow(
            id=uuid4(),
            code=empty_code,
            source_series_id=empty_code,
            name=f"Empty series {suffix}",
            source_id=bcb.id,
            unit="percent_per_day",
            value_semantics="REFERENCE",
        )
    )
    db_session.commit()
    return SimpleNamespace(
        b3_ticker=b3_ticker,
        b3_instrument_id=str(b3_instrument.id),
        yahoo_ticker=yahoo_ticker,
        fund_id=fund_id,
        series_code=series_code,
        empty_series_code=empty_code,
        suffix=suffix,
    )


def test_cors_header_present_when_origins_set(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _cors_client(monkeypatch, "http://localhost:3000")
    response = client.get("/v1/health", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_cors_header_absent_when_origins_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _cors_client(monkeypatch, "")
    response = client.get("/v1/health", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_history_limit_schema_default_500_max_5000() -> None:
    spec = _client().get("/openapi.json").json()
    paths = (
        "/v1/quotes/{identifier}",
        "/v1/quotes/{identifier}/history",
        "/v1/funds/{identifier}/quotes",
        "/v1/series/{code}/observations",
    )
    for path in paths:
        params = spec["paths"][path]["get"]["parameters"]
        names = {item["name"] for item in params}
        assert {"start", "end", "cursor", "limit"} <= names
        limit = next(item for item in params if item["name"] == "limit")
        schema = limit["schema"]
        assert schema["default"] == 500
        assert schema["maximum"] == 5000
        assert schema["minimum"] == 1


def test_quotes_limit_5001_is_unprocessable() -> None:
    response = _client().get("/v1/quotes/PETR4", params={"limit": 5001})
    assert response.status_code == 422


def test_instruments_empty_q_returns_400() -> None:
    client = _client()
    missing = client.get("/v1/instruments")
    assert missing.status_code == 400
    blank = client.get("/v1/instruments", params={"q": ""})
    assert blank.status_code == 400
    whitespace = client.get("/v1/instruments", params={"q": "   "})
    assert whitespace.status_code == 400


@pytest.mark.db
def test_yahoo_quotes_and_instruments_are_visible(explorer_seed) -> None:
    client = _client()
    visible = client.get(f"/v1/quotes/{explorer_seed.yahoo_ticker}")
    assert visible.status_code == 200
    body = visible.json()
    assert body["quotes"]
    assert Decimal(body["quotes"][0]["price"]) == Decimal("99.99")
    search = client.get("/v1/instruments", params={"q": explorer_seed.yahoo_ticker})
    assert search.status_code == 200
    rows = search.json()["instruments"]
    assert len(rows) == 1
    assert explorer_seed.yahoo_ticker in rows[0]["identifiers"]


@pytest.mark.db
def test_b3_api_only_quotes_are_visible_as_decimal_strings(explorer_seed) -> None:
    client = _client()
    response = client.get(f"/v1/quotes/{explorer_seed.b3_ticker}")
    assert response.status_code == 200
    body = response.json()
    assert body["quotes"]
    price = body["quotes"][0]["price"]
    assert isinstance(price, str)
    assert Decimal(price) == Decimal("12.00")
    assert body["quotes"][0]["price_type"] == PriceType.LAST.value
    assert "retrieved_at" in body["quotes"][0]
    assert "raw_artifact_sha256" in body["quotes"][0]
    assert "revision" in body["quotes"][0]
    assert "official" in body["quotes"][0]


@pytest.mark.db
def test_quotes_history_alias_start_end_and_revision_dedup(explorer_seed) -> None:
    client = _client()
    ranged = client.get(
        f"/v1/quotes/{explorer_seed.b3_ticker}/history",
        params={"start": "2026-01-05", "end": "2026-01-06"},
    )
    assert ranged.status_code == 200
    quotes = ranged.json()["quotes"]
    dates = [item["date"] for item in quotes]
    assert dates == ["2026-01-06", "2026-01-05"]
    jan5 = next(item for item in quotes if item["date"] == "2026-01-05")
    assert isinstance(jan5["price"], str)
    assert Decimal(jan5["price"]) == Decimal("10.50")
    assert jan5["revision"] == 2


@pytest.mark.db
def test_quotes_cursor_and_next_cursor(explorer_seed) -> None:
    client = _client()
    first = client.get(f"/v1/quotes/{explorer_seed.b3_ticker}", params={"limit": 2})
    assert first.status_code == 200
    body = first.json()
    assert [item["date"] for item in body["quotes"]] == ["2026-01-07", "2026-01-06"]
    assert body["next_cursor"] == "2026-01-05"
    second = client.get(
        f"/v1/quotes/{explorer_seed.b3_ticker}",
        params={"limit": 2, "cursor": body["next_cursor"]},
    )
    assert second.status_code == 200
    page = second.json()
    assert [item["date"] for item in page["quotes"]] == ["2026-01-05"]
    assert page["next_cursor"] is None


@pytest.mark.db
def test_quotes_limit_5000_accepted(explorer_seed) -> None:
    response = _client().get(
        f"/v1/quotes/{explorer_seed.b3_ticker}",
        params={"limit": 5000},
    )
    assert response.status_code == 200


@pytest.mark.db
def test_quotes_date_inconsistent_with_start_end_is_422(explorer_seed) -> None:
    response = _client().get(
        f"/v1/quotes/{explorer_seed.b3_ticker}",
        params={"date": "2026-01-07", "start": "2026-01-05", "end": "2026-01-06"},
    )
    assert response.status_code == 422


@pytest.mark.db
def test_funds_start_end_cursor_and_decimal_strings(explorer_seed) -> None:
    client = _client()
    first = client.get(
        f"/v1/funds/{explorer_seed.fund_id}/quotes",
        params={"start": "2026-02-01", "end": "2026-02-03", "limit": 2},
    )
    assert first.status_code == 200
    body = first.json()
    assert [item["date"] for item in body["quotes"]] == ["2026-02-03", "2026-02-02"]
    assert isinstance(body["quotes"][0]["price"], str)
    assert Decimal(body["quotes"][0]["price"]) == Decimal("1.30000000")
    assert body["next_cursor"] == "2026-02-01"
    second = client.get(
        f"/v1/funds/{explorer_seed.fund_id}/quotes",
        params={"cursor": body["next_cursor"], "limit": 2},
    )
    assert [item["date"] for item in second.json()["quotes"]] == ["2026-02-01"]
    assert second.json()["next_cursor"] is None


@pytest.mark.db
def test_series_observations_start_end_cursor_and_latest(explorer_seed) -> None:
    client = _client()
    first = client.get(
        f"/v1/series/{explorer_seed.series_code}/observations",
        params={"start": "2026-03-01", "end": "2026-03-03", "limit": 2},
    )
    assert first.status_code == 200
    body = first.json()
    assert [item["date"] for item in body["observations"]] == ["2026-03-03", "2026-03-02"]
    assert isinstance(body["observations"][0]["value"], str)
    assert Decimal(body["observations"][0]["value"]) == Decimal("0.043000")
    assert body["next_cursor"] == "2026-03-01"
    latest = client.get(f"/v1/series/{explorer_seed.series_code}/latest")
    assert latest.status_code == 200
    payload = latest.json()
    assert payload["date"] == "2026-03-03"
    assert isinstance(payload["value"], str)
    assert Decimal(payload["value"]) == Decimal("0.043000")


@pytest.mark.db
def test_series_latest_404_if_none(explorer_seed) -> None:
    response = _client().get(f"/v1/series/{explorer_seed.empty_series_code}/latest")
    assert response.status_code == 404


@pytest.mark.db
def test_instruments_search_public_only(explorer_seed) -> None:
    client = _client()
    by_ticker = client.get("/v1/instruments", params={"q": explorer_seed.b3_ticker})
    assert by_ticker.status_code == 200
    rows = by_ticker.json()["instruments"]
    assert len(rows) == 1
    assert rows[0]["instrument_id"] == explorer_seed.b3_instrument_id
    assert rows[0]["name"] == f"Visible B3 Equity {explorer_seed.suffix}"
    assert rows[0]["asset_class"] == AssetClass.EQUITY.value
    assert explorer_seed.b3_ticker in rows[0]["identifiers"]
    by_name = client.get(
        "/v1/instruments", params={"q": f"Visible B3 Equity {explorer_seed.suffix}"}
    )
    assert by_name.status_code == 200
    assert by_name.json()["instruments"][0]["instrument_id"] == explorer_seed.b3_instrument_id
