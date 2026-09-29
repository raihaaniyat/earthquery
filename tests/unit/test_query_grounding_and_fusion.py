"""
Unit tests for Query Grounding, Temporal Object Matching, Vegetation Loss,
Optical/SAR Fusion, and Intelligent Model Selection in SatQuery AI.
"""

import os
import pytest
import numpy as np
from PIL import Image

from backend.app.schemas.manifests import SceneManifest, TaskRequest, AnalysisPlan
from backend.app.services.routing import parse_user_intent, decide_route, create_scene_manifest
from backend.app.services.raster_measurements import (
    align_spatial_pair,
    compute_temporal_object_matching,
    compute_temporal_vegetation_change,
    compute_optical_sar_fusion
)
from backend.app.services.multi_model_pipeline import run_multi_model_pipeline


@pytest.fixture
def sample_test_rasters(tmp_path):
    """Generates two simple test images for temporal & multimodal testing."""
    p1 = tmp_path / "obs_t1.png"
    p2 = tmp_path / "obs_t2.png"
    sar_p = tmp_path / "sar_obs.png"

    # Observation 1: baseline with green vegetation and natural variation
    np.random.seed(42)
    arr1 = np.zeros((100, 100, 3), dtype=np.uint8)
    arr1[:, :, 1] = 180  # green channel
    arr1[:, :, 0] = 50   # red channel
    arr1 = np.clip(arr1.astype(np.int16) + np.random.randint(-20, 20, size=arr1.shape), 0, 255).astype(np.uint8)
    Image.fromarray(arr1).save(str(p1))

    # Observation 2: vegetation cleared in top half (reduced green, increased red)
    arr2 = arr1.copy()
    arr2[:50, :, 1] = 60
    arr2[:50, :, 0] = 140
    Image.fromarray(arr2).save(str(p2))

    # SAR observation: dark water in corner
    arr_sar = np.ones((100, 100), dtype=np.uint8) * 128
    arr_sar[:30, :30] = 10  # low backscatter specular water
    arr_sar = np.clip(arr_sar.astype(np.int16) + np.random.randint(-15, 15, size=arr_sar.shape), 0, 255).astype(np.uint8)
    Image.fromarray(arr_sar).save(str(sar_p))

    return str(p1), str(p2), str(sar_p)


def test_query_grounded_intent_routing():
    """Verify that specific queries map to appropriate minimum-model AnalysisPlans."""
    # 1. Raster metadata query -> 0 GPU models
    req_meta = parse_user_intent("What is the area of the uploaded raster?", manifests=[])
    assert req_meta.intent == "raster_metadata"
    assert req_meta.analysis_plan is not None
    assert req_meta.analysis_plan.required_models == []

    # 2. Object detection query -> OWLv2 only
    req_obj = parse_user_intent("How many buildings are present in this image?", manifests=[])
    assert req_obj.intent == "visual_grounding"
    assert req_obj.analysis_plan.required_models == ["owlv2"]

    # 3. Land cover query -> UPerNet only
    req_seg = parse_user_intent("Identify vegetation, water and built-up areas.", manifests=[])
    assert req_seg.intent == "classification"
    assert req_seg.analysis_plan.required_models == ["upernet"]

    # 4. Temporal building change query -> OWLv2 + spatial matching
    dummy_m = [SceneManifest(scene_id="s1", sha256="1"), SceneManifest(scene_id="s2", sha256="2")]
    req_temp_bldg = parse_user_intent("How many new buildings appeared between the two images?", manifests=dummy_m)
    assert req_temp_bldg.intent == "temporal_building_change"
    assert req_temp_bldg.analysis_plan.required_models == ["owlv2"]
    assert "spatial_object_matching" in req_temp_bldg.analysis_plan.operations

    # 5. Temporal vegetation loss query -> deterministic vegetation delta (0 GPU models)
    req_temp_veg = parse_user_intent("How much vegetation was lost between the two dates?", manifests=dummy_m)
    assert req_temp_veg.intent == "temporal_vegetation_loss"
    assert req_temp_veg.analysis_plan.required_models == []


def test_temporal_object_matching_logic():
    """
    Verify spatial object matching adheres strictly to Section 13 & 14:
    An unchanged object present in T1 and T2 is NOT counted as new!
    """
    # T1 detections: 2 buildings
    t1_preds = [
        {"label": "building", "box": [10, 10, 30, 30], "score": 0.90},  # will match in T2
        {"label": "building", "box": [50, 50, 70, 70], "score": 0.88},  # disappeared in T2
    ]

    # T2 detections: 2 buildings (one at identical location as T1, one newly constructed)
    t2_preds = [
        {"label": "building", "box": [11, 10, 31, 30], "score": 0.92},  # matches T1 (unchanged)
        {"label": "building", "box": [80, 80, 95, 95], "score": 0.85},  # brand new
    ]

    result = compute_temporal_object_matching(t1_preds, t2_preds, iou_threshold=0.25)

    assert result["unchanged_count"] == 1
    assert result["new_count"] == 1
    assert result["disappeared_count"] == 1
    # Verify the unchanged building wasn't counted as new
    assert result["newly_appeared"][0]["box"] == [80, 80, 95, 95]


def test_temporal_vegetation_change(sample_test_rasters):
    """Verify comparative vegetation loss computes percentage and primary spatial sector."""
    p1, p2, _ = sample_test_rasters
    res = compute_temporal_vegetation_change(p1, p2)

    assert res["status"] == "computed"
    assert res["loss_pct_of_baseline"] > 0
    assert res["primary_loss_sector"] == "northern"


def test_optical_sar_fusion(sample_test_rasters):
    """Verify Optical + SAR fusion cross-modal consensus and mask asset generation."""
    p1, _, sar_p = sample_test_rasters
    res = compute_optical_sar_fusion(p1, sar_p, query_focus="flood")

    assert res["focus"] == "flood"
    assert "fused_flood_pct" in res
    assert "Joint Optical-SAR" in res["fusion_method"]
    assert "mask_path" in res
    assert res["mask_path"] is not None
    assert os.path.exists(res["mask_path"])


def test_multi_model_pipeline_direct_answer_structure(sample_test_rasters):
    """Verify that multi_model_pipeline produces unified direct answers without generic dumps."""
    p1, p2, _ = sample_test_rasters

    # Run temporal vegetation loss query
    res = run_multi_model_pipeline(
        file_paths=[p1, p2],
        prompt="How much vegetation was lost between the two dates?",
        pair_type="bitemporal"
    )

    summary = res["summary"]
    # Verify direct answer is present without generic dumps
    assert "vegetation" in summary.lower()
    assert "loss" in summary.lower()
    # Verify it does NOT contain the 10 generic irrelevant headings
    assert "## Image / Scene Type" not in summary
    assert "## What Is Present in the Image" not in summary


def test_optical_sar_multimodal_pipeline(sample_test_rasters):
    """Verify Optical-SAR fusion execution in multi_model_pipeline with mask output asset."""
    p1, _, sar_p = sample_test_rasters

    res = run_multi_model_pipeline(
        file_paths=[sar_p, p1],
        prompt="Perform optical-sar fusion to verify inundation and flood extent.",
        pair_type="optical_sar",
        user_intent="optical_sar_flood"
    )

    assert res["status"] == "COMPLETED"
    assert "output_assets" in res
    assert "fusion_mask" in res["output_assets"]
    assert os.path.exists(res["output_assets"]["fusion_mask"])
    assert any("Optical-SAR" in f.get("label", "") or "Flood" in f.get("label", "") for f in res.get("findings", []))
    assert "flood" in res["summary"].lower() or "inundation" in res["summary"].lower()
