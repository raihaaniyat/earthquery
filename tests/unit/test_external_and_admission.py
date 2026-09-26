"""
Unit Tests: External Providers (BHOONIDHI, Bhuvan) and Resource Admission Gates.
Verifies rate limits, online item verification, context provenance records,
GPU VRAM headroom admission checks, and queue capacity backpressure (429 Retry-After).
"""

import pytest
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import settings
from backend.app.db.session import Base
from backend.app.db.models import User, Project, AnalysisJob, ExternalDataSource, ExternalContextRecord
from backend.app.services.bhoonidhi import bhoonidhi_provider, SUPPORTED_COLLECTIONS
from backend.app.services.bhuvan import bhuvan_provider, ALLOWLISTED_BHUVAN_LAYERS
from backend.app.services.jobs import JobService, CapacityExceededError
from backend.runtime.supervisor import ProcessSupervisor
from backend.runtime.protocol import SubprocessRequest


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed test user and project
    user = User(id="user-1", email="test@satquery.local", full_name="Test User", hashed_password="hash")
    project = Project(id="proj-1", owner_id="user-1", name="Test Project")
    session.add_all([user, project])
    session.commit()


    yield session
    session.close()


def test_bhoonidhi_collections_listing():
    """Verify BHOONIDHI exposes official NRSC collections."""
    cols = bhoonidhi_provider.list_collections()
    col_ids = {c["id"] for c in cols}
    assert "RS2_LISS3" in col_ids
    assert "EOS04_SAR" in col_ids
    assert "S1_SAR" in col_ids
    assert "CARTOSAT1_DEM" in col_ids
    assert len(cols) == len(SUPPORTED_COLLECTIONS)


def test_bhoonidhi_search_normalization_and_online_flag():
    """Verify BHOONIDHI STAC search normalizes features with Online flag."""
    res = bhoonidhi_provider.search(
        collections=["RS2_LISS3"],
        bbox=[77.0, 12.8, 77.5, 13.3],
        limit=5
    )
    assert res["type"] == "FeatureCollection"
    assert len(res["features"]) > 0
    first = res["features"][0]
    assert first["properties"]["online"] == "Y"
    assert first["properties"]["attribution"] == "NRSC / ISRO BHOONIDHI Geoportal"


def test_bhoonidhi_import_product_and_metadata(db_session):
    """Verify staged product import writes to ObjectStore and records external_data_sources."""
    res = bhoonidhi_provider.import_product(
        db=db_session,
        project_id="proj-1",
        collection_id="RS2_LISS3",
        item_id="RS2_2026_001"
    )
    assert res["status"] == "imported_pending_validation"
    assert "sha256" in res
    assert res["provider"] == "bhoonidhi"

    # Verify database persistence
    record = db_session.query(ExternalDataSource).filter(
        ExternalDataSource.item_id == "RS2_2026_001"
    ).first()
    assert record is not None
    assert record.collection_id == "RS2_LISS3"
    assert record.is_imported is True


def test_bhuvan_layers_and_thematic_statistics(db_session):
    """Verify Bhuvan allowlisted layers and AOI statistics provenance recording."""
    layers = bhuvan_provider.get_allowlisted_layers()
    layer_ids = {l["layer_identifier"] for l in layers}
    assert "bhuvan:lulc_50k" in layer_ids
    assert "bhuvan:flood_hazard" in layer_ids

    # Query statistics
    stats_res = bhuvan_provider.get_thematic_statistics(
        db=db_session,
        aoi_polygon={"type": "Polygon", "coordinates": [[[77.0, 12.8], [77.5, 12.8], [77.5, 13.3], [77.0, 13.3], [77.0, 12.8]]]},
        layer_identifier="bhuvan:lulc_50k"
    )
    assert "digest" in stats_res
    assert len(stats_res["statistics"]["classes"]) > 0

    # Verify context provenance record
    ctx = db_session.query(ExternalContextRecord).filter(
        ExternalContextRecord.id == stats_res["context_record_id"]
    ).first()
    assert ctx is not None
    assert ctx.provider == "bhuvan"
    assert ctx.service_name == "lulc_statistics"


def test_gpu_supervisor_vram_reserve_admission():
    """Verify ProcessSupervisor rejects GPU task when free VRAM is below GPU_MIN_FREE_MIB."""
    req = SubprocessRequest(
        protocol_version="1.0",
        job_id="job-sim-1",
        step_key="step-sim-1",
        attempt_id="1",
        model_version_id="model-1",
        task_type="vqa",
        output_dir="storage/test_sim"
    )


    # Mock low VRAM: 1024 MiB free (below 2048 MiB reserve)
    with patch.object(ProcessSupervisor, "get_gpu_memory_status", return_value={"free_mib": 1024, "total_mib": 8192}):
        resp = ProcessSupervisor.run_isolated_step(
            request=req,
            target_env="satquery-core",
            entrypoint_module="backend.runtime.internvl",
            requires_gpu=True,
            required_vram_mib=1000
        )
        assert resp.success is False
        assert resp.error_code == "GPU_MEMORY_RESERVE_INSUFFICIENT"
        assert "below required system reserve" in resp.error_message


def test_job_queue_capacity_backpressure(db_session):
    """Verify JobService raises CapacityExceededError when MAX_QUEUED_GPU_JOBS is exceeded."""
    # Seed active jobs up to MAX_QUEUED_GPU_JOBS (default 2)
    with patch.object(settings, "MAX_QUEUED_GPU_JOBS", 2):
        job1, _ = JobService.create_job(
            db=db_session,
            project_id="proj-1",
            task_type="vqa",
            canonical_request={"image": "img1.tif", "prompt": "test 1"},
            idempotency_key="key-1"
        )
        assert job1.status in ("queued", "waiting_for_resources")

        job2, _ = JobService.create_job(
            db=db_session,
            project_id="proj-1",
            task_type="vqa",
            canonical_request={"image": "img2.tif", "prompt": "test 2"},
            idempotency_key="key-2"
        )
        assert job2.status in ("queued", "waiting_for_resources")

        # Third job exceeds capacity of 2
        with pytest.raises(CapacityExceededError) as exc_info:
            JobService.create_job(
                db=db_session,
                project_id="proj-1",
                task_type="vqa",
                canonical_request={"image": "img3.tif", "prompt": "test 3"},
                idempotency_key="key-3"
            )
        assert "maximum capacity" in str(exc_info.value)
        assert exc_info.value.retry_after_seconds == 30
