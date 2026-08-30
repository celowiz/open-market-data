from collections.abc import Callable, Mapping, Sequence
from datetime import date
from logging import INFO, basicConfig
from pathlib import Path
from sys import stderr

import typer
from sqlalchemy.orm import Session

from marketdata import __version__
from marketdata.config import get_settings
from marketdata.providers.bootstrap import register_default_providers
from marketdata.providers.registry import registry
from marketdata.storage.database import create_db_engine, create_session_factory

app = typer.Typer(
    name="marketdata",
    help="Open Market Data CLI.",
    no_args_is_help=True,
)
ingest_app = typer.Typer(help="Ingest a market-data provider.")
publish_app = typer.Typer(help="Publish public datasets.")
backfill_app = typer.Typer(help="Historical range ingest (not the daily cron).")
app.add_typer(ingest_app, name="ingest")
app.add_typer(publish_app, name="publish")
app.add_typer(backfill_app, name="backfill")


@app.callback()
def main() -> None:
    """Open Market Data command-line interface."""
    basicConfig(
        level=INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=stderr,
        force=True,
    )
    register_default_providers()


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command("providers")
def list_providers() -> None:
    """List registered market-data providers."""
    register_default_providers()
    names = registry.names()
    if not names:
        typer.echo("No providers registered.")
        return
    for name in names:
        typer.echo(name)


def _session() -> Session:
    settings = get_settings()
    if not settings.database_url:
        raise typer.BadParameter("DATABASE_URL is required")
    return create_session_factory(create_db_engine(settings))()


_RESULT_KEYS = (
    "run_id",
    "inserted",
    "updated",
    "skipped",
    "rejected",
    "artifacts",
    "empty_days",
    "months",
    "status",
)


def _echo_result(label: str, result: Mapping[str, object]) -> None:
    parts = [label]
    for key in _RESULT_KEYS:
        if key in result:
            parts.append(f"{key}={result[key]}")
    typer.echo(" ".join(parts))


def _with_session(work: Callable[[Session], Mapping[str, object]]) -> Mapping[str, object]:
    session = _session()
    try:
        result = work(session)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _run_jobs(
    session: Session,
    jobs: Sequence[tuple[str, Callable[[Session], Mapping[str, object]]]],
) -> list[str]:
    failed: list[str] = []
    for label, work in jobs:
        try:
            result = work(session)
            session.commit()
            _echo_result(label, result)
        except Exception as exc:
            session.rollback()
            typer.echo(f"{label} failed: {exc}")
            failed.append(label)
    return failed


_START_OPTION = typer.Option(..., "--start", help="Inclusive start date YYYY-MM-DD")
_END_OPTION = typer.Option(..., "--end", help="Inclusive end date YYYY-MM-DD")
_RESUME_OPTION = typer.Option(
    True,
    "--resume/--force",
    help="Resume from a matching checkpoint. --force starts the range fresh.",
)


@ingest_app.command("cvm")
def ingest_cvm_command(
    date_value: str = typer.Option(..., "--date", help="Reference date YYYY-MM-DD"),
    lookback_days: int | None = typer.Option(None, "--lookback-days"),
) -> None:
    """Fetch CVM Informe Diário ZIPs, persist fund NAVs, and record provenance."""
    from marketdata.ingestion.cvm import ingest_cvm

    reference = date.fromisoformat(date_value)
    session = _session()
    try:
        result = ingest_cvm(session, reference_date=reference, lookback_days=lookback_days)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    typer.echo(
        "CVM ingest "
        f"run={result['run_id']} artifacts={result['artifacts']} "
        f"inserted={result['inserted']} updated={result['updated']} "
        f"skipped={result['skipped']} rejected={result['rejected']}"
    )


@ingest_app.command("tesouro")
def ingest_tesouro_command(
    date_value: str = typer.Option(..., "--date", help="Reference date YYYY-MM-DD"),
) -> None:
    """Ingest Tesouro Direto CKAN quotes for a reference date."""
    from marketdata.ingestion.tesouro import ingest_tesouro

    reference = date.fromisoformat(date_value)
    session = _session()
    try:
        result = ingest_tesouro(session, reference_date=reference)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    typer.echo(
        "Tesouro ingest "
        f"run={result['run_id']} inserted={result['inserted']} "
        f"updated={result['updated']} skipped={result['skipped']}"
    )


@ingest_app.command("bcb")
def ingest_bcb_command(
    date_value: str = typer.Option(..., "--date", help="Reference date YYYY-MM-DD"),
) -> None:
    """Ingest BCB SGS series for a reference date."""
    from marketdata.ingestion.bcb import ingest_bcb

    reference = date.fromisoformat(date_value)
    session = _session()
    try:
        result = ingest_bcb(session, reference_date=reference)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    typer.echo(
        "BCB ingest "
        f"run={result['run_id']} inserted={result['inserted']} "
        f"updated={result['updated']} skipped={result['skipped']}"
    )


@ingest_app.command("b3")
def ingest_b3_command(
    date_value: str = typer.Option(..., "--date", help="Reference date YYYY-MM-DD"),
) -> None:
    """Ingest B3 BVBG.186 last trades, BVBG.187 settlement, and OTC credit prints."""
    from marketdata.ingestion.b3 import ingest_b3

    reference = date.fromisoformat(date_value)
    session = _session()
    try:
        result = ingest_b3(session, reference_date=reference)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    typer.echo(
        "B3 ingest "
        f"run={result['run_id']} artifacts={result['artifacts']} "
        f"inserted={result['inserted']} updated={result['updated']} "
        f"skipped={result['skipped']} rejected={result['rejected']}"
    )


_YAHOO_SYMBOL_OPTION = typer.Option(
    None,
    "--symbol",
    help="Yahoo symbol (repeatable). Defaults to AAPL.",
)


@ingest_app.command("yahoo")
def ingest_yahoo_command(
    date_value: str = typer.Option(..., "--date", help="Reference date YYYY-MM-DD"),
    symbols: list[str] | None = _YAHOO_SYMBOL_OPTION,
) -> None:
    """Ingest unofficial Yahoo Finance EOD closes for local/POC coverage."""
    from marketdata.ingestion.yahoo import ingest_yahoo

    reference = date.fromisoformat(date_value)
    session = _session()
    try:
        result = ingest_yahoo(session, reference_date=reference, symbols=symbols or None)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
    typer.echo(
        "Yahoo ingest "
        f"run={result['run_id']} artifacts={result['artifacts']} "
        f"inserted={result['inserted']} updated={result['updated']} "
        f"skipped={result['skipped']}"
    )


@ingest_app.command("all")
def ingest_all_command(
    date_value: str = typer.Option(..., "--date", help="Reference date YYYY-MM-DD"),
) -> None:
    """Ingest CVM, Tesouro, BCB, B3, and Yahoo (if enabled) for one date."""
    from marketdata.ingestion.b3 import ingest_b3
    from marketdata.ingestion.bcb import ingest_bcb
    from marketdata.ingestion.cvm import ingest_cvm
    from marketdata.ingestion.tesouro import ingest_tesouro
    from marketdata.ingestion.yahoo import ingest_yahoo

    reference = date.fromisoformat(date_value)
    settings = get_settings()
    jobs: list[tuple[str, Callable[[Session], Mapping[str, object]]]] = [
        ("CVM ingest", lambda session: ingest_cvm(session, reference_date=reference)),
        ("Tesouro ingest", lambda session: ingest_tesouro(session, reference_date=reference)),
        ("BCB ingest", lambda session: ingest_bcb(session, reference_date=reference)),
        ("B3 ingest", lambda session: ingest_b3(session, reference_date=reference)),
    ]
    if settings.yahoo_provider_enabled:
        jobs.append(
            ("Yahoo ingest", lambda session: ingest_yahoo(session, reference_date=reference))
        )
    else:
        typer.echo("Yahoo ingest skipped (yahoo_provider_enabled=false)")
    session = _session()
    try:
        failed = _run_jobs(session, jobs)
    finally:
        session.close()
    if failed:
        raise typer.Exit(code=1)


@backfill_app.command("cvm")
def backfill_cvm_command(
    start_value: str = _START_OPTION,
    end_value: str = _END_OPTION,
    max_months: int | None = typer.Option(
        None,
        "--max-months",
        help="Optional safety cap on months processed.",
    ),
    resume: bool = _RESUME_OPTION,
) -> None:
    """Backfill CVM Informe Diario months for --start/--end."""
    from marketdata.ingestion.cvm import backfill_cvm

    start = date.fromisoformat(start_value)
    end = date.fromisoformat(end_value)
    result = _with_session(
        lambda session: backfill_cvm(
            session,
            start=start,
            end=end,
            resume=resume,
            max_months=max_months,
        )
    )
    _echo_result("CVM backfill", result)


@backfill_app.command("tesouro")
def backfill_tesouro_command(
    start_value: str = _START_OPTION,
    end_value: str = _END_OPTION,
    resume: bool = _RESUME_OPTION,
) -> None:
    """Backfill Tesouro Direto quotes from one CKAN CSV for --start/--end."""
    from marketdata.ingestion.tesouro import backfill_tesouro

    start = date.fromisoformat(start_value)
    end = date.fromisoformat(end_value)
    result = _with_session(
        lambda session: backfill_tesouro(session, start=start, end=end, resume=resume)
    )
    _echo_result("Tesouro backfill", result)


@backfill_app.command("bcb")
def backfill_bcb_command(
    start_value: str = _START_OPTION,
    end_value: str = _END_OPTION,
    resume: bool = _RESUME_OPTION,
) -> None:
    """Backfill BCB SGS series for --start/--end using 10-year chunks."""
    from marketdata.ingestion.bcb import backfill_bcb

    start = date.fromisoformat(start_value)
    end = date.fromisoformat(end_value)
    result = _with_session(
        lambda session: backfill_bcb(session, start=start, end=end, resume=resume)
    )
    _echo_result("BCB backfill", result)


@backfill_app.command("b3")
def backfill_b3_command(
    start_value: str = _START_OPTION,
    end_value: str = _END_OPTION,
    cotahist: bool = typer.Option(
        False,
        "--cotahist",
        help="Also ingest annual COTAHIST equity history (LAST only).",
    ),
    delay_seconds: float = typer.Option(
        0.5,
        "--delay-seconds",
        help="Sleep between live B3 HTTP days.",
    ),
    resume: bool = _RESUME_OPTION,
) -> None:
    """Backfill B3 trading days for --start/--end; weekends and empty ZIPs are skipped."""
    from marketdata.ingestion.b3 import backfill_b3

    start = date.fromisoformat(start_value)
    end = date.fromisoformat(end_value)
    result = _with_session(
        lambda session: backfill_b3(
            session,
            start=start,
            end=end,
            delay_seconds=delay_seconds,
            include_cotahist=cotahist,
            resume=resume,
        )
    )
    _echo_result("B3 backfill", result)


@backfill_app.command("yahoo")
def backfill_yahoo_command(
    start_value: str = _START_OPTION,
    end_value: str = _END_OPTION,
    symbols: list[str] | None = _YAHOO_SYMBOL_OPTION,
) -> None:
    """Backfill unofficial Yahoo Finance history (local store; not public API)."""
    from marketdata.ingestion.yahoo import backfill_yahoo

    start = date.fromisoformat(start_value)
    end = date.fromisoformat(end_value)
    result = _with_session(
        lambda session: backfill_yahoo(
            session,
            start=start,
            end=end,
            symbols=symbols or None,
        )
    )
    _echo_result("Yahoo backfill", result)


@backfill_app.command("all")
def backfill_all_command(
    start_value: str = _START_OPTION,
    end_value: str = _END_OPTION,
    resume: bool = _RESUME_OPTION,
) -> None:
    """Backfill tesouro, bcb, cvm, b3, then yahoo (if enabled)."""
    from marketdata.ingestion.b3 import backfill_b3
    from marketdata.ingestion.bcb import backfill_bcb
    from marketdata.ingestion.cvm import backfill_cvm
    from marketdata.ingestion.tesouro import backfill_tesouro
    from marketdata.ingestion.yahoo import backfill_yahoo

    start = date.fromisoformat(start_value)
    end = date.fromisoformat(end_value)
    settings = get_settings()
    jobs: list[tuple[str, Callable[[Session], Mapping[str, object]]]] = [
        (
            "Tesouro backfill",
            lambda session: backfill_tesouro(session, start=start, end=end, resume=resume),
        ),
        (
            "BCB backfill",
            lambda session: backfill_bcb(session, start=start, end=end, resume=resume),
        ),
        (
            "CVM backfill",
            lambda session: backfill_cvm(session, start=start, end=end, resume=resume),
        ),
        (
            "B3 backfill",
            lambda session: backfill_b3(session, start=start, end=end, resume=resume),
        ),
    ]
    if settings.yahoo_provider_enabled:
        jobs.append(
            (
                "Yahoo backfill",
                lambda session: backfill_yahoo(session, start=start, end=end),
            )
        )
    else:
        typer.echo("Yahoo backfill skipped (yahoo_provider_enabled=false)")
    session = _session()
    try:
        failed = _run_jobs(session, jobs)
    finally:
        session.close()
    if failed:
        raise typer.Exit(code=1)


@app.command("explain")
def explain(
    identifier: str = typer.Argument(..., help="CNPJ or other instrument identifier"),
    date_value: str = typer.Option(..., "--date", help="Reference date YYYY-MM-DD"),
) -> None:
    """Show provenance for a stored observation."""
    from sqlalchemy import select

    from marketdata.storage.models import InstrumentQuoteRow, RawArtifactRow, SourceRow
    from marketdata.storage.repositories import resolve_instrument_id

    reference = date.fromisoformat(date_value)
    session = _session()
    try:
        instrument_id = resolve_instrument_id(session, identifier)
        if instrument_id is None:
            raise typer.BadParameter(f"instrument not found: {identifier}")
        quote = session.scalar(
            select(InstrumentQuoteRow)
            .where(
                InstrumentQuoteRow.instrument_id == instrument_id,
                InstrumentQuoteRow.reference_date == reference,
            )
            .order_by(InstrumentQuoteRow.revision.desc())
        )
        if quote is None:
            raise typer.BadParameter(f"no quote for {identifier} on {reference.isoformat()}")
        source = session.get(SourceRow, quote.source_id)
        artifact = (
            session.get(RawArtifactRow, quote.raw_artifact_id) if quote.raw_artifact_id else None
        )
        typer.echo(f"Instrument       {identifier}")
        typer.echo(f"Reference date   {quote.reference_date.isoformat()}")
        typer.echo(f"Price            {quote.value}")
        typer.echo(f"Currency         {quote.currency}")
        typer.echo(f"Price type       {quote.price_type}")
        typer.echo(f"Source           {source.name if source else 'unknown'}")
        typer.echo(f"Official         {'yes' if quote.is_official else 'no'}")
        typer.echo(f"Revision         {quote.revision}")
        if artifact is not None:
            typer.echo("")
            typer.echo("Raw artifact")
            typer.echo("-------------")
            typer.echo(f"File             {artifact.filename}")
            typer.echo(f"SHA256           {artifact.sha256}")
            typer.echo(f"Retrieved at     {artifact.retrieved_at.isoformat()}")
            typer.echo(f"Source URL       {artifact.source_url}")
            typer.echo(f"Storage URI      {artifact.storage_uri}")
            typer.echo(f"Ingestion run    {artifact.ingestion_run_id}")
    finally:
        session.close()


_COVERAGE_UNIVERSE_OPTION = typer.Option(None, "--universe", help="Universe CSV path")
_PUBLISH_DATASET_OPTION = typer.Option(
    None,
    "--dataset",
    help="Catalog name (repeatable). Defaults to sources, instruments, quotes, fund_nav, rates.",
)


@publish_app.command("datasets")
def publish_datasets_command(
    date_value: str = typer.Option(..., "--date", help="Snapshot date YYYY-MM-DD"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate without writing objects"),
    datasets: list[str] | None = _PUBLISH_DATASET_OPTION,
) -> None:
    """Publish ODbL Parquet snapshots plus atomic latest manifests."""
    from marketdata.datasets.manifest import CATALOG_NAMES
    from marketdata.datasets.publish import publish_datasets
    from marketdata.storage.object_store import build_object_storage

    settings = get_settings()
    if not settings.public_dataset_publication_enabled:
        raise typer.BadParameter(
            "PUBLIC_DATASET_PUBLICATION_ENABLED must be true to publish datasets"
        )
    if settings.public_dataset_format.lower() != "parquet":
        raise typer.BadParameter("Phase 9 supports parquet only (PUBLIC_DATASET_FORMAT=parquet)")
    snapshot = date.fromisoformat(date_value)
    requested = datasets or None
    if requested:
        unknown = [name for name in requested if name not in CATALOG_NAMES]
        if unknown:
            raise typer.BadParameter(f"unknown dataset names: {', '.join(unknown)}")
    session = _session()
    try:
        summary = publish_datasets(
            session=session,
            store=build_object_storage(),
            snapshot_date=snapshot,
            names=requested,
            dry_run=dry_run,
            public_data_base_url=settings.public_data_base_url,
        )
    finally:
        session.close()
    published = sum(1 for item in summary.outcomes if item.status in {"published", "dry_run"})
    skipped = sum(1 for item in summary.outcomes if item.status == "skipped")
    failed = sum(1 for item in summary.outcomes if item.status == "failed")
    typer.echo(f"published={published} skipped={skipped} failed={failed}")
    for item in summary.outcomes:
        detail = item.object_key or item.error or ""
        typer.echo(f"{item.name} {item.status} rows={item.row_count} {detail}".rstrip())
    if summary.failed:
        raise typer.Exit(code=1)


@app.command("coverage")
def coverage_command(
    date_value: str = typer.Option(..., "--date", help="Reference date YYYY-MM-DD"),
    universe: Path | None = _COVERAGE_UNIVERSE_OPTION,
    public: bool = typer.Option(
        False, "--public", help="Apply the public API licensing gate (Yahoo omitted)"
    ),
) -> None:
    """Score a CSV universe against stored quotes for a reference date."""
    from marketdata.coverage.csv import load_universe
    from marketdata.coverage.engine import CoverageMode, evaluate_coverage, format_coverage_report
    from marketdata.coverage.paths import default_universe_path
    from marketdata.coverage.store import SessionCoverageStore

    reference = date.fromisoformat(date_value)
    csv_path = (
        universe
        if universe is not None
        else default_universe_path(get_settings().coverage_config_dir)
    )
    if not csv_path.is_file():
        raise typer.BadParameter(f"universe file not found: {csv_path}")
    session = _session()
    try:
        report = evaluate_coverage(
            load_universe(csv_path),
            reference_date=reference,
            store=SessionCoverageStore(session),
            mode=CoverageMode.PUBLIC if public else CoverageMode.LOCAL,
            universe_name=csv_path.name,
        )
    finally:
        session.close()
    typer.echo(format_coverage_report(report))
