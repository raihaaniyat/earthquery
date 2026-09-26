"""Initial relational and spatial schema migration

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-09-25 21:50:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable PostGIS extension if available
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # 1. users
    op.create_table(
        'users',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # 2. api_tokens
    op.create_table(
        'api_tokens',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('token_hash', sa.String(length=255), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_api_tokens_token_hash', 'api_tokens', ['token_hash'], unique=True)
    op.create_index('ix_api_tokens_user_id', 'api_tokens', ['user_id'], unique=False)

    # 3. projects
    op.create_table(
        'projects',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('owner_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_projects_owner_id', 'projects', ['owner_id'], unique=False)

    # 4. project_members
    op.create_table(
        'project_members',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'user_id', name='uq_project_member')
    )
    op.create_index('ix_project_members_project_id', 'project_members', ['project_id'], unique=False)
    op.create_index('ix_project_members_user_id', 'project_members', ['user_id'], unique=False)

    # 5. scenes
    op.create_table(
        'scenes',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('sensor_platform', sa.String(length=100), nullable=True),
        sa.Column('product_level', sa.String(length=50), nullable=True),
        sa.Column('acquisition_time', sa.DateTime(timezone=True), nullable=True),
        sa.Column('provenance', sa.String(length=255), nullable=True),
        sa.Column('coordinate_space', sa.String(length=50), nullable=False),
        sa.Column('native_crs_wkt', sa.Text(), nullable=True),
        sa.Column('native_crs_epsg', sa.Integer(), nullable=True),
        sa.Column('width', sa.Integer(), nullable=False),
        sa.Column('height', sa.Integer(), nullable=False),
        sa.Column('pixel_size_x', sa.Float(), nullable=True),
        sa.Column('pixel_size_y', sa.Float(), nullable=True),
        sa.Column('pixel_unit', sa.String(length=50), nullable=True),
        sa.Column('footprint', Geometry(geometry_type='MULTIPOLYGON', srid=4326), nullable=True),
        sa.Column('validation_status', sa.String(length=50), nullable=False),
        sa.Column('validation_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scenes_project_id', 'scenes', ['project_id'], unique=False)
    op.create_index('ix_scenes_acquisition_time', 'scenes', ['acquisition_time'], unique=False)
    op.create_index('ix_scenes_validation_status', 'scenes', ['validation_status'], unique=False)
    op.create_index('ix_scenes_project_time', 'scenes', ['project_id', 'acquisition_time'], unique=False)
    op.create_index('ix_scenes_sensor_status', 'scenes', ['sensor_platform', 'validation_status'], unique=False)

    # 6. assets
    op.create_table(
        'assets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('scene_id', sa.String(length=36), nullable=True),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('bucket', sa.String(length=100), nullable=False),
        sa.Column('storage_key', sa.String(length=512), nullable=False),
        sa.Column('object_version', sa.String(length=100), nullable=True),
        sa.Column('sha256_hash', sa.String(length=64), nullable=False),
        sa.Column('byte_size', sa.BigInteger(), nullable=False),
        sa.Column('media_type', sa.String(length=100), nullable=False),
        sa.Column('band_count', sa.Integer(), nullable=True),
        sa.Column('dtype', sa.String(length=50), nullable=True),
        sa.Column('nodata_value', sa.Float(), nullable=True),
        sa.Column('affine_transform', sa.Text(), nullable=True),
        sa.Column('processing_version', sa.String(length=50), nullable=False),
        sa.Column('commit_status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scene_id'], ['scenes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_assets_project_id', 'assets', ['project_id'], unique=False)
    op.create_index('ix_assets_scene_id', 'assets', ['scene_id'], unique=False)
    op.create_index('ix_assets_sha256_hash', 'assets', ['sha256_hash'], unique=False)

    # 7. scene_quality
    op.create_table(
        'scene_quality',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('scene_id', sa.String(length=36), nullable=False),
        sa.Column('method_version', sa.String(length=50), nullable=False),
        sa.Column('valid_pixel_fraction', sa.Float(), nullable=True),
        sa.Column('cloud_fraction', sa.Float(), nullable=True),
        sa.Column('quality_flags', sa.Text(), nullable=True),
        sa.Column('supporting_asset_id', sa.String(length=36), nullable=True),
        sa.Column('assessed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['scene_id'], ['scenes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['supporting_asset_id'], ['assets.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('scene_id')
    )

    # 8. scene_pairs
    op.create_table(
        'scene_pairs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('source_scene_a_id', sa.String(length=36), nullable=False),
        sa.Column('source_scene_b_id', sa.String(length=36), nullable=False),
        sa.Column('source_asset_a_id', sa.String(length=36), nullable=False),
        sa.Column('source_asset_b_id', sa.String(length=36), nullable=False),
        sa.Column('pair_type', sa.String(length=50), nullable=False),
        sa.Column('overlap_geom', Geometry(geometry_type='MULTIPOLYGON', srid=4326), nullable=True),
        sa.Column('overlap_fraction_a', sa.Float(), nullable=True),
        sa.Column('overlap_fraction_b', sa.Float(), nullable=True),
        sa.Column('time_gap_seconds', sa.Float(), nullable=True),
        sa.Column('reference_grid_json', sa.Text(), nullable=True),
        sa.Column('alignment_error', sa.Float(), nullable=True),
        sa.Column('alignment_units', sa.String(length=50), nullable=True),
        sa.Column('alignment_method', sa.String(length=100), nullable=True),
        sa.Column('policy_version', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_asset_a_id'], ['assets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_asset_b_id'], ['assets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_scene_a_id'], ['scenes.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_scene_b_id'], ['scenes.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scene_pairs_project_id', 'scene_pairs', ['project_id'], unique=False)

    # 9. dataset_versions
    op.create_table(
        'dataset_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('dataset_id', sa.String(length=100), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('license', sa.String(length=100), nullable=False),
        sa.Column('source_url', sa.String(length=512), nullable=True),
        sa.Column('manifest_json', sa.Text(), nullable=True),
        sa.Column('split_policy', sa.String(length=100), nullable=True),
        sa.Column('checksum_sha256', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_dataset_versions_dataset_id', 'dataset_versions', ['dataset_id'], unique=False)

    # 10. model_versions
    op.create_table(
        'model_versions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('model_id', sa.String(length=100), nullable=False),
        sa.Column('version', sa.String(length=50), nullable=False),
        sa.Column('source_revision', sa.String(length=100), nullable=True),
        sa.Column('checkpoint_manifest', sa.Text(), nullable=True),
        sa.Column('code_revision', sa.String(length=100), nullable=True),
        sa.Column('contract_json', sa.Text(), nullable=True),
        sa.Column('preprocessing_recipe_version', sa.String(length=50), nullable=False),
        sa.Column('verification_state', sa.String(length=50), nullable=False),
        sa.Column('verification_history_json', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_model_versions_model_id', 'model_versions', ['model_id'], unique=False)

    # 11. analysis_jobs
    op.create_table(
        'analysis_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('project_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('task_type', sa.String(length=50), nullable=False),
        sa.Column('user_request_text', sa.Text(), nullable=True),
        sa.Column('canonical_request_json', sa.Text(), nullable=False),
        sa.Column('request_hash', sa.String(length=64), nullable=False),
        sa.Column('idempotency_key', sa.String(length=128), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('current_attempt', sa.Integer(), nullable=False),
        sa.Column('lease_token', sa.String(length=64), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_code', sa.String(length=100), nullable=True),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('project_id', 'idempotency_key', name='uq_project_idempotency')
    )
    op.create_index('ix_analysis_jobs_idempotency_key', 'analysis_jobs', ['idempotency_key'], unique=False)
    op.create_index('ix_analysis_jobs_project_id', 'analysis_jobs', ['project_id'], unique=False)
    op.create_index('ix_analysis_jobs_request_hash', 'analysis_jobs', ['request_hash'], unique=False)
    op.create_index('ix_analysis_jobs_status', 'analysis_jobs', ['status'], unique=False)
    op.create_index('ix_analysis_jobs_user_id', 'analysis_jobs', ['user_id'], unique=False)

    # 12. job_inputs
    op.create_table(
        'job_inputs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('scene_id', sa.String(length=36), nullable=True),
        sa.Column('asset_id', sa.String(length=36), nullable=True),
        sa.Column('input_role', sa.String(length=50), nullable=False),
        sa.Column('aoi_geometry', Geometry(geometry_type='MULTIPOLYGON', srid=4326), nullable=True),
        sa.Column('time_context_json', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['job_id'], ['analysis_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scene_id'], ['scenes.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_job_inputs_job_id', 'job_inputs', ['job_id'], unique=False)

    # 13. execution_steps
    op.create_table(
        'execution_steps',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('step_key', sa.String(length=100), nullable=False),
        sa.Column('step_order', sa.Integer(), nullable=False),
        sa.Column('attempt', sa.Integer(), nullable=False),
        sa.Column('tool_or_model', sa.String(length=100), nullable=False),
        sa.Column('model_version_id', sa.String(length=36), nullable=True),
        sa.Column('parameters_json', sa.Text(), nullable=True),
        sa.Column('environment_name', sa.String(length=100), nullable=False),
        sa.Column('code_version', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('duration_ms', sa.Float(), nullable=True),
        sa.Column('vram_peak_mb', sa.Float(), nullable=True),
        sa.Column('ram_peak_mb', sa.Float(), nullable=True),
        sa.Column('error_details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['analysis_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['model_version_id'], ['model_versions.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_execution_steps_job_id', 'execution_steps', ['job_id'], unique=False)

    # 14. execution_step_assets
    op.create_table(
        'execution_step_assets',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('step_id', sa.String(length=36), nullable=False),
        sa.Column('asset_id', sa.String(length=36), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('tile_window_json', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['step_id'], ['execution_steps.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_execution_step_assets_asset_id', 'execution_step_assets', ['asset_id'], unique=False)
    op.create_index('ix_execution_step_assets_step_id', 'execution_step_assets', ['step_id'], unique=False)

    # 15. findings
    op.create_table(
        'findings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('finding_type', sa.String(length=100), nullable=False),
        sa.Column('text_summary', sa.Text(), nullable=False),
        sa.Column('geographic_geometry', Geometry(geometry_type='GEOMETRY', srid=4326), nullable=True),
        sa.Column('pixel_geometry_json', sa.Text(), nullable=True),
        sa.Column('measurements_json', sa.Text(), nullable=True),
        sa.Column('confidence_details_json', sa.Text(), nullable=True),
        sa.Column('review_status', sa.String(length=50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['analysis_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_findings_job_id', 'findings', ['job_id'], unique=False)

    # 16. finding_evidence
    op.create_table(
        'finding_evidence',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('finding_id', sa.String(length=36), nullable=False),
        sa.Column('scene_id', sa.String(length=36), nullable=True),
        sa.Column('asset_id', sa.String(length=36), nullable=True),
        sa.Column('step_id', sa.String(length=36), nullable=True),
        sa.Column('region_json', sa.Text(), nullable=True),
        sa.Column('evidence_role', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['asset_id'], ['assets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['finding_id'], ['findings.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['scene_id'], ['scenes.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['step_id'], ['execution_steps.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_finding_evidence_finding_id', 'finding_evidence', ['finding_id'], unique=False)

    # 17. reports
    op.create_table(
        'reports',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('report_asset_id', sa.String(length=36), nullable=False),
        sa.Column('format', sa.String(length=20), nullable=False),
        sa.Column('manifest_digest', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['analysis_jobs.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['report_asset_id'], ['assets.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_reports_job_id', 'reports', ['job_id'], unique=False)

    # 18. outbox_events
    op.create_table(
        'outbox_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('aggregate_type', sa.String(length=100), nullable=False),
        sa.Column('aggregate_id', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=False),
        sa.Column('delivery_attempts', sa.Integer(), nullable=False),
        sa.Column('next_attempt_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_outbox_events_aggregate_id', 'outbox_events', ['aggregate_id'], unique=False)
    op.create_index('ix_outbox_events_next_attempt_at', 'outbox_events', ['next_attempt_at'], unique=False)

    # 19. job_events
    op.create_table(
        'job_events',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('job_id', sa.String(length=36), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['analysis_jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_job_events_job_id', 'job_events', ['job_id'], unique=False)
    op.create_index('ix_job_events_job_id_id', 'job_events', ['job_id', 'id'], unique=False)


def downgrade() -> None:
    op.drop_table('job_events')
    op.drop_table('outbox_events')
    op.drop_table('reports')
    op.drop_table('finding_evidence')
    op.drop_table('findings')
    op.drop_table('execution_step_assets')
    op.drop_table('execution_steps')
    op.drop_table('job_inputs')
    op.drop_table('analysis_jobs')
    op.drop_table('model_versions')
    op.drop_table('dataset_versions')
    op.drop_table('scene_pairs')
    op.drop_table('scene_quality')
    op.drop_table('assets')
    op.drop_table('scenes')
    op.drop_table('project_members')
    op.drop_table('projects')
    op.drop_table('api_tokens')
    op.drop_table('users')
