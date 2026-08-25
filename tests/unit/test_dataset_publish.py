from datetime import UTC, date, datetime
from decimal import Decimal
from json import loads
from uuid import uuid4

import polars as pl
import pytest

from marketdata.datasets.access import source_allows_public_dataset
from marketdata.datasets.manifest import latest_manifest_key, parquet_object_key
from marketdata.datasets.publish import publish_datasets
from marketdata.datasets.schema import QUOTES_SCHEMA, RATES_SCHEMA, SCHEMA_VERSION, empty_frame
from marketdata.domain.enums import RedistributionPolicy
from marketdata.storage.object_store import LocalFileObjectStorage, ObjectStorageError

SNAPSHOT = date(2026, 8, 21)
RETRIEVED = datetime(2026, 8, 21, 15, 0, tzinfo=UTC)


def _quote(
    *,
    source: str,
    price_type: str,
    value: str,
    ticker: str | None = None,
    cnpj: str | None = None,
    title_type: str | None = None,
    public_dataset_enabled: bool = True,
    redistribution_policy: str = RedistributionPolicy.PUBLIC_WITH_ATTRIBUTION.value,
) -> tuple[dict[str, object], dict[str, object]]:
    source_meta = {
        "name": source,
        "public_dataset_enabled": public_dataset_enabled,
        "redistribution_policy": redistribution_policy,
    }
    row = {
        "schema_version": SCHEMA_VERSION,
        "instrument_id": str(uuid4()),
        "source": source,
        "reference_date": date(2026, 8, 3),
        "value": Decimal(value),
        "currency": "BRL" if source != "yahoo" else "USD",
        "unit": "BRL" if source != "yahoo" else "USD",
        "price_type": price_type,
        "is_official": source != "yahoo",
        "retrieved_at": RETRIEVED,
        "raw_artifact_id": str(uuid4()),
        "ingestion_run_id": str(uuid4()),
        "revision": 1,
        "quality_status": "ok",
        "ticker": ticker,
        "isin": None,
        "cnpj_fundo_classe": cnpj,
        "cvm_subclass_id": None,
        "title_type": title_type,
        "maturity_date": date(2029, 1, 1) if title_type else None,
    }
    return source_meta, row


def _eligible_quotes(pairs: list[tuple[dict[str, object], dict[str, object]]]) -> pl.DataFrame:
    rows = [
        row
        for meta, row in pairs
        if source_allows_public_dataset(
            public_dataset_enabled=bool(meta["public_dataset_enabled"]),
            redistribution_policy=str(meta["redistribution_policy"]),
        )
    ]
    return pl.DataFrame(rows, schema=QUOTES_SCHEMA) if rows else empty_frame(QUOTES_SCHEMA)


def _extractors(frames: dict[str, pl.DataFrame]):
    return {name: (lambda _session, frame=frame: frame) for name, frame in frames.items()}


class _StoreProxy:
    def __init__(self, inner: LocalFileObjectStorage, *, fail_after: int | None = None) -> None:
        self.inner = inner
        self.fail_after = fail_after
        self.stores = 0

    def store(self, key: str, data: bytes, *, content_type: str | None = None) -> str:
        if self.fail_after is not None and self.stores >= self.fail_after:
            raise RuntimeError("injected failure")
        self.stores += 1
        return self.inner.store(key, data, content_type=content_type)

    def retrieve(self, key: str) -> bytes:
        return self.inner.retrieve(key)

    def exists(self, key: str) -> bool:
        return self.inner.exists(key)


def test_odbl_quotes_publish_parquet_and_manifest(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    frame = _eligible_quotes(
        [
            _quote(source="cvm", price_type="FUND_NAV", value="1.2345", cnpj="00017024000153"),
            _quote(source="tesouro", price_type="PU_BASE", value="986.12", title_type="LTN"),
        ]
    )
    summary = publish_datasets(
        store=store,
        snapshot_date=SNAPSHOT,
        names=["quotes"],
        extractors=_extractors({"quotes": frame}),
    )
    assert not summary.failed
    assert summary.outcomes[0].status == "published"
    key = parquet_object_key("quotes", SNAPSHOT)
    assert store.exists(key)
    restored = pl.read_parquet(store.retrieve(key))
    assert restored.schema["value"] == pl.Decimal(38, 16)
    assert "price_type" in restored.columns
    manifest = loads(store.retrieve(latest_manifest_key("quotes")))
    assert manifest["sha256"] == summary.outcomes[0].sha256
    assert manifest["row_count"] == 2
    assert manifest["license"] == "ODbL-1.0"
    assert manifest["redistribution_policy"] == "PUBLIC_WITH_ATTRIBUTION"
    assert any("CVM" in item for item in manifest["attribution"])
    assert any("Tesouro" in item for item in manifest["attribution"])


def test_mixed_quotes_omit_b3_yahoo_and_restricted_odbl(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    frame = _eligible_quotes(
        [
            _quote(source="cvm", price_type="FUND_NAV", value="2.5", cnpj="00017024000153"),
            _quote(source="tesouro", price_type="PU_BASE", value="100.00", title_type="LTN"),
            _quote(
                source="b3",
                price_type="LAST",
                value="32.51",
                ticker="PETR4",
                public_dataset_enabled=False,
                redistribution_policy=RedistributionPolicy.API_ONLY.value,
            ),
            _quote(
                source="b3",
                price_type="OFFICIAL_SETTLEMENT",
                value="98642.12",
                ticker="DI1F27",
                public_dataset_enabled=False,
                redistribution_policy=RedistributionPolicy.API_ONLY.value,
            ),
            _quote(
                source="b3",
                price_type="LAST",
                value="101.50",
                ticker="JALL14",
                public_dataset_enabled=False,
                redistribution_policy=RedistributionPolicy.API_ONLY.value,
            ),
            _quote(
                source="yahoo",
                price_type="CLOSE",
                value="185.64",
                ticker="AAPL",
                public_dataset_enabled=False,
                redistribution_policy=RedistributionPolicy.UNKNOWN.value,
            ),
            _quote(
                source="cvm",
                price_type="FUND_NAV",
                value="3.0",
                cnpj="11111111000191",
                public_dataset_enabled=False,
            ),
            _quote(
                source="b3",
                price_type="LAST",
                value="10.00",
                ticker="FAKE4",
                public_dataset_enabled=True,
                redistribution_policy=RedistributionPolicy.API_ONLY.value,
            ),
        ]
    )
    publish_datasets(
        store=store,
        snapshot_date=SNAPSHOT,
        names=["quotes"],
        extractors=_extractors({"quotes": frame}),
    )
    restored = pl.read_parquet(store.retrieve(parquet_object_key("quotes", SNAPSHOT)))
    assert set(restored["source"].to_list()) == {"cvm", "tesouro"}
    tickers = set(value for value in restored["ticker"].to_list() if value is not None)
    assert tickers.isdisjoint({"PETR4", "DI1F27", "JALL14", "AAPL", "FAKE4"})
    assert "CLOSE" not in restored["price_type"].to_list()
    assert "LAST" not in restored["price_type"].to_list()
    assert "OFFICIAL_SETTLEMENT" not in restored["price_type"].to_list()


def test_empty_dataset_does_not_move_latest(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    quotes = _eligible_quotes(
        [_quote(source="cvm", price_type="FUND_NAV", value="1.0", cnpj="00017024000153")]
    )
    publish_datasets(
        store=store,
        snapshot_date=SNAPSHOT,
        names=["quotes"],
        extractors=_extractors({"quotes": quotes}),
    )
    latest_before = store.retrieve(latest_manifest_key("quotes"))
    summary = publish_datasets(
        store=store,
        snapshot_date=date(2026, 8, 22),
        names=["quotes", "rates"],
        extractors=_extractors(
            {"quotes": empty_frame(QUOTES_SCHEMA), "rates": empty_frame(RATES_SCHEMA)}
        ),
    )
    assert [outcome.status for outcome in summary.outcomes] == ["skipped", "skipped"]
    assert store.retrieve(latest_manifest_key("quotes")) == latest_before
    with pytest.raises(ObjectStorageError):
        store.retrieve(latest_manifest_key("rates"))


def test_atomic_republish_keeps_latest_on_failure(tmp_path) -> None:
    inner = LocalFileObjectStorage(tmp_path)
    quotes_v1 = _eligible_quotes(
        [_quote(source="cvm", price_type="FUND_NAV", value="1.0", cnpj="00017024000153")]
    )
    first = publish_datasets(
        store=inner,
        snapshot_date=SNAPSHOT,
        names=["quotes"],
        extractors=_extractors({"quotes": quotes_v1}),
        now=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
    )
    latest_v1 = loads(inner.retrieve(latest_manifest_key("quotes")))
    assert latest_v1["sha256"] == first.outcomes[0].sha256

    quotes_v2 = _eligible_quotes(
        [_quote(source="cvm", price_type="FUND_NAV", value="9.0", cnpj="00017024000153")]
    )
    failing = _StoreProxy(inner, fail_after=2)
    second = publish_datasets(
        store=failing,
        snapshot_date=date(2026, 8, 22),
        names=["quotes"],
        extractors=_extractors({"quotes": quotes_v2}),
    )
    assert second.failed
    latest = loads(inner.retrieve(latest_manifest_key("quotes")))
    assert latest["snapshot_date"] == SNAPSHOT.isoformat()
    assert latest["sha256"] == latest_v1["sha256"]
    assert inner.exists(parquet_object_key("quotes", date(2026, 8, 22)))


def test_successful_republish_points_latest_at_new_file(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    v1 = _eligible_quotes(
        [_quote(source="cvm", price_type="FUND_NAV", value="1.0", cnpj="00017024000153")]
    )
    v2 = _eligible_quotes(
        [_quote(source="cvm", price_type="FUND_NAV", value="9.0", cnpj="00017024000153")]
    )
    publish_datasets(
        store=store,
        snapshot_date=SNAPSHOT,
        names=["quotes"],
        extractors=_extractors({"quotes": v1}),
    )
    second = publish_datasets(
        store=store,
        snapshot_date=date(2026, 8, 22),
        names=["quotes"],
        extractors=_extractors({"quotes": v2}),
    )
    latest = loads(store.retrieve(latest_manifest_key("quotes")))
    assert latest["sha256"] == second.outcomes[0].sha256
    assert latest["snapshot_date"] == "2026-08-22"
    restored = pl.read_parquet(store.retrieve(latest["object_key"]))
    assert Decimal(str(restored["value"][0])) == Decimal("9.0")


def test_same_date_republish_is_idempotent_success(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    frame = _eligible_quotes(
        [_quote(source="bcb", price_type="FUND_NAV", value="1.0", cnpj="00017024000153")]
    )
    first = publish_datasets(
        store=store,
        snapshot_date=SNAPSHOT,
        names=["quotes"],
        extractors=_extractors({"quotes": frame}),
        now=datetime(2026, 8, 21, 12, 0, tzinfo=UTC),
    )
    second = publish_datasets(
        store=store,
        snapshot_date=SNAPSHOT,
        names=["quotes"],
        extractors=_extractors({"quotes": frame}),
        now=datetime(2026, 8, 21, 18, 0, tzinfo=UTC),
    )
    assert first.outcomes[0].status == "published"
    assert second.outcomes[0].status == "published"
    assert store.exists(latest_manifest_key("quotes"))
    assert first.outcomes[0].sha256 == second.outcomes[0].sha256
    latest = loads(store.retrieve(latest_manifest_key("quotes")))
    assert latest["generated_at"].startswith("2026-08-21T18:00:00")


def test_dry_run_writes_nothing(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    frame = _eligible_quotes(
        [_quote(source="cvm", price_type="FUND_NAV", value="1.0", cnpj="00017024000153")]
    )
    summary = publish_datasets(
        store=store,
        snapshot_date=SNAPSHOT,
        names=["quotes"],
        dry_run=True,
        extractors=_extractors({"quotes": frame}),
    )
    assert summary.outcomes[0].status == "dry_run"
    assert summary.outcomes[0].row_count == 1
    assert not store.exists(parquet_object_key("quotes", SNAPSHOT))
    assert not store.exists(latest_manifest_key("quotes"))


def test_quotes_failure_does_not_block_rates(tmp_path) -> None:
    store = LocalFileObjectStorage(tmp_path)
    rates = pl.DataFrame(
        [
            {
                "schema_version": SCHEMA_VERSION,
                "series_code": "BCB:CDI_DAILY",
                "source_series_id": "12",
                "source": "bcb",
                "name": "CDI",
                "reference_date": date(2026, 8, 21),
                "value": Decimal("0.045"),
                "unit": "percent_per_day",
                "value_semantics": "REFERENCE",
                "retrieved_at": RETRIEVED,
                "raw_artifact_id": str(uuid4()),
                "ingestion_run_id": str(uuid4()),
                "revision": 1,
                "quality_status": "ok",
            }
        ],
        schema=RATES_SCHEMA,
    )

    def fail_quotes(_session):
        raise RuntimeError("quotes exploded")

    summary = publish_datasets(
        store=store,
        snapshot_date=SNAPSHOT,
        names=["quotes", "rates"],
        extractors={"quotes": fail_quotes, "rates": lambda _session: rates},
    )
    assert summary.failed
    statuses = {outcome.name: outcome.status for outcome in summary.outcomes}
    assert statuses["quotes"] == "failed"
    assert statuses["rates"] == "published"
    assert store.exists(latest_manifest_key("rates"))
    assert not store.exists(latest_manifest_key("quotes"))
