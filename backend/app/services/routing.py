"""
Centralized Scientific Routing Service for SatQuery AI.
Deterministic decision engine matching validated SceneManifests and user scientific intent
against model capabilities, sensor contracts, and resource constraints.
The user chooses a question or desired outcome, not a model.
"""

import os
from typing import Dict, Any, Optional, List
from pathlib import Path

from backend.app.schemas.manifests import (
    SceneManifest,
    PairManifest,
    TaskRequest,
    RouteDecision
)
from backend.app.models_registry import REGISTRY, ModelStatus


def create_scene_manifest(file_path: str, scene_id: Optional[str] = None) -> SceneManifest:
    """
    Input Sifter: inspects actual file content, sensor metadata, bands, CRS,
    transform, nodata, and dimensions to produce an immutable typed SceneManifest.
    """
    import hashlib
    from backend.app.services.raster_measurements import extract_geotiff_facts

    path_obj = Path(file_path)
    ext = path_obj.suffix.lower()
    sid = scene_id or path_obj.stem

    # Compute SHA-256
    sha256_hash = ""
    if os.path.exists(file_path):
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                hasher.update(chunk)
        sha256_hash = hasher.hexdigest()

    is_tif = ext in (".tif", ".tiff")
    format_name = "geotiff" if is_tif else ("png" if ext == ".png" else ("jpeg" if ext in (".jpg", ".jpeg") else "unknown"))

    # Extract raster facts
    facts = extract_geotiff_facts(file_path) if is_tif else {}

    # Detect modality & sensor
    if is_tif and facts.get("is_georeferenced"):
        modality = "sar" if "SAR" in facts.get("sensor_inferred", "") else "optical"
        sensor = facts.get("sensor_inferred", "Unknown Satellite")
        georeferencing = "projected" if "UTM" in str(facts.get("crs", "")) else "geographic"
    elif is_tif:
        modality = "optical"
        sensor = "Unreferenced TIFF"
        georeferencing = "unreferenced"
    else:
        # Standard JPG/PNG benchmark
        modality = "benchmark_pixel"
        sensor = "Benchmark Image"
        georeferencing = "pixel_only"
        if os.path.exists(file_path):
            try:
                from PIL import Image
                with Image.open(file_path) as im:
                    facts["width"] = im.width
                    facts["height"] = im.height
                    facts["bands"] = len(im.getbands())
            except Exception:
                pass

    limitations = list(facts.get("limitations", []))
    if georeferencing == "pixel_only":
        limitations.append("Pixel-coordinate space only. Real-world CRS, geographic coordinates and physical area in km² cannot be asserted.")
    elif georeferencing == "unreferenced":
        limitations.append("GeoTIFF lacks genuine CRS or geotransform. Operating in pixel coordinates.")

    bands = []
    band_count = facts.get("bands", 3 if not is_tif else 0)
    if modality == "sar":
        bands = ["VV", "VH"] if band_count >= 2 else ["VV"]
    elif band_count >= 4:
        bands = ["B02_Blue", "B03_Green", "B04_Red", "B08_NIR"]
    elif band_count == 3:
        bands = ["Red", "Green", "Blue"]
    elif band_count == 1:
        bands = ["Single_Band"]

    return SceneManifest(
        scene_id=sid,
        sha256=sha256_hash,
        source="local_upload",
        format=format_name,
        sensor=sensor,
        product_level="L2A" if "Sentinel-2" in sensor else ("GRD" if "Sentinel-1" in sensor else None),
        modality=modality,
        footprint_or_null={"type": "Polygon", "coordinates": [[
            [facts["bounds"][0], facts["bounds"][1]],
            [facts["bounds"][2], facts["bounds"][1]],
            [facts["bounds"][2], facts["bounds"][3]],
            [facts["bounds"][0], facts["bounds"][3]],
            [facts["bounds"][0], facts["bounds"][1]]
        ]]} if facts.get("bounds") else None,
        crs_or_null=facts.get("crs"),
        affine_or_null=None,
        width=facts.get("width", 0),
        height=facts.get("height", 0),
        resolution_or_null=facts.get("resolution_m"),
        pixel_unit="metre" if georeferencing == "projected" else ("degree" if georeferencing == "geographic" else "pixel"),
        bands_or_polarizations=bands,
        scale_offset=None,
        nodata=facts.get("nodata"),
        quality_mask=None,
        georeferencing_mode=georeferencing,
        processing_history=["input_sifter_validation"],
        limitations=limitations
    )


def create_pair_manifest(manifest_a: SceneManifest, manifest_b: SceneManifest) -> PairManifest:
    """
    Validates paired relationship between two scenes:
    - Bitemporal optical change (same modality, temporal difference)
    - Optical + SAR multimodal pair
    """
    quality_flags = []

    # Check modality combination
    if manifest_a.modality == "optical" and manifest_b.modality == "sar":
        purpose = "optical_sar"
    elif manifest_a.modality == "sar" and manifest_b.modality == "optical":
        purpose = "optical_sar"
    else:
        purpose = "temporal"

    # Check spatial overlap
    overlap_fraction = 1.0
    if manifest_a.georeferencing_mode != "pixel_only" and manifest_b.georeferencing_mode != "pixel_only":
        if manifest_a.crs_or_null != manifest_b.crs_or_null:
            quality_flags.append(f"Mismatched CRS: {manifest_a.crs_or_null} vs {manifest_b.crs_or_null}. On-the-fly reprojection required.")
    else:
        quality_flags.append("Pixel-coordinate imagery. Registration verified only if dimensions match.")
        if (manifest_a.width, manifest_a.height) != (manifest_b.width, manifest_b.height):
            quality_flags.append("Dimension mismatch in pixel-space pair.")
            overlap_fraction = 0.8

    return PairManifest(
        purpose=purpose,
        ordered_scene_ids=[manifest_a.scene_id, manifest_b.scene_id],
        acquisition_gap=None,
        overlap_fraction=overlap_fraction,
        common_crs_and_grid={"crs": manifest_a.crs_or_null or "pixel_space"},
        alignment_error_or_unknown=None,
        resampling_method="bilinear",
        quality_flags=quality_flags
    )


def parse_user_intent(
    query: str,
    manifests: List[SceneManifest],
    pair: Optional[PairManifest] = None,
    diagnostic_override: Optional[str] = None
) -> TaskRequest:
    """
    Parses user scientific intent from query keywords and input modalities.
    """
    q_lower = query.lower().strip()
    scene_ids = [m.scene_id for m in manifests]

    intent = "scene_description"
    requested_measurements = []
    output_type = "narrative"

    # Spectral indices intent
    if any(k in q_lower for k in ["ndvi", "vegetation index", "ndwi", "water index", "greenness", "spectral"]):
        intent = "spectral_index"
        requested_measurements = ["ndvi"]
        output_type = "metrics"

    # Change detection intent
    elif any(k in q_lower for k in ["change", "difference", "compare", "deforestation", "construction", "disaster"]) and (pair or len(manifests) >= 2):
        intent = "change_detection"
        requested_measurements = ["bitemporal_difference", "changed_area_km2"]
        output_type = "mask"

    # General scene description / visual questioning (takes precedence over generic 'find' words)
    elif any(k in q_lower for k in ["what is", "image type", "what does", "what have", "what are", "describe", "explain", "scene type"]):
        intent = "scene_description"
        output_type = "narrative"

    # Visual grounding intent (explicit object localization)
    elif any(k in q_lower for k in ["locate", "detect", "ground", "where are", "count", "bounding box", "owlv2", "owl", "geoground"]) or (
        "find" in q_lower and any(obj in q_lower for obj in ["building", "vehicle", "ship", "car", "plane", "aircraft", "structure", "road"])
    ):
        intent = "visual_grounding"
        output_type = "mask"

    # Classification / segmentation intent
    elif any(k in q_lower for k in ["classify", "land cover", "segment", "segmentation", "classes"]):
        intent = "classification"
        output_type = "mask"

    # Optical + SAR fusion intent
    elif pair and pair.purpose == "optical_sar":
        intent = "optical_sar_fusion"
        requested_measurements = ["multimodal_features"]

    return TaskRequest(
        user_question=query,
        intent=intent,
        scene_ids=scene_ids,
        requested_output=output_type,
        requested_measurements=requested_measurements,
        diagnostic_model_override=diagnostic_override
    )


def decide_route(
    manifests: List[SceneManifest],
    pair: Optional[PairManifest],
    task_req: TaskRequest,
    capabilities: Optional[Dict[str, Any]] = None
) -> RouteDecision:
    """
    Deterministic routing engine:
    Matches validated input contracts and intent to model capabilities.
    Enforces scientific gates (e.g. no area claims for pixel-only benchmarks,
    no unsupported model dispatch).
    """
    intent = task_req.intent
    override = task_req.diagnostic_model_override
    blocked_reasons: List[str] = []
    fallback_measurements: List[str] = []
    validation_checks: Dict[str, Any] = {}

    # Diagnostic override branch
    if override:
        desc = REGISTRY.get(override.lower())
        if desc and desc.status != ModelStatus.INSTALLED_NOT_RUNNABLE_LOCALLY:
            return RouteDecision(
                task=intent,
                selected_adapter_or_none=override.lower(),
                preprocessing_profile="diagnostic_override",
                validation_checks={"diagnostic_override": True, "model": override},
                blocked_reasons=[],
                fallback_measurements=[],
                capabilities_version="2.0.0",
                model_version=override,
                estimated_resources={"vram_mb": 4096},
                automatic_route=False,
                decision_reason=f"Diagnostic model override requested: {override}"
            )

    # 1. Deterministic Spectral Index Route (No GPU model required)
    if intent == "spectral_index":
        if not manifests:
            blocked_reasons.append("No scene provided for spectral index computation.")
        elif manifests[0].modality == "benchmark_pixel" and len(manifests[0].bands_or_polarizations) < 3:
            blocked_reasons.append("Single-band pixel benchmark cannot calculate multi-band spectral indices.")
        else:
            return RouteDecision(
                task="spectral_index",
                selected_adapter_or_none=None,  # Pure deterministic raster calculation
                preprocessing_profile="spectral_calculation",
                validation_checks={"bands_verified": True, "modality": manifests[0].modality},
                blocked_reasons=[],
                fallback_measurements=["ndvi", "exceedance_area_km2"],
                capabilities_version="2.0.0",
                model_version="deterministic_raster_v1",
                estimated_resources={"vram_mb": 0, "cpu_only": True},
                automatic_route=True,
                decision_reason="Deterministic spectral index calculation (NDVI/NDWI) with exact raster calibration and histogram statistics."
            )

    # 2. Bitemporal Change Detection Route
    if intent == "change_detection":
        if not pair and len(manifests) < 2:
            blocked_reasons.append("Change detection requires two registered acquisitions (before and after).")
        else:
            # Check ChangeFormer availability
            cf_desc = REGISTRY.get("changeformer")
            if cf_desc and cf_desc.status == ModelStatus.VERIFIED:
                return RouteDecision(
                    task="change_detection",
                    selected_adapter_or_none="changeformer",
                    preprocessing_profile="bitemporal_aligned",
                    validation_checks={"pair_validated": True, "overlap_fraction": pair.overlap_fraction if pair else 1.0},
                    blocked_reasons=[],
                    fallback_measurements=["bitemporal_difference", "changed_area_km2"],
                    capabilities_version="2.0.0",
                    model_version="ChangeFormerV6-LEVIR",
                    estimated_resources={"vram_mb": 0, "cpu_only": True},
                    automatic_route=True,
                    decision_reason="ChangeFormerV6 Siamese transformer candidate change mask supplemented with deterministic raster difference."
                )
            else:
                fallback_measurements.append("bitemporal_difference")
                return RouteDecision(
                    task="change_difference_raster",
                    selected_adapter_or_none=None,
                    preprocessing_profile="bitemporal_difference",
                    validation_checks={"model_fallback": "ChangeFormer unavailable"},
                    blocked_reasons=["ChangeFormer weights not loaded locally"],
                    fallback_measurements=fallback_measurements,
                    capabilities_version="2.0.0",
                    model_version="deterministic_diff_v1",
                    estimated_resources={"vram_mb": 0},
                    automatic_route=True,
                    decision_reason="Deterministic signed difference on aligned acquisitions with equal-area changed percentage."
                )

    # 3. Optical + SAR Fusion Route (CROMA)
    if intent == "optical_sar_fusion" or (pair and pair.purpose == "optical_sar"):
        croma_desc = REGISTRY.get("croma")
        if croma_desc and croma_desc.status == ModelStatus.VERIFIED:
            return RouteDecision(
                task="feature_extraction",
                selected_adapter_or_none="croma",
                preprocessing_profile="croma_dual_sensor",
                validation_checks={"optical_sar_pair": True},
                blocked_reasons=[],
                fallback_measurements=["cross_modal_features"],
                capabilities_version="2.0.0",
                model_version="CROMA-Base",
                estimated_resources={"vram_mb": 2560},
                automatic_route=True,
                decision_reason="CROMA-Base dual-backbone optical/SAR joint feature representation."
            )
        else:
            blocked_reasons.append("CROMA-Base model unavailable.")

    # 4. Visual Grounding Route
    if intent == "visual_grounding":
        gg_desc = REGISTRY.get("owlv2") or REGISTRY.get("geoground")
        if gg_desc and gg_desc.status == ModelStatus.VERIFIED:
            return RouteDecision(
                task="visual_grounding",
                selected_adapter_or_none="owlv2",
                preprocessing_profile="owlv2_grounding",
                validation_checks={"zero_shot_vocabulary": True},
                blocked_reasons=[],
                fallback_measurements=[],
                capabilities_version="2.0.0",
                model_version="google/owlv2-base-patch16-ensemble",
                estimated_resources={"vram_mb": 1860},
                automatic_route=True,
                decision_reason="OWLv2 open-vocabulary object grounding and localization under 6 GB VRAM limit."
            )
        else:
            blocked_reasons.append("GeoGround-7B is unavailable on 8 GB GPU; open-vocabulary grounding requires tested OWLv2 adapter.")

    # 5. Semantic Classification Route (UPerNet)
    if intent == "classification":
        up_desc = REGISTRY.get("upernet")
        if up_desc and up_desc.status == ModelStatus.VERIFIED:
            return RouteDecision(
                task="segmentation",
                selected_adapter_or_none="upernet",
                preprocessing_profile="upernet_convnext",
                validation_checks={"semantic_classes": True},
                blocked_reasons=[],
                fallback_measurements=["class_distribution"],
                capabilities_version="2.0.0",
                model_version="upernet-convnext-tiny",
                estimated_resources={"vram_mb": 2048},
                automatic_route=True,
                decision_reason="UPerNet ConvNeXt semantic segmentation for land-cover classification."
            )

    # 6. Default: Optical Scene Description & VQA (InternVL3-2B)
    ivl_desc = REGISTRY.get("internvl3")
    if ivl_desc and ivl_desc.status == ModelStatus.VERIFIED:
        is_geo = bool(manifests and manifests[0].georeferencing_mode in ("projected", "geographic"))
        reason = (
            "InternVL3-2B visual observation supplemented by deterministic GeoTIFF raster facts and CRS bounds."
            if is_geo else
            "InternVL3-2B pixel-only visual observation for benchmark imagery. No geographic claims asserted."
        )
        return RouteDecision(
            task="scene_description",
            selected_adapter_or_none="internvl3",
            preprocessing_profile="normalized_rgb_preview",
            validation_checks={"georeferenced": is_geo},
            blocked_reasons=blocked_reasons,
            fallback_measurements=["geotiff_facts"],
            capabilities_version="2.0.0",
            model_version="InternVL3-2B",
            estimated_resources={"vram_mb": 4074},
            automatic_route=True,
            decision_reason=reason
        )

    # Blocked fallback if no route succeeds
    return RouteDecision(
        task="blocked",
        selected_adapter_or_none=None,
        preprocessing_profile="none",
        validation_checks={},
        blocked_reasons=blocked_reasons or ["No suitable model adapter or raster calculation available for request."],
        fallback_measurements=[],
        capabilities_version="2.0.0",
        model_version=None,
        estimated_resources={"vram_mb": 0},
        automatic_route=True,
        decision_reason="Request cannot be safely executed with current local resources and model weights."
    )
