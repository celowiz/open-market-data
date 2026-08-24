"""Initial serving schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("official", sa.Boolean(), nullable=False),
        sa.Column("homepage", sa.String(length=512), nullable=True),
        sa.Column("documentation_url", sa.String(length=512), nullable=True),
        sa.Column("data_license", sa.String(length=128), nullable=True),
        sa.Column("redistribution_policy", sa.String(length=64), nullable=False),
        sa.Column("ingestion_enabled", sa.Boolean(), nullable=False),
        sa.Column("public_api_enabled", sa.Boolean(), nullable=False),
        sa.Column("public_dataset_enabled", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_sources"),
        sa.UniqueConstraint("name", name="uq_sources_name"),
    )
    op.create_table(
        "instruments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("asset_class", sa.String(length=64), nullable=False),
        sa.Column("instrument_type", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("exchange", sa.String(length=64), nullable=True),
        sa.Column("mic", sa.String(length=16), nullable=True),
        sa.Column("issuer", sa.String(length=256), nullable=True),
        sa.Column("maturity_date", sa.Date(), nullable=True),
        sa.Column("active_from", sa.Date(), nullable=True),
        sa.Column("active_until", sa.Date(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_instruments"),
    )
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("requested_reference_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("artifacts_downloaded", sa.Integer(), nullable=False),
        sa.Column("records_parsed", sa.Integer(), nullable=False),
        sa.Column("records_normalized", sa.Integer(), nullable=False),
        sa.Column("records_inserted", sa.Integer(), nullable=False),
        sa.Column("records_updated", sa.Integer(), nullable=False),
        sa.Column("records_rejected", sa.Integer(), nullable=False),
        sa.Column("warnings", sa.Integer(), nullable=False),
        sa.Column("errors", sa.Integer(), nullable=False),
        sa.Column("git_sha", sa.String(length=64), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name="fk_ingestion_runs_source_id_sources"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ingestion_runs"),
    )
    op.create_index("ix_ingestion_runs_provider", "ingestion_runs", ["provider"])
    op.create_table(
        "instrument_identifiers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("identifier_type", sa.String(length=64), nullable=False),
        sa.Column("identifier_value", sa.String(length=128), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_instrument_identifiers_instrument_id_instruments",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name="fk_instrument_identifiers_source_id_sources"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_instrument_identifiers"),
        sa.UniqueConstraint(
            "identifier_type",
            "identifier_value",
            "source_id",
            name="uq_instrument_identifiers_type_value_source",
        ),
    )
    op.create_index(
        "ix_instrument_identifiers_instrument_id", "instrument_identifiers", ["instrument_id"]
    )
    op.create_index("ix_instrument_identifiers_source_id", "instrument_identifiers", ["source_id"])
    op.create_index(
        "ix_instrument_identifiers_type_value",
        "instrument_identifiers",
        ["identifier_type", "identifier_value"],
    )
    op.create_table(
        "market_series",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("source_series_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("unit", sa.String(length=64), nullable=False),
        sa.Column("value_semantics", sa.String(length=64), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name="fk_market_series_source_id_sources"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_market_series"),
        sa.UniqueConstraint("code", name="uq_market_series_code"),
    )
    op.create_table(
        "provider_status",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("last_success", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reference_date", sa.Date(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False),
        sa.Column("latest_error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name="fk_provider_status_source_id_sources"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_provider_status"),
        sa.UniqueConstraint("provider", name="uq_provider_status_provider"),
    )
    op.create_table(
        "quality_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.Column("instrument_id", sa.Uuid(), nullable=True),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name="fk_quality_events_ingestion_run_id_ingestion_runs",
        ),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_quality_events_instrument_id_instruments",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name="fk_quality_events_source_id_sources"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_quality_events"),
    )
    op.create_index("ix_quality_events_ingestion_run_id", "quality_events", ["ingestion_run_id"])
    op.create_table(
        "raw_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_url", sa.String(length=1024), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("encoding", sa.String(length=64), nullable=True),
        sa.Column("filename", sa.String(length=256), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("etag", sa.String(length=256), nullable=True),
        sa.Column("last_modified", sa.String(length=128), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("storage_uri", sa.String(length=1024), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name="fk_raw_artifacts_source_id_sources"
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name="fk_raw_artifacts_ingestion_run_id_ingestion_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_raw_artifacts"),
    )
    op.create_index("ix_raw_artifacts_sha256", "raw_artifacts", ["sha256"])
    op.create_table(
        "instrument_quotes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("instrument_id", sa.Uuid(), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(precision=38, scale=16), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=True),
        sa.Column("unit", sa.String(length=64), nullable=True),
        sa.Column("price_type", sa.String(length=64), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("source_instrument_id", sa.String(length=128), nullable=True),
        sa.Column("is_official", sa.Boolean(), nullable=False),
        sa.Column("source_published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("quality_status", sa.String(length=32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"],
            ["instruments.id"],
            name="fk_instrument_quotes_instrument_id_instruments",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name="fk_instrument_quotes_source_id_sources"
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"],
            ["raw_artifacts.id"],
            name="fk_instrument_quotes_raw_artifact_id_raw_artifacts",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name="fk_instrument_quotes_ingestion_run_id_ingestion_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_instrument_quotes"),
        sa.UniqueConstraint(
            "instrument_id",
            "reference_date",
            "source_id",
            "price_type",
            "revision",
            name="uq_instrument_quotes_identity",
        ),
    )
    op.create_index("ix_instrument_quotes_instrument_id", "instrument_quotes", ["instrument_id"])
    op.create_index("ix_instrument_quotes_reference_date", "instrument_quotes", ["reference_date"])
    op.create_index("ix_instrument_quotes_source_id", "instrument_quotes", ["source_id"])
    op.create_index(
        "ix_instrument_quotes_instrument_date",
        "instrument_quotes",
        ["instrument_id", "reference_date"],
    )
    op.create_index(
        "ix_instrument_quotes_source_date", "instrument_quotes", ["source_id", "reference_date"]
    )
    op.create_table(
        "market_series_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("series_id", sa.Uuid(), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(precision=38, scale=16), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_artifact_id", sa.Uuid(), nullable=True),
        sa.Column("ingestion_run_id", sa.Uuid(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("quality_status", sa.String(length=32), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["series_id"],
            ["market_series.id"],
            name="fk_market_series_observations_series_id_market_series",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["sources.id"], name="fk_market_series_observations_source_id_sources"
        ),
        sa.ForeignKeyConstraint(
            ["raw_artifact_id"],
            ["raw_artifacts.id"],
            name="fk_market_series_observations_raw_artifact_id_raw_artifacts",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"],
            ["ingestion_runs.id"],
            name="fk_market_series_observations_ingestion_run_id_ingestion_runs",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_market_series_observations"),
        sa.UniqueConstraint(
            "series_id",
            "reference_date",
            "source_id",
            "revision",
            name="uq_market_series_observations_identity",
        ),
    )
    op.create_index(
        "ix_market_series_observations_series_id", "market_series_observations", ["series_id"]
    )
    op.create_index(
        "ix_market_series_observations_reference_date",
        "market_series_observations",
        ["reference_date"],
    )


def downgrade() -> None:
    op.drop_table("market_series_observations")
    op.drop_table("instrument_quotes")
    op.drop_table("raw_artifacts")
    op.drop_table("quality_events")
    op.drop_table("provider_status")
    op.drop_table("market_series")
    op.drop_table("instrument_identifiers")
    op.drop_table("ingestion_runs")
    op.drop_table("instruments")
    op.drop_table("sources")
