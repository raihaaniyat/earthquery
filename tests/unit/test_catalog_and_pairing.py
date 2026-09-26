"""
Unit tests for Scene Catalog Search and Scene Pairing Services.
Verifies project scoping, spatial exclusion of pixel benchmarks, temporal ordering,
and multimodal pairing policies.
"""

import pytest
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base
from backend.app.db.models import User, Project, Scene, Asset, ScenePair
from backend.app.services.catalog import SceneCatalogService
from backend.app.services.pairing import PairValidationService


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed test project and user
    user = User(id="user-1", email="test@satquery.local", hashed_password="pw")
    project = Project(id="proj-1", owner_id="user-1", name="Test Project")
    session.add_all([user, project])
    session.commit()

    yield session
    session.close()


def test_catalog_search_filters_and_excludes_pixel_benchmarks(db_session):
    # Scene 1: Geographic Sentinel-2
    s1 = Scene(
        id="s1",
        project_id="proj-1",
        name="Sentinel2_Scene.tif",
        sensor_platform="Sentinel-2",
        coordinate_space="geographic",
        width=512,
        height=512,
        validation_status="ready",
        acquisition_time=datetime(2026, 1, 15, tzinfo=timezone.utc),
        native_crs_wkt="GEOGCS[\"WGS 84\",...]"
    )
    # Scene 2: Benchmark Pixel Scene
    s2 = Scene(
        id="s2",
        project_id="proj-1",
        name="Benchmark_Sample.png",
        sensor_platform="Benchmark",
        coordinate_space="pixel",
        width=256,
        height=256,
        validation_status="ready",
        acquisition_time=None
    )
    db_session.add_all([s1, s2])
    db_session.commit()

    # Geographic search must strictly return only s1
    geo_results = SceneCatalogService.search_scenes(
        db=db_session,
        project_id="proj-1",
        coordinate_space="geographic"
    )
    assert len(geo_results) == 1
    assert geo_results[0].id == "s1"

    # Pixel search returns s2
    pixel_results = SceneCatalogService.search_scenes(
        db=db_session,
        project_id="proj-1",
        coordinate_space="pixel"
    )
    assert len(pixel_results) == 1
    assert pixel_results[0].id == "s2"


def test_stac_export_rejects_pixel_scene(db_session):
    pixel_scene = Scene(
        id="s_pixel",
        project_id="proj-1",
        name="Pixel.png",
        coordinate_space="pixel",
        width=256,
        height=256,
        validation_status="ready"
    )
    db_session.add(pixel_scene)
    db_session.commit()

    with pytest.raises(ValueError, match="Non-geographic or benchmark pixel scenes cannot be exported"):
        SceneCatalogService.export_stac_item(pixel_scene)


def test_bitemporal_pairing_temporal_inversion(db_session):
    t_after = datetime(2026, 3, 1, tzinfo=timezone.utc)
    t_before = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # Inverted: Scene A is AFTER Scene B
    s_a = Scene(id="sa", project_id="proj-1", name="Post.tif", width=256, height=256, acquisition_time=t_after)
    s_b = Scene(id="sb", project_id="proj-1", name="Pre.tif", width=256, height=256, acquisition_time=t_before)
    a_a = Asset(id="aa", project_id="proj-1", scene_id="sa", role="original", bucket="b", storage_key="k1", sha256_hash="h1", byte_size=10, media_type="image/tiff")
    a_b = Asset(id="ab", project_id="proj-1", scene_id="sb", role="original", bucket="b", storage_key="k2", sha256_hash="h2", byte_size=10, media_type="image/tiff")

    db_session.add_all([s_a, s_b, a_a, a_b])
    db_session.commit()

    pair = PairValidationService.validate_bitemporal_optical_pair(
        db=db_session,
        project_id="proj-1",
        scene_a=s_a,
        scene_b=s_b,
        asset_a=a_a,
        asset_b=a_b
    )

    assert pair.status == "rejected"
    assert "Temporal inversion" in pair.rejection_reason


def test_optical_sar_pairing_blocks_unsupported_sensors(db_session):
    opt = Scene(id="s_opt", project_id="proj-1", name="S2.tif", sensor_platform="Sentinel-2", width=120, height=120)
    sar_unsupported = Scene(id="s_risat", project_id="proj-1", name="RISAT.tif", sensor_platform="RISAT-1", width=120, height=120)

    a_opt = Asset(id="a_opt", project_id="proj-1", scene_id="s_opt", role="original", bucket="b", storage_key="k3", sha256_hash="h3", byte_size=10, media_type="image/tiff")
    a_sar = Asset(id="a_sar", project_id="proj-1", scene_id="s_risat", role="original", bucket="b", storage_key="k4", sha256_hash="h4", byte_size=10, media_type="image/tiff")

    db_session.add_all([opt, sar_unsupported, a_opt, a_sar])
    db_session.commit()

    pair = PairValidationService.validate_optical_sar_pair(
        db=db_session,
        project_id="proj-1",
        optical_scene=opt,
        sar_scene=sar_unsupported,
        optical_asset=a_opt,
        sar_asset=a_sar
    )

    assert pair.status == "rejected"
    assert "RISAT-1" in pair.rejection_reason or "not supported" in pair.rejection_reason
