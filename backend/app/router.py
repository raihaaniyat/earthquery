"""
LangGraph Task Router & Scientific Analysis Engine for SatQuery AI.
Implements the verified scientific workflow:
Input Sifter -> Geospatial/Pixel Preparation -> Query & Pair Checks ->
Deterministic Task Router -> Model/Raster Processing -> Evidence Validator.
"""

import os
import json
from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph, END

from backend.app.models_registry import REGISTRY, ModelStatus
from backend.app.input_validator import validate_geotiff, validate_benchmark_image
from backend.app.worker import get_queue
from backend.app.schemas.manifests import (
    SceneManifest,
    PairManifest,
    TaskRequest,
    RouteDecision,
    EvidenceBundle
)
from backend.app.services.routing import (
    create_scene_manifest,
    create_pair_manifest,
    parse_user_intent,
    decide_route
)
from backend.app.services.raster_measurements import (
    extract_geotiff_facts,
    compute_spectral_index,
    compute_bitemporal_metrics,
    build_evidence_bundle,
    format_scientific_sections
)
from backend.app.tasks.inference_tasks import (
    execute_internvl_task,
    execute_croma_task,
    execute_changeformer_task,
    execute_upernet_task,
    execute_geoground_task,
    execute_change_vqa_task,
    execute_optical_sar_task,
    execute_pipeline_task
)
from backend.app.services.multi_model_pipeline import run_multi_model_pipeline


class RouterState(TypedDict):
    task: str
    input_category: str  # "geotiff" or "benchmark"
    file_paths: List[str]
    prompt: str
    pair_type: str
    target_model_id: str
    validation_info: Dict[str, Any]
    manifests: List[Dict[str, Any]]
    pair_manifest: Optional[Dict[str, Any]]
    route_decision: Dict[str, Any]
    raster_measurements: Dict[str, Any]
    evidence_bundle: Dict[str, Any]
    dispatch_mode: str
    result: Dict[str, Any]


def node_sift_and_validate(state: RouterState) -> Dict[str, Any]:
    """
    Stage 1: Input Sifter & Geospatial Validation.
    Inspects physical file contents, sensor metadata, bands, CRS, transform,
    and dimensions to issue immutable SceneManifests.
    """
    file_paths = state.get("file_paths", [])
    validation_info = {}
    manifests = []

    for p in file_paths:
        if not os.path.exists(p):
            continue

        manifest = create_scene_manifest(p)
        manifests.append(manifest.model_dump())

        if manifest.format == "geotiff" and manifest.georeferencing_mode != "pixel_only":
            res = validate_geotiff(p)
            validation_info[p] = res.to_dict()
        else:
            try:
                validation_info[p] = validate_benchmark_image(p)
            except Exception as e:
                validation_info[p] = {"is_valid": False, "error": str(e)}

    # Pair check if 2 scenes present
    pair_manifest = None
    if len(manifests) >= 2:
        m_a = SceneManifest(**manifests[0])
        m_b = SceneManifest(**manifests[1])
        pair = create_pair_manifest(m_a, m_b)
        pair_manifest = pair.model_dump()

    return {
        "validation_info": validation_info,
        "manifests": manifests,
        "pair_manifest": pair_manifest
    }


def node_route_decision(state: RouterState) -> Dict[str, Any]:
    """
    Stage 2: Query Compiler & Deterministic Routing.
    Matches user scientific intent and validated manifests to model adapters
    and deterministic raster measurement tools.
    """
    manifest_objs = [SceneManifest(**m) for m in state.get("manifests", [])]
    pair_obj = PairManifest(**state["pair_manifest"]) if state.get("pair_manifest") else None
    query = state.get("prompt", "")

    # Parse intent
    task_req = parse_user_intent(
        query=query,
        manifests=manifest_objs,
        pair=pair_obj,
        diagnostic_override=state.get("target_model_id") or None
    )

    # Determine route
    decision = decide_route(manifest_objs, pair_obj, task_req)

    return {
        "route_decision": decision.model_dump(),
        "target_model_id": decision.selected_adapter_or_none or "",
        "task": decision.task
    }


def node_raster_measurements(state: RouterState) -> Dict[str, Any]:
    """
    Stage 3: Scientific Evidence Preparation.
    Computes deterministic raster metrics (GeoTIFF facts, NDVI/spectral indices,
    bitemporal difference) prior to any model narrative.
    """
    file_paths = state.get("file_paths", [])
    decision = state.get("route_decision", {})
    task = decision.get("task", state.get("task", "internvl"))

    facts = {}
    measurements = []
    pair_metrics = None

    if file_paths:
        facts = extract_geotiff_facts(file_paths[0])

    if task == "spectral_index" and file_paths:
        idx_res = compute_spectral_index(file_paths[0], index_type="ndvi")
        if "error" not in idx_res:
            measurements.append(idx_res)

    elif task in ("change_detection", "change_difference_raster") and len(file_paths) >= 2:
        pair_metrics = compute_bitemporal_metrics(file_paths[0], file_paths[1])

    # Construct EvidenceBundle
    bundle = build_evidence_bundle(
        facts=facts,
        measurements=measurements,
        user_query=state.get("prompt", ""),
        pair_metrics=pair_metrics
    )

    return {
        "raster_measurements": {
            "facts": facts,
            "spectral": measurements,
            "temporal": pair_metrics
        },
        "evidence_bundle": bundle.model_dump()
    }


def node_dispatch_or_execute(state: RouterState) -> Dict[str, Any]:
    """
    Stage 4 & 5: Model Processing & Evidence Validation.
    Executes model inference (or returns pure deterministic raster findings)
    and formats the final output into the three required scientific headings.
    """
    decision = state.get("route_decision", {})
    model_id = decision.get("selected_adapter_or_none")
    task = decision.get("task", "scene_description")
    dispatch_mode = state.get("dispatch_mode", "direct")
    files = state.get("file_paths", [])
    default_img = files[0] if files and os.path.exists(files[0]) else "data/samples/sample_optical.png"
    evidence_bundle_dict = state.get("evidence_bundle", {})
    bundle = EvidenceBundle(**evidence_bundle_dict) if evidence_bundle_dict else None

    # Blocked Route Handler
    if decision.get("blocked_reasons"):
        return {
            "result": {
                "status": "BLOCKED",
                "message": " ; ".join(decision["blocked_reasons"]),
                "decision_reason": decision.get("decision_reason"),
                "fallback_measurements": decision.get("fallback_measurements", [])
            }
        }

    # Pure Deterministic Route (No model needed)
    if model_id is None:
        meas_info = state.get("raster_measurements", {})
        if task == "spectral_index":
            idx = meas_info.get("spectral", [{}])[0] if meas_info.get("spectral") else {}
            narrative = f"NDVI mean: {idx.get('mean', 'N/A')}, range [{idx.get('min')}, {idx.get('max')}]. Threshold exceedance: {idx.get('threshold_exceed_pct', 0)}% of valid pixels."
        elif task == "change_difference_raster":
            tmp = meas_info.get("temporal", {})
            narrative = f"Bitemporal difference detected: {tmp.get('change_pct', 0)}% changed pixels ({tmp.get('changed_area_km2', 'N/A')} km²)."
        else:
            narrative = "Deterministic raster analysis complete."

        sections = format_scientific_sections(bundle, narrative, "Deterministic Raster Tool")
        return {
            "result": {
                "status": "EXECUTED_ISOLATED",
                "summary": narrative,
                "sections": sections,
                "output_metadata": {"answer": narrative, "sections": sections},
                "metrics": {"status": "completed", "cpu_only": True}
            }
        }

    # Model Execution Branch
    desc = REGISTRY.get(model_id)
    if desc and desc.status == ModelStatus.TRAINING_REQUIRED:
        return {
            "result": {
                "status": "TRAINING_REQUIRED",
                "message": f"Model '{desc.name}' requires training. No SatQuery-specific weights exist.",
                "notes": desc.notes
            }
        }
    if desc and desc.status == ModelStatus.INSTALLED_NOT_RUNNABLE_LOCALLY:
        return {
            "result": {
                "status": "INSTALLED_BUT_NOT_RUNNABLE_LOCALLY",
                "message": f"Model '{desc.name}' exceeds local 8GB VRAM capacity.",
                "notes": desc.notes
            }
        }

    diagnostic_override = state.get("diagnostic_override") or (
        state.get("target_model_id") if state.get("diagnostic_mode") else None
    )

    q = get_queue() if dispatch_mode not in ("direct", "isolated") else None
    if q is not None:
        try:
            from rq import Worker
            workers = Worker.all(connection=q.connection)
            has_active = any(q.name in [queue.name for queue in w.queues] for w in workers)
            if not has_active:
                logger.info(f"No active RQ worker found listening on queue '{q.name}'. Falling back to synchronous execution.")
                q = None
        except Exception as e:
            logger.warning(f"Could not inspect RQ workers ({e}). Proceeding to synchronous execution.")
            q = None

    # Worker queue dispatch
    if q is not None:
        if diagnostic_override:
            if diagnostic_override == "internvl3":
                job = q.enqueue(execute_internvl_task, default_img, state.get("prompt", ""))
            elif diagnostic_override == "croma":
                s1 = files[0] if len(files) > 0 and os.path.exists(files[0]) else "data/samples/sample_sar.tif"
                s2 = files[1] if len(files) > 1 and os.path.exists(files[1]) else default_img
                job = q.enqueue(execute_croma_task, sentinel_1_path=s1, sentinel_2_path=s2)
            elif diagnostic_override == "changeformer":
                t1 = files[0] if len(files) > 0 and os.path.exists(files[0]) else "data/samples/sample_optical.png"
                t2 = files[1] if len(files) > 1 and os.path.exists(files[1]) else t1
                job = q.enqueue(execute_changeformer_task, t1, t2)
            elif diagnostic_override == "upernet":
                job = q.enqueue(execute_upernet_task, default_img)
            elif diagnostic_override in ("geoground", "owlv2"):
                job = q.enqueue(execute_geoground_task, default_img, state.get("prompt", ""))
            elif diagnostic_override == "change_vqa":
                t1 = files[0] if len(files) > 0 and os.path.exists(files[0]) else "data/samples/sample_optical.png"
                t2 = files[1] if len(files) > 1 and os.path.exists(files[1]) else t1
                job = q.enqueue(execute_change_vqa_task, t1, t2, state.get("prompt", ""))
            elif diagnostic_override == "optical_sar_head":
                s1 = files[0] if len(files) > 0 and os.path.exists(files[0]) else "data/samples/sample_sar.tif"
                s2 = files[1] if len(files) > 1 and os.path.exists(files[1]) else default_img
                job = q.enqueue(execute_optical_sar_task, sentinel_1_path=s1, sentinel_2_path=s2)
            else:
                job = q.enqueue(
                    execute_pipeline_task,
                    file_paths=files if files else [default_img],
                    prompt=state.get("prompt", ""),
                    pair_type=state.get("pair_type", "single_image"),
                    user_intent=task,
                    diagnostic_override=diagnostic_override
                )
        else:
            job = q.enqueue(
                execute_pipeline_task,
                file_paths=files if files else [default_img],
                prompt=state.get("prompt", ""),
                pair_type=state.get("pair_type", "single_image"),
                user_intent=task,
                diagnostic_override=None
            )

        return {
            "result": {
                "status": "QUEUED_IN_RQ_WORKER",
                "job_id": job.id if job else None,
                "queue": "satquery-analysis",
                "model": desc.name if desc else model_id,
                "decision_reason": decision.get("decision_reason"),
                "evidence_bundle": bundle
            }
        }

    # Direct synchronous execution fallback
    if diagnostic_override:
        if diagnostic_override == "internvl3":
            exec_res = execute_internvl_task(default_img, state.get("prompt", ""))
        elif diagnostic_override == "changeformer":
            t1 = files[0] if len(files) > 0 and os.path.exists(files[0]) else "data/samples/sample_optical.png"
            t2 = files[1] if len(files) > 1 and os.path.exists(files[1]) else t1
            exec_res = execute_changeformer_task(t1, t2)
        elif diagnostic_override in ("geoground", "owlv2"):
            exec_res = execute_geoground_task(default_img, state.get("prompt", ""))
        elif diagnostic_override == "upernet":
            exec_res = execute_upernet_task(default_img)
        elif diagnostic_override == "croma":
            s1 = files[0] if len(files) > 0 and os.path.exists(files[0]) else "data/samples/sample_sar.tif"
            s2 = files[1] if len(files) > 1 and os.path.exists(files[1]) else default_img
            exec_res = execute_croma_task(sentinel_1_path=s1, sentinel_2_path=s2)
        elif diagnostic_override == "change_vqa":
            t1 = files[0] if len(files) > 0 and os.path.exists(files[0]) else "data/samples/sample_optical.png"
            t2 = files[1] if len(files) > 1 and os.path.exists(files[1]) else t1
            exec_res = execute_change_vqa_task(t1, t2, state.get("prompt", ""))
        elif diagnostic_override == "optical_sar_head":
            s1 = files[0] if len(files) > 0 and os.path.exists(files[0]) else "data/samples/sample_sar.tif"
            s2 = files[1] if len(files) > 1 and os.path.exists(files[1]) else default_img
            exec_res = execute_optical_sar_task(sentinel_1_path=s1, sentinel_2_path=s2)
        else:
            exec_res = run_multi_model_pipeline(
                file_paths=files if files else [default_img],
                prompt=state.get("prompt", ""),
                pair_type=state.get("pair_type", "single_image"),
                user_intent=task,
                diagnostic_override=diagnostic_override
            )
        narrative = exec_res.get("summary") or exec_res.get("output_metadata", {}).get("answer") or str(exec_res)
        sections = exec_res.get("sections") or (format_scientific_sections(bundle, narrative, desc.name if desc else model_id) if bundle else {})
        return {
            "result": {
                "status": "EXECUTED_ISOLATED",
                "execution_result": exec_res,
                "summary": narrative,
                "sections": sections,
                "findings": exec_res.get("findings", []),
                "decision_reason": decision.get("decision_reason")
            }
        }
    else:
        exec_res = run_multi_model_pipeline(
            file_paths=files if files else [default_img],
            prompt=state.get("prompt", ""),
            pair_type=state.get("pair_type", "single_image"),
            user_intent=task,
            diagnostic_override=None
        )
        narrative = exec_res.get("summary", "")
        sections = exec_res.get("sections") or (format_scientific_sections(bundle, narrative, desc.name if desc else model_id) if bundle else {})
        return {
            "result": {
                "status": "EXECUTED_ISOLATED",
                "execution_result": exec_res,
                "summary": narrative,
                "sections": sections,
                "findings": exec_res.get("findings", []),
                "output_assets": exec_res.get("output_assets", {}),
                "participating_models": exec_res.get("participating_models", []),
                "decision_reason": decision.get("decision_reason")
            }
        }


# Construct StateGraph with the complete scientific pipeline
builder = StateGraph(RouterState)

builder.add_node("sift_and_validate", node_sift_and_validate)
builder.add_node("route_decision", node_route_decision)
builder.add_node("raster_measurements", node_raster_measurements)
builder.add_node("dispatch_or_execute", node_dispatch_or_execute)

builder.set_entry_point("sift_and_validate")
builder.add_edge("sift_and_validate", "route_decision")
builder.add_edge("route_decision", "raster_measurements")
builder.add_edge("raster_measurements", "dispatch_or_execute")
builder.add_edge("dispatch_or_execute", END)

task_router_app = builder.compile()
