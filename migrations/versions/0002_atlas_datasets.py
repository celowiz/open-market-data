"""Events, B3 lending snapshots, filtered COT, and 13F holdings.

Revision ID: 0002_atlas_datasets
Revises: 0001_initial_schema
Create Date: 2026-09-02
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_atlas_datasets"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=True),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("headline", sa.String(length=512), nullable=False),
        sa.Column("url", sa.String(length=1024), nullable=True),
        sa.Column("external_id", sa.String(length=256), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], name="fk_events_instrument_id_instruments"
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"],
            ["raw_artifacts.id"],
            name="fk_events_raw_artifact_id_raw_artifacts",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name="fk_events_ingestion_run_id_ingestion_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_events"),
        sa.UniqueConstraint("source", "external_id", name="uq_events_source_external_id"),
    )
    op.create_index("ix_events_ticker_occurred", "events", ["ticker", "occurred_at"])
    op.create_index("ix_events_instrument_id", "events", ["instrument_id"])

    op.create_table(
        "lending_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=True),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("snapshot_type", sa.String(length=32), nullable=False),
        sa.Column("qty", sa.Numeric(precision=38, scale=16), nullable=True),
        sa.Column("avg_rate", sa.Numeric(precision=38, scale=16), nullable=True),
        sa.Column("contracts", sa.Integer(), nullable=True),
        sa.Column("avg_price", sa.Numeric(precision=38, scale=16), nullable=True),
        sa.Column("balance_brl", sa.Numeric(precision=38, scale=16), nullable=True),
        sa.Column("market", sa.String(length=64), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_lending_snapshots_instrument_id_instruments",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name="fk_lending_snapshots_source_id_sources"
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"],
            ["raw_artifacts.id"],
            name="fk_lending_snapshots_raw_artifact_id_raw_artifacts",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name="fk_lending_snapshots_ingestion_run_id_ingestion_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_lending_snapshots"),
        sa.UniqueConstraint(
            "ticker",
            "reference_date",
            "snapshot_type",
            "source_id",
            name="uq_lending_snapshots_identity",
        ),
    )
    op.create_index(
        "ix_lending_snapshots_ticker_date",
        "lending_snapshots",
        ["ticker", "reference_date"],
    )
    op.create_index("ix_lending_snapshots_instrument_id", "lending_snapshots", ["instrument_id"])
    op.create_index("ix_lending_snapshots_reference_date", "lending_snapshots", ["reference_date"])

    op.create_table(
        "cot_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("contract_code", sa.String(length=32), nullable=False),
        sa.Column("contract_name", sa.String(length=128), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("open_interest", sa.Numeric(precision=38, scale=16), nullable=True),
        sa.Column("long_spec", sa.Numeric(precision=38, scale=16), nullable=True),
        sa.Column("short_spec", sa.Numeric(precision=38, scale=16), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name="fk_cot_snapshots_source_id_sources"
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"],
            ["raw_artifacts.id"],
            name="fk_cot_snapshots_raw_artifact_id_raw_artifacts",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name="fk_cot_snapshots_ingestion_run_id_ingestion_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_cot_snapshots"),
        sa.UniqueConstraint(
            "contract_code",
            "reference_date",
            "source_id",
            name="uq_cot_snapshots_identity",
        ),
    )
    op.create_index("ix_cot_snapshots_reference_date", "cot_snapshots", ["reference_date"])

    op.create_table(
        "thirteen_f_holdings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("filer_cik", sa.String(length=16), nullable=False),
        sa.Column("filer_name", sa.String(length=256), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("cusip", sa.String(length=16), nullable=False),
        sa.Column("ticker", sa.String(length=32), nullable=False),
        sa.Column("shares", sa.Numeric(precision=38, scale=16), nullable=True),
        sa.Column("value_usd", sa.Numeric(precision=38, scale=16), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name="fk_thirteen_f_holdings_source_id_sources"
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"],
            ["raw_artifacts.id"],
            name="fk_thirteen_f_holdings_raw_artifact_id_raw_artifacts",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name="fk_thirteen_f_holdings_ingestion_run_id_ingestion_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_thirteen_f_holdings"),
        sa.UniqueConstraint(
            "filer_cik",
            "report_date",
            "cusip",
            "source_id",
            name="uq_thirteen_f_holdings_identity",
        ),
    )
    op.create_index(
        "ix_thirteen_f_holdings_ticker_date",
        "thirteen_f_holdings",
        ["ticker", "report_date"],
    )
    op.create_index("ix_thirteen_f_holdings_report_date", "thirteen_f_holdings", ["report_date"])


def downgrade() -> None:
    op.drop_index("ix_thirteen_f_holdings_report_date", table_name="thirteen_f_holdings")
    op.drop_index("ix_thirteen_f_holdings_ticker_date", table_name="thirteen_f_holdings")
    op.drop_table("thirteen_f_holdings")
    op.drop_index("ix_cot_snapshots_reference_date", table_name="cot_snapshots")
    op.drop_table("cot_snapshots")
    op.drop_index("ix_lending_snapshots_reference_date", table_name="lending_snapshots")
    op.drop_index("ix_lending_snapshots_instrument_id", table_name="lending_snapshots")
    op.drop_index("ix_lending_snapshots_ticker_date", table_name="lending_snapshots")
    op.drop_table("lending_snapshots")
    op.drop_index("ix_events_instrument_id", table_name="events")
    op.drop_index("ix_events_ticker_occurred", table_name="events")
    op.drop_table("events")
