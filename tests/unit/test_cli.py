from datetime import date

import click
import pytest
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
    assert "fred" in result.output
    assert "ibge" in result.output
    assert "cftc" in result.output
    assert "edgar" in result.output


def test_cli_ingest_help_includes_yahoo() -> None:
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "yahoo" in result.output
    assert "b3-lending" in result.output
    assert "fred" in result.output
    assert "cvm-events" in result.output


def test_cli_ingest_fred_skips_without_api_key(monkeypatch) -> None:
    from marketdata.config import Settings

    monkeypatch.setattr(
        "marketdata.cli.main.get_settings",
        lambda: Settings(_env_file=None, fred_api_key="", fred_provider_enabled=True),
    )
    result = runner.invoke(app, ["ingest", "fred", "--date", "2026-08-21"])
    assert result.exit_code == 0
    assert "FRED_API_KEY" in result.output


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


def test_cli_publish_datasets_skips_when_object_storage_is_not_s3(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = type(
        "S",
        (),
        {
            "public_dataset_publication_enabled": True,
            "public_dataset_format": "parquet",
            "object_storage_backend": "local",
            "object_storage_bucket": "",
            "public_data_base_url": "",
            "database_url": "",
        },
    )()
    monkeypatch.setattr("marketdata.cli.main.get_settings", lambda: settings)
    result = runner.invoke(app, ["publish", "datasets", "--date", "2026-08-21"])
    assert result.exit_code == 0, result.output
    assert "skip" in result.output.lower()
    assert "s3" in result.output.lower() or "r2" in result.output.lower()


def test_cli_backfill_help_lists_providers() -> None:
    result = runner.invoke(app, ["backfill", "--help"])
    assert result.exit_code == 0
    output = _plain(result.output)
    assert "cvm" in output
    assert "tesouro" in output
    assert "bcb" in output
    assert "b3" in output
    assert "yahoo" in output


def test_cli_backfill_cvm_help_shows_start_end() -> None:
    result = runner.invoke(app, ["backfill", "cvm", "--help"])
    assert result.exit_code == 0
    output = _plain(result.output)
    assert "--start" in output
    assert "--end" in output


def test_cli_ingest_help_includes_all() -> None:
    result = runner.invoke(app, ["ingest", "--help"])
    assert result.exit_code == 0
    assert "all" in result.output


def test_cli_ingest_all_help_shows_date() -> None:
    result = runner.invoke(app, ["ingest", "all", "--help"])
    assert result.exit_code == 0
    assert "--date" in _plain(result.output)


class _FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1

    def close(self) -> None:
        self.closed = True


def _ok_result(**extra: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "run_id": "run-1",
        "inserted": 1,
        "updated": 0,
        "skipped": 0,
        "status": "succeeded",
    }
    payload.update(extra)
    return payload


def _patch_session(monkeypatch: pytest.MonkeyPatch) -> _FakeSession:
    session = _FakeSession()
    monkeypatch.setattr("marketdata.cli.main._session", lambda: session)
    return session


def test_backfill_tesouro_force_passes_resume_false(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _patch_session(monkeypatch)
    captured: dict[str, object] = {}

    def fake_backfill(db_session, *, start, end, resume=True):
        captured["session"] = db_session
        captured["start"] = start
        captured["end"] = end
        captured["resume"] = resume
        return _ok_result()

    monkeypatch.setattr("marketdata.ingestion.tesouro.backfill_tesouro", fake_backfill)
    result = runner.invoke(
        app,
        ["backfill", "tesouro", "--start", "2020-01-01", "--end", "2020-12-31", "--force"],
    )
    assert result.exit_code == 0, result.output
    assert captured["resume"] is False
    assert captured["start"] == date(2020, 1, 1)
    assert captured["end"] == date(2020, 12, 31)
    assert captured["session"] is session
    assert session.closed is True
    assert "inserted=" in result.output


def test_backfill_bcb_default_passes_resume_true(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session(monkeypatch)
    captured: dict[str, object] = {}

    def fake_backfill(db_session, *, start, end, resume=True):
        captured["resume"] = resume
        captured["kwargs"] = {"start": start, "end": end, "resume": resume}
        return _ok_result()

    monkeypatch.setattr("marketdata.ingestion.bcb.backfill_bcb", fake_backfill)
    result = runner.invoke(
        app,
        ["backfill", "bcb", "--start", "2000-01-01", "--end", "2010-01-01"],
    )
    assert result.exit_code == 0, result.output
    assert captured["resume"] is True
    assert "force" not in captured["kwargs"]


def test_backfill_cvm_passes_max_months(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session(monkeypatch)
    captured: dict[str, object] = {}

    def fake_backfill(db_session, *, start, end, resume=True, max_months=None):
        captured.update(start=start, end=end, resume=resume, max_months=max_months)
        return _ok_result(months=2)

    monkeypatch.setattr("marketdata.ingestion.cvm.backfill_cvm", fake_backfill)
    result = runner.invoke(
        app,
        [
            "backfill",
            "cvm",
            "--start",
            "2025-01-01",
            "--end",
            "2025-06-01",
            "--max-months",
            "2",
            "--force",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured == {
        "start": date(2025, 1, 1),
        "end": date(2025, 6, 1),
        "resume": False,
        "max_months": 2,
    }


def test_backfill_b3_maps_cotahist_and_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session(monkeypatch)
    captured: dict[str, object] = {}

    def fake_backfill(
        db_session,
        *,
        start,
        end,
        delay_seconds=0.5,
        include_cotahist=False,
        resume=True,
    ):
        captured.update(
            start=start,
            end=end,
            delay_seconds=delay_seconds,
            include_cotahist=include_cotahist,
            resume=resume,
        )
        return _ok_result(empty_days=0)

    monkeypatch.setattr("marketdata.ingestion.b3.backfill_b3", fake_backfill)
    result = runner.invoke(
        app,
        [
            "backfill",
            "b3",
            "--start",
            "2024-01-01",
            "--end",
            "2024-01-31",
            "--cotahist",
            "--delay-seconds",
            "0",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["include_cotahist"] is True
    assert captured["delay_seconds"] == 0.0
    assert captured["resume"] is True


def test_backfill_yahoo_does_not_pass_resume(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_session(monkeypatch)
    monkeypatch.setattr(
        "marketdata.cli.main.get_settings",
        lambda: _provider_settings(yahoo_provider_enabled=True),
    )
    captured: dict[str, object] = {}

    def fake_backfill(db_session, *, start, end, symbols=None):
        captured.update(start=start, end=end, symbols=symbols)
        return _ok_result()

    monkeypatch.setattr("marketdata.ingestion.yahoo.backfill_yahoo", fake_backfill)
    result = runner.invoke(
        app,
        [
            "backfill",
            "yahoo",
            "--start",
            "2020-01-01",
            "--end",
            "2020-12-31",
            "--symbol",
            "AAPL",
            "--symbol",
            "MSFT",
        ],
    )
    assert result.exit_code == 0, result.output
    assert captured["symbols"] == ["AAPL", "MSFT"]
    assert captured["start"] == date(2020, 1, 1)


def _provider_settings(**overrides: bool) -> object:
    flags = {
        "cvm_provider_enabled": True,
        "b3_provider_enabled": True,
        "tesouro_provider_enabled": True,
        "bcb_provider_enabled": True,
        "yahoo_provider_enabled": False,
        "anbima_provider_enabled": False,
    }
    flags.update(overrides)
    return type("S", (), flags)()


def test_backfill_all_order_and_yahoo_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _patch_session(monkeypatch)
    monkeypatch.setattr(
        "marketdata.cli.main.get_settings",
        lambda: _provider_settings(yahoo_provider_enabled=False),
    )
    called: list[str] = []

    def track(name: str):
        def fake(db_session, **kwargs):
            called.append(name)
            return _ok_result()

        return fake

    monkeypatch.setattr("marketdata.ingestion.tesouro.backfill_tesouro", track("tesouro"))
    monkeypatch.setattr("marketdata.ingestion.bcb.backfill_bcb", track("bcb"))
    monkeypatch.setattr("marketdata.ingestion.cvm.backfill_cvm", track("cvm"))
    monkeypatch.setattr("marketdata.ingestion.b3.backfill_b3", track("b3"))

    def fail_yahoo(*_args, **_kwargs):
        raise AssertionError("yahoo must be skipped when disabled")

    monkeypatch.setattr("marketdata.ingestion.yahoo.backfill_yahoo", fail_yahoo)
    result = runner.invoke(
        app,
        ["backfill", "all", "--start", "2024-01-01", "--end", "2024-01-31"],
    )
    assert result.exit_code == 0, result.output
    assert called == ["tesouro", "bcb", "cvm", "b3"]
    assert session.closed is True
    assert "skipped" in result.output.lower()


def test_ingest_all_continues_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _patch_session(monkeypatch)
    monkeypatch.setattr(
        "marketdata.cli.main.get_settings",
        lambda: _provider_settings(yahoo_provider_enabled=True),
    )
    called: list[str] = []

    def boom(db_session, **kwargs):
        called.append("cvm")
        raise RuntimeError("cvm down")

    def track(name: str):
        def fake(db_session, **kwargs):
            called.append(name)
            return _ok_result()

        return fake

    monkeypatch.setattr("marketdata.ingestion.cvm.ingest_cvm", boom)
    monkeypatch.setattr("marketdata.ingestion.tesouro.ingest_tesouro", track("tesouro"))
    monkeypatch.setattr("marketdata.ingestion.bcb.ingest_bcb", track("bcb"))
    monkeypatch.setattr("marketdata.ingestion.b3.ingest_b3", track("b3"))
    monkeypatch.setattr("marketdata.ingestion.yahoo.ingest_yahoo", track("yahoo"))
    result = runner.invoke(app, ["ingest", "all", "--date", "2026-08-24"])
    assert result.exit_code == 1
    assert called == ["cvm", "tesouro", "bcb", "b3", "yahoo"]
    assert session.rollbacks == 1
    assert session.commits == 4
    assert session.closed is True
    assert "failed" in result.output.lower()


def test_ingest_all_skips_disabled_live_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _patch_session(monkeypatch)
    monkeypatch.setattr(
        "marketdata.cli.main.get_settings",
        lambda: _provider_settings(
            cvm_provider_enabled=False,
            tesouro_provider_enabled=False,
            yahoo_provider_enabled=False,
        ),
    )
    called: list[str] = []

    def track(name: str):
        def fake(db_session, **kwargs):
            called.append(name)
            return _ok_result()

        return fake

    def must_skip(name: str):
        def fake(*_args, **_kwargs):
            raise AssertionError(f"{name} must be skipped when disabled")

        return fake

    monkeypatch.setattr("marketdata.ingestion.cvm.ingest_cvm", must_skip("cvm"))
    monkeypatch.setattr("marketdata.ingestion.tesouro.ingest_tesouro", must_skip("tesouro"))
    monkeypatch.setattr("marketdata.ingestion.bcb.ingest_bcb", track("bcb"))
    monkeypatch.setattr("marketdata.ingestion.b3.ingest_b3", track("b3"))
    monkeypatch.setattr("marketdata.ingestion.yahoo.ingest_yahoo", must_skip("yahoo"))
    result = runner.invoke(app, ["ingest", "all", "--date", "2026-08-24"])
    assert result.exit_code == 0, result.output
    assert called == ["bcb", "b3"]
    assert session.closed is True
    assert "cvm ingest skipped" in result.output.lower()
    assert "tesouro ingest skipped" in result.output.lower()
    assert "yahoo ingest skipped" in result.output.lower()


def test_backfill_all_skips_disabled_live_providers(monkeypatch: pytest.MonkeyPatch) -> None:
    session = _patch_session(monkeypatch)
    monkeypatch.setattr(
        "marketdata.cli.main.get_settings",
        lambda: _provider_settings(
            b3_provider_enabled=False,
            bcb_provider_enabled=False,
            yahoo_provider_enabled=False,
        ),
    )
    called: list[str] = []

    def track(name: str):
        def fake(db_session, **kwargs):
            called.append(name)
            return _ok_result()

        return fake

    def must_skip(name: str):
        def fake(*_args, **_kwargs):
            raise AssertionError(f"{name} must be skipped when disabled")

        return fake

    monkeypatch.setattr("marketdata.ingestion.tesouro.backfill_tesouro", track("tesouro"))
    monkeypatch.setattr("marketdata.ingestion.bcb.backfill_bcb", must_skip("bcb"))
    monkeypatch.setattr("marketdata.ingestion.cvm.backfill_cvm", track("cvm"))
    monkeypatch.setattr("marketdata.ingestion.b3.backfill_b3", must_skip("b3"))
    monkeypatch.setattr("marketdata.ingestion.yahoo.backfill_yahoo", must_skip("yahoo"))
    result = runner.invoke(
        app,
        ["backfill", "all", "--start", "2024-01-01", "--end", "2024-01-31"],
    )
    assert result.exit_code == 0, result.output
    assert called == ["tesouro", "cvm"]
    assert session.closed is True
    assert "bcb backfill skipped" in result.output.lower()
    assert "b3 backfill skipped" in result.output.lower()


def test_ingest_cvm_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "marketdata.cli.main.get_settings",
        lambda: _provider_settings(cvm_provider_enabled=False),
    )

    def fail_cvm(*_args, **_kwargs):
        raise AssertionError("cvm ingest must be skipped when disabled")

    monkeypatch.setattr("marketdata.ingestion.cvm.ingest_cvm", fail_cvm)
    result = runner.invoke(app, ["ingest", "cvm", "--date", "2026-08-24"])
    assert result.exit_code == 0, result.output
    assert "cvm ingest skipped" in result.output.lower()


def test_ingest_yahoo_skips_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "marketdata.cli.main.get_settings",
        lambda: _provider_settings(yahoo_provider_enabled=False),
    )

    def fail_yahoo(*_args, **_kwargs):
        raise AssertionError("yahoo ingest must be skipped when disabled")

    monkeypatch.setattr("marketdata.ingestion.yahoo.ingest_yahoo", fail_yahoo)
    result = runner.invoke(app, ["ingest", "yahoo", "--date", "2026-08-24"])
    assert result.exit_code == 0, result.output
    assert "yahoo ingest skipped" in result.output.lower()
