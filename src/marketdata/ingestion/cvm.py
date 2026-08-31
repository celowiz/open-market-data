from __future__ import annotations

from calendar import monthrange
from collections.abc import Iterable, Iterator, Mapping
from datetime import date
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from marketdata.config import get_settings
from marketdata.domain.enums import IngestionRunStatus, PriceType
from marketdata.ingestion.checkpoint import (
    BackfillCheckpoint,
    effective_last_completed,
    load_checkpoint,
    save_checkpoint,
)
from marketdata.providers.cvm import (
    CvmCadastroClass,
    CvmDailyRecord,
    CvmParseError,
    CvmProvider,
    extract_csv_from_zip,
    iter_csv_members_for_month,
    iter_informe_diario,
    months_covering,
    months_in_range,
    parse_cadastro_zip,
    parse_cvm_class_allowlist,
    should_persist_cvm_class,
    uses_monthly_dados,
)
from marketdata.storage.models import (
    InstrumentIdentifierRow,
    InstrumentQuoteRow,
    InstrumentRow,
    RawArtifactRow,
)
from marketdata.storage.object_store import (
    LocalFileObjectStorage,
    ObjectStorage,
    build_object_storage,
)
from marketdata.storage.repositories import (
    build_instrument_quote,
    finish_ingestion_run,
    get_or_create_cvm_source,
    get_or_create_fund_instrument,
    load_quote_keys,
    max_quote_reference_date,
    start_ingestion_run,
    store_raw_artifact,
)

CVM_CHECKPOINT_PROVIDER = "cvm"
_DEFAULT_FLUSH_EVERY = 1000
_TRANSIENT_ROWS = (InstrumentQuoteRow, InstrumentRow, InstrumentIdentifierRow)
_UNSET: object = object()
_CADASTRO_OBJECT_KEY = "raw/cvm/cadastro/registro_fundo_classe.zip"


def _month_token(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _resolve_class_allowlist(class_allowlist: object) -> frozenset[str] | None:
    if class_allowlist is _UNSET:
        return parse_cvm_class_allowlist(get_settings().cvm_classes)
    if class_allowlist is None:
        return None
    if isinstance(class_allowlist, frozenset):
        return class_allowlist
    raise TypeError("class_allowlist must be frozenset[str] | None")


def _store_cadastro(
    session: Session,
    *,
    cvm: CvmProvider,
    object_store: ObjectStorage,
    source_id: UUID,
    ingestion_run_id: UUID,
    keep: tuple[object, ...],
) -> tuple[dict[str, CvmCadastroClass], RawArtifactRow]:
    response = cvm.fetch_cadastro()
    payload = response.content
    uri = object_store.store(_CADASTRO_OBJECT_KEY, payload, content_type="application/zip")
    artifact = store_raw_artifact(
        session,
        source_id=source_id,
        ingestion_run_id=ingestion_run_id,
        source_url=str(response.request.url)
        if response.request is not None
        else cvm.cadastro_url(),
        payload=payload,
        storage_uri=uri,
        filename="registro_fundo_classe.zip",
        content_type=response.headers.get("content-type"),
        http_status=response.status_code,
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
        reference_date=None,
    )
    lookup = parse_cadastro_zip(payload)
    _expunge_transient_rows(session, keep=(*keep, artifact))
    return lookup, artifact


def _month_date_bounds(year: int, month: int) -> tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def _monthly_object_key(year: int, month: int) -> str:
    return f"raw/cvm/year={year:04d}/month={month:02d}/inf_diario_fi_{year:04d}{month:02d}.zip"


def _hist_object_key(year: int) -> str:
    return f"raw/cvm/hist/inf_diario_fi_{year:04d}.zip"


def _expunge_transient_rows(session: Session, *, keep: tuple[object, ...]) -> None:
    keep_ids = {id(obj) for obj in keep if obj is not None}
    for obj in list(session):
        if id(obj) in keep_ids:
            continue
        if isinstance(obj, _TRANSIENT_ROWS):
            session.expunge(obj)


def _persist_cvm_records(
    session: Session,
    records: Iterable[CvmDailyRecord],
    *,
    source_id: UUID,
    artifact: RawArtifactRow,
    ingestion_run_id: UUID,
    flush_every: int = _DEFAULT_FLUSH_EVERY,
    keep: tuple[object, ...] = (),
    identity_start: date | None = None,
    identity_end: date | None = None,
    cadastro: Mapping[str, CvmCadastroClass] | None = None,
    class_allowlist: frozenset[str] | None = None,
) -> tuple[int, int, int, int]:
    """Insert fund NAV quotes, flushing and committing every ``flush_every`` rows.

    The caller owns the session lifecycle. Batched commits keep HIST months from
    retaining every ORM object at once. Existing identities are skipped in
    memory so Neon backfills are not one SELECT per row.
    """
    inserted = updated = skipped = rejected = 0
    retain = (artifact, *keep)
    batch = flush_every if flush_every > 0 else _DEFAULT_FLUSH_EVERY
    fund_ids: dict[str, UUID] = {}
    lookup = cadastro or {}
    existing = load_quote_keys(
        session,
        source_id=source_id,
        start=identity_start,
        end=identity_end,
    )
    pending_rows: list[InstrumentQuoteRow] = []

    def _flush_pending() -> None:
        if not pending_rows:
            return
        session.add_all(pending_rows)
        session.flush()
        session.commit()
        _expunge_transient_rows(session, keep=retain)
        pending_rows.clear()

    for record in records:
        if record.quota_value <= 0:
            rejected += 1
            continue
        joined = lookup.get(record.cnpj_fundo_classe)
        classe = joined.classe if joined is not None else None
        if not should_persist_cvm_class(classe, class_allowlist):
            skipped += 1
            continue
        source_key = f"{record.cnpj_fundo_classe}:{record.subclass_id or ''}"
        instrument_id = fund_ids.get(source_key)
        if instrument_id is None:
            instrument = get_or_create_fund_instrument(
                session,
                source_id=source_id,
                record=record,
                cadastro=joined,
            )
            instrument_id = instrument.id
            fund_ids[source_key] = instrument_id
        identity = (instrument_id, record.reference_date, PriceType.FUND_NAV.value)
        if identity in existing:
            skipped += 1
            continue
        pending_rows.append(
            build_instrument_quote(
                instrument_id=instrument_id,
                source_id=source_id,
                reference_date=record.reference_date,
                value=record.quota_value,
                price_type=PriceType.FUND_NAV,
                artifact=artifact,
                ingestion_run_id=ingestion_run_id,
                currency="BRL",
                unit="BRL_per_quota",
                source_instrument_id=record.cnpj_fundo_classe,
                extra={
                    "vl_patrim_liq": (
                        str(record.net_assets) if record.net_assets is not None else None
                    ),
                    "schema_era": record.schema_era,
                    "subclass_id": record.subclass_id,
                },
            )
        )
        existing.add(identity)
        inserted += 1
        if len(pending_rows) >= batch:
            _flush_pending()
    _flush_pending()
    return inserted, updated, skipped, rejected


def _records_in_range(csv_text: str, start: date, end: date) -> Iterator[CvmDailyRecord]:
    for record in iter_informe_diario(csv_text):
        if start <= record.reference_date <= end:
            yield record


def ingest_cvm(
    session: Session,
    *,
    reference_date: date,
    lookback_days: int | None = None,
    storage: LocalFileObjectStorage | None = None,
    provider: CvmProvider | None = None,
    flush_every: int = _DEFAULT_FLUSH_EVERY,
    class_allowlist: object = _UNSET,
) -> dict[str, int | str]:
    settings = get_settings()
    days = settings.recent_reprocess_days if lookback_days is None else lookback_days
    allowlist = _resolve_class_allowlist(class_allowlist)
    cvm = provider or CvmProvider()
    object_store = storage or build_object_storage()
    source = get_or_create_cvm_source(session)
    run = start_ingestion_run(
        session, provider=cvm.name, source_id=source.id, reference_date=reference_date
    )
    inserted = updated = skipped = rejected = 0
    artifacts = 0
    parsed = 0
    try:
        cadastro, cadastro_artifact = _store_cadastro(
            session,
            cvm=cvm,
            object_store=object_store,
            source_id=source.id,
            ingestion_run_id=run.id,
            keep=(run, source),
        )
        artifacts += 1
        for year, month in months_covering(reference_date, days):
            response = cvm.fetch_month(year, month)
            payload = response.content
            uri = object_store.store(
                _monthly_object_key(year, month), payload, content_type="application/zip"
            )
            artifact = store_raw_artifact(
                session,
                source_id=source.id,
                ingestion_run_id=run.id,
                source_url=str(response.request.url)
                if response.request is not None
                else cvm.month_url(year, month),
                payload=payload,
                storage_uri=uri,
                filename=f"inf_diario_fi_{year:04d}{month:02d}.zip",
                content_type=response.headers.get("content-type"),
                http_status=response.status_code,
                etag=response.headers.get("etag"),
                last_modified=response.headers.get("last-modified"),
                reference_date=date(year, month, 1),
            )
            artifacts += 1
            try:
                csv_text = extract_csv_from_zip(payload)
                records = iter_informe_diario(csv_text)
            except CvmParseError:
                rejected += 1
                continue
            ins, upd, skip, rej = _persist_cvm_records(
                session,
                records,
                source_id=source.id,
                artifact=artifact,
                ingestion_run_id=run.id,
                flush_every=flush_every,
                keep=(run, source, artifact, cadastro_artifact),
                identity_start=_month_date_bounds(year, month)[0],
                identity_end=_month_date_bounds(year, month)[1],
                cadastro=cadastro,
                class_allowlist=allowlist,
            )
            parsed += ins + upd + skip + rej
            inserted += ins
            updated += upd
            skipped += skip
            rejected += rej
        run.artifacts_downloaded = artifacts
        run.records_parsed = parsed
        run.records_inserted = inserted
        run.records_updated = updated
        run.records_rejected = rejected
        run.records_normalized = inserted + updated + skipped
        finish_ingestion_run(run, status=IngestionRunStatus.SUCCEEDED)
        session.flush()
        return {
            "run_id": str(run.id),
            "artifacts": artifacts,
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "rejected": rejected,
            "status": run.status,
        }
    except Exception:
        finish_ingestion_run(run, status=IngestionRunStatus.FAILED)
        session.flush()
        raise


def _save_cvm_checkpoint(
    store: ObjectStorage,
    *,
    start: date,
    end: date,
    last_completed: str | None,
    status: str,
) -> None:
    save_checkpoint(
        store,
        BackfillCheckpoint(
            provider=CVM_CHECKPOINT_PROVIDER,
            start=start.isoformat(),
            end=end.isoformat(),
            last_completed=last_completed,
            status=status,
        ),
    )


def _load_hist_year(
    *,
    year: int,
    cvm: CvmProvider,
    object_store: ObjectStorage,
    cache: dict[int, tuple[bytes, str]],
) -> tuple[bytes, str, str, int | None, str | None, str | None, str | None]:
    """Return ZIP bytes and provenance, fetching each HIST year at most once."""
    key = _hist_object_key(year)
    if year in cache:
        payload, uri = cache[year]
        return payload, uri, cvm.hist_year_url(year), 200, "application/zip", None, None
    source_url = cvm.hist_year_url(year)
    http_status: int | None = 200
    content_type: str | None = "application/zip"
    etag: str | None = None
    last_modified: str | None = None
    if object_store.exists(key):
        payload = object_store.retrieve(key)
    else:
        response = cvm.fetch_hist_year(year)
        payload = response.content
        if response.request is not None:
            source_url = str(response.request.url)
        http_status = response.status_code
        content_type = response.headers.get("content-type")
        etag = response.headers.get("etag")
        last_modified = response.headers.get("last-modified")
    uri = object_store.store(key, payload, content_type="application/zip")
    cache[year] = (payload, uri)
    return payload, uri, source_url, http_status, content_type, etag, last_modified


def backfill_cvm(
    session: Session,
    *,
    start: date,
    end: date,
    storage: LocalFileObjectStorage | None = None,
    provider: CvmProvider | None = None,
    resume: bool = True,
    max_months: int | None = None,
    as_of: date | None = None,
    flush_every: int = _DEFAULT_FLUSH_EVERY,
    class_allowlist: object = _UNSET,
) -> dict[str, int | str]:
    """Backfill Informe Diário months in ``[start, end]``.

    Months inside the rolling 12-month DADOS/ window (relative to ``as_of``,
    defaulting to today) use monthly ZIPs. Older months use that year's HIST
    ZIP once, cached at ``raw/cvm/hist/inf_diario_fi_{YYYY}.zip``.
    Daily ``lookback`` is not applied.
    """
    months = months_in_range(start, end)
    allowlist = _resolve_class_allowlist(class_allowlist)
    cvm = provider or CvmProvider()
    object_store = storage or build_object_storage()
    window_as_of = as_of or date.today()
    existing = load_checkpoint(object_store, CVM_CHECKPOINT_PROVIDER)
    db_last: str | None = None
    if resume:
        db_max = max_quote_reference_date(session, CVM_CHECKPOINT_PROVIDER, start=start, end=end)
        db_last = _month_token(db_max.year, db_max.month) if db_max is not None else None
    last_completed = effective_last_completed(existing, start, end, db_last, resume=resume)
    _save_cvm_checkpoint(
        object_store,
        start=start,
        end=end,
        last_completed=last_completed,
        status="running",
    )
    source = get_or_create_cvm_source(session)
    run = start_ingestion_run(session, provider=cvm.name, source_id=source.id, reference_date=end)
    inserted = updated = skipped = rejected = 0
    artifacts = 0
    parsed = 0
    processed = 0
    truncated = False
    hist_cache: dict[int, tuple[bytes, str]] = {}
    hist_artifacts: dict[int, RawArtifactRow] = {}
    try:
        cadastro, cadastro_artifact = _store_cadastro(
            session,
            cvm=cvm,
            object_store=object_store,
            source_id=source.id,
            ingestion_run_id=run.id,
            keep=(run, source),
        )
        artifacts += 1
        for year, month in months:
            token = _month_token(year, month)
            if last_completed is not None and token <= last_completed:
                continue
            if max_months is not None and processed >= max_months:
                truncated = True
                break
            try:
                use_monthly = uses_monthly_dados(year, month, window_as_of)
                payload = b""
                uri = ""
                source_url = ""
                http_status: int | None = None
                content_type: str | None = None
                etag: str | None = None
                last_modified: str | None = None
                if not use_monthly:
                    try:
                        if hist_cache and year not in hist_cache:
                            hist_cache.clear()
                            hist_artifacts.clear()
                        payload, uri, source_url, http_status, content_type, etag, last_modified = (
                            _load_hist_year(
                                year=year,
                                cvm=cvm,
                                object_store=object_store,
                                cache=hist_cache,
                            )
                        )
                    except httpx.HTTPStatusError as exc:
                        if exc.response.status_code != 404:
                            raise
                        use_monthly = True
                if use_monthly:
                    response = cvm.fetch_month(year, month)
                    payload = response.content
                    uri = object_store.store(
                        _monthly_object_key(year, month),
                        payload,
                        content_type="application/zip",
                    )
                    artifact = store_raw_artifact(
                        session,
                        source_id=source.id,
                        ingestion_run_id=run.id,
                        source_url=str(response.request.url)
                        if response.request is not None
                        else cvm.month_url(year, month),
                        payload=payload,
                        storage_uri=uri,
                        filename=f"inf_diario_fi_{year:04d}{month:02d}.zip",
                        content_type=response.headers.get("content-type"),
                        http_status=response.status_code,
                        etag=response.headers.get("etag"),
                        last_modified=response.headers.get("last-modified"),
                        reference_date=date(year, month, 1),
                    )
                    artifacts += 1
                    csv_texts = [extract_csv_from_zip(payload)]
                else:
                    if year not in hist_artifacts:
                        artifact = store_raw_artifact(
                            session,
                            source_id=source.id,
                            ingestion_run_id=run.id,
                            source_url=source_url,
                            payload=payload,
                            storage_uri=uri,
                            filename=f"inf_diario_fi_{year:04d}.zip",
                            content_type=content_type,
                            http_status=http_status,
                            etag=etag,
                            last_modified=last_modified,
                            reference_date=date(year, month, 1),
                        )
                        hist_artifacts[year] = artifact
                        artifacts += 1
                    artifact = hist_artifacts[year]
                    csv_texts = [
                        text for _name, text in iter_csv_members_for_month(payload, year, month)
                    ]
            except CvmParseError:
                rejected += 1
                last_completed = token
                processed += 1
                session.commit()
                _save_cvm_checkpoint(
                    object_store,
                    start=start,
                    end=end,
                    last_completed=last_completed,
                    status="running",
                )
                continue
            for csv_text in csv_texts:
                try:
                    ins, upd, skip, rej = _persist_cvm_records(
                        session,
                        _records_in_range(csv_text, start, end),
                        source_id=source.id,
                        artifact=artifact,
                        ingestion_run_id=run.id,
                        flush_every=flush_every,
                        keep=(run, source, artifact, cadastro_artifact),
                        identity_start=max(start, _month_date_bounds(year, month)[0]),
                        identity_end=min(end, _month_date_bounds(year, month)[1]),
                        cadastro=cadastro,
                        class_allowlist=allowlist,
                    )
                except CvmParseError:
                    rejected += 1
                    continue
                parsed += ins + upd + skip + rej
                inserted += ins
                updated += upd
                skipped += skip
                rejected += rej
            last_completed = token
            processed += 1
            session.commit()
            _save_cvm_checkpoint(
                object_store,
                start=start,
                end=end,
                last_completed=last_completed,
                status="running",
            )
        checkpoint_status = "running" if truncated else "succeeded"
        run_status = IngestionRunStatus.PARTIAL if truncated else IngestionRunStatus.SUCCEEDED
        _save_cvm_checkpoint(
            object_store,
            start=start,
            end=end,
            last_completed=last_completed,
            status=checkpoint_status,
        )
        run.artifacts_downloaded = artifacts
        run.records_parsed = parsed
        run.records_inserted = inserted
        run.records_updated = updated
        run.records_rejected = rejected
        run.records_normalized = inserted + updated + skipped
        finish_ingestion_run(run, status=run_status)
        session.commit()
        return {
            "run_id": str(run.id),
            "artifacts": artifacts,
            "inserted": inserted,
            "updated": updated,
            "skipped": skipped,
            "rejected": rejected,
            "status": run.status,
            "months": processed,
        }
    except Exception:
        _save_cvm_checkpoint(
            object_store,
            start=start,
            end=end,
            last_completed=last_completed,
            status="failed",
        )
        session.rollback()
        raise
