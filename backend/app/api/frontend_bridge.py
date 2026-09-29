"""
Frontend Bridge API Routes.

Provides unified endpoints that the new React frontend expects.
These routes translate between the frontend's contract and the existing
backend infrastructure (LangGraph router, RQ workers, model registry).
Supports both multipart form data (with file attachments) and application/json.
"""

import os
import re
import json
import uuid
import time
import shutil
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from backend.app.config import settings
from backend.app.db.session import get_db, check_db_connection
from backend.app.db.models import (
    User,
    Conversation,
    ConversationMessage,
    ConversationTurn,
    ConversationDataset,
    ConversationResult
)
from backend.app.auth import get_current_user
from backend.app.models_registry import list_models, get_capabilities
from backend.app.router import task_router_app
from backend.app.worker import get_redis_connection, check_redis_connection
from backend.app.services.conversation_service import (
    ConversationEngine,
    extract_count_from_summary_or_findings
)
from backend.app.services.routing import (
    create_scene_manifest,
    create_pair_manifest,
    parse_user_intent,
    decide_route
)
from backend.app.services.raster_measurements import (
    extract_geotiff_facts,
    build_evidence_bundle,
    format_scientific_sections
)

router = APIRouter()

UPLOAD_DIR = os.path.join(settings.SATQUERY_STORAGE_ROOT, "uploads")
SCRATCH_DIR = os.path.join(settings.SATQUERY_STORAGE_ROOT, "scratch")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(SCRATCH_DIR, exist_ok=True)


async def parse_request_data_and_files(request: Request) -> Tuple[Dict[str, Any], List[str]]:
    """
    Parses request body whether sent as application/json or multipart/form-data.
    Saves uploaded files to disk and returns (parsed_dict, list_of_saved_file_paths).
    """
    content_type = request.headers.get("content-type", "")
    file_paths: List[str] = []
    data: Dict[str, Any] = {}

    if "multipart/form-data" in content_type or "application/x-www-form-urlencoded" in content_type:
        form = await request.form()
        raw_payload = form.get("payload")
        if raw_payload and isinstance(raw_payload, str):
            try:
                data = json.loads(raw_payload)
            except json.JSONDecodeError:
                data = {}
        uploaded_files = []
        for k, v in form.items():
            if k == "payload":
                continue
            if hasattr(v, "filename") and v.filename:
                uploaded_files.append(v)
            elif isinstance(v, str):
                data[k] = v

        # Also check getlist for common keys in case of multiple files under the same key
        for list_key in ("images", "files", "file", "image"):
            for uf in form.getlist(list_key):
                if hasattr(uf, "filename") and uf.filename and uf not in uploaded_files:
                    uploaded_files.append(uf)

        for uf in uploaded_files:
            if not uf.filename:
                continue
            ext = os.path.splitext(uf.filename)[1].lower()
            if ext and ext not in ('.png', '.jpg', '.jpeg', '.tif', '.tiff', '.webp', '.bmp', '.jp2'):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported file format '{ext}'. Supported formats: .tif, .tiff, .png, .jpg, .jpeg, .webp, .bmp, .jp2."
                )
            save_name = f"{uuid.uuid4().hex}_{uf.filename}"
            save_path = os.path.join(UPLOAD_DIR, save_name)
            content = await uf.read()
            with open(save_path, "wb") as f:
                f.write(content)
            file_paths.append(save_path)
    else:
        try:
            data = await request.json()
            if isinstance(data, dict):
                json_files = data.get("file_paths") or data.get("files") or []
                if isinstance(json_files, list):
                    file_paths.extend([f for f in json_files if isinstance(f, str) and os.path.exists(f)])
        except Exception:
            data = {}

    return data, file_paths


async def poll_job_or_format(
    result: Dict[str, Any],
    target_model_id: str,
    timeout_seconds: float = 25.0,
    fallback_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Formats the task router execution result into the frontend AnalysisResponse.
    If the task was queued to an RQ worker, polls briefly for completion so that
    fast tasks return their real outputs synchronously to the user interface.
    If the worker is not active or times out, immediately falls back to direct
    synchronous execution so the user always receives a genuine answer.
    """
    result_status = result.get("status", "UNKNOWN")
    response: Dict[str, Any] = {
        "summary": "",
        "findings": [],
        "model": target_model_id or "unknown",
        "validation": "passed" if result_status in ("QUEUED_IN_RQ_WORKER", "EXECUTED_ISOLATED") else "skipped",
    }

    if result_status == "QUEUED_IN_RQ_WORKER":
        job_id = result.get("job_id", "")
        if job_id:
            try:
                from rq.job import Job
                from rq import Worker
                redis_conn = get_redis_connection()
                active_workers = Worker.all(connection=redis_conn)
                if not active_workers:
                    logger.info("No active RQ workers registered on Redis queue. Executing local fallback immediately without delay.")
                else:
                    poll_limit = min(timeout_seconds, 6.0)
                    steps = int(poll_limit / 0.25)
                    for _ in range(steps):
                        await asyncio.sleep(0.25)
                        try:
                            job = Job.fetch(job_id, connection=redis_conn)
                            if job.is_finished:
                                exec_result = job.result
                                if isinstance(exec_result, dict):
                                    meta = exec_result.get("output_metadata", {})
                                    response["summary"] = (
                                        exec_result.get("summary") or
                                        meta.get("answer") or
                                        meta.get("summary") or
                                        exec_result.get("answer") or
                                        str(meta or exec_result)
                                    )
                                    if exec_result.get("findings"):
                                        response["findings"] = exec_result["findings"]
                                    else:
                                        if "predictions" in meta:
                                            for pred in meta.get("predictions", []):
                                                response["findings"].append({
                                                    "label": pred.get("label", "Detection"),
                                                    "detail": f"Score: {pred.get('score', 'N/A')}",
                                                    "confidence": pred.get("score")
                                                })
                                        if "classes" in meta:
                                            for cls_name, cls_val in meta.get("classes", {}).items():
                                                response["findings"].append({
                                                    "label": cls_name,
                                                    "detail": f"Probability: {cls_val}",
                                                })

                                    if exec_result.get("sections"):
                                        response["sections"] = exec_result["sections"]

                                    if exec_result.get("participating_models"):
                                        response["model"] = " + ".join(exec_result["participating_models"])

                                    metrics_data = exec_result.get("metrics") or {}
                                    if hasattr(metrics_data, "model_dump"):
                                        metrics_data = metrics_data.model_dump()
                                    elif not isinstance(metrics_data, dict):
                                        metrics_data = {"status": "completed"}
                                    metrics_data["status"] = "completed"
                                    response["metrics"] = metrics_data

                                    current_task = str((fallback_params or {}).get("task") or result.get("task") or "")
                                    assets = exec_result.get("output_assets", {})
                                    if "change_mask" in assets:
                                        mask_rel = Path(assets["change_mask"]).name
                                        response["maskUrl"] = f"/api/assets/{mask_rel}"
                                    elif "grounding_overlay" in assets:
                                        mask_rel = Path(assets["grounding_overlay"]).name
                                        response["maskUrl"] = f"/api/assets/{mask_rel}"
                                    elif "segmentation_mask" in assets and current_task.lower() in ("segmentation", "landcover", "land_cover", "classification"):
                                        mask_rel = Path(assets["segmentation_mask"]).name
                                        response["maskUrl"] = f"/api/assets/{mask_rel}"
                                break
                            elif job.is_failed:
                                logger.warning(f"Worker job {job_id} reported failure: {job.exc_info}. Executing direct fallback.")
                                break
                        except Exception:
                            pass
            except Exception:
                pass

        if not response.get("summary"):
            if fallback_params:
                logger.info("Worker did not return in time or queue was idle. Executing multi-model pipeline synchronously.")
                from backend.app.services.multi_model_pipeline import run_multi_model_pipeline
                fallback_res = run_multi_model_pipeline(
                    file_paths=fallback_params.get("file_paths", []),
                    prompt=fallback_params.get("prompt", "Analyze this imagery."),
                    pair_type=fallback_params.get("pair_type", "single_image"),
                    user_intent=fallback_params.get("task", "scene_description"),
                    diagnostic_override=fallback_params.get("diagnostic_override")
                )
                response["summary"] = fallback_res.get("summary", "")
                response["supporting_findings"] = fallback_res.get("supporting_findings", [])
                response["findings"] = fallback_res.get("findings", [])
                response["sections"] = fallback_res.get("sections", {})
                if fallback_res.get("participating_models"):
                    response["model"] = " + ".join(fallback_res["participating_models"])
                response["metrics"] = {"status": "completed"}
                current_task = str((fallback_params or {}).get("task") or result.get("task") or "")
                assets = fallback_res.get("output_assets", {})
                if "change_mask" in assets:
                    mask_rel = Path(assets["change_mask"]).name
                    response["maskUrl"] = f"/api/assets/{mask_rel}"
                elif "grounding_overlay" in assets:
                    mask_rel = Path(assets["grounding_overlay"]).name
                    response["maskUrl"] = f"/api/assets/{mask_rel}"
                elif "segmentation_mask" in assets and current_task.lower() in ("segmentation", "landcover", "land_cover", "classification"):
                    mask_rel = Path(assets["segmentation_mask"]).name
                    response["maskUrl"] = f"/api/assets/{mask_rel}"
            else:
                response["summary"] = f"Analysis job queued successfully. Model: {result.get('model', 'unknown')}. Job ID: {job_id}"
                response["metrics"] = {"job_id": job_id, "status": "queued"}

    elif result_status == "EXECUTED_ISOLATED":
        exec_result = result.get("execution_result", {})
        if isinstance(exec_result, dict):
            meta = exec_result.get("output_metadata", {})
            response["summary"] = (
                result.get("summary") or
                exec_result.get("summary") or
                meta.get("answer") or
                meta.get("summary") or
                exec_result.get("answer") or
                str(meta or exec_result)
            )
            if exec_result.get("findings"):
                response["findings"] = exec_result["findings"]
            elif result.get("findings"):
                response["findings"] = result["findings"]
            else:
                for pred in (meta.get("predictions") or exec_result.get("predictions", [])):
                    response["findings"].append({
                        "label": pred.get("label", "Detection"),
                        "detail": f"Score: {pred.get('score', 'N/A')}",
                        "confidence": pred.get("score")
                    })
                for cls_name, cls_val in (meta.get("classes") or exec_result.get("classes", {})).items():
                    response["findings"].append({
                        "label": cls_name,
                        "detail": f"Probability: {cls_val}",
                    })

            if exec_result.get("sections"):
                response["sections"] = exec_result["sections"]
            elif result.get("sections"):
                response["sections"] = result["sections"]

            if exec_result.get("supporting_findings"):
                response["supporting_findings"] = exec_result["supporting_findings"]
            elif result.get("supporting_findings"):
                response["supporting_findings"] = result["supporting_findings"]

            if exec_result.get("participating_models"):
                response["model"] = " + ".join(exec_result["participating_models"])
            elif result.get("participating_models"):
                response["model"] = " + ".join(result["participating_models"])

            current_task = str((fallback_params or {}).get("task") or result.get("task") or "")
            assets = exec_result.get("output_assets", {}) or result.get("output_assets", {})
            if "change_mask" in assets:
                mask_rel = Path(assets["change_mask"]).name
                response["maskUrl"] = f"/api/assets/{mask_rel}"
            elif "grounding_overlay" in assets:
                mask_rel = Path(assets["grounding_overlay"]).name
                response["maskUrl"] = f"/api/assets/{mask_rel}"
            elif "segmentation_mask" in assets and current_task.lower() in ("segmentation", "landcover", "land_cover", "classification"):
                mask_rel = Path(assets["segmentation_mask"]).name
                response["maskUrl"] = f"/api/assets/{mask_rel}"
        else:
            response["summary"] = str(result.get("summary") or exec_result)
        response["metrics"] = {"status": "completed"}
    elif result_status in ("TRAINING_REQUIRED", "INSTALLED_BUT_NOT_RUNNABLE_LOCALLY"):
        response["summary"] = result.get("message", "Model is not currently available.")
        response["validation"] = "failed"
    else:
        response["summary"] = result.get("message", f"Task dispatched with status: {result_status}")

    # Pass scientific evidence sections if available
    if "sections" in result and not response.get("sections"):
        response["sections"] = result["sections"]
    elif result.get("evidence_bundle") and not response.get("sections"):
        response["sections"] = format_scientific_sections(
            result["evidence_bundle"],
            response.get("summary", ""),
            result.get("model", target_model_id or "Vision Model")
        )

    # Populate findings from measured raster facts if findings list was empty
    if response.get("sections") and not response.get("findings") and "measured_from_raster" in response["sections"]:
        for item in response["sections"]["measured_from_raster"]:
            parts = item.split(":", 1)
            label = parts[0].strip() if len(parts) > 1 else "Raster Fact"
            detail = parts[1].strip() if len(parts) > 1 else item
            response["findings"].append({
                "label": label,
                "detail": detail,
                "confidence": 1.0
            })

    if "decision_reason" in result:
        response["decision_reason"] = result["decision_reason"]

    return response


# ----- /api/route-preview -----

@router.post("/route-preview")
async def frontend_route_preview(
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Lightweight route preview API before execution.
    Inspects input files/metadata and query intent, returning:
    selected_task, input_type, automatic_route, available, blocked_reasons, decision_reason.
    No GPU model loads for this preview.
    """
    data, file_paths = await parse_request_data_and_files(request)
    prompt = data.get("prompt") or data.get("query") or "Describe this satellite scene."
    override = data.get("model") or None

    manifests = [create_scene_manifest(p) for p in file_paths if os.path.exists(p)]
    pair = None
    if len(manifests) >= 2:
        pair = create_pair_manifest(manifests[0], manifests[1])

    task_req = parse_user_intent(prompt, manifests, pair, diagnostic_override=override)
    decision = decide_route(manifests, pair, task_req)

    return {
        "selected_task": decision.task,
        "input_type": manifests[0].modality if manifests else "query_only",
        "sensor": manifests[0].sensor if manifests else "None",
        "georeferenced": manifests[0].georeferencing_mode in ("projected", "geographic") if manifests else False,
        "automatic_route": decision.automatic_route,
        "available": len(decision.blocked_reasons) == 0,
        "blocked_reasons": decision.blocked_reasons,
        "decision_reason": decision.decision_reason,
        "model": decision.selected_adapter_or_none,
        "fallback_measurements": decision.fallback_measurements,
        "estimated_resources": decision.estimated_resources
    }


# ----- /api/analysis -----

@router.post("/analysis")
async def frontend_analysis(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Bridge endpoint for frontend analysis.
    Accepts multipart/form-data (with file uploads) or application/json.
    Dispatches through the LangGraph task router and awaits worker completion.
    """
    data, file_paths = await parse_request_data_and_files(request)
    conv_id = data.get("conversation_id")
    if conv_id:
        return await execute_conversation_turn(conversation_id=conv_id, request=request, db=db)


    task = data.get("task", "internvl")
    prompt = data.get("prompt", "Analyze this satellite imagery.")
    pair_type = data.get("pair_type", "single_image")
    target_model_id = data.get("model", "")

    has_geotiff = any(p.lower().endswith((".tif", ".tiff")) for p in file_paths)
    input_cat = "geotiff" if has_geotiff else ("benchmark" if file_paths else "query")

    state_input = {
        "task": task,
        "input_category": input_cat,
        "file_paths": file_paths,
        "prompt": prompt,
        "pair_type": pair_type if len(file_paths) >= 2 else "single_image",
        "target_model_id": target_model_id,
        "validation_info": {},
        "dispatch_mode": "worker",
        "result": {}
    }

    routed = task_router_app.invoke(state_input)
    model_id = routed.get("target_model_id", target_model_id or "unknown")
    result = routed.get("result", {})
    fallback_params = {
        "file_paths": file_paths,
        "prompt": prompt,
        "pair_type": pair_type if len(file_paths) >= 2 else "single_image",
        "task": task,
        "diagnostic_override": target_model_id or None
    }
    return await poll_job_or_format(result, model_id, fallback_params=fallback_params)


# ----- /api/change-detection -----

@router.post("/change-detection")
async def frontend_change_detection(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Change detection bridge. Dispatches as change_detection task.
    """
    data, file_paths = await parse_request_data_and_files(request)
    prompt = data.get("prompt", "Detect changes between these satellite images.")

    has_geotiff = any(p.lower().endswith((".tif", ".tiff")) for p in file_paths)
    input_cat = "geotiff" if has_geotiff else ("benchmark" if file_paths else "query")

    state_input = {
        "task": "change_detection",
        "input_category": input_cat,
        "file_paths": file_paths,
        "prompt": prompt,
        "pair_type": "bitemporal" if len(file_paths) >= 2 else "single_image",
        "target_model_id": data.get("model", ""),
        "validation_info": {},
        "dispatch_mode": "worker",
        "result": {}
    }

    routed = task_router_app.invoke(state_input)
    model_id = routed.get("target_model_id", "changeformer")
    result = routed.get("result", {})

    fallback_params = {
        "file_paths": file_paths,
        "prompt": prompt,
        "pair_type": "bitemporal" if len(file_paths) >= 2 else "single_image",
        "task": "change_detection",
        "diagnostic_override": data.get("model") or None
    }
    return await poll_job_or_format(result, model_id, fallback_params=fallback_params)


# ----- /api/prediction -----

@router.post("/prediction")
async def frontend_prediction(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Prediction bridge for object detection / visual grounding / segmentation tasks.
    """
    data, file_paths = await parse_request_data_and_files(request)
    task = data.get("task", "visual_grounding")
    prompt = data.get("prompt", "Find objects or detect features in this image.")

    has_geotiff = any(p.lower().endswith((".tif", ".tiff")) for p in file_paths)
    input_cat = "geotiff" if has_geotiff else ("benchmark" if file_paths else "query")

    state_input = {
        "task": task,
        "input_category": input_cat,
        "file_paths": file_paths,
        "prompt": prompt,
        "pair_type": "single_image",
        "target_model_id": data.get("model", ""),
        "validation_info": {},
        "dispatch_mode": "worker",
        "result": {}
    }

    routed = task_router_app.invoke(state_input)
    model_id = routed.get("target_model_id", "geoground")
    result = routed.get("result", {})

    fallback_params = {
        "file_paths": file_paths,
        "prompt": prompt,
        "pair_type": "single_image",
        "task": task,
        "diagnostic_override": data.get("model") or None
    }
    return await poll_job_or_format(result, model_id, fallback_params=fallback_params)


# ----- /api/search (STAC proxy) -----

@router.post("/search")
async def frontend_search(body: Dict[str, Any]):
    """
    Proxies STAC search requests to the Copernicus Data Space STAC API.
    """
    import httpx

    stac_url = "https://stac.dataspace.copernicus.eu/v1/search"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(stac_url, json=body)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        return JSONResponse(
            content={"error": str(e), "features": []},
            status_code=502
        )


# ----- /api/imagery, /api/optical, /api/sar -----

@router.post("/imagery")
@router.post("/optical")
@router.post("/sar")
async def frontend_imagery(body: Dict[str, Any]):
    """
    Imagery endpoint metadata stub for Sentinel Hub / GIBS tile layers.
    """
    return {
        "tileUrl": None,
        "imageUrl": None,
        "bounds": body.get("bbox"),
        "acquired": body.get("date"),
        "note": "Imagery is rendered via direct tile layer URLs configured in the frontend. "
                "Use the STAC search to find specific scenes."
    }


# ----- /api/worker-status & /api/system-status -----

@router.get("/worker-status")
def get_worker_status():
    """
    Provides real-time RQ worker and queue metrics.
    """
    try:
        r = get_redis_connection()
        r.ping()
        from rq import Worker, Queue
        workers = Worker.all(connection=r)
        q = Queue(settings.RQ_QUEUE_NAME, connection=r)
        return {
            "status": "online",
            "redis_connected": True,
            "queue_name": settings.RQ_QUEUE_NAME,
            "jobs_queued": len(q),
            "workers_active": len(workers),
            "worker_names": [w.name for w in workers]
        }
    except Exception as e:
        return {
            "status": "degraded",
            "redis_connected": False,
            "error": str(e)
        }


@router.get("/system-status")
def get_system_status():
    """
    Unified system health summary for database, redis, workers, and hardware.
    """
    db_ok = check_db_connection()
    redis_ok = check_redis_connection()
    return {
        "status": "healthy" if db_ok.get("connected") and redis_ok.get("connected") else "degraded",
        "database": db_ok,
        "redis": redis_ok,
        "hardware": {
            "gpu_name": "NVIDIA GeForce RTX 5060 Laptop GPU",
            "vram_limit_mb": 7680,
            "cuda_available": True
        }
    }


def generate_raster_preview(tif_path: str) -> Optional[str]:
    """
    Generates an 8-bit normalized PNG preview for multi-band, floating-point, or SAR GeoTIFFs.
    Uses out_shape downsampled read to avoid memory overhead on large rasters,
    and 2nd-98th percentile stretching per band for scientific contrast.
    """
    thumb_dir = os.path.join(SCRATCH_DIR, "thumbs")
    os.makedirs(thumb_dir, exist_ok=True)
    thumb_path = os.path.join(thumb_dir, f"{Path(tif_path).name}.png")
    if os.path.isfile(thumb_path) and os.path.getsize(thumb_path) > 0:
        return thumb_path

    try:
        import rasterio
        from rasterio.enums import Resampling
        from PIL import Image
        import numpy as np

        with rasterio.open(tif_path) as src:
            count = src.count
            orig_w, orig_h = src.width, src.height
            max_dim = 1280
            if orig_w > max_dim or orig_h > max_dim:
                scale = max_dim / max(orig_w, orig_h)
                target_w = max(64, int(orig_w * scale))
                target_h = max(64, int(orig_h * scale))
            else:
                target_w, target_h = orig_w, orig_h

            nodata = src.nodata

            if count >= 3:
                # Select optical RGB bands
                if count >= 12:
                    # Sentinel-2: Band 4 (Red), Band 3 (Green), Band 2 (Blue)
                    band_idx = [4, 3, 2]
                else:
                    band_idx = [1, 2, 3]

                arr = src.read(band_idx, out_shape=(3, target_h, target_w), resampling=Resampling.bilinear)
                channels = []
                for c in range(3):
                    ch = arr[c].astype(np.float32)
                    valid_mask = np.isfinite(ch)
                    if nodata is not None:
                        valid_mask &= (ch != nodata)
                    valid = ch[valid_mask]
                    if len(valid) > 10:
                        p2, p98 = np.percentile(valid, (2, 98))
                        if p98 > p2:
                            scaled = np.clip((ch - p2) / (p98 - p2) * 255.0, 0, 255).astype(np.uint8)
                        else:
                            scaled = np.zeros_like(ch, dtype=np.uint8)
                    else:
                        scaled = np.clip(ch, 0, 255).astype(np.uint8)
                    channels.append(scaled)

                rgb = np.stack(channels, axis=-1)
                img = Image.fromarray(rgb, mode="RGB")

            elif count == 2:
                # Dual polarization SAR (e.g. VV / VH)
                arr = src.read(1, out_shape=(target_h, target_w), resampling=Resampling.bilinear).astype(np.float32)
                valid_mask = np.isfinite(arr)
                if nodata is not None:
                    valid_mask &= (arr != nodata)
                valid = arr[valid_mask]
                if len(valid) > 10:
                    p2, p98 = np.percentile(valid, (2, 98))
                    if p98 > p2:
                        scaled = np.clip((arr - p2) / (p98 - p2) * 255.0, 0, 255).astype(np.uint8)
                    else:
                        scaled = np.zeros_like(arr, dtype=np.uint8)
                else:
                    scaled = np.clip(arr, 0, 255).astype(np.uint8)
                img = Image.fromarray(scaled, mode="L")

            else:
                # Single band (Grayscale, SAR, Elevation, Index)
                arr = src.read(1, out_shape=(target_h, target_w), resampling=Resampling.bilinear).astype(np.float32)
                valid_mask = np.isfinite(arr)
                if nodata is not None:
                    valid_mask &= (arr != nodata)
                valid = arr[valid_mask]
                if len(valid) > 10:
                    p2, p98 = np.percentile(valid, (2, 98))
                    if p98 > p2:
                        scaled = np.clip((arr - p2) / (p98 - p2) * 255.0, 0, 255).astype(np.uint8)
                    else:
                        scaled = np.zeros_like(arr, dtype=np.uint8)
                else:
                    scaled = np.clip(arr, 0, 255).astype(np.uint8)
                img = Image.fromarray(scaled, mode="L")

            img.save(thumb_path, format="PNG")
            return thumb_path
    except Exception as e:
        logger.warning(f"Could not generate raster thumbnail for {tif_path}: {e}")
        return None


def cleanup_old_scratch_files(max_age_hours: int = 24) -> None:
    """Evicts scratch directories older than max_age_hours to prevent unbounded disk growth."""
    try:
        now = time.time()
        cutoff = now - (max_age_hours * 3600)
        scratch_p = Path(SCRATCH_DIR)
        if not scratch_p.exists():
            return
        for item in scratch_p.iterdir():
            if item.name == "thumbs":
                continue
            if item.is_dir():
                mtime = item.stat().st_mtime
                if mtime < cutoff:
                    shutil.rmtree(item, ignore_errors=True)
    except Exception as e:
        logger.debug(f"Scratch cleanup skipped: {e}")


# ----- Output Asset Serving & GeoTIFF Preview -----

@router.get("/assets/{file_path:path}")
def get_asset_file(file_path: str, preview: Optional[bool] = None, raw: Optional[bool] = None):
    """
    Serves generated output masks or images from the storage scratch or uploads directory.
    Automatically generates 8-bit PNG previews for GeoTIFFs so browsers can render thumbnails natively.
    """
    found_candidate = None
    for candidate in [
        os.path.join(SCRATCH_DIR, file_path),
        os.path.join(UPLOAD_DIR, file_path)
    ]:
        if os.path.isfile(candidate):
            found_candidate = candidate
            break

    if not found_candidate:
        matches = list(Path(SCRATCH_DIR).glob(f"**/{file_path}"))
        if matches and matches[0].is_file():
            found_candidate = str(matches[0])

    if not found_candidate:
        matches_up = list(Path(UPLOAD_DIR).glob(f"**/{file_path}"))
        if matches_up and matches_up[0].is_file():
            found_candidate = str(matches_up[0])

    if not found_candidate:
        raise HTTPException(status_code=404, detail="Asset not found")

    is_tif = found_candidate.lower().endswith((".tif", ".tiff"))
    if is_tif and not raw:
        preview_png = generate_raster_preview(found_candidate)
        if preview_png and os.path.isfile(preview_png):
            return FileResponse(preview_png, media_type="image/png")

    return FileResponse(found_candidate)


@router.post("/geotiff/preview")
async def preview_geotiff(request: Request):
    """
    Accepts an uploaded GeoTIFF file or file_path reference, generates a visual PNG preview,
    extracts metadata (CRS, bounds, dimensions, bands), and returns unified asset representation.
    """
    parsed_data, saved_paths = await parse_request_data_and_files(request)

    target_path = None
    if saved_paths:
        target_path = saved_paths[0]
    elif parsed_data.get("file_path"):
        cand = parsed_data["file_path"]
        if os.path.isfile(cand):
            target_path = cand
        elif os.path.isfile(os.path.join(UPLOAD_DIR, cand)):
            target_path = os.path.join(UPLOAD_DIR, cand)
        elif os.path.isfile(os.path.join(SCRATCH_DIR, cand)):
            target_path = os.path.join(SCRATCH_DIR, cand)

    if not target_path or not os.path.isfile(target_path):
        raise HTTPException(status_code=400, detail="No GeoTIFF file uploaded or found.")

    facts = extract_geotiff_facts(target_path)
    preview_png = generate_raster_preview(target_path)
    filename = Path(target_path).name

    is_sar = False
    name_lower = filename.lower()
    sensor_lower = str(facts.get("sensor_inferred", "")).lower()
    if any(k in name_lower or k in sensor_lower for k in ("sar", "sentinel-1", "s1", "nisar", "grd", "slc")):
        is_sar = True

    preview_url = f"/api/assets/thumbs/{filename}.png" if preview_png else f"/api/assets/{filename}?preview=true"

    return {
        "status": "success",
        "filename": filename,
        "file_path": target_path,
        "preview_url": preview_url,
        "previewUrl": preview_url,
        "width": facts.get("width", 0),
        "height": facts.get("height", 0),
        "bands": facts.get("bands", 1),
        "crs": facts.get("crs"),
        "bounds": facts.get("bounds"),
        "resolution_m": facts.get("resolution_m"),
        "sensor": facts.get("sensor_inferred"),
        "is_sar": is_sar,
        "isSar": is_sar,
        "is_georeferenced": facts.get("is_georeferenced", False)
    }


# =============================================================
# Multi-Turn Conversational Analyst API Endpoints
# =============================================================

@router.get("/conversations")
def list_conversations(
    db: Session = Depends(get_db)
):
    """
    Lists persisted analyst conversations ordered by most recent update.
    Returns title, timestamps, message count, and active pending tasks.
    """
    convs = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    output = []
    for c in convs:
        msg_count = db.query(ConversationMessage).filter(ConversationMessage.conversation_id == c.id).count()
        ds_count = db.query(ConversationDataset).filter(ConversationDataset.conversation_id == c.id).count()
        ctx = json.loads(c.active_context_json or "{}")
        output.append({
            "id": c.id,
            "title": c.title,
            "state_revision": c.state_revision,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "updated_at": c.updated_at.isoformat() if c.updated_at else None,
            "message_count": msg_count,
            "dataset_count": ds_count,
            "pending_task": ctx.get("pending_task")
        })
    return output


@router.post("/conversations")
async def create_conversation(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Creates a new persistent conversation identity.
    Avoids duplicate creation if client passes an existing conversation_id.
    """
    data, _ = await parse_request_data_and_files(request)
    conv_id = data.get("id") or data.get("conversation_id") or str(uuid.uuid4())
    title = data.get("title") or "New Analysis Conversation"
    conv = ConversationEngine.get_or_create_conversation(db, conversation_id=conv_id, title=title)
    conv_dict = {
        "id": conv.id,
        "title": conv.title,
        "state_revision": conv.state_revision,
        "created_at": conv.created_at.isoformat() if conv.created_at else None,
        "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
    }
    return {
        **conv_dict,
        "conversation": conv_dict,
        "messages": [],
        "datasets": [],
        "active_context": json.loads(conv.active_context_json or "{}"),
        "pending_task": None,
        "latest_map_action": None
    }


@router.get("/conversations/{conversation_id}")
def get_conversation_snapshot(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """
    Returns the canonical snapshot of a conversation:
    Persisted messages, dataset associations, active analytical context,
    pending comparison tasks, and durable map state.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail=f"Conversation '{conversation_id}' not found.")

    messages = db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == conversation_id
    ).order_by(ConversationMessage.created_at.asc()).all()

    datasets = db.query(ConversationDataset).filter(
        ConversationDataset.conversation_id == conversation_id
    ).order_by(ConversationDataset.created_at.asc()).all()

    active_context = json.loads(conv.active_context_json or "{}")

    formatted_messages = []
    for m in messages:
        meta = json.loads(m.metadata_json or "{}") if m.metadata_json else {}
        formatted_messages.append({
            "id": m.id,
            "conversation_id": m.conversation_id,
            "turn_id": m.turn_id,
            "role": m.role,
            "content": m.content,
            "client_request_id": m.client_request_id,
            "created_at": m.created_at.isoformat() if m.created_at else None,
            "metadata": meta,
            "summary": meta.get("summary") or (m.content if m.role == "assistant" else None),
            "supporting_findings": meta.get("supporting_findings", []),
            "findings": meta.get("findings", []),
            "sections": meta.get("sections", {}),
            "model": meta.get("model", ""),
            "maskUrl": meta.get("maskUrl"),
            "mapAction": meta.get("mapAction"),
            "validation": meta.get("validation", "passed")
        })

    formatted_datasets = []
    for d in datasets:
        formatted_datasets.append({
            "id": d.id,
            "file_name": d.file_name,
            "file_path": d.file_path,
            "role": d.role,
            "file_size": d.file_size,
            "mime_type": d.mime_type,
            "acquisition_date": d.acquisition_date.isoformat() if d.acquisition_date else None,
            "created_at": d.created_at.isoformat() if d.created_at else None
        })

    return {
        "conversation": {
            "id": conv.id,
            "title": conv.title,
            "state_revision": conv.state_revision,
            "created_at": conv.created_at.isoformat() if conv.created_at else None,
            "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
        },
        "messages": formatted_messages,
        "datasets": formatted_datasets,
        "active_context": active_context,
        "pending_task": active_context.get("pending_task"),
        "latest_map_action": active_context.get("map_state")
    }


@router.delete("/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db)
):
    """Deletes conversation and associated database entities."""
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found.")

    db.query(ConversationMessage).filter(ConversationMessage.conversation_id == conversation_id).delete()
    db.query(ConversationTurn).filter(ConversationTurn.conversation_id == conversation_id).delete()
    db.query(ConversationResult).filter(ConversationResult.conversation_id == conversation_id).delete()
    db.query(ConversationDataset).filter(ConversationDataset.conversation_id == conversation_id).delete()
    db.delete(conv)
    db.commit()
    return {"deleted": True, "conversation_id": conversation_id}


@router.post("/conversations/{conversation_id}/messages")
async def execute_conversation_turn(
    conversation_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Executes a multi-turn analytical step in the persistent conversation.
    Supports both JSON and multipart form data with file uploads.
    Enforces idempotency, context reuse, lineage tracking, and honest spatial verification.
    """
    data, uploaded_files = await parse_request_data_and_files(request)

    prompt = (
        data.get("prompt") or
        data.get("content") or
        data.get("message") or
        data.get("query") or
        ""
    ).strip()

    client_request_id = data.get("client_request_id") or str(uuid.uuid4())
    conv = ConversationEngine.get_or_create_conversation(db, conversation_id=conversation_id)

    # 1. Idempotency Check (Invariant 7 & Section 21)
    existing_turn = db.query(ConversationTurn).filter(
        ConversationTurn.conversation_id == conversation_id,
        ConversationTurn.client_request_id == client_request_id
    ).first()

    if existing_turn:
        # Check if client attempted to reuse client_request_id with a different payload
        existing_user_msg = db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.client_request_id == client_request_id,
            ConversationMessage.role == "user"
        ).first()
        if existing_user_msg and existing_user_msg.content.strip() != prompt:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Conflict: client_request_id '{client_request_id}' was already submitted with a different payload."
            )

        # If completed, return existing assistant message and state
        existing_asst_msg = db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.turn_id == existing_turn.id,
            ConversationMessage.role == "assistant"
        ).first()
        if existing_asst_msg:
            meta = json.loads(existing_asst_msg.metadata_json or "{}")
            return {
                "conversation_id": conversation_id,
                "turn_id": existing_turn.id,
                "client_request_id": client_request_id,
                "state_revision": conv.state_revision,
                "user_message": {
                    "id": existing_user_msg.id if existing_user_msg else None,
                    "role": "user",
                    "content": existing_user_msg.content if existing_user_msg else prompt,
                    "created_at": existing_user_msg.created_at.isoformat() if existing_user_msg and existing_user_msg.created_at else None
                },
                "assistant_message": {
                    "id": existing_asst_msg.id,
                    "role": "assistant",
                    "content": existing_asst_msg.content,
                    "metadata": meta,
                    "created_at": existing_asst_msg.created_at.isoformat() if existing_asst_msg.created_at else None
                },
                "summary": meta.get("summary") or existing_asst_msg.content,
                "findings": meta.get("findings", []),
                "sections": meta.get("sections", {}),
                "model": meta.get("model", ""),
                "maskUrl": meta.get("maskUrl"),
                "mapAction": meta.get("mapAction"),
                "pending_task": meta.get("pending_task"),
                "active_context": json.loads(conv.active_context_json or "{}"),
            }

    # 1b. Concurrency Policy (Section 22): reject overlapping submissions for the same conversation
    running_turn = db.query(ConversationTurn).filter(
        ConversationTurn.conversation_id == conversation_id,
        ConversationTurn.status == "RUNNING"
    ).first()
    if running_turn and running_turn.client_request_id != client_request_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Another analysis turn is currently in progress for this conversation. Please wait for it to complete or retry shortly."
        )

    # 2. Persist uploaded files as ConversationDataset records
    active_context = json.loads(conv.active_context_json or "{}")
    existing_datasets = db.query(ConversationDataset).filter(
        ConversationDataset.conversation_id == conversation_id
    ).order_by(ConversationDataset.created_at.asc()).all()

    new_dataset_ids = []
    has_pending = bool(active_context.get("pending_task"))

    for p in uploaded_files:
        p_name = os.path.basename(p)
        # Determine dataset role
        if existing_datasets or has_pending:
            role = "comparison_input"
        else:
            role = "original"

        ds = ConversationDataset(
            id=str(uuid.uuid4()),
            conversation_id=conversation_id,
            file_path=p,
            file_name=p_name,
            file_size=os.path.getsize(p) if os.path.exists(p) else 0,
            mime_type="image/tiff" if p.lower().endswith((".tif", ".tiff")) else "image/jpeg",
            role=role,
            metadata_json=json.dumps({"upload_turn_client_id": client_request_id})
        )
        db.add(ds)
        db.commit()
        db.refresh(ds)
        new_dataset_ids.append(ds.id)
        existing_datasets.append(ds)

    # 3. Resolve file paths for execution
    if uploaded_files:
        exec_files = uploaded_files
    else:
        # Ordinary follow-up: reuse the existing conversation datasets!
        exec_files = [ds.file_path for ds in existing_datasets if os.path.exists(ds.file_path)]

    # 4. Persist User Message and Create Turn
    turn_id = str(uuid.uuid4())
    user_msg_id = str(uuid.uuid4())

    user_msg = ConversationMessage(
        id=user_msg_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        role="user",
        content=prompt or ("Attached files for analysis" if uploaded_files else ""),
        client_request_id=client_request_id,
        metadata_json=json.dumps({"has_attachments": bool(uploaded_files), "files": [os.path.basename(f) for f in exec_files]})
    )
    db.add(user_msg)

    turn = ConversationTurn(
        id=turn_id,
        conversation_id=conversation_id,
        client_request_id=client_request_id,
        status="RUNNING",
        attempt=1
    )
    db.add(turn)
    db.commit()

    # 5. Execute via LangGraph Task Router
    try:
        last_op = active_context.get("last_operation") or {}
        task = data.get("task") or last_op.get("type") or "internvl"
        target_model = data.get("model", "")

        has_geotiff = any(p.lower().endswith((".tif", ".tiff")) for p in exec_files)
        input_cat = "geotiff" if has_geotiff else ("benchmark" if exec_files else "query")

        state_input = {
            "conversation_id": conversation_id,
            "client_request_id": client_request_id,
            "task": task,
            "input_category": input_cat,
            "file_paths": exec_files,
            "has_new_files": bool(uploaded_files),
            "prompt": prompt,
            "pair_type": "bitemporal" if len(exec_files) >= 2 else "single_image",
            "target_model_id": target_model,
            "validation_info": {},
            "dispatch_mode": "worker",
            "active_context": active_context,
            "pending_task": active_context.get("pending_task"),
            "result": {}
        }

        routed = task_router_app.invoke(state_input)
        turn_action = routed.get("turn_action_type", "new_analysis")
        routed_result = routed.get("result", {})
        map_action = routed.get("map_action") or routed_result.get("map_action")
        model_id = routed.get("target_model_id", target_model or "Task Router")

        # If lightweight action executed, result is already directly available in routed_result
        if turn_action in ("saved_fact", "map_action", "explanation", "parameter_modification", "spatial_proximity", "clarification", "conversational_followup"):
            formatted_res = {
                "summary": routed_result.get("summary", ""),
                "supporting_findings": routed_result.get("supporting_findings", []),
                "findings": routed_result.get("findings", []),
                "sections": routed_result.get("sections", {}),
                "model": routed_result.get("model", model_id),
                "validation": routed_result.get("validation", "passed"),
                "maskUrl": routed_result.get("maskUrl"),
                "mapAction": map_action,
                "metrics": routed_result.get("metrics", {})
            }
        else:
            # Scientific model pipeline ran
            fallback_params = {
                "file_paths": exec_files,
                "prompt": prompt,
                "pair_type": "bitemporal" if len(exec_files) >= 2 else "single_image",
                "task": task,
                "diagnostic_override": target_model or None
            }
            formatted_res = await poll_job_or_format(routed_result, model_id, fallback_params=fallback_params)

        summary = formatted_res.get("summary", "")
        supporting_findings = formatted_res.get("supporting_findings", [])
        findings = formatted_res.get("findings", [])
        sections = formatted_res.get("sections", {})
        mask_url = formatted_res.get("maskUrl")
        metrics = formatted_res.get("metrics", {})

        # 6. Result Lineage & Persistence
        # If this turn produced analytical findings or a mask, record a ConversationResult
        turn.turn_type = turn_action
        if turn_action in ("new_analysis", "pending_input_continuation") and (findings or mask_url or summary):
            asst_count = db.query(ConversationMessage).filter(
                ConversationMessage.conversation_id == conversation_id,
                ConversationMessage.role == "assistant"
            ).count()
            is_first = (active_context.get("original_result_id") is None) or (asst_count == 0)
            result_role = "original" if is_first else "derived"
            parent_id = None if is_first else active_context.get("current_result_id")

            new_res_id = str(uuid.uuid4())
            conv_result = ConversationResult(
                id=new_res_id,
                conversation_id=conversation_id,
                turn_id=turn_id,
                parent_result_id=parent_id,
                result_role=result_role,
                operation=task or "detection",
                parameters_json=json.dumps({"prompt": prompt, "model": model_id}),
                summary=summary,
                findings_json=json.dumps(findings),
                sections_json=json.dumps(sections),
                metrics_json=json.dumps(metrics),
                mask_url=mask_url,
                source_dataset_ids_json=json.dumps([d.id for d in existing_datasets])
            )
            db.add(conv_result)
            db.commit()

            if is_first:
                active_context["original_result_id"] = new_res_id
            active_context["current_result_id"] = new_res_id
            active_context["last_operation"] = {"type": task, "parameters": {"prompt": prompt, "model": model_id}}
            turn.result_id = new_res_id

            # Clear pending task if this fulfilled it
            if turn_action == "pending_input_continuation":
                active_context["pending_task"] = None

        elif turn_action == "clarification":
            active_context["pending_task"] = routed.get("pending_task") or routed_result.get("pending_task")
        elif turn_action in ("parameter_modification", "saved_fact", "map_action", "spatial_proximity"):
            if routed_result.get("result_id"):
                turn.result_id = routed_result.get("result_id")

        # Update map action if issued
        if map_action:
            active_context["map_state"] = map_action

        # Update deterministic title on first meaningful query
        if conv.title in ("New Analysis Conversation", "New Analysis") and prompt:
            clean_title = re.sub(r'[\r\n\t]+', ' ', prompt).strip()
            conv.title = (clean_title[:38] + "...") if len(clean_title) > 40 else clean_title

        # Increment analytical state revision
        conv.state_revision += 1
        conv.active_context_json = json.dumps(active_context)
        turn.status = "COMPLETED"
        turn.completed_at = datetime.now(timezone.utc)

        # 7. Persist Assistant Message
        asst_msg_id = str(uuid.uuid4())
        msg_meta = {
            "summary": summary,
            "supporting_findings": supporting_findings,
            "findings": findings,
            "sections": sections,
            "model": formatted_res.get("model", model_id),
            "maskUrl": mask_url,
            "mapAction": map_action,
            "turn_action_type": turn_action,
            "validation": formatted_res.get("validation", "passed"),
            "pending_task": active_context.get("pending_task"),
            "state_revision": conv.state_revision,
            "metrics": metrics
        }
        asst_msg = ConversationMessage(
            id=asst_msg_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            role="assistant",
            content=summary,
            client_request_id=client_request_id,
            metadata_json=json.dumps(msg_meta)
        )
        db.add(asst_msg)
        db.commit()

        return {
            "conversation_id": conversation_id,
            "turn_id": turn_id,
            "client_request_id": client_request_id,
            "state_revision": conv.state_revision,
            "user_message": {
                "id": user_msg_id,
                "role": "user",
                "content": user_msg.content,
                "created_at": user_msg.created_at.isoformat() if user_msg.created_at else None
            },
            "assistant_message": {
                "id": asst_msg_id,
                "role": "assistant",
                "content": asst_msg.content,
                "metadata": msg_meta,
                "created_at": asst_msg.created_at.isoformat() if asst_msg.created_at else None
            },
            "summary": summary,
            "supporting_findings": supporting_findings,
            "findings": findings,
            "sections": sections,
            "model": formatted_res.get("model", model_id),
            "maskUrl": mask_url,
            "mapAction": map_action,
            "pending_task": active_context.get("pending_task"),
            "active_context": active_context,
            "validation": formatted_res.get("validation", "passed"),
            "status": "COMPLETED"
        }

    except Exception as e:
        logger.error(f"Error executing conversation turn for conversation {conversation_id}: {e}", exc_info=True)
        turn.status = "FAILED"
        turn.error_message = str(e)
        turn.completed_at = datetime.now(timezone.utc)

        # Invariant 9: "A failed turn does not erase the last valid analytical context."
        # Safe error assistant message
        safe_msg = f"An issue occurred while processing this turn: {str(e)}. Your previous analytical context remains preserved."
        asst_msg_id = str(uuid.uuid4())
        error_meta = {
            "error": str(e),
            "validation": "failed",
            "turn_action_type": "error"
        }
        asst_msg = ConversationMessage(
            id=asst_msg_id,
            conversation_id=conversation_id,
            turn_id=turn_id,
            role="assistant",
            content=safe_msg,
            client_request_id=client_request_id,
            metadata_json=json.dumps(error_meta)
        )
        db.add(asst_msg)
        db.commit()

        return {
            "conversation_id": conversation_id,
            "turn_id": turn_id,
            "client_request_id": client_request_id,
            "state_revision": conv.state_revision,
            "user_message": {
                "id": user_msg_id,
                "role": "user",
                "content": user_msg.content,
                "created_at": user_msg.created_at.isoformat() if user_msg.created_at else None
            },
            "assistant_message": {
                "id": asst_msg_id,
                "role": "assistant",
                "content": safe_msg,
                "metadata": error_meta,
                "created_at": asst_msg.created_at.isoformat() if asst_msg.created_at else None
            },
            "summary": safe_msg,
            "findings": [],
            "sections": {},
            "model": "Error Recovery",
            "maskUrl": None,
            "mapAction": None,
            "pending_task": active_context.get("pending_task"),
            "active_context": active_context,
            "status": "FAILED"
        }

