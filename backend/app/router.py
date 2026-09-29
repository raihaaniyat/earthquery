"""
LangGraph Task Router & Scientific Analysis Engine for SatQuery AI.
Implements the verified scientific workflow:
Input Sifter -> Geospatial/Pixel Preparation -> Query & Pair Checks ->
Deterministic Task Router -> Model/Raster Processing -> Evidence Validator.
"""

import os
import json
import logging
from typing import TypedDict, List, Optional, Dict, Any
from langgraph.graph import StateGraph, END

logger = logging.getLogger("satquery.router")

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
from backend.app.db.session import SessionLocal
from backend.app.db.models import Conversation, ConversationResult, ConversationDataset
from backend.app.services.conversation_service import ConversationEngine


class RouterState(TypedDict, total=False):
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

    # Conversational Additions
    conversation_id: Optional[str]
    client_request_id: Optional[str]
    turn_action_type: Optional[str]
    turn_action_details: Optional[Dict[str, Any]]
    has_new_files: Optional[bool]
    active_context: Optional[Dict[str, Any]]
    pending_task: Optional[Dict[str, Any]]
    map_action: Optional[Dict[str, Any]]


def node_sift_and_validate(state: RouterState) -> Dict[str, Any]:
    """
    Stage 1: Input Sifter & Geospatial Validation.
    Inspects physical file contents, sensor metadata, bands, CRS, transform,
    and dimensions to issue immutable SceneManifests.
    """
    file_paths = list(state.get("file_paths", []))
    conv_id = state.get("conversation_id")

    # If this is a pending input continuation (e.g. comparison awaiting second image)
    # and only the new image was uploaded in this turn, automatically pair with the original image
    if conv_id and len(file_paths) == 1 and state.get("turn_action_type") == "pending_input_continuation":
        db = SessionLocal()
        try:
            orig_ds = db.query(ConversationDataset).filter(
                ConversationDataset.conversation_id == conv_id,
                ConversationDataset.role.in_(["original", "primary"])
            ).order_by(ConversationDataset.created_at.asc()).first()
            if orig_ds and os.path.exists(orig_ds.file_path) and orig_ds.file_path not in file_paths:
                file_paths.insert(0, orig_ds.file_path)
        except Exception as e:
            logger.warning(f"Could not link previous original dataset: {e}")
        finally:
            db.close()

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
        "file_paths": file_paths,
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
    location_info = None

    if file_paths:
        facts = extract_geotiff_facts(file_paths[0])
        if task in ("location_identification", "common_location_identification", "multi_intent_location_and_change") or any(w in state.get("prompt", "").lower() for w in ["place", "city", "country", "state", "where", "location"]):
            from backend.app.services.geo_lookup import identify_location_for_scenes
            location_info = identify_location_for_scenes(file_paths)

    veg_delta = None
    if task == "spectral_index" and file_paths:
        idx_res = compute_spectral_index(file_paths[0], index_type="ndvi")
        if "error" not in idx_res:
            measurements.append(idx_res)

    elif task in ("change_detection", "change_difference_raster") and len(file_paths) >= 2:
        pair_metrics = compute_bitemporal_metrics(file_paths[0], file_paths[1])

    elif task == "temporal_vegetation_loss" and len(file_paths) >= 2:
        from backend.app.services.raster_measurements import compute_temporal_vegetation_change
        veg_delta = compute_temporal_vegetation_change(file_paths[0], file_paths[1])

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
            "temporal": pair_metrics,
            "vegetation_delta": veg_delta,
            "location": location_info
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
        if task == "raster_metadata":
            facts = meas_info.get("facts", {})
            fp = facts.get("footprint_km2")
            fp_str = f"{fp} km²" if fp is not None else "unreferenced in physical ground space"
            narrative = (
                f"The uploaded raster image covers a physical surface footprint of {fp_str} "
                f"(native pixel resolution: {facts.get('resolution_m', 'N/A')} m, Coordinate Reference System: {facts.get('crs') or 'Pixel Space'}, "
                f"dimensions: {facts.get('width', 0)} × {facts.get('height', 0)} pixels across {facts.get('bands', 0)} bands)."
            )
        elif task == "spectral_index":
            idx = meas_info.get("spectral", [{}])[0] if meas_info.get("spectral") else {}
            narrative = f"NDVI mean: {idx.get('mean', 'N/A')}, range [{idx.get('min')}, {idx.get('max')}]. Threshold exceedance: {idx.get('threshold_exceed_pct', 0)}% of valid pixels."
        elif task == "temporal_vegetation_loss":
            veg = meas_info.get("vegetation_delta") or {}
            loss_pct = veg.get("loss_pct_of_baseline", 0)
            lost_km2 = veg.get("lost_vegetation_area_km2")
            area_str = f" ({lost_km2} km²)" if lost_km2 is not None else ""
            narrative = (
                f"Comparative vegetation analysis between the earlier and later satellite observations reveals a {loss_pct}% loss "
                f"of baseline vegetation{area_str}. The primary concentration of vegetation clearance occurred in the {veg.get('primary_loss_sector', 'central')} sector."
            )
        elif task in ("location_identification", "common_location_identification"):
            from backend.app.services.geo_lookup import identify_location_for_scenes
            from backend.app.services.response_composer import compose_conversational_response
            loc = meas_info.get("location") or identify_location_for_scenes(files)
            facts = meas_info.get("facts", {})
            findings_data = {
                "query": state.get("prompt", ""),
                "location": loc,
                "common_area_km2": loc.get("common_area_km2") or facts.get("footprint_km2"),
                "crs": loc.get("crs") or facts.get("crs"),
                "resolution_m": loc.get("resolution_m") or facts.get("resolution_m")
            }
            comp = compose_conversational_response(
                query=state.get("prompt", ""),
                intent=task,
                findings_data=findings_data
            )
            narrative = comp["answer"]
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


# ---------------- Conversational Nodes ----------------

def node_classify_turn(state: RouterState) -> Dict[str, Any]:
    """
    Lightweight Turn Classifier & Intent Resolution Node.
    Inspects user prompt, conversation context, and new files to determine
    the appropriate execution path (saved_fact, map_action, explanation,
    parameter_modification, spatial_proximity, clarification, or new_analysis).
    """
    conv_id = state.get("conversation_id")
    prompt = state.get("prompt", "")
    files = state.get("file_paths", [])
    active_ctx = state.get("active_context") or {}

    # If active_context is empty but conversation_id exists, load from DB
    if conv_id and not active_ctx:
        db = SessionLocal()
        try:
            conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
            if conv and conv.active_context_json:
                active_ctx = json.loads(conv.active_context_json)
        except Exception as e:
            logger.warning(f"Could not load conversation active_context: {e}")
        finally:
            db.close()

    # If action_type was explicitly pre-specified in state, preserve it
    action_type = state.get("turn_action_type")
    details = state.get("turn_action_details") or {}

    has_new_files = state.get("has_new_files")
    if has_new_files is None:
        has_new_files = False

    if not action_type:
        action_type, details = ConversationEngine.parse_turn_intent(
            prompt=prompt,
            active_context=active_ctx,
            has_new_files=has_new_files,
            file_paths=files
        )

    return {
        "turn_action_type": action_type,
        "turn_action_details": details,
        "active_context": active_ctx
    }


def _get_active_db():
    """Returns active DB session, respecting FastAPI dependency overrides in test environments."""
    try:
        from backend.app.main import app
        from backend.app.db.session import get_db
        if hasattr(app, "dependency_overrides") and get_db in app.dependency_overrides:
            override = app.dependency_overrides[get_db]
            return next(override())
    except Exception:
        pass
    return SessionLocal()


def node_saved_fact(state: RouterState) -> Dict[str, Any]:
    """
    Saved Fact Node: Resolves verified statistical or detection facts
    from previous results without triggering redundant vision model inference.
    """
    conv_id = state.get("conversation_id")
    details = state.get("turn_action_details") or {}
    target = details.get("target_result", "current")
    metric = details.get("metric", "count")

    db = _get_active_db()
    try:
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first() if conv_id else None
        if not conv:
            res = {
                "status": "EXECUTED_ISOLATED",
                "summary": "No conversation found to retrieve facts from.",
                "findings": [],
                "validation": "skipped",
                "model": "Fact Retrieval (Deterministic)"
            }
        else:
            fact_res = ConversationEngine.execute_saved_fact(db, conv, target, metric)
            res = {
                "status": "EXECUTED_ISOLATED",
                "summary": fact_res["summary"],
                "findings": fact_res.get("findings", []),
                "sections": fact_res.get("sections", {}),
                "metrics": fact_res.get("metrics", {}),
                "validation": fact_res.get("validation", "passed"),
                "model": fact_res.get("model", "Fact Retrieval (Deterministic)")
            }
        return {"result": res}
    finally:
        db.close()


def node_map_action(state: RouterState) -> Dict[str, Any]:
    """
    Map Action Node: Resolves active result and issues structured map display command
    without triggering model inference.
    """
    conv_id = state.get("conversation_id")
    db = _get_active_db()
    try:
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first() if conv_id else None
        if not conv:
            res = {
                "status": "EXECUTED_ISOLATED",
                "summary": "No active conversation available for map actions.",
                "findings": [],
                "validation": "skipped",
                "model": "Map Controller"
            }
            return {"result": res}

        map_res = ConversationEngine.execute_map_action(db, conv)
        res = {
            "status": "EXECUTED_ISOLATED",
            "summary": map_res["summary"],
            "findings": map_res.get("findings", []),
            "maskUrl": map_res.get("maskUrl"),
            "map_action": map_res.get("map_action"),
            "validation": map_res.get("validation", "passed"),
            "model": "Map Action Controller"
        }
        return {"result": res, "map_action": map_res.get("map_action")}
    finally:
        db.close()


def node_explanation(state: RouterState) -> Dict[str, Any]:
    """
    Explanation Node: Explains evidence, methods, and observations from the active result
    without repeating GPU inference.
    """
    conv_id = state.get("conversation_id")
    db = _get_active_db()
    try:
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first() if conv_id else None
        if not conv:
            res = {
                "status": "EXECUTED_ISOLATED",
                "summary": "No previous analysis result available to explain.",
                "findings": [],
                "validation": "skipped"
            }
        else:
            exp_res = ConversationEngine.execute_explanation(db, conv)
            res = {
                "status": "EXECUTED_ISOLATED",
                "summary": exp_res["summary"],
                "findings": exp_res.get("findings", []),
                "sections": exp_res.get("sections", {}),
                "validation": exp_res.get("validation", "passed"),
                "model": "Evidence Explainer"
            }
        return {"result": res}
    finally:
        db.close()


def node_parameter_modification(state: RouterState) -> Dict[str, Any]:
    """
    Parameter Modification Node: Modifies an analytical parameter (e.g., distance threshold)
    against the original base result, creating a new derived result with lineage.
    Enforces spatial integrity checks (Section 16).
    """
    conv_id = state.get("conversation_id")
    details = state.get("turn_action_details") or {}
    param_key = details.get("parameter", "distance_m")
    val = details.get("value", 500)
    op = details.get("operation", "proximity_filter")

    db = _get_active_db()
    try:
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first() if conv_id else None
        if not conv:
            res = {
                "status": "BLOCKED",
                "summary": "No conversation found for parameter modification.",
                "validation": "failed",
                "decision_reason": "Missing conversation context."
            }
        else:
            param_res = ConversationEngine.execute_parameter_modification(
                db=db,
                conversation=conv,
                parameter_key=param_key,
                value=val,
                operation=op
            )
            res = {
                "status": "EXECUTED_ISOLATED" if param_res.get("validation") == "passed" else "BLOCKED",
                "summary": param_res["summary"],
                "findings": param_res.get("findings", []),
                "sections": param_res.get("sections", {}),
                "validation": param_res.get("validation", "passed"),
                "model": param_res.get("model", "Spatial Parameter Engine"),
                "decision_reason": param_res.get("decision_reason")
            }
        return {"result": res}
    finally:
        db.close()


def node_spatial_proximity(state: RouterState) -> Dict[str, Any]:
    """
    Spatial Proximity Gate Node: Enforces Section 16 & Requirement 7.
    Rejects unspecified proximity ("close") without distance threshold or road geometry.
    """
    conv_id = state.get("conversation_id")
    details = state.get("turn_action_details") or {}

    db = _get_active_db()
    try:
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first() if conv_id else None
        if not conv:
            res = {
                "status": "BLOCKED",
                "summary": "No active conversation context for spatial proximity query.",
                "validation": "failed"
            }
        else:
            prox_res = ConversationEngine.handle_spatial_proximity_query(db, conv, details)
            res = {
                "status": "EXECUTED_ISOLATED" if prox_res.get("validation") == "passed" else "BLOCKED",
                "summary": prox_res["summary"],
                "findings": prox_res.get("findings", []),
                "sections": prox_res.get("sections", {}),
                "validation": prox_res.get("validation", "failed"),
                "model": prox_res.get("model", "Spatial Proximity Validator"),
                "decision_reason": prox_res.get("decision_reason")
            }
        return {"result": res}
    finally:
        db.close()


def node_clarification(state: RouterState) -> Dict[str, Any]:
    """
    Clarification Node: Emits a structured request for missing input (e.g. comparison image)
    and records the pending task in the conversation.
    """
    conv_id = state.get("conversation_id")
    details = state.get("turn_action_details") or {}
    msg = details.get("message", "Clarification requested.")
    pending = details.get("pending_task")

    # Persist pending_task into conversation active_context
    if conv_id and pending:
        db = _get_active_db()
        try:
            conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
            if conv:
                ctx = json.loads(conv.active_context_json or "{}")
                ctx["pending_task"] = pending
                conv.active_context_json = json.dumps(ctx)
                db.commit()
        except Exception as e:
            logger.warning(f"Failed to record pending_task: {e}")
        finally:
            db.close()

    res = {
        "status": "NEEDS_INPUT",
        "summary": msg,
        "findings": [],
        "validation": "skipped",
        "pending_task": pending,
        "model": "Conversation Controller",
        "decision_reason": "Awaiting second comparison image."
    }
    return {"result": res, "pending_task": pending}


def node_conversational_followup(state: RouterState) -> Dict[str, Any]:
    """
    Conversational Follow-Up Node: Composes a query-focused, evidence-grounded
    natural-language answer to follow-up questions using existing findings without
    re-running redundant GPU vision models.
    """
    conv_id = state.get("conversation_id")
    prompt = state.get("prompt", "")
    db = _get_active_db()
    try:
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first() if conv_id else None
        if not conv:
            res = {
                "status": "EXECUTED_ISOLATED",
                "summary": "No active conversation available for conversational follow-up.",
                "supporting_findings": [],
                "findings": [],
                "validation": "skipped",
                "model": "SatQuery Conversational AI"
            }
        else:
            followup_res = ConversationEngine.execute_conversational_followup(db, conv, prompt)
            res = {
                "status": "EXECUTED_ISOLATED",
                "summary": followup_res["summary"],
                "supporting_findings": followup_res.get("supporting_findings", []),
                "findings": followup_res.get("findings", []),
                "sections": followup_res.get("sections", {}),
                "validation": followup_res.get("validation", "passed"),
                "result_id": followup_res.get("result_id"),
                "model": followup_res.get("model", "SatQuery Conversational AI")
            }
        return {"result": res, "summary": res["summary"]}
    finally:
        db.close()


def route_turn_path(state: RouterState) -> str:
    """Conditional router function directing the turn to the appropriate branch."""
    action = state.get("turn_action_type", "new_analysis")
    if action == "saved_fact":
        return "saved_fact"
    elif action == "map_action":
        return "map_action"
    elif action == "explanation":
        return "explanation"
    elif action == "conversational_followup":
        return "conversational_followup"
    elif action == "parameter_modification":
        return "parameter_modification"
    elif action == "spatial_proximity":
        return "spatial_proximity"
    elif action == "clarification":
        return "clarification"
    return "sift_and_validate"


# Construct StateGraph with Conversational Intelligence & Scientific Pipeline
builder = StateGraph(RouterState)

# Conversational routing nodes
builder.add_node("classify_turn", node_classify_turn)
builder.add_node("saved_fact", node_saved_fact)
builder.add_node("map_action", node_map_action)
builder.add_node("explanation", node_explanation)
builder.add_node("conversational_followup", node_conversational_followup)
builder.add_node("parameter_modification", node_parameter_modification)
builder.add_node("spatial_proximity", node_spatial_proximity)
builder.add_node("clarification", node_clarification)

# Scientific analytical pipeline nodes
builder.add_node("sift_and_validate", node_sift_and_validate)
builder.add_node("route_decision", node_route_decision)
builder.add_node("raster_measurements", node_raster_measurements)
builder.add_node("dispatch_or_execute", node_dispatch_or_execute)

# Entry point & conditional branches
builder.set_entry_point("classify_turn")

builder.add_conditional_edges(
    "classify_turn",
    route_turn_path,
    {
        "saved_fact": "saved_fact",
        "map_action": "map_action",
        "explanation": "explanation",
        "conversational_followup": "conversational_followup",
        "parameter_modification": "parameter_modification",
        "spatial_proximity": "spatial_proximity",
        "clarification": "clarification",
        "sift_and_validate": "sift_and_validate",
    }
)

# Terminal edges for conversational actions
builder.add_edge("saved_fact", END)
builder.add_edge("map_action", END)
builder.add_edge("explanation", END)
builder.add_edge("conversational_followup", END)
builder.add_edge("parameter_modification", END)
builder.add_edge("spatial_proximity", END)
builder.add_edge("clarification", END)

# Sequential edges for analytical pipeline
builder.add_edge("sift_and_validate", "route_decision")
builder.add_edge("route_decision", "raster_measurements")
builder.add_edge("raster_measurements", "dispatch_or_execute")
builder.add_edge("dispatch_or_execute", END)

task_router_app = builder.compile()

