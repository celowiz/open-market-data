from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from marketdata.api.access import source_allows_public_api
from marketdata.coverage.csv import load_universe
from marketdata.coverage.engine import CoverageMode, evaluate_coverage
from marketdata.coverage.store import InMemoryCoverageStore, SourceView, StoredQuote
from marketdata.domain.enums import (
    CoverageStatus,
    IdentifierType,
    MissingReason,
    PriceType,
    QualityStatus,
    RedistributionPolicy,
)

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "coverage" / "universe.tiny.csv"
REF = date(2026, 8, 21)


def _b3_source() -> SourceView:
    return SourceView(
        name="b3",
        ingestion_enabled=True,
        public_api_enabled=True,
        redistribution_policy=RedistributionPolicy.API_ONLY.value,
    )


def _yahoo_source() -> SourceView:
    return SourceView(
        name="yahoo",
        ingestion_enabled=True,
        public_api_enabled=False,
        redistribution_policy=RedistributionPolicy.UNKNOWN.value,
    )


def test_example_universe_csv_loads() -> None:
    path = Path(__file__).resolve().parents[2] / "config" / "instruments.example.csv"
    rows = load_universe(path)
    tickers = {row.ticker for row in rows}
    assert "PETR4" in tickers
    assert "DI1F27" in tickers
    assert "AAPL" in tickers
    assert all(row.preferred_provider in {"b3", "yahoo"} for row in rows)
    assert any(row.universe == "ibov" for row in rows)
    assert any(row.universe == "smll" for row in rows)
    assert any(row.universe == "spx" for row in rows)
    assert any(row.universe == "ndx" for row in rows)
    assert any(row.universe == "djia" for row in rows)
    assert any(row.universe == "b3_futures" for row in rows)


def test_load_universe_reads_tiny_fixture_and_skips_comments() -> None:
    rows = load_universe(FIXTURE)
    assert [row.ticker for row in rows] == ["PETR4", "DI1F27", "AAPL", "UNKNOWN1", "CVMSTUB"]
    assert rows[0].asset_class == "equity"
    assert rows[0].isin == "BRPETRACNOR9"
    assert rows[0].preferred_provider == "b3"
    assert rows[1].asset_class == "future"
    assert rows[1].maturity_date == date(2027, 1, 4)
    assert rows[2].preferred_provider == "yahoo"
    assert rows[4].asset_class == "fund"
    assert rows[0].instrument_id is None


def test_coverage_engine_does_not_import_yfinance() -> None:
    coverage_root = Path(__file__).resolve().parents[2] / "src" / "marketdata" / "coverage"
    offenders = [
        str(path.relative_to(coverage_root)).replace("\\", "/")
        for path in coverage_root.rglob("*.py")
        if "yfinance" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_b3_equity_last_is_priced_locally_and_publicly() -> None:
    petr4 = uuid4()
    store = InMemoryCoverageStore()
    store.add_source(_b3_source())
    store.add_instrument(petr4)
    store.add_identifier(petr4, IdentifierType.TICKER, "PETR4", "b3")
    store.add_identifier(petr4, IdentifierType.ISIN, "BRPETRACNOR9", "b3")
    store.add_quote(
        StoredQuote(
            instrument_id=petr4,
            reference_date=REF,
            value=Decimal("32.51"),
            price_type=PriceType.LAST,
            source_name="b3",
            quality_status=QualityStatus.OK.value,
        )
    )
    report = evaluate_coverage(
        load_universe(FIXTURE)[:1],
        reference_date=REF,
        store=store,
        mode=CoverageMode.PUBLIC,
        today=REF,
    )
    result = report.results[0]
    assert result.status is CoverageStatus.PRICED
    assert result.missing_reason is None
    assert result.price == Decimal("32.51")
    assert result.price_type == PriceType.LAST.value
    assert result.provider == "b3"
    assert report.priced == 1
    assert source_allows_public_api(
        public_api_enabled=True,
        redistribution_policy=RedistributionPolicy.API_ONLY.value,
    )


def test_futures_settlement_is_priced_last_is_not_used_as_settlement() -> None:
    di1 = uuid4()
    store = InMemoryCoverageStore()
    store.add_source(_b3_source())
    store.add_instrument(di1)
    store.add_identifier(di1, IdentifierType.TICKER, "DI1F27", "b3")
    store.add_quote(
        StoredQuote(
            instrument_id=di1,
            reference_date=REF,
            value=Decimal("0.15"),
            price_type=PriceType.LAST,
            source_name="b3",
            quality_status=QualityStatus.OK.value,
        )
    )
    store.add_ingest("b3", REF)
    rows = [row for row in load_universe(FIXTURE) if row.ticker == "DI1F27"]
    missing = evaluate_coverage(
        rows, reference_date=REF, store=store, mode=CoverageMode.LOCAL, today=REF
    )
    assert missing.results[0].status is CoverageStatus.MISSING
    assert missing.results[0].missing_reason is MissingReason.NO_TRADE
    assert missing.results[0].price is None

    store.add_quote(
        StoredQuote(
            instrument_id=di1,
            reference_date=REF,
            value=Decimal("98642.12"),
            price_type=PriceType.OFFICIAL_SETTLEMENT,
            source_name="b3",
            quality_status=QualityStatus.OK.value,
        )
    )
    priced = evaluate_coverage(
        rows, reference_date=REF, store=store, mode=CoverageMode.PUBLIC, today=REF
    )
    assert priced.results[0].status is CoverageStatus.PRICED
    assert priced.results[0].price == Decimal("98642.12")
    assert priced.results[0].price_type == PriceType.OFFICIAL_SETTLEMENT.value


def test_yahoo_close_is_priced_locally_and_restricted_publicly() -> None:
    aapl = uuid4()
    store = InMemoryCoverageStore()
    store.add_source(_yahoo_source())
    store.add_instrument(aapl)
    store.add_identifier(aapl, IdentifierType.YAHOO_SYMBOL, "AAPL", "yahoo")
    store.add_identifier(aapl, IdentifierType.TICKER, "AAPL", "yahoo")
    store.add_quote(
        StoredQuote(
            instrument_id=aapl,
            reference_date=REF,
            value=Decimal("185.64"),
            price_type=PriceType.CLOSE,
            source_name="yahoo",
            quality_status=QualityStatus.OK.value,
        )
    )
    rows = [row for row in load_universe(FIXTURE) if row.ticker == "AAPL"]
    local = evaluate_coverage(
        rows, reference_date=REF, store=store, mode=CoverageMode.LOCAL, today=REF
    )
    assert local.results[0].status is CoverageStatus.PRICED
    assert local.results[0].price == Decimal("185.64")
    assert local.priced == 1

    public = evaluate_coverage(
        rows, reference_date=REF, store=store, mode=CoverageMode.PUBLIC, today=REF
    )
    assert public.results[0].status is CoverageStatus.RESTRICTED
    assert public.results[0].missing_reason is MissingReason.REDISTRIBUTION_RESTRICTED
    assert public.results[0].price is None
    assert public.priced == 0
    assert public.universe_size == 1


def test_unknown_ticker_is_mapping_error() -> None:
    store = InMemoryCoverageStore()
    store.add_source(_b3_source())
    rows = [row for row in load_universe(FIXTURE) if row.ticker == "UNKNOWN1"]
    report = evaluate_coverage(
        rows, reference_date=REF, store=store, mode=CoverageMode.LOCAL, today=REF
    )
    assert report.results[0].status is CoverageStatus.MISSING
    assert report.results[0].missing_reason is MissingReason.MAPPING_ERROR


def test_fund_row_is_unsupported() -> None:
    store = InMemoryCoverageStore()
    rows = [row for row in load_universe(FIXTURE) if row.ticker == "CVMSTUB"]
    report = evaluate_coverage(
        rows, reference_date=REF, store=store, mode=CoverageMode.LOCAL, today=REF
    )
    assert report.results[0].missing_reason is MissingReason.UNSUPPORTED


def test_prior_day_quote_is_stale_and_not_used_as_today() -> None:
    petr4 = uuid4()
    store = InMemoryCoverageStore()
    store.add_source(_b3_source())
    store.add_instrument(petr4)
    store.add_identifier(petr4, IdentifierType.TICKER, "PETR4", "b3")
    store.add_quote(
        StoredQuote(
            instrument_id=petr4,
            reference_date=date(2026, 8, 20),
            value=Decimal("31.00"),
            price_type=PriceType.LAST,
            source_name="b3",
            quality_status=QualityStatus.OK.value,
        )
    )
    rows = [row for row in load_universe(FIXTURE) if row.ticker == "PETR4"]
    report = evaluate_coverage(
        rows, reference_date=REF, store=store, mode=CoverageMode.LOCAL, today=REF
    )
    result = report.results[0]
    assert result.status is CoverageStatus.MISSING
    assert result.missing_reason is MissingReason.STALE
    assert result.price is None
    assert result.staleness == 1


def test_ingest_without_print_is_no_trade_not_a_fake_last() -> None:
    petr4 = uuid4()
    store = InMemoryCoverageStore()
    store.add_source(_b3_source())
    store.add_instrument(petr4)
    store.add_identifier(petr4, IdentifierType.TICKER, "PETR4", "b3")
    store.add_ingest("b3", REF)
    store.add_no_public_price(petr4, REF)
    rows = [row for row in load_universe(FIXTURE) if row.ticker == "PETR4"]
    report = evaluate_coverage(
        rows, reference_date=REF, store=store, mode=CoverageMode.LOCAL, today=REF
    )
    assert report.results[0].missing_reason is MissingReason.NO_TRADE
    assert report.results[0].price is None


def test_missing_source_is_source_unavailable() -> None:
    rows = [row for row in load_universe(FIXTURE) if row.ticker == "PETR4"]
    report = evaluate_coverage(
        rows,
        reference_date=REF,
        store=InMemoryCoverageStore(),
        mode=CoverageMode.LOCAL,
        today=REF,
    )
    assert report.results[0].missing_reason is MissingReason.SOURCE_UNAVAILABLE


def test_rejected_quote_is_invalid_value() -> None:
    petr4 = uuid4()
    store = InMemoryCoverageStore()
    store.add_source(_b3_source())
    store.add_instrument(petr4)
    store.add_identifier(petr4, IdentifierType.TICKER, "PETR4", "b3")
    store.add_quote(
        StoredQuote(
            instrument_id=petr4,
            reference_date=REF,
            value=Decimal("32.51"),
            price_type=PriceType.LAST,
            source_name="b3",
            quality_status=QualityStatus.REJECTED.value,
        )
    )
    rows = [row for row in load_universe(FIXTURE) if row.ticker == "PETR4"]
    report = evaluate_coverage(
        rows, reference_date=REF, store=store, mode=CoverageMode.LOCAL, today=REF
    )
    assert report.results[0].missing_reason is MissingReason.INVALID_VALUE
    assert report.results[0].price is None


def test_no_ingest_on_past_session_is_no_data() -> None:
    petr4 = uuid4()
    store = InMemoryCoverageStore()
    store.add_source(_b3_source())
    store.add_instrument(petr4)
    store.add_identifier(petr4, IdentifierType.TICKER, "PETR4", "b3")
    rows = [row for row in load_universe(FIXTURE) if row.ticker == "PETR4"]
    past = date(2026, 8, 14)
    report = evaluate_coverage(
        rows, reference_date=past, store=store, mode=CoverageMode.LOCAL, today=REF
    )
    assert report.results[0].missing_reason is MissingReason.NO_DATA


def test_no_ingest_on_today_is_not_published_yet() -> None:
    petr4 = uuid4()
    store = InMemoryCoverageStore()
    store.add_source(_b3_source())
    store.add_instrument(petr4)
    store.add_identifier(petr4, IdentifierType.TICKER, "PETR4", "b3")
    rows = [row for row in load_universe(FIXTURE) if row.ticker == "PETR4"]
    report = evaluate_coverage(
        rows, reference_date=REF, store=store, mode=CoverageMode.LOCAL, today=REF
    )
    assert report.results[0].missing_reason is MissingReason.NOT_PUBLISHED_YET


def test_uuid_column_skips_ticker_lookup() -> None:
    instrument_id = uuid4()
    store = InMemoryCoverageStore()
    store.add_source(_b3_source())
    store.add_instrument(instrument_id)
    store.add_quote(
        StoredQuote(
            instrument_id=instrument_id,
            reference_date=REF,
            value=Decimal("10.00"),
            price_type=PriceType.LAST,
            source_name="b3",
            quality_status=QualityStatus.OK.value,
        )
    )
    from marketdata.coverage.csv import UniverseRow

    row = UniverseRow(
        instrument_id=instrument_id,
        asset_class="equity",
        ticker="IGNORED",
        isin=None,
        cnpj_fundo_classe=None,
        title_type=None,
        maturity_date=None,
        exchange="B3",
        currency="BRL",
        preferred_provider="b3",
        universe="ibov",
    )
    report = evaluate_coverage(
        [row], reference_date=REF, store=store, mode=CoverageMode.LOCAL, today=REF
    )
    assert report.results[0].status is CoverageStatus.PRICED
    assert report.results[0].instrument == str(instrument_id)


def test_ambiguous_ticker_is_mapping_error() -> None:
    first = uuid4()
    second = uuid4()
    store = InMemoryCoverageStore()
    store.add_source(_b3_source())
    store.add_instrument(first)
    store.add_instrument(second)
    store.add_identifier(first, IdentifierType.TICKER, "PETR4", "b3")
    store.add_identifier(second, IdentifierType.TICKER, "PETR4", "b3")
    rows = [row for row in load_universe(FIXTURE) if row.ticker == "PETR4"]
    report = evaluate_coverage(
        rows, reference_date=REF, store=store, mode=CoverageMode.LOCAL, today=REF
    )
    assert report.results[0].missing_reason is MissingReason.MAPPING_ERROR


def test_preferred_provider_does_not_use_other_source_ticker() -> None:
    yahoo_id = uuid4()
    store = InMemoryCoverageStore()
    store.add_source(_b3_source())
    store.add_source(_yahoo_source())
    store.add_instrument(yahoo_id)
    store.add_identifier(yahoo_id, IdentifierType.TICKER, "PETR4", "yahoo")
    rows = [row for row in load_universe(FIXTURE) if row.ticker == "PETR4"]
    report = evaluate_coverage(
        rows, reference_date=REF, store=store, mode=CoverageMode.LOCAL, today=REF
    )
    assert report.results[0].missing_reason is MissingReason.MAPPING_ERROR
