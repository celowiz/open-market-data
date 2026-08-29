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
