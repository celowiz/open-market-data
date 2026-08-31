from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / ".github" / "workflows"
B3_JOBS = (
    WORKFLOWS / "ingest-b3.yml",
    WORKFLOWS / "ingest-all.yml",
    WORKFLOWS / "backfill.yml",
)


def test_b3_ingest_workflows_forward_ingest_universe_repo_var() -> None:
    """Without this, marketdata ingest/backfill b3 persists the full BVBG.186 file."""
    expected = (
        "INGEST_UNIVERSE: ${{ vars.INGEST_UNIVERSE }}",
        "B3_EQUITY_UNIVERSE_PATH: ${{ vars.B3_EQUITY_UNIVERSE_PATH }}",
    )
    for path in B3_JOBS:
        text = path.read_text(encoding="utf-8")
        for needle in expected:
            assert needle in text, f"{path.name} must pass {needle.split(':')[0]} into job env"


def test_b3_ingest_workflows_unbuffer_python_and_do_not_raise_job_cap() -> None:
    """Cancelled run 33334956436 printed nothing for 2h; unbuffered logs are required."""
    for path in B3_JOBS:
        text = path.read_text(encoding="utf-8")
        assert "PYTHONUNBUFFERED:" in text, (
            f"{path.name} must set PYTHONUNBUFFERED so stage logs flush"
        )


def test_backfill_workflow_restores_and_uploads_checkpoint_without_scheduling() -> None:
    text = (WORKFLOWS / "backfill.yml").read_text(encoding="utf-8")
    assert "cancel-in-progress: false" in text
    assert "timeout-minutes: 360" in text
    assert "data/state/backfill" in text
    assert "actions/cache/restore@" in text
    assert "actions/cache/save@" in text
    assert "actions/upload-artifact@" in text
    assert "if: always()" in text
    assert "path: data/state/backfill/" in text
    on_block = text.split("\njobs:", 1)[0]
    assert "workflow_dispatch:" in on_block
    assert "schedule:" not in on_block
