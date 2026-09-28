"""
SQLAlchemy 2.0 ORM Models for SatQuery AI.
Implements the complete relational schema with PostGIS spatial geometries,
evidence chains, model registries, and outbox event publishing.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import (
    Column, String, Integer, BigInteger, Float, Boolean, DateTime, Text,
    ForeignKey, Table, Index, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from geoalchemy2 import Geometry

from backend.app.db.session import Base

def generate_uuid() -> str:
    return str(uuid.uuid4())

def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    tokens = relationship("ApiToken", back_populates="user", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="owner")
    memberships = relationship("ProjectMember", back_populates="user")


class ApiToken(Base):
    __tablename__ = "api_tokens"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(100), nullable=False)
    token_hash = Column(String(255), unique=True, index=True, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", back_populates="tokens")


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    owner_id = Column(String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    owner = relationship("User", back_populates="projects")
    members = relationship("ProjectMember", back_populates="project", cascade="all, delete-orphan")
    scenes = relationship("Scene", back_populates="project", cascade="all, delete-orphan")
    assets = relationship("Asset", back_populates="project", cascade="all, delete-orphan")
    jobs = relationship("AnalysisJob", back_populates="project", cascade="all, delete-orphan")


class ProjectMember(Base):
    __tablename__ = "project_members"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), default="member", nullable=False) # 'owner', 'admin', 'member', 'viewer'
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    project = relationship("Project", back_populates="members")
    user = relationship("User", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )


class Scene(Base):
    __tablename__ = "scenes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    sensor_platform = Column(String(100), nullable=True)  # e.g., 'Sentinel-1', 'Sentinel-2', 'Benchmark'
    product_level = Column(String(50), nullable=True)    # e.g., 'L2A', 'GRD'
    acquisition_time = Column(DateTime(timezone=True), nullable=True, index=True)
    provenance = Column(String(255), nullable=True)
    coordinate_space = Column(String(50), default="geographic", nullable=False) # 'geographic' or 'pixel'
    
    native_crs_wkt = Column(Text, nullable=True)
    native_crs_epsg = Column(Integer, nullable=True)
    width = Column(Integer, nullable=False)
    height = Column(Integer, nullable=False)
    pixel_size_x = Column(Float, nullable=True)
    pixel_size_y = Column(Float, nullable=True)
    pixel_unit = Column(String(50), nullable=True)       # e.g., 'metre', 'degree', 'pixel'
    
    # PostGIS Footprint in EPSG:4326, nullable for coordinate_space='pixel'
    footprint = Column(Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=True)
    
    validation_status = Column(String(50), default="pending_upload", nullable=False, index=True)
    # 'pending_upload', 'pending_validation', 'validating', 'ready', 'invalid', 'failed'
    validation_error = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    project = relationship("Project", back_populates="scenes")
    assets = relationship("Asset", back_populates="scene", cascade="all, delete-orphan")
    quality = relationship("SceneQuality", back_populates="scene", uselist=False, cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_scenes_project_time", "project_id", "acquisition_time"),
        Index("ix_scenes_sensor_status", "sensor_platform", "validation_status"),
    )


class Asset(Base):
    __tablename__ = "assets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    scene_id = Column(String(36), ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True, index=True)
    role = Column(String(50), nullable=False) # 'original', 'preview', 'cog', 'mask', 'features', 'report', 'checkpoint'
    
    bucket = Column(String(100), nullable=False)
    storage_key = Column(String(512), nullable=False)
    object_version = Column(String(100), nullable=True)
    sha256_hash = Column(String(64), nullable=False, index=True)
    byte_size = Column(BigInteger, nullable=False)
    media_type = Column(String(100), nullable=False) # e.g. 'image/tiff', 'image/png', 'application/pdf'
    
    band_count = Column(Integer, nullable=True)
    dtype = Column(String(50), nullable=True)
    nodata_value = Column(Float, nullable=True)
    affine_transform = Column(Text, nullable=True) # Serialized 6-element affine matrix
    processing_version = Column(String(50), default="1.0", nullable=False)
    commit_status = Column(String(50), default="staging", nullable=False) # 'staging', 'committed', 'orphan'
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    project = relationship("Project", back_populates="assets")
    scene = relationship("Scene", back_populates="assets")


class SceneQuality(Base):
    __tablename__ = "scene_quality"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    scene_id = Column(String(36), ForeignKey("scenes.id", ondelete="CASCADE"), unique=True, nullable=False)
    method_version = Column(String(50), default="1.0", nullable=False)
    valid_pixel_fraction = Column(Float, nullable=True)
    cloud_fraction = Column(Float, nullable=True) # Unknown cloud fraction is NULL
    quality_flags = Column(Text, nullable=True)   # JSON string or bitfield
    supporting_asset_id = Column(String(36), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    assessed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    scene = relationship("Scene", back_populates="quality")


class ScenePair(Base):
    __tablename__ = "scene_pairs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    source_scene_a_id = Column(String(36), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False)
    source_scene_b_id = Column(String(36), ForeignKey("scenes.id", ondelete="CASCADE"), nullable=False)
    source_asset_a_id = Column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    source_asset_b_id = Column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    
    pair_type = Column(String(50), nullable=False) # 'bitemporal_optical', 'optical_sar'
    overlap_geom = Column(Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=True)
    overlap_fraction_a = Column(Float, nullable=True)
    overlap_fraction_b = Column(Float, nullable=True)
    time_gap_seconds = Column(Float, nullable=True)
    reference_grid_json = Column(Text, nullable=True)
    
    alignment_error = Column(Float, nullable=True)
    alignment_units = Column(String(50), nullable=True) # 'pixels', 'metres'
    alignment_method = Column(String(100), nullable=True)
    policy_version = Column(String(50), default="1.0", nullable=False)
    
    status = Column(String(50), default="unverified", nullable=False) # 'ready', 'unverified', 'rejected'
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    dataset_id = Column(String(100), nullable=False, index=True)
    version = Column(String(50), nullable=False)
    license = Column(String(100), nullable=False)
    source_url = Column(String(512), nullable=True)
    manifest_json = Column(Text, nullable=True)
    split_policy = Column(String(100), nullable=True)
    checksum_sha256 = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    model_id = Column(String(100), nullable=False, index=True) # e.g. 'InternVL3-2B', 'CROMA-Base', 'ChangeFormerV6'
    version = Column(String(50), nullable=False)
    source_revision = Column(String(100), nullable=True)
    checkpoint_manifest = Column(Text, nullable=True)
    code_revision = Column(String(100), nullable=True)
    contract_json = Column(Text, nullable=True)
    preprocessing_recipe_version = Column(String(50), default="1.0", nullable=False)
    
    verification_state = Column(String(50), default="DOWNLOADED", nullable=False)
    # 'DOWNLOADED', 'CHECKSUM_VERIFIED', 'LOAD_TESTED', 'INFERENCE_TESTED', 'EVALUATED', 'UNAVAILABLE', 'TRAINING_REQUIRED'
    verification_history_json = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class AnalysisJob(Base):
    __tablename__ = "analysis_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    task_type = Column(String(50), nullable=False) # 'vqa', 'change_detection', 'land_cover', 'optical_sar'
    
    user_request_text = Column(Text, nullable=True)
    canonical_request_json = Column(Text, nullable=False)
    request_hash = Column(String(64), nullable=False, index=True)
    idempotency_key = Column(String(128), nullable=True, index=True)
    
    status = Column(String(50), default="queued", nullable=False, index=True)
    # 'queued', 'waiting_for_resources', 'running', 'needs_input', 'retry_wait', 'cancel_requested', 'cancelled', 'succeeded', 'failed'
    waiting_reason = Column(String(100), nullable=True) # 'gpu_busy', 'gpu_memory_reserve', 'disk_pressure', 'provider_rate_limit'
    estimated_queue_position = Column(Integer, nullable=True)
    current_attempt = Column(Integer, default=1, nullable=False)
    lease_token = Column(String(64), nullable=True)
    lease_holder = Column(String(100), nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    error_code = Column(String(100), nullable=True)
    error_summary = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


    project = relationship("Project", back_populates="jobs")
    inputs = relationship("JobInput", back_populates="job", cascade="all, delete-orphan")
    steps = relationship("ExecutionStep", back_populates="job", cascade="all, delete-orphan")
    findings = relationship("Finding", back_populates="job", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="job", cascade="all, delete-orphan")
    events = relationship("JobEvent", back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("project_id", "idempotency_key", name="uq_project_idempotency"),
    )


class JobInput(Base):
    __tablename__ = "job_inputs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    scene_id = Column(String(36), ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    input_role = Column(String(50), nullable=False) # 'primary', 'before_scene', 'after_scene', 'optical', 'sar'
    aoi_geometry = Column(Geometry(geometry_type="MULTIPOLYGON", srid=4326), nullable=True)
    time_context_json = Column(Text, nullable=True)

    job = relationship("AnalysisJob", back_populates="inputs")


class ExecutionStep(Base):
    __tablename__ = "execution_steps"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_key = Column(String(100), nullable=False) # e.g., 'pair_validation', 'preprocess', 'change_inference'
    step_order = Column(Integer, nullable=False)
    attempt = Column(Integer, default=1, nullable=False)
    
    tool_or_model = Column(String(100), nullable=False)
    model_version_id = Column(String(36), ForeignKey("model_versions.id", ondelete="SET NULL"), nullable=True)
    parameters_json = Column(Text, nullable=True)
    environment_name = Column(String(100), nullable=False)
    code_version = Column(String(50), nullable=True)
    
    status = Column(String(50), default="queued", nullable=False) # 'queued', 'running', 'succeeded', 'failed', 'cancelled'
    duration_ms = Column(Float, nullable=True)
    vram_peak_mb = Column(Float, nullable=True)
    ram_peak_mb = Column(Float, nullable=True)
    error_details = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    job = relationship("AnalysisJob", back_populates="steps")
    step_assets = relationship("ExecutionStepAsset", back_populates="step", cascade="all, delete-orphan")


class ExecutionStepAsset(Base):
    __tablename__ = "execution_step_assets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    step_id = Column(String(36), ForeignKey("execution_steps.id", ondelete="CASCADE"), nullable=False, index=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False) # 'input', 'output'
    tile_window_json = Column(Text, nullable=True)

    step = relationship("ExecutionStep", back_populates="step_assets")


class Finding(Base):
    __tablename__ = "findings"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id = Column(String(36), ForeignKey("execution_steps.id", ondelete="SET NULL"), nullable=True, index=True)
    finding_type = Column(String(100), nullable=False) # 'vqa_answer', 'change_polygon', 'classification_summary'
    text_summary = Column(Text, nullable=False)
    
    geographic_geometry = Column(Geometry(geometry_type="GEOMETRY", srid=4326), nullable=True)
    pixel_geometry_json = Column(Text, nullable=True) # For benchmark images
    measurements_json = Column(Text, nullable=True)   # E.g. {"area_sq_m": 12450.5}
    confidence_details_json = Column(Text, nullable=True) # Calibration, model uncertainty, quality limits
    review_status = Column(String(50), default="unreviewed", nullable=False) # 'unreviewed', 'accepted', 'flagged'
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    job = relationship("AnalysisJob", back_populates="findings")
    evidence = relationship("FindingEvidence", back_populates="finding", cascade="all, delete-orphan")

    @property
    def finding_text(self) -> str:
        return self.text_summary

    @finding_text.setter
    def finding_text(self, val: str) -> None:
        self.text_summary = val


class FindingEvidence(Base):
    __tablename__ = "finding_evidence"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    finding_id = Column(String(36), ForeignKey("findings.id", ondelete="CASCADE"), nullable=False, index=True)
    scene_id = Column(String(36), ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True)
    asset_id = Column(String(36), ForeignKey("assets.id", ondelete="SET NULL"), nullable=True)
    step_id = Column(String(36), ForeignKey("execution_steps.id", ondelete="SET NULL"), nullable=True)
    region_json = Column(Text, nullable=True)
    evidence_role = Column(String(50), nullable=False) # 'source_observation', 'inference_mask', 'supporting_feature'
    observation_scope = Column(String(50), default="scene", nullable=True)

    finding = relationship("Finding", back_populates="evidence")



class Report(Base):
    __tablename__ = "reports"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    report_asset_id = Column(String(36), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False)
    format = Column(String(20), default="pdf", nullable=False) # 'pdf', 'json'
    manifest_digest = Column(String(64), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    job = relationship("AnalysisJob", back_populates="reports")

    @property
    def report_format(self) -> str:
        return self.format

    @report_format.setter
    def report_format(self, val: str) -> None:
        self.format = val


class OutboxEvent(Base):
    __tablename__ = "outbox_events"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    aggregate_type = Column(String(100), nullable=False) # 'job', 'scene', 'asset'
    aggregate_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)     # 'job.created', 'scene.uploaded', 'job.cancelled'
    payload_json = Column(Text, nullable=False)
    delivery_attempts = Column(Integer, default=0, nullable=False)
    max_attempts = Column(Integer, default=5, nullable=False)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    next_attempt_at = Column(DateTime(timezone=True), default=utc_now, nullable=False, index=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class JobEvent(Base):
    __tablename__ = "job_events"

    id = Column(Integer().with_variant(BigInteger, "postgresql"), primary_key=True, autoincrement=True) # Monotonic ID
    job_id = Column(String(36), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    job = relationship("AnalysisJob", back_populates="events")

    __table_args__ = (
        Index("ix_job_events_job_id_id", "job_id", "id"),
    )


class ExternalDataSource(Base):
    __tablename__ = "external_data_sources"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    provider = Column(String(50), nullable=False, index=True) # 'bhoonidhi', 'bhuvan', 'copernicus'
    collection_id = Column(String(100), nullable=False, index=True)
    item_id = Column(String(150), nullable=False, index=True)
    catalogue_url = Column(Text, nullable=True)
    retrieved_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    source_metadata_json = Column(Text, nullable=False)
    license_terms = Column(Text, nullable=True)
    attribution = Column(Text, nullable=True)
    is_imported = Column(Boolean, default=False, nullable=False)
    imported_scene_id = Column(String(36), ForeignKey("scenes.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "collection_id", "item_id", name="uq_external_provider_item"),
    )


class ExternalMapLayer(Base):
    __tablename__ = "external_map_layers"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    provider = Column(String(50), nullable=False, index=True) # 'bhuvan', 'isro'
    service_type = Column(String(20), nullable=False) # 'WMS', 'WMTS', 'REST'
    base_url = Column(Text, nullable=False)
    layer_identifier = Column(String(150), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    supported_crs_json = Column(Text, nullable=False) # e.g. '["EPSG:4326", "EPSG:3857"]'
    extent_wgs84_json = Column(Text, nullable=True)
    min_scale = Column(Float, nullable=True)
    max_scale = Column(Float, nullable=True)
    is_allowlisted = Column(Boolean, default=True, nullable=False)
    last_checked_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    attribution = Column(Text, nullable=True)
    use_terms = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("provider", "layer_identifier", name="uq_external_layer_ident"),
    )


class ExternalContextRecord(Base):
    __tablename__ = "external_context_records"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    job_id = Column(String(36), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=True, index=True)
    finding_id = Column(String(36), ForeignKey("findings.id", ondelete="CASCADE"), nullable=True, index=True)
    provider = Column(String(50), nullable=False) # 'bhuvan'
    service_name = Column(String(100), nullable=False) # 'lulc_statistics', 'village_geocoding'
    date_version = Column(String(50), nullable=True)
    query_parameters_json = Column(Text, nullable=False)
    returned_record_digest = Column(String(64), nullable=False)
    result_data_json = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    job = relationship("AnalysisJob", backref="external_contexts")
    finding = relationship("Finding", backref="external_contexts")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    title = Column(String(255), default="New Analysis Conversation", nullable=False)
    state_revision = Column(Integer, default=1, nullable=False)
    active_context_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    messages = relationship("ConversationMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationMessage.created_at")
    turns = relationship("ConversationTurn", back_populates="conversation", cascade="all, delete-orphan", order_by="ConversationTurn.created_at")
    datasets = relationship("ConversationDataset", back_populates="conversation", cascade="all, delete-orphan")
    results = relationship("ConversationResult", back_populates="conversation", cascade="all, delete-orphan")


class ConversationMessage(Base):
    __tablename__ = "conversation_messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_id = Column(String(36), nullable=True, index=True)
    role = Column(String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = Column(Text, nullable=False)
    client_request_id = Column(String(128), nullable=True, index=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    conversation = relationship("Conversation", back_populates="messages")


class ConversationTurn(Base):
    __tablename__ = "conversation_turns"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    client_request_id = Column(String(128), nullable=False, index=True)
    user_message_id = Column(String(36), nullable=True)
    status = Column(String(50), default="accepted", nullable=False)  # 'accepted', 'running', 'completed', 'needs_input', 'failed'
    turn_type = Column(String(50), default="analysis", nullable=False)  # 'analysis', 'saved_fact', 'map_action', 'parameter_modification', 'explanation', 'clarification'
    result_id = Column(String(36), nullable=True)
    job_id = Column(String(36), nullable=True)
    attempt = Column(Integer, default=1, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    conversation = relationship("Conversation", back_populates="turns")

    __table_args__ = (
        UniqueConstraint("conversation_id", "client_request_id", name="uq_conv_turn_request"),
    )


class ConversationDataset(Base):
    __tablename__ = "conversation_datasets"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    file_path = Column(String(512), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_size = Column(BigInteger, nullable=True)
    mime_type = Column(String(100), nullable=True)
    role = Column(String(50), default="original", nullable=False)  # 'original', 'earlier_image', 'later_image', 'comparison_input'
    acquisition_date = Column(String(50), nullable=True)
    metadata_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    conversation = relationship("Conversation", back_populates="datasets")


class ConversationResult(Base):
    __tablename__ = "conversation_results"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_id = Column(String(36), nullable=True, index=True)
    parent_result_id = Column(String(36), nullable=True, index=True)
    result_role = Column(String(50), default="original", nullable=False)  # 'original', 'derived', 'filtered', 'comparison'
    operation = Column(String(100), nullable=False)
    parameters_json = Column(Text, nullable=True)
    summary = Column(Text, nullable=False)
    findings_json = Column(Text, nullable=True)
    sections_json = Column(Text, nullable=True)
    metrics_json = Column(Text, nullable=True)
    mask_url = Column(String(512), nullable=True)
    source_dataset_ids_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    conversation = relationship("Conversation", back_populates="results")



