from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from zoneinfo import ZoneInfo

from marketdata.api.access import source_allows_public_api
from marketdata.coverage.csv import UniverseRow
from marketdata.coverage.resolve import resolve_row
from marketdata.coverage.store import CoverageStore, StoredQuote
from marketdata.domain.enums import CoverageStatus, MissingReason, PriceType, QualityStatus

EXPECTED_PRICE_TYPE: dict[tuple[str, str], PriceType] = {
    ("b3", "equity"): PriceType.LAST,
    ("b3", "future"): PriceType.OFFICIAL_SETTLEMENT,
    ("yahoo", "equity"): PriceType.CLOSE,
}


class CoverageMode(StrEnum):
    LOCAL = "local"
    PUBLIC = "public"


@dataclass(frozen=True)
class CoverageResult:
    instrument: str
    asset_class: str
    provider: str | None
    reference_date: date
    price: Decimal | None
    price_type: str | None
    status: CoverageStatus
    staleness: int | None
    missing_reason: MissingReason | None


@dataclass(frozen=True)
class CoverageReport:
    date: date
    universe: str
    mode: CoverageMode
    universe_size: int
    priced: int
    priced_pct: Decimal
    missing_reason_counts: dict[str, int]
    results: list[CoverageResult]


def evaluate_coverage(
    rows: Sequence[UniverseRow],
    *,
    reference_date: date,
    store: CoverageStore,
    mode: CoverageMode = CoverageMode.LOCAL,
    today: date | None = None,
    universe_name: str = "example",
) -> CoverageReport:
    as_of = today or datetime.now(ZoneInfo("America/Sao_Paulo")).date()
    results = [
        _evaluate_row(row, reference_date=reference_date, store=store, mode=mode, today=as_of)
        for row in rows
    ]
    priced = sum(1 for result in results if result.status is CoverageStatus.PRICED)
    universe_size = len(results)
    priced_pct = (
        Decimal("0.00")
        if universe_size == 0
        else (Decimal(priced) * Decimal("100") / Decimal(universe_size)).quantize(Decimal("0.01"))
    )
    counts: dict[str, int] = {}
    for result in results:
        if result.missing_reason is None:
            continue
        key = result.missing_reason.value
        counts[key] = counts.get(key, 0) + 1
    return CoverageReport(
        date=reference_date,
        universe=universe_name,
        mode=mode,
        universe_size=universe_size,
        priced=priced,
        priced_pct=priced_pct,
        missing_reason_counts=counts,
        results=results,
    )


def _label(row: UniverseRow) -> str:
    if row.instrument_id is not None:
        return str(row.instrument_id)
    return row.ticker


def _missing(
    row: UniverseRow,
    *,
    reference_date: date,
    reason: MissingReason,
    status: CoverageStatus = CoverageStatus.MISSING,
    staleness: int | None = None,
    price_type: str | None = None,
) -> CoverageResult:
    return CoverageResult(
        instrument=_label(row),
        asset_class=row.asset_class,
        provider=row.preferred_provider or None,
        reference_date=reference_date,
        price=None,
        price_type=price_type,
        status=status,
        staleness=staleness,
        missing_reason=reason,
    )


def _valid_value(quote: StoredQuote) -> bool:
    if quote.quality_status == QualityStatus.REJECTED.value:
        return False
    return quote.value > 0


def _evaluate_row(
    row: UniverseRow,
    *,
    reference_date: date,
    store: CoverageStore,
    mode: CoverageMode,
    today: date,
) -> CoverageResult:
    expected = EXPECTED_PRICE_TYPE.get((row.preferred_provider, row.asset_class))
    if expected is None:
        return _missing(row, reference_date=reference_date, reason=MissingReason.UNSUPPORTED)
    source = store.source(row.preferred_provider)
    if source is None or not source.ingestion_enabled:
        return _missing(row, reference_date=reference_date, reason=MissingReason.SOURCE_UNAVAILABLE)
    ids = resolve_row(row, store)
    if len(ids) != 1:
        return _missing(row, reference_date=reference_date, reason=MissingReason.MAPPING_ERROR)
    instrument_id = ids[0]
    quote = store.quote(
        instrument_id,
        reference_date=reference_date,
        price_type=expected,
        source_name=row.preferred_provider,
    )
    if quote is not None:
        if mode is CoverageMode.PUBLIC and not source_allows_public_api(
            public_api_enabled=source.public_api_enabled,
            redistribution_policy=source.redistribution_policy,
        ):
            return _missing(
                row,
                reference_date=reference_date,
                reason=MissingReason.REDISTRIBUTION_RESTRICTED,
                status=CoverageStatus.RESTRICTED,
                price_type=expected.value,
            )
        if not _valid_value(quote):
            return _missing(
                row,
                reference_date=reference_date,
                reason=MissingReason.INVALID_VALUE,
                price_type=expected.value,
            )
        return CoverageResult(
            instrument=_label(row),
            asset_class=row.asset_class,
            provider=row.preferred_provider,
            reference_date=reference_date,
            price=quote.value,
            price_type=expected.value,
            status=CoverageStatus.PRICED,
            staleness=None,
            missing_reason=None,
        )
    if store.has_no_public_price(instrument_id, reference_date) or store.ingest_succeeded(
        row.preferred_provider, reference_date
    ):
        return _missing(
            row,
            reference_date=reference_date,
            reason=MissingReason.NO_TRADE,
            price_type=expected.value,
        )
    prior = store.prior_quote_date(
        instrument_id,
        before=reference_date,
        price_type=expected,
        source_name=row.preferred_provider,
    )
    if prior is not None:
        return _missing(
            row,
            reference_date=reference_date,
            reason=MissingReason.STALE,
            staleness=(reference_date - prior).days,
            price_type=expected.value,
        )
    if reference_date >= today:
        return _missing(
            row,
            reference_date=reference_date,
            reason=MissingReason.NOT_PUBLISHED_YET,
            price_type=expected.value,
        )
    return _missing(
        row,
        reference_date=reference_date,
        reason=MissingReason.NO_DATA,
        price_type=expected.value,
    )


def format_coverage_report(report: CoverageReport) -> str:
    lines = [
        (
            f"Coverage  date={report.date.isoformat()} "
            f"universe={report.universe} mode={report.mode.value}"
        ),
        (
            f"universe_size={report.universe_size} priced={report.priced} "
            f"priced_pct={report.priced_pct}"
        ),
    ]
    if report.missing_reason_counts:
        counts = " ".join(
            f"{key}={value}" for key, value in sorted(report.missing_reason_counts.items())
        )
        lines.append(f"missing  {counts}")
    for result in report.results:
        reason = result.missing_reason.value if result.missing_reason is not None else ""
        price = format(result.price, "f") if result.price is not None else ""
        price_type = result.price_type or ""
        lines.append(
            f"{result.instrument}  {result.status.value}  {price_type}  {price}  {reason}".rstrip()
        )
    return "\n".join(lines)
