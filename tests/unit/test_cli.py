import click
from typer.testing import CliRunner

from marketdata import __version__
from marketdata.cli.main import app

runner = CliRunner()


def _plain(output: str) -> str:
    # Rich may insert ANSI inside flags (e.g. between the hyphens of --date).
    return click.unstyle(output)


def test_cli_help() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Open Market Data" in result.output


def test_cli_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_providers_lists_defaults() -> None:
    result = runner.invoke(app, ["providers"])
    assert result.exit_code == 0
    assert "cvm" in result.output
    assert "tesouro" in result.output
    assert "bcb" in result.output
    assert "b3" in result.output
    assert "yahoo" in result.output


def test_cli_ingest_help_includes_yahoo() -> None:
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "yahoo" in result.output


def test_cli_coverage_help() -> None:
    result = runner.invoke(app, ["coverage", "--help"])
    assert result.exit_code == 0
    output = _plain(result.output)
    assert "--date" in output
    assert "--universe" in output
    assert "--public" in output


def test_cli_ingest_b3_help_mentions_credit() -> None:
    result = runner.invoke(app, ["ingest", "b3", "--help"])
    assert result.exit_code == 0
    assert "credit" in result.output.lower()


def test_cli_publish_help_lists_datasets() -> None:
    result = runner.invoke(app, ["publish", "--help"])
    assert result.exit_code == 0
    assert "datasets" in result.output
    assert "b3" not in result.output


def test_cli_publish_datasets_help() -> None:
    result = runner.invoke(app, ["publish", "datasets", "--help"])
    assert result.exit_code == 0
    output = _plain(result.output)
    assert "--date" in output
    assert "--dry-run" in output
    assert "--dataset" in output


def test_cli_publish_has_no_b3_command() -> None:
    result = runner.invoke(app, ["publish", "b3"])
    assert result.exit_code != 0


def test_cli_publish_datasets_requires_publication_flag() -> None:
    result = runner.invoke(app, ["publish", "datasets", "--date", "2026-08-21"])
    assert result.exit_code != 0
    assert "PUBLIC_DATASET_PUBLICATION_ENABLED" in result.output
