"""
Typed Contracts for Scientific Analysis and Automatic Routing.
Defines immutable data models for SceneManifest, PairManifest, TaskRequest,
RouteDecision, EvidenceBundle, and ScientificFinding.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field


class SceneManifest(BaseModel):
    """
    Immutable typed manifest issued by the Input Sifter inspecting
    actual file content, sensor metadata, bands, CRS, transform, nodata,
    and dimensions.
    """
    scene_id: str
    sha256: str
    source: str = "local_upload"  # "local_upload", "stac", "copernicus", "benchmark"
    format: str = "geotiff"  # "geotiff", "png", "jpeg", "unknown"
    sensor: str = "Unknown"  # "Sentinel-2", "Sentinel-1", "Landsat", "Benchmark", "Unknown"
    product_level: Optional[str] = None  # "L2A", "GRD", "Level-1C"
    modality: str = "optical"  # "optical", "sar", "multispectral", "benchmark_pixel", "unknown"
    acquisition_utc: Optional[str] = None
    footprint_or_null: Optional[Dict[str, Any]] = None  # GeoJSON polygon or None
    crs_or_null: Optional[str] = None  # E.g. "EPSG:32631"
    affine_or_null: Optional[List[float]] = None  # [a, b, c, d, e, f]
    width: int = 0
    height: int = 0
    resolution_or_null: Optional[float] = None  # native pixel size in metres or degrees
    pixel_unit: str = "pixel"  # "metre", "degree", "pixel"
    bands_or_polarizations: List[str] = Field(default_factory=list)
    scale_offset: Optional[Dict[str, float]] = None
    nodata: Optional[float] = None
    quality_mask: Optional[str] = None
    georeferencing_mode: str = "pixel_only"  # "geographic", "projected", "pixel_only", "unreferenced"
    processing_history: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)


class PairManifest(BaseModel):
    """
    Validated pair relationship between two scenes (bitemporal or optical+SAR).
    """
    purpose: str = "temporal"  # "temporal" | "optical_sar"
    ordered_scene_ids: List[str] = Field(default_factory=list)  # [before_id, after_id] or [optical_id, sar_id]
    acquisition_gap: Optional[float] = None  # Gap in days
    overlap_fraction: Optional[float] = None  # Fraction 0.0 to 1.0 of spatial overlap
    common_crs_and_grid: Optional[Dict[str, Any]] = None
    alignment_error_or_unknown: Optional[float] = None
    resampling_method: Optional[str] = "bilinear"
    quality_flags: List[str] = Field(default_factory=list)


class AnalysisPlan(BaseModel):
    """
    Internal structured plan created before executing models to ensure query-grounded,
    minimal-model execution (1-3 models max) and coordinated evidence generation.
    """
    intent: str
    target_focus: str = "general"  # "buildings", "vegetation", "flood", "water", "urban", "metadata", "general"
    inputs: List[str] = Field(default_factory=list)
    is_temporal: bool = False
    is_multimodal: bool = False
    operations: List[str] = Field(default_factory=list)
    required_models: List[str] = Field(default_factory=list)  # 1-3 models max: e.g. ["owlv2"], ["upernet"], ["changeformer"]
    output_requirements: List[str] = Field(default_factory=list)
    requested_length: Optional[Dict[str, Any]] = None  # e.g. {"value": 500, "unit": "words", "mode": "target"}
    detail_level: str = "moderate"  # "concise", "moderate", "high", "very_high"
    summary_goal: str = ""


class TaskRequest(BaseModel):
    """
    Parsed scientific intent from the user query and inputs.
    """
    user_question: str
    intent: str = "scene_description"
    # "scene_description", "spectral_index", "change_detection",
    # "visual_grounding", "classification", "feature_extraction"
    scene_ids: List[str] = Field(default_factory=list)
    requested_output: str = "narrative"  # "narrative", "mask", "metrics", "table"
    spatial_scope: Optional[Dict[str, Any]] = None  # AOI geometry
    model_capability_required: Optional[str] = None
    requested_measurements: List[str] = Field(default_factory=list)
    requested_length: Optional[Dict[str, Any]] = None
    detail_level: str = "moderate"
    diagnostic_model_override: Optional[str] = None  # Only for diagnostic testing
    analysis_plan: Optional[AnalysisPlan] = None


class RouteDecision(BaseModel):
    """
    Deterministic routing decision matching validated manifests + intent to model
    capabilities and deterministic raster tools.
    """
    task: str
    selected_adapter_or_none: Optional[str] = None
    preprocessing_profile: str = "standard"
    validation_checks: Dict[str, Any] = Field(default_factory=dict)
    blocked_reasons: List[str] = Field(default_factory=list)
    fallback_measurements: List[str] = Field(default_factory=list)
    capabilities_version: str = "2.0.0"
    model_version: Optional[str] = None
    estimated_resources: Dict[str, Any] = Field(default_factory=dict)
    automatic_route: bool = True
    decision_reason: str = ""


class ScientificMeasurement(BaseModel):
    metric: str
    value: Optional[float] = None
    unit: str = ""
    status: str = "computed"
    details: Optional[Dict[str, Any]] = None


class ScientificFinding(BaseModel):
    observation: str
    measurement: Optional[ScientificMeasurement] = None
    method: str = ""
    evidence: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    validation_status: str = "validated_raster_metric"


class EvidenceBundle(BaseModel):
    """
    Sanitized evidence bundle supplied to the vision-language model.
    Constrains the model's explanations to verified raster observations,
    prohibiting unsupported claims, unverified numbers, or ground-truth asserts.
    """
    raster_facts: Dict[str, Any] = Field(default_factory=dict)
    computed_measurements: List[ScientificMeasurement] = Field(default_factory=list)
    valid_interpretations: List[str] = Field(default_factory=list)
    prohibited_claims: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    source_references: List[str] = Field(default_factory=list)
