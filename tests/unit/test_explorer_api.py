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
    hidden = _source(
        db_session,
        name=f"hidden-api-{suffix.lower()}",
        policy=RedistributionPolicy.INTERNAL_ONLY,
        public_api=False,
    )
    hidden_instrument = _add_instrument(
        db_session,
        ticker=f"HD{suffix}",
        name=f"Hidden Equity {suffix}",
        source=hidden,
        asset_class=AssetClass.EQUITY,
        instrument_type="stock",
    )
    _add_quote(
        db_session,
        instrument_id=hidden_instrument.id,
        source_id=hidden.id,
        reference_date=date(2026, 1, 7),
        value=Decimal("1.00"),
        price_type=PriceType.LAST.value,
    )

    db_session.commit()
    return SimpleNamespace(
        b3_ticker=b3_ticker,
        b3_instrument_id=str(b3_instrument.id),
        b3_source_name=b3.name,
        yahoo_ticker=yahoo_ticker,
        yahoo_instrument_id=str(yahoo_instrument.id),
        yahoo_source_name=yahoo.name,
        fund_id=fund_id,
        fund_instrument_id=str(fund.id),
        cvm_source_name=cvm.name,
        hidden_instrument_id=str(hidden_instrument.id),
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


def test_quotes_limit_5001_is_unprocessable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "marketdata.api.deps.get_settings",
        lambda: Settings(_env_file=None, database_url=""),
    )
    response = _client().get("/v1/quotes/PETR4", params={"limit": 5001})
    assert response.status_code == 422


def test_quotes_without_database_url_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "marketdata.api.deps.get_settings",
        lambda: Settings(_env_file=None, database_url=""),
    )
    response = _client().get("/v1/quotes/PETR4")
    assert response.status_code == 503
    assert response.json()["detail"] == "DATABASE_URL is not configured"


def test_instruments_openapi_lists_with_optional_q() -> None:
    spec = _client().get("/openapi.json").json()
    operation = spec["paths"]["/v1/instruments"]["get"]
    params = {item["name"]: item for item in operation["parameters"]}
    assert params["q"].get("required") is not True
    assert {"cursor", "limit", "source", "asset_class"} <= set(params)
    assert params["limit"]["schema"]["default"] == 20
    assert params["limit"]["schema"]["maximum"] == 100
    schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    if "$ref" in schema:
        name = schema["$ref"].rsplit("/", 1)[-1]
        schema = spec["components"]["schemas"][name]
    assert "next_cursor" in schema["properties"]
    item = spec["components"]["schemas"]["InstrumentSearchItem"]
    assert "sources" in item["properties"]
    assert "first_quote_date" in item["properties"]
    assert "last_quote_date" in item["properties"]
    assert "quote_count" in item["properties"]


def test_sources_openapi_hides_test_rows_by_default() -> None:
    spec = _client().get("/openapi.json").json()
    operation = spec["paths"]["/v1/sources"]["get"]
    params = {item["name"]: item for item in operation["parameters"]}
    assert params["include_test"]["schema"]["default"] is False
    assert params["include_test"].get("required") is not True


def test_instruments_invalid_cursor_returns_400() -> None:
    response = _client().get("/v1/instruments", params={"cursor": "not-a-uuid"})
    assert response.status_code == 400
    assert "cursor" in str(response.json()["detail"]).lower()


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


def _instrument_ids(response) -> set[str]:
    return {row["instrument_id"] for row in response.json()["instruments"]}


def _list_all_instruments(client, **params) -> list[dict]:
    items: list[dict] = []
    cursor: str | None = None
    query = dict(params)
    query.setdefault("limit", 100)
    for _ in range(50):
        page_query = dict(query)
        if cursor is not None:
            page_query["cursor"] = cursor
        response = client.get("/v1/instruments", params=page_query)
        assert response.status_code == 200
        body = response.json()
        items.extend(body["instruments"])
        cursor = body["next_cursor"]
        if not cursor:
            return items
    raise AssertionError("instrument catalog pagination did not terminate")


@pytest.mark.db
def test_instruments_empty_q_lists_visible_public_instruments(explorer_seed) -> None:
    client = _client()
    listed = (
        _list_all_instruments(client),
        _list_all_instruments(client, q=""),
        _list_all_instruments(client, q="   "),
    )
    for rows in listed:
        ids = {row["instrument_id"] for row in rows}
        assert explorer_seed.b3_instrument_id in ids
        assert explorer_seed.yahoo_instrument_id in ids
        assert explorer_seed.fund_instrument_id in ids
        assert explorer_seed.hidden_instrument_id not in ids
        b3_row = next(row for row in rows if row["instrument_id"] == explorer_seed.b3_instrument_id)
        assert b3_row["name"] == f"Visible B3 Equity {explorer_seed.suffix}"
        assert b3_row["asset_class"] == AssetClass.EQUITY.value
        assert explorer_seed.b3_ticker in b3_row["identifiers"]
        assert explorer_seed.b3_source_name in b3_row["sources"]


@pytest.mark.db
def test_instruments_q_still_searches(explorer_seed) -> None:
    client = _client()
    response = client.get("/v1/instruments", params={"q": explorer_seed.yahoo_ticker})
    assert response.status_code == 200
    rows = response.json()["instruments"]
    assert [row["instrument_id"] for row in rows] == [explorer_seed.yahoo_instrument_id]
    missed = client.get(
        "/v1/instruments", params={"q": f"no-such-instrument-{explorer_seed.suffix}"}
    )
    assert missed.status_code == 200
    assert missed.json()["instruments"] == []
    assert missed.json()["next_cursor"] is None


@pytest.mark.db
def test_instruments_list_pagination_and_source_filter(explorer_seed, db_session) -> None:
    suffix = explorer_seed.suffix
    source = _source(
        db_session,
        name=f"page-api-{suffix.lower()}",
        policy=RedistributionPolicy.PUBLIC,
        public_api=True,
    )
    created: list[str] = []
    for index in range(3):
        instrument = _add_instrument(
            db_session,
            ticker=f"PG{index}{suffix}",
            name=f"Page {index:02d} {suffix}",
            source=source,
            asset_class=AssetClass.EQUITY,
            instrument_type="stock",
        )
        _add_quote(
            db_session,
            instrument_id=instrument.id,
            source_id=source.id,
            reference_date=date(2026, 1, 7),
            value=Decimal("1.00"),
            price_type=PriceType.LAST.value,
        )
        created.append(str(instrument.id))
    db_session.commit()

    client = _client()
    first = client.get(
        "/v1/instruments",
        params={"source": source.name, "limit": 1},
    )
    assert first.status_code == 200
    body = first.json()
    assert len(body["instruments"]) == 1
    assert body["instruments"][0]["instrument_id"] == created[0]
    assert body["next_cursor"] == created[0]
    second = client.get(
        "/v1/instruments",
        params={"source": source.name, "limit": 1, "cursor": body["next_cursor"]},
    )
    assert second.status_code == 200
    page = second.json()
    assert [row["instrument_id"] for row in page["instruments"]] == [created[1]]
    assert page["next_cursor"] == created[1]
    third = client.get(
        "/v1/instruments",
        params={"source": source.name, "limit": 1, "cursor": page["next_cursor"]},
    )
    assert [row["instrument_id"] for row in third.json()["instruments"]] == [created[2]]
    assert third.json()["next_cursor"] is None
    filtered = client.get(
        "/v1/instruments",
        params={"source": explorer_seed.b3_source_name, "asset_class": AssetClass.EQUITY.value},
    )
    assert filtered.status_code == 200
    assert _instrument_ids(filtered) == {explorer_seed.b3_instrument_id}
    funds = client.get("/v1/instruments", params={"asset_class": AssetClass.FUND.value})
    fund_ids = _instrument_ids(funds)
    assert explorer_seed.fund_instrument_id in fund_ids
    assert explorer_seed.b3_instrument_id not in fund_ids


@pytest.mark.db
def test_instruments_include_quote_span_fields(explorer_seed) -> None:
    client = _client()
    response = client.get("/v1/instruments", params={"q": explorer_seed.b3_ticker})
    assert response.status_code == 200
    rows = response.json()["instruments"]
    assert len(rows) == 1
    row = rows[0]
    assert row["first_quote_date"] == "2026-01-05"
    assert row["last_quote_date"] == "2026-01-07"
    assert row["quote_count"] == 3


@pytest.mark.db
def test_sources_default_hides_test_names(explorer_seed, db_session) -> None:
    canonical = _source(
        db_session,
        name="b3",
        policy=RedistributionPolicy.API_ONLY,
        public_api=True,
    )
    canonical.public_api_enabled = True
    db_session.commit()
    client = _client()
    names = {row["name"] for row in client.get("/v1/sources").json()}
    assert canonical.name in names
    assert explorer_seed.b3_source_name not in names
    assert explorer_seed.yahoo_source_name not in names
    with_tests = {
        row["name"] for row in client.get("/v1/sources", params={"include_test": True}).json()
    }
    assert explorer_seed.b3_source_name in with_tests
    assert explorer_seed.yahoo_source_name in with_tests
    assert canonical.name in with_tests
