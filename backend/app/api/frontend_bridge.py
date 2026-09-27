"""
Frontend Bridge API Routes.

Provides unified endpoints that the new React frontend expects.
These routes translate between the frontend's contract and the existing
backend infrastructure (LangGraph router, RQ workers, model registry).
Supports both multipart form data (with file attachments) and application/json.
"""

import os
import json
import uuid
import asyncio
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException, Depends, status
from fastapi.responses import JSONResponse, FileResponse
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from backend.app.config import settings
from backend.app.db.session import get_db, check_db_connection
from backend.app.db.models import User
from backend.app.auth import get_current_user
from backend.app.models_registry import list_models, get_capabilities
from backend.app.router import task_router_app
from backend.app.worker import get_redis_connection, check_redis_connection
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
                redis_conn = get_redis_connection()
                steps = int(timeout_seconds / 0.5)
                for _ in range(steps):
                    await asyncio.sleep(0.5)
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

                                assets = exec_result.get("output_assets", {})
                                if "change_mask" in assets:
                                    mask_rel = Path(assets["change_mask"]).name
                                    response["maskUrl"] = f"/api/assets/{mask_rel}"
                                elif "segmentation_mask" in assets:
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
                response["findings"] = fallback_res.get("findings", [])
                response["sections"] = fallback_res.get("sections", {})
                if fallback_res.get("participating_models"):
                    response["model"] = " + ".join(fallback_res["participating_models"])
                response["metrics"] = {"status": "completed"}
                assets = fallback_res.get("output_assets", {})
                if "change_mask" in assets:
                    mask_rel = Path(assets["change_mask"]).name
                    response["maskUrl"] = f"/api/assets/{mask_rel}"
                elif "segmentation_mask" in assets:
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

            if exec_result.get("participating_models"):
                response["model"] = " + ".join(exec_result["participating_models"])
            elif result.get("participating_models"):
                response["model"] = " + ".join(result["participating_models"])

            assets = exec_result.get("output_assets", {}) or result.get("output_assets", {})
            if "change_mask" in assets:
                mask_rel = Path(assets["change_mask"]).name
                response["maskUrl"] = f"/api/assets/{mask_rel}"
            elif "segmentation_mask" in assets:
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


# ----- Output Asset Serving -----

@router.get("/assets/{file_path:path}")
def get_asset_file(file_path: str):
    """
    Serves generated output masks or images from the storage scratch or uploads directory.
    """
    # Check scratch dir recursively
    for candidate in [
        os.path.join(SCRATCH_DIR, file_path),
        os.path.join(UPLOAD_DIR, file_path)
    ]:
        if os.path.isfile(candidate):
            return FileResponse(candidate)

    # Search in subdirectories of scratch
    matches = list(Path(SCRATCH_DIR).glob(f"**/{file_path}"))
    if matches and matches[0].is_file():
        return FileResponse(str(matches[0]))

    raise HTTPException(status_code=404, detail="Asset not found")
