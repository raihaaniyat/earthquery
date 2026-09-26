"""
Integration tests for SatQuery AI REST API v1.
Tests health probes, project creation, capability matrix, scene upload,
job submission (202 Accepted), and model versions.
"""

import io
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.main import app
from backend.app.db.session import Base, get_db
from sqlalchemy.pool import StaticPool
from backend.app.db.models import User, Project
from backend.app.auth import DEFAULT_DEV_TOKEN, hash_token

# Test in-memory database using StaticPool to share state across threads
test_engine = create_engine(
    "sqlite:///:memory:",
    echo=False,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
Base.metadata.create_all(bind=test_engine)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    db = TestingSessionLocal()
    # Clean tables between tests while keeping schema
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(table.delete())
    db.commit()

    user = User(
        id="dev-user-id",
        email="developer@satquery.local",
        hashed_password=hash_token("dev-pw"),
        is_active=True,
        is_admin=True
    )
    db.add(user)
    db.commit()
    db.close()



def test_health_live_endpoint():
    resp = client.get("/health/live")
    assert resp.status_code == 200
    assert resp.json() == {"status": "live"}


def test_capabilities_endpoint():
    resp = client.get("/api/v1/capabilities")
    assert resp.status_code == 200
    data = resp.json()
    assert "capabilities" in data
    assert "internvl3" in data["capabilities"]
    assert "croma" in data["capabilities"]
    assert "changeformer" in data["capabilities"]
    assert data["capabilities"]["internvl3"]["is_runnable"] is True
    assert data["capabilities"]["geoground"]["is_runnable"] is True


def test_projects_lifecycle():
    # 1. Create project
    create_resp = client.post(
        "/api/v1/projects",
        json={"name": "Delta Monitoring 2026", "description": "Coastal wetland observation"}
    )
    assert create_resp.status_code == 201
    proj_data = create_resp.json()
    assert proj_data["name"] == "Delta Monitoring 2026"
    proj_id = proj_data["id"]

    # 2. List projects
    list_resp = client.get("/api/v1/projects")
    assert list_resp.status_code == 200
    projects = list_resp.json()
    assert len(projects) >= 1
    assert any(p["id"] == proj_id for p in projects)


def test_scene_upload_and_search():
    # Create project first
    p_resp = client.post("/api/v1/projects", json={"name": "Scene Test Project"})
    proj_id = p_resp.json()["id"]

    # Upload test image
    fake_png = io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82")
    files = {"file": ("test_sample.png", fake_png, "image/png")}
    data = {"sensor_platform": "Benchmark"}

    upload_resp = client.post(f"/api/v1/projects/{proj_id}/scenes", files=files, data=data)
    assert upload_resp.status_code == 201
    scene_info = upload_resp.json()
    assert "scene_id" in scene_info
    assert scene_info["filename"] == "test_sample.png"

    # Search scenes
    search_resp = client.get(f"/api/v1/projects/{proj_id}/scenes?coordinate_space=pixel")
    assert search_resp.status_code == 200
    results = search_resp.json()
    assert len(results) >= 1
    assert results[0]["id"] == scene_info["scene_id"]


def test_job_submission_and_status():
    p_resp = client.post("/api/v1/projects", json={"name": "Job Test Project"})
    proj_id = p_resp.json()["id"]

    submit_payload = {
        "project_id": proj_id,
        "task_type": "vqa",
        "canonical_request": {"prompt": "Describe scene"},
        "user_request_text": "What do you see?",
        "idempotency_key": "job-test-key-1"
    }

    # Submit job (expects 202 Accepted)
    sub_resp = client.post("/api/v1/analysis-jobs", json=submit_payload)
    assert sub_resp.status_code == 202
    job_info = sub_resp.json()
    assert job_info["status"] == "queued"
    job_id = job_info["job_id"]

    # Poll status
    status_resp = client.get(f"/api/v1/analysis-jobs/{job_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["id"] == job_id
    assert status_resp.json()["task_type"] == "vqa"

    # Cancel job
    cancel_resp = client.post(f"/api/v1/analysis-jobs/{job_id}/cancel")
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == "cancelled"


def test_model_versions_endpoint():
    resp = client.get("/api/v1/model-versions")
    assert resp.status_code == 200
    models = resp.json()
    assert len(models) >= 4
    model_ids = [m["id"] for m in models]
    assert "internvl3" in model_ids
    assert "changeformer" in model_ids


def test_auth_session_endpoints():
    # Attempt invalid token
    bad_resp = client.post("/api/v1/auth/session", json={"token": "invalid_token"})
    assert bad_resp.status_code == 401

    # Revoke session
    del_resp = client.delete("/api/v1/auth/session")
    assert del_resp.status_code == 204


def test_external_providers_endpoints():
    # 1. Provider status
    p_resp = client.get("/api/v1/external/providers")
    assert p_resp.status_code == 200
    data = p_resp.json()
    assert len(data["providers"]) == 2
    prov_ids = {p["id"] for p in data["providers"]}
    assert "bhoonidhi" in prov_ids
    assert "bhuvan" in prov_ids

    # 2. BHOONIDHI Collections
    col_resp = client.get("/api/v1/external/bhoonidhi/collections")
    assert col_resp.status_code == 200
    assert len(col_resp.json()["collections"]) >= 4

    # 3. BHOONIDHI Search
    search_resp = client.post("/api/v1/external/bhoonidhi/search", json={
        "collections": ["RS2_LISS3"],
        "bbox": [77.0, 12.8, 77.5, 13.3],
        "limit": 3
    })
    assert search_resp.status_code == 200
    stac_res = search_resp.json()
    assert stac_res["type"] == "FeatureCollection"
    assert len(stac_res["features"]) > 0

    # 4. Bhuvan Layers
    layers_resp = client.get("/api/v1/external/bhuvan/layers")
    assert layers_resp.status_code == 200
    assert len(layers_resp.json()["layers"]) >= 3

