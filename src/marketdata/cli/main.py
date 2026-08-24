from datetime import date

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
app.add_typer(ingest_app, name="ingest")


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
        raise typer.BadParameter("DATABASE_URL is required for ingestion")
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
    """Ingest B3 BVBG.186 last-trade quotes and BVBG.187 official settlement."""
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
