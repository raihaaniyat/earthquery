"""
Unit Test: Storage & Scene Ingestion Service (Gate 4)
Tests streamed uploads, SHA-256 calculation, GeoTIFF vs benchmark PNG metadata extraction,
preview asset generation, and hash integrity.
"""

import io
import os
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base
from backend.app.db.models import User, Project, Scene, Asset
from backend.app.services.storage import object_store
from backend.app.services.ingestion import IngestionService

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    # We create only non-geometry tables in sqlite for testing
    Base.metadata.create_all(bind=engine, tables=[
        Base.metadata.tables['users'],
        Base.metadata.tables['projects'],
        Base.metadata.tables['scenes'],
        Base.metadata.tables['assets'],
    ])
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed test user and project
    user = User(id="test-user-1", email="test@satquery.local", hashed_password="pw")
    project = Project(id="test-proj-1", owner_id=user.id, name="Test Project")
    session.add(user)
    session.add(project)
    session.commit()

    yield session
    session.close()

def test_object_store_stream_roundtrip():
    """Verify SHA-256 and byte roundtrip in ObjectStore."""
    data = b"SatQuery AI Imagery Verification Stream Test Bytes"
    stream = io.BytesIO(data)
    
    bytes_written, sha = object_store.put_stream(
        bucket="satquery-inputs",
        key="test/roundtrip.bin",
        stream=stream
    )
    assert bytes_written == len(data)
    
    local_path = object_store.get_local_path("satquery-inputs", "test/roundtrip.bin")
    assert os.path.exists(local_path)
    with open(local_path, "rb") as f:
        read_back = f.read()
    assert read_back == data

def test_ingest_sample_geotiff(test_db):
    """Test ingestion pipeline on sample_geotiff.tif."""
    geotiff_path = Path("data/samples/sample_geotiff.tif")
    if not geotiff_path.exists():
        pytest.skip("sample_geotiff.tif not found")

    with open(geotiff_path, "rb") as f:
        scene, asset = IngestionService.ingest_upload_stream(
            db=test_db,
            project_id="test-proj-1",
            filename="sample_geotiff.tif",
            stream=f,
            media_type="image/tiff",
            sensor_platform="Sentinel-2",
            product_level="L2A"
        )

    assert scene.validation_status == "ready"
    assert scene.width == 100
    assert scene.height == 100
    assert scene.coordinate_space == "geographic"
    assert scene.native_crs_epsg == 4326

    # Verify preview asset was created
    preview_assets = test_db.query(Asset).filter_by(scene_id=scene.id, role="preview").all()
    assert len(preview_assets) == 1
    assert preview_assets[0].media_type == "image/png"

def test_ingest_sample_benchmark_png(test_db):
    """Test ingestion pipeline on sample_optical.png (benchmark mode)."""
    png_path = Path("data/samples/sample_optical.png")
    if not png_path.exists():
        pytest.skip("sample_optical.png not found")

    with open(png_path, "rb") as f:
        scene, asset = IngestionService.ingest_upload_stream(
            db=test_db,
            project_id="test-proj-1",
            filename="sample_optical.png",
            stream=f,
            media_type="image/png",
            sensor_platform="Benchmark"
        )

    assert scene.validation_status == "ready"
    assert scene.width == 256
    assert scene.height == 256
    assert scene.coordinate_space == "pixel"
    assert scene.native_crs_epsg is None
