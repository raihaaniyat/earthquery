"""
Unit and integration tests for SatQuery AI Scientific Routing and Raster Measurements.
Validates:
1. Geodesic and metric area computation.
2. Synthetic spectral index and bitemporal metric calculations.
3. Input Sifter SceneManifest generation.
4. User intent parsing and deterministic route decisions.
5. EvidenceBundle structure and 3-section formatting (Raster Facts, Model Candidate, Review).
6. Fast Route Preview API endpoint (/api/route-preview).
"""

import os
import io
import tempfile
import numpy as np
import pytest
from PIL import Image
from fastapi.testclient import TestClient

import rasterio
from rasterio.transform import from_origin

from backend.app.main import app
from backend.app.schemas.manifests import (
    SceneManifest,
    PairManifest,
    TaskRequest,
    RouteDecision,
    ScientificMeasurement,
    EvidenceBundle,
)
from backend.app.services.raster_measurements import (
    compute_geodesic_area_km2,
    extract_geotiff_facts,
    compute_spectral_index,
    compute_bitemporal_metrics,
    build_evidence_bundle,
    format_scientific_sections,
)
from backend.app.services.routing import (
    create_scene_manifest,
    create_pair_manifest,
    parse_user_intent,
    decide_route,
)

client = TestClient(app)


def test_compute_geodesic_area_km2():
    # 1. Projected UTM CRS: 1000m x 1000m = 1 km2
    utm_bounds = (500000.0, 4649000.0, 501000.0, 4650000.0)
    utm_area = compute_geodesic_area_km2(utm_bounds, crs_str="EPSG:32632 (UTM zone 32N)")
    assert pytest.approx(utm_area, rel=1e-3) == 1.0

    # 2. Geographic WGS84 CRS: ~0.01 deg square near equator
    geo_bounds = (10.0, 0.0, 10.01, 0.01)
    geo_area = compute_geodesic_area_km2(geo_bounds, crs_str="EPSG:4326")
    # 0.01 deg at equator is ~1.113 km -> Area ~ 1.23 km2
    assert 1.0 < geo_area < 1.5

    # 3. Invalid or zero bounds
    zero_area = compute_geodesic_area_km2((0, 0, 0, 0), crs_str="EPSG:4326")
    assert zero_area == 0.0


def test_compute_spectral_index_on_geotiff():
    with tempfile.NamedTemporaryFile(suffix=".tif", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Create a synthetic 4-band GeoTIFF (B1=B, B2=G, B3=R, B4=NIR)
        transform = from_origin(500000.0, 4650000.0, 10.0, 10.0)
        data = np.zeros((4, 100, 100), dtype=np.float32)
        # Red low, NIR high -> vegetation
        data[2, :50, :] = 200.0   # Red
        data[3, :50, :] = 1800.0  # NIR
        # Red high, NIR low -> bare ground/water
        data[2, 50:, :] = 1200.0  # Red
        data[3, 50:, :] = 400.0   # NIR

        with rasterio.open(
            tmp_path,
            "w",
            driver="GTiff",
            height=100,
            width=100,
            count=4,
            dtype=np.float32,
            crs="EPSG:32632",
            transform=transform,
        ) as dst:
            dst.write(data)

        # Compute NDVI
        res = compute_spectral_index(tmp_path, index_type="ndvi")
        assert "index_type" in res
        assert res["index_type"] == "NDVI"
        assert "mean" in res
        assert "histogram" in res
        assert len(res["histogram"]) == 10
        assert res["threshold_exceed_pct"] > 40.0
        assert res["exceed_area_km2"] is not None
        assert res["exceed_area_km2"] > 0.0
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_compute_bitemporal_metrics_on_geotiffs():
    with tempfile.NamedTemporaryFile(suffix="_t1.tif", delete=False) as tmp1, \
         tempfile.NamedTemporaryFile(suffix="_t2.tif", delete=False) as tmp2:
        p1 = tmp1.name
        p2 = tmp2.name

    try:
        transform = from_origin(500000.0, 4650000.0, 10.0, 10.0)
        t1_arr = np.ones((1, 50, 50), dtype=np.float32) * 100.0
        t2_arr = np.ones((1, 50, 50), dtype=np.float32) * 100.0
        # Add change in top half
        t2_arr[0, :25, :] = 500.0

        for path, arr in [(p1, t1_arr), (p2, t2_arr)]:
            with rasterio.open(
                path,
                "w",
                driver="GTiff",
                height=50,
                width=50,
                count=1,
                dtype=np.float32,
                crs="EPSG:32632",
                transform=transform,
            ) as dst:
                dst.write(arr)

        res = compute_bitemporal_metrics(p1, p2, threshold=0.1)
        assert res["status"] == "computed"
        assert res["mean_signed_diff"] > 0
        assert res["changed_pixels"] > 0
        assert res["change_pct"] > 40.0
    finally:
        for p in (p1, p2):
            if os.path.exists(p):
                os.remove(p)


def test_create_scene_manifest_png():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img = Image.new("RGB", (64, 64), color="forestgreen")
        img.save(tmp.name)
        tmp_path = tmp.name

    try:
        manifest = create_scene_manifest(tmp_path, scene_id="test_scene_01")
        assert manifest.scene_id == "test_scene_01"
        assert manifest.format == "png"
        assert manifest.width == 64
        assert manifest.height == 64
        assert len(manifest.bands_or_polarizations) == 3
        assert manifest.sha256 != ""
        assert manifest.modality == "benchmark_pixel"
        assert manifest.georeferencing_mode == "pixel_only"
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def test_parse_user_intent():
    dummy_m = SceneManifest(
        scene_id="s1",
        sha256="abc",
        source="local_upload",
        format="geotiff",
        sensor="Sentinel-2",
        modality="optical",
        width=512,
        height=512,
        bands_or_polarizations=["B2", "B3", "B4", "B8"],
    )
    req1 = parse_user_intent("Calculate NDVI and vegetation health", [dummy_m])
    assert req1.intent == "spectral_index"

    dummy_pair = create_pair_manifest(dummy_m, dummy_m)
    req2 = parse_user_intent("Compare 2024 and 2026 imagery for urban change", [dummy_m, dummy_m], pair=dummy_pair)
    assert req2.intent == "change_detection"

    req3 = parse_user_intent("Detect and locate storage tanks and solar panels", [dummy_m])
    assert req3.intent == "visual_grounding"

    req4 = parse_user_intent("Describe the terrain, water bodies, and roads", [dummy_m])
    assert req4.intent == "scene_description"


def test_decide_route_single_scene():
    manifest = SceneManifest(
        scene_id="s1",
        sha256="abc",
        source="local_upload",
        format="png",
        sensor="Benchmark",
        modality="benchmark_pixel",
        width=512,
        height=512,
        bands_or_polarizations=["R", "G", "B"],
        georeferencing_mode="pixel_only",
    )
    task_req = TaskRequest(
        user_question="Describe this scene",
        intent="scene_description",
        scene_ids=["s1"],
    )
    decision = decide_route([manifest], None, task_req)
    assert decision.selected_adapter_or_none in ("internvl3", "internvl")
    assert decision.automatic_route is True
    assert len(decision.decision_reason) > 0
    assert "InternVL3" in decision.decision_reason


def test_evidence_bundle_and_three_sections():
    facts = {
        "file_name": "sentinel2_sample.tif",
        "crs": "EPSG:32632",
        "footprint_km2": 45.2,
        "resolution_m": 10.0,
        "is_georeferenced": True,
        "radiometry": {"mean": 1150.0, "min": 120.0, "max": 8500.0},
        "valid_pixel_pct": 99.8,
    }
    measurements = [
        {
            "index_type": "NDVI",
            "mean": 0.68,
            "min": -0.12,
            "max": 0.89,
            "threshold_exceed_pct": 65.4,
            "exceed_area_km2": 29.56,
            "units": "ratio (-1 to 1)",
            "limitations": ["Atmospheric correction not validated against ground AERONET stations."],
        }
    ]

    bundle = build_evidence_bundle(facts, measurements, limitations=["Sensor nadir view geometry only."])
    sections = format_scientific_sections(
        bundle,
        model_narrative="VLM observed extensive agricultural parcels and irrigation corridors.",
        model_name="InternVL3-2B"
    )

    assert "measured_from_raster" in sections
    assert "model_candidate" in sections
    assert "interpretation_requiring_review" in sections

    # Check 1. Measured from raster
    assert any("Footprint: 45.2 km²" in m for m in sections["measured_from_raster"])
    assert any("Mean NDVI: 0.68" in m for m in sections["measured_from_raster"])

    # Check 2. Model candidate
    assert sections["model_candidate"]["model"] == "InternVL3-2B"
    assert "agricultural parcels" in sections["model_candidate"]["observation"]

    # Check 3. Interpretation requiring review
    assert any("AERONET" in lim or "nadir" in lim for lim in sections["interpretation_requiring_review"])


def test_route_preview_api_endpoint():
    # Test preview with synthetic image file upload
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        img = Image.new("RGB", (64, 64), color="darkblue")
        img.save(tmp.name)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as f:
            files = {"file": ("test_ocean.png", f, "image/png")}
            data = {"prompt": "Describe this scene and identify features"}
            resp = client.post("/api/route-preview", files=files, data=data)

        assert resp.status_code == 200
        preview = resp.json()
        assert "selected_task" in preview
        assert "input_type" in preview
        assert "automatic_route" in preview
        assert "available" in preview
        assert "decision_reason" in preview
        assert preview["automatic_route"] is True
        assert preview["available"] is True
        assert preview["model"] in ("internvl3", "internvl")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
