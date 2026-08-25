from typer.testing import CliRunner

from marketdata import __version__
from marketdata.cli.main import app

runner = CliRunner()


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
    assert "--date" in result.output
    assert "--universe" in result.output
    assert "--public" in result.output


def test_cli_ingest_b3_help_mentions_credit() -> None:
    result = runner.invoke(app, ["ingest", "b3", "--help"])
    assert result.exit_code == 0
    assert "credit" in result.output.lower()
