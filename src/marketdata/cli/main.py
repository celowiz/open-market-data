from datetime import date
from pathlib import Path

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
app.add_typer(ingest_app, name="ingest")
app.add_typer(publish_app, name="publish")


@app.callback()
def main() -> None:
    """Open Market Data command-line interface."""
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
