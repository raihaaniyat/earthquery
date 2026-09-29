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
    RouteDecision,
    AnalysisPlan
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
    Constructs an explicit AnalysisPlan guaranteeing minimal model execution (1-3 models max)
    and deterministic raster tool precedence where appropriate.
    """
    q_lower = query.lower().strip()
    scene_ids = [m.scene_id for m in manifests]
    is_temporal = bool(pair and pair.purpose == "temporal") or len(manifests) >= 2
    is_optical_sar = bool(pair and pair.purpose == "optical_sar") or (
        len(manifests) >= 2 and any(m.modality == "sar" for m in manifests) and any(m.modality == "optical" for m in manifests)
    )

    requested_measurements: List[str] = []
    output_type: str = "narrative"

    # Location intent detection
    is_location_query = any(phrase in q_lower for phrase in [
        "place name", "what place", "which place", "what is the place", "name of the place",
        "where is this", "where was this", "where are these", "what city", "which city",
        "what state", "which state", "what country", "which country", "tell me the country",
        "tell me the place", "tell me the city", "tell me the state", "tell me country",
        "place, city, state, country", "city, state, country", "city, state and country",
        "place, city, state", "common place", "common location", "location of the image",
        "location of these", "what location", "which location", "geographic location",
        "where were these two images taken", "where are these two images taken",
        "what place is shown in both", "what place is common", "place shown in both",
        "place of the image"
    ]) or ("place" in q_lower and any(w in q_lower for w in ["city", "country", "state", "shown", "both", "image"]))

    is_change_query = any(phrase in q_lower for phrase in [
        "what changed", "what has changed", "difference between", "how much area changed",
        "change detection", "surface change", "demolition", "construction", "vegetation loss",
        "deforestation", "new buildings", "built-up expansion", "what was changed", "changed between",
        "finding in", "about finding", "about the finding", "about findings", "compare", "comparison"
    ]) or ("change" in q_lower and not is_location_query)

    # Detail Level extraction
    if any(phrase in q_lower for phrase in ["very high detail", "very high details", "in-depth", "exhaustive", "comprehensive", "maximum detail", "deep analysis"]):
        detail_level = "very_high"
    elif any(phrase in q_lower for phrase in ["in detail", "in details", "detailed", "deep dive", "thoroughly"]):
        detail_level = "high"
    elif any(phrase in q_lower for phrase in ["briefly", "brief", "short", "in short", "summary", "summarize in one sentence", "give me only the answer", "quick"]):
        detail_level = "concise"
    else:
        detail_level = "moderate"

    # Requested length extraction (e.g. 500 words, 300 words, 100 words)
    requested_length = None
    import re
    w_match = re.search(r"(?:in|about|approx|approximately|around|within)?\s*(\d+)\s*(?:words|word|w\b)", q_lower)
    if w_match:
        val = int(w_match.group(1))
        requested_length = {"value": val, "unit": "words", "mode": "target"}
        if val >= 250:
            detail_level = "very_high"
        elif val <= 100:
            detail_level = "concise"

    # Single-scene SAR Description check
    is_sar_scene = (
        (len(manifests) == 1 and manifests[0].modality == "sar")
        or (any(w in q_lower for w in ["sar image", "sar observation", "radar image", "sar data"]) and not any(w in q_lower for w in ["optical", "rgb"]))
    )

    # 1. Multi-Intent: Location AND Change
    if is_location_query and is_change_query and len(manifests) >= 2:
        intent = "multi_intent_location_and_change"
        target_focus = "location_and_change"
        required_models = ["changeformer"]
        operations = ["read_geospatial_metadata", "calculate_spatial_overlap", "reverse_geocode", "spatial_alignment", "bitemporal_difference"]
        output_type = "narrative"
        requested_measurements = ["place", "city", "state", "country", "common_area_km2", "changed_area_km2", "change_pct"]
        summary_goal = "Determine shared geographic location and quantify temporal surface differences."

    # 2. Location Identification for Temporal / Multi-image Pair
    elif is_location_query and len(manifests) >= 2:
        intent = "common_location_identification"
        target_focus = "common_location"
        required_models = ["internvl3"] if any(w in q_lower for w in ["detail", "describe", "combine", "summary"]) else []
        operations = ["read_geospatial_metadata", "calculate_spatial_overlap", "identify_common_footprint", "reverse_geocode"]
        output_type = "narrative"
        requested_measurements = ["place", "city", "state", "country", "common_area_km2", "overlap_pct", "coordinates"]
        summary_goal = "Determine shared geographic place, city, state, and country from paired spatial footprints and reverse geocoding."

    # 3. Location Identification for Single Image
    elif is_location_query:
        intent = "location_identification"
        target_focus = "location"
        required_models = ["internvl3"] if any(w in q_lower for w in ["detail", "describe", "summary"]) else []
        operations = ["read_geospatial_metadata", "wgs84_reprojection", "reverse_geocode"]
        output_type = "narrative"
        requested_measurements = ["place", "city", "state", "country", "coordinates"]
        summary_goal = "Determine geographic place, city, state, and country from georeferenced raster metadata."

    # 4. Pure Raster Metadata Query (No vision models needed)
    elif any(k in q_lower for k in [
        "area of the raster", "area of the image", "area of the uploaded", "what is the area",
        "footprint of", "what is the crs", "coordinate system", "pixel resolution", "ground sampling distance",
        "raster bounds", "spatial extent of"
    ]) and not any(k in q_lower for k in ["change", "building", "vegetation", "flood", "new", "compare"]):
        intent = "raster_metadata"
        target_focus = "metadata"
        required_models = []
        operations = ["raster_metadata_extraction", "geodesic_area_calculation"]
        output_type = "metrics"
        requested_measurements = ["footprint_km2", "resolution_m", "crs"]
        summary_goal = "Directly report verified GeoTIFF metadata, physical footprint area, and coordinate system."

    # 5. Spectral Indices Intent (Deterministic, no GPU model needed)
    elif any(k in q_lower for k in ["ndvi", "vegetation index", "ndwi", "water index", "greenness", "spectral"]):
        intent = "spectral_index"
        target_focus = "vegetation" if "ndvi" in q_lower or "greenness" in q_lower else "water"
        required_models = []
        operations = ["spectral_band_extraction", "deterministic_index_ratio", "histogram_thresholding"]
        output_type = "metrics"
        requested_measurements = ["ndvi"]
        summary_goal = "Deterministic spectral index computation with histogram distribution and threshold exceedance."

    # 4. Optical + SAR Multimodal Queries (Placed before temporal comparison so multimodal phrasing like 'fusion between the two' is prioritized)
    elif is_optical_sar or (pair and pair.purpose == "optical_sar") or any(m in q_lower for m in ["optical-sar", "optical_sar", "sar-optical", "croma"]) or (
        any(m in q_lower for m in ["sar", "radar"]) and any(m in q_lower for m in ["optical", "rgb", "multispectral", "both", "fusion", "two", "between"])
    ) or (
        "fusion" in q_lower and any(m in q_lower for m in ["sar", "radar", "optical", "two", "between"])
    ):
        is_multimodal = True
        if any(f in q_lower for f in ["flood", "water", "inundat", "overflow"]):
            intent = "optical_sar_flood"
            target_focus = "flood"
            required_models = ["croma", "optical_sar_head", "change_vqa"]
            operations = ["spatial_alignment", "optical_water_index", "sar_specular_thresholding", "cross_modal_consensus"]
            output_type = "mask"
            requested_measurements = ["fused_flood_area_km2", "fused_flood_pct"]
            summary_goal = "Fuse optical spectral reflectance with SAR specular backscatter to delineate confirmed flood extent."
        elif any(b in q_lower for b in ["building", "structure", "urban"]):
            intent = "optical_sar_buildings"
            target_focus = "buildings"
            required_models = ["croma", "optical_sar_head", "owlv2"]
            operations = ["spatial_alignment", "optical_grounding", "sar_structural_double_bounce", "cross_modal_fusion"]
            output_type = "mask"
            requested_measurements = ["structure_pct"]
            summary_goal = "Identify structural features via joint optical visual patterns and SAR corner backscatter."
        else:
            intent = "optical_sar_fusion"
            target_focus = "general"
            required_models = ["croma", "optical_sar_head", "change_vqa"]
            operations = ["spatial_alignment", "croma_cross_modal_features", "multimodal_classification", "cross_sensor_vqa"]
            output_type = "narrative"
            requested_measurements = ["multimodal_features", "primary_class", "change_vqa_answer"]
            summary_goal = "Joint optical and SAR feature representation, cross-sensor surface classification, and multimodal reasoning."

    # 6. Temporal Comparison Queries (ONLY when query specifically asks about change or comparison)
    elif len(manifests) >= 2 and (is_change_query or any(k in q_lower for k in ["compare", "difference", "earlier", "later", "what changed", "two dates", "between", "lost"])):
        is_temporal = True
        # 6a. Temporal Building Change / Construction
        if any(b in q_lower for b in ["building", "structure", "house", "construction", "built-up", "urban development", "expansion"]):
            intent = "temporal_building_change"
            target_focus = "buildings"
            required_models = ["owlv2"]
            operations = ["spatial_alignment", "temporal_comparison", "bitemporal_object_detection", "spatial_object_matching", "statistics"]
            output_type = "mask"
            requested_measurements = ["new_building_count", "unchanged_building_count", "disappeared_building_count"]
            summary_goal = "Compare aligned temporal observations, match spatial building objects, and report newly appeared vs unchanged structures."

        # 6b. Temporal Vegetation Loss / Deforestation
        elif any(v in q_lower for v in ["vegetation", "forest", "tree", "greenery", "deforestation", "canopy"]):
            intent = "temporal_vegetation_loss"
            target_focus = "vegetation"
            required_models = []  # Deterministic aligned vegetation delta
            operations = ["spatial_alignment", "bitemporal_vegetation_delta", "loss_quantification", "statistics"]
            output_type = "metrics"
            requested_measurements = ["lost_vegetation_area_km2", "loss_pct_of_baseline"]
            summary_goal = "Calculate comparative vegetation loss and area change between spatially aligned temporal observations."

        # 6c. General Temporal Change Detection
        else:
            intent = "change_detection"
            target_focus = "general_change"
            required_models = ["changeformer", "change_vqa"]
            operations = ["spatial_alignment", "bitemporal_difference", "siamese_change_detection", "temporal_reasoning"]
            output_type = "mask"
            requested_measurements = ["bitemporal_difference", "changed_area_km2"]
            summary_goal = "Spatially align observations to common footprint and synthesize comparative change dynamics."

    # 5. Object Detection / Visual Grounding Intent
    elif any(k in q_lower for k in ["locate", "detect", "ground", "where are", "count", "bounding box", "owlv2", "owl", "geoground"]) or (
        "find" in q_lower and any(obj in q_lower for obj in ["building", "vehicle", "ship", "car", "plane", "aircraft", "structure", "road", "solar", "tank"])
    ) or any(phrase in q_lower for phrase in ["how many buildings", "how many vehicles", "how many ships", "how many planes", "how many structures"]):
        intent = "visual_grounding"
        target_focus = "objects"
        required_models = ["owlv2"]
        operations = ["zero_shot_localization", "bounding_box_extraction", "spatial_coordinates"]
        output_type = "mask"
        requested_measurements = ["object_count"]
        summary_goal = "Detect, localize, and count target physical features using open-vocabulary visual grounding."

    # 6. Classification / Land Cover Segmentation Intent
    elif any(k in q_lower for k in ["classify", "land cover", "segment", "segmentation", "classes", "vegetation, water", "land-cover"]):
        intent = "classification"
        target_focus = "land_cover"
        required_models = ["upernet"]
        operations = ["semantic_segmentation", "class_percentage_distribution"]
        output_type = "mask"
        requested_measurements = ["class_distribution"]
        summary_goal = "Segment and quantify surface land cover categories."

    # 6d. Single-scene SAR Description (CROMA-Base or deterministic SAR backscatter)
    elif is_sar_scene and not is_optical_sar:
        intent = "sar_scene_description"
        target_focus = "sar"
        required_models = ["croma"]
        operations = ["sar_radiometry_extraction", "specular_backscatter_analysis", "polarization_decomposition"]
        output_type = "narrative"
        requested_measurements = ["backscatter_mean", "polarization"]
        summary_goal = "Provide expert Synthetic Aperture Radar (SAR) backscatter interpretation answering the specific inquiry."

    # 7. Scene Description / General VQA Intent
    else:
        intent = "scene_description"
        target_focus = "general"
        required_models = ["internvl3"]
        operations = ["visual_question_answering", "radiometric_context", "scene_interpretation"]
        output_type = "narrative"
        summary_goal = "Provide expert remote sensing interpretation answering the specific inquiry."

    plan = AnalysisPlan(
        intent=intent,
        target_focus=target_focus,
        inputs=scene_ids,
        is_temporal=is_temporal,
        is_multimodal=is_optical_sar,
        operations=operations,
        required_models=required_models,
        output_requirements=requested_measurements + [output_type],
        requested_length=requested_length,
        detail_level=detail_level,
        summary_goal=summary_goal
    )

    return TaskRequest(
        user_question=query,
        intent=intent,
        scene_ids=scene_ids,
        requested_output=output_type,
        requested_measurements=requested_measurements,
        requested_length=requested_length,
        detail_level=detail_level,
        diagnostic_model_override=diagnostic_override,
        analysis_plan=plan
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

    # 1. Geographic Location Identification (Single or Paired Images)
    if intent in ("location_identification", "common_location_identification"):
        needs_vision = any(w in task_req.user_question.lower() for w in ["detail", "describe", "combine", "summary"])
        return RouteDecision(
            task=intent,
            selected_adapter_or_none="internvl3" if needs_vision else None,
            preprocessing_profile="geospatial_location_resolution",
            validation_checks={"location_intent_verified": True},
            blocked_reasons=[],
            fallback_measurements=["place", "city", "state", "country", "common_area_km2"],
            capabilities_version="2.0.0",
            model_version="geo_lookup_v1",
            estimated_resources={"vram_mb": 2048 if needs_vision else 0, "cpu_only": not needs_vision},
            automatic_route=True,
            decision_reason="Evidence-based geographic location identification and spatial footprint intersection."
        )

    # 2. Multi-Intent: Location AND Change Detection
    if intent == "multi_intent_location_and_change":
        return RouteDecision(
            task="multi_intent_location_and_change",
            selected_adapter_or_none="changeformer",
            preprocessing_profile="bitemporal_location_and_change",
            validation_checks={"location_intent_verified": True, "pair_validated": True},
            blocked_reasons=[],
            fallback_measurements=["place", "city", "state", "country", "changed_area_km2", "change_pct"],
            capabilities_version="2.0.0",
            model_version="geo_lookup_plus_changeformer_v1",
            estimated_resources={"vram_mb": 2048},
            automatic_route=True,
            decision_reason="Dual-objective pipeline: Geographic location resolution followed by bitemporal change quantification."
        )

    # 3. Deterministic Raster Metadata Route (Zero models needed)
    if intent == "raster_metadata":
        return RouteDecision(
            task="raster_metadata",
            selected_adapter_or_none=None,
            preprocessing_profile="geotiff_header_inspection",
            validation_checks={"metadata_verified": True},
            blocked_reasons=[],
            fallback_measurements=["footprint_km2", "resolution_m", "crs"],
            capabilities_version="2.0.0",
            model_version="deterministic_raster_v1",
            estimated_resources={"vram_mb": 0, "cpu_only": True},
            automatic_route=True,
            decision_reason="Pure deterministic GeoTIFF header and spatial extent inspection. No vision models required."
        )

    # 2. Deterministic Spectral Index Route (No GPU model required)
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

    # 3. Temporal Routes
    if intent in ("change_detection", "temporal_building_change", "temporal_vegetation_loss"):
        if not pair and len(manifests) < 2:
            blocked_reasons.append("Change detection requires two registered acquisitions (before and after).")
        elif intent == "temporal_vegetation_loss":
            return RouteDecision(
                task="temporal_vegetation_loss",
                selected_adapter_or_none=None,  # Pure deterministic vegetation difference
                preprocessing_profile="bitemporal_aligned_vegetation",
                validation_checks={"pair_validated": True},
                blocked_reasons=[],
                fallback_measurements=["lost_vegetation_area_km2", "loss_pct_of_baseline"],
                capabilities_version="2.0.0",
                model_version="deterministic_diff_v1",
                estimated_resources={"vram_mb": 0, "cpu_only": True},
                automatic_route=True,
                decision_reason="Deterministic aligned NDVI difference quantifying baseline vegetation versus post-event loss."
            )
        elif intent == "temporal_building_change":
            return RouteDecision(
                task="temporal_building_change",
                selected_adapter_or_none="owlv2",
                preprocessing_profile="bitemporal_object_matching",
                validation_checks={"pair_validated": True, "spatial_matching": True},
                blocked_reasons=[],
                fallback_measurements=["new_building_count", "unchanged_building_count"],
                capabilities_version="2.0.0",
                model_version="google/owlv2-base-patch16-ensemble",
                estimated_resources={"vram_mb": 1860},
                automatic_route=True,
                decision_reason="OWLv2 visual grounding on temporal pair with spatial bipartite IoU matching to separate unchanged from newly constructed objects."
            )
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

    # 4. Optical + SAR Fusion Routes
    if intent in ("optical_sar_fusion", "optical_sar_flood", "optical_sar_buildings") or (pair and pair.purpose == "optical_sar"):
        croma_desc = REGISTRY.get("croma")
        if croma_desc and croma_desc.status == ModelStatus.VERIFIED:
            return RouteDecision(
                task=intent,
                selected_adapter_or_none="croma",
                preprocessing_profile="croma_dual_sensor",
                validation_checks={"optical_sar_pair": True},
                blocked_reasons=[],
                fallback_measurements=["cross_modal_features"],
                capabilities_version="2.0.0",
                model_version="CROMA-Base",
                estimated_resources={"vram_mb": 2560},
                automatic_route=True,
                decision_reason="CROMA-Base dual-backbone optical/SAR joint feature representation with cross-modal evidence fusion."
            )
        else:
            blocked_reasons.append("CROMA-Base model unavailable.")

    # 5. Visual Grounding Route
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

    # 6. Semantic Classification Route (UPerNet)
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

    # 6b. Single-scene SAR Description Route (CROMA-Base)
    if intent == "sar_scene_description":
        croma_desc = REGISTRY.get("croma")
        return RouteDecision(
            task="sar_scene_description",
            selected_adapter_or_none="croma" if (croma_desc and croma_desc.status == ModelStatus.VERIFIED) else None,
            preprocessing_profile="sar_radiometric_analysis",
            validation_checks={"sar_scene_verified": True},
            blocked_reasons=[],
            fallback_measurements=["backscatter_summary", "sar_polarization"],
            capabilities_version="2.0.0",
            model_version="CROMA-Base" if (croma_desc and croma_desc.status == ModelStatus.VERIFIED) else "deterministic_sar_v1",
            estimated_resources={"vram_mb": 2560 if (croma_desc and croma_desc.status == ModelStatus.VERIFIED) else 0},
            automatic_route=True,
            decision_reason="Synthetic Aperture Radar (SAR) backscatter analysis and radiometry interpretation via CROMA."
        )

    # 7. Default: Optical Scene Description & VQA (InternVL3-2B)
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
