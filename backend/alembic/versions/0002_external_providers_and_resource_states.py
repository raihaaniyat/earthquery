"""External providers and resource admission schema migration

Revision ID: 0002_external_providers
Revises: 0001_initial_schema
Create Date: 2026-09-26 14:35:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002_external_providers'
down_revision: Union[str, None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add waiting_reason and estimated_queue_position to analysis_jobs
    with op.batch_alter_table("analysis_jobs") as batch_op:
        batch_op.add_column(sa.Column("waiting_reason", sa.String(100), nullable=True))
        batch_op.add_column(sa.Column("estimated_queue_position", sa.Integer(), nullable=True))

    # 2. Create external_data_sources table
    op.create_table(
        "external_data_sources",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("collection_id", sa.String(100), nullable=False),
        sa.Column("item_id", sa.String(150), nullable=False),
        sa.Column("catalogue_url", sa.Text(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_metadata_json", sa.Text(), nullable=False),
        sa.Column("license_terms", sa.Text(), nullable=True),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column("is_imported", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("imported_scene_id", sa.String(36), sa.ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "collection_id", "item_id", name="uq_external_provider_item"),
    )
    op.create_index("ix_external_data_sources_provider", "external_data_sources", ["provider"])
    op.create_index("ix_external_data_sources_collection_id", "external_data_sources", ["collection_id"])
    op.create_index("ix_external_data_sources_item_id", "external_data_sources", ["item_id"])
    op.create_index("ix_external_data_sources_project_id", "external_data_sources", ["project_id"])

    # 3. Create external_map_layers table
    op.create_table(
        "external_map_layers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("service_type", sa.String(20), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("layer_identifier", sa.String(150), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("supported_crs_json", sa.Text(), nullable=False),
        sa.Column("extent_wgs84_json", sa.Text(), nullable=True),
        sa.Column("min_scale", sa.Float(), nullable=True),
        sa.Column("max_scale", sa.Float(), nullable=True),
        sa.Column("is_allowlisted", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attribution", sa.Text(), nullable=True),
        sa.Column("use_terms", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("provider", "layer_identifier", name="uq_external_layer_ident"),
    )
    op.create_index("ix_external_map_layers_provider", "external_map_layers", ["provider"])
    op.create_index("ix_external_map_layers_layer_identifier", "external_map_layers", ["layer_identifier"])

    # 4. Create external_context_records table
    op.create_table(
        "external_context_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=True),
        sa.Column("finding_id", sa.String(36), sa.ForeignKey("findings.id", ondelete="CASCADE"), nullable=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("service_name", sa.String(100), nullable=False),
        sa.Column("date_version", sa.String(50), nullable=True),
        sa.Column("query_parameters_json", sa.Text(), nullable=False),
        sa.Column("returned_record_digest", sa.String(64), nullable=False),
        sa.Column("result_data_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_external_context_records_job_id", "external_context_records", ["job_id"])
    op.create_index("ix_external_context_records_finding_id", "external_context_records", ["finding_id"])


def downgrade() -> None:
    op.drop_table("external_context_records")
    op.drop_table("external_map_layers")
    op.drop_table("external_data_sources")
    with op.batch_alter_table("analysis_jobs") as batch_op:
        batch_op.drop_column("estimated_queue_position")
        batch_op.drop_column("waiting_reason")
