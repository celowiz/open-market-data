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
