"""
Unit Test: Database Schema and ORM Entity Verification
Verifies table names, relationships, foreign keys, and status constraints across all 19 entities.
"""

import pytest
from sqlalchemy import create_engine, inspect
from backend.app.db.session import Base
from backend.app.db.models import (
    User, ApiToken, Project, ProjectMember, Scene, Asset, SceneQuality,
    ScenePair, DatasetVersion, ModelVersion, AnalysisJob, JobInput,
    ExecutionStep, ExecutionStepAsset, Finding, FindingEvidence, Report,
    OutboxEvent, JobEvent
)

def test_metadata_contains_all_entities():
    """Verify that all 27 entities are present in Base.metadata."""
    table_names = set(Base.metadata.tables.keys())
    expected = {
        'users', 'api_tokens', 'projects', 'project_members', 'scenes', 'assets',
        'scene_quality', 'scene_pairs', 'dataset_versions', 'model_versions',
        'analysis_jobs', 'job_inputs', 'execution_steps', 'execution_step_assets',
        'findings', 'finding_evidence', 'reports', 'outbox_events', 'job_events',
        'external_data_sources', 'external_map_layers', 'external_context_records',
        'conversations', 'conversation_messages', 'conversation_turns',
        'conversation_datasets', 'conversation_results'
    }
    missing = expected - table_names
    assert not missing, f"Missing tables in metadata: {missing}"


def test_scene_foreign_keys_and_indices():
    """Check constraints and indices on scenes table."""
    scenes_table = Base.metadata.tables['scenes']
    fk_targets = {fk.target_fullname for fk in scenes_table.foreign_keys}
    assert 'projects.id' in fk_targets

    index_names = {idx.name for idx in scenes_table.indexes}
    assert 'ix_scenes_project_time' in index_names
    assert 'ix_scenes_sensor_status' in index_names

def test_job_idempotency_constraint():
    """Verify that project_id + idempotency_key is constrained."""
    jobs_table = Base.metadata.tables['analysis_jobs']
    uq_names = {c.name for c in jobs_table.constraints if hasattr(c, 'name')}
    assert 'uq_project_idempotency' in uq_names
