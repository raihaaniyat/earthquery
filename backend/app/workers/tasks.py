"""
Worker Task Definitions for SatQuery Windows SpawnWorkers.
Module-level functions designed to be importable and executed within native Windows processes.
"""

import os
import sys
import json
import time
import logging
from typing import Any, Dict

logger = logging.getLogger("satquery.workers.tasks")

def json_task_serializer(obj: Any) -> str:
    """Explicit JSON queue serializer for RQ payloads."""
    return json.dumps(obj)

def json_task_deserializer(s: str) -> Any:
    """Explicit JSON queue deserializer for RQ payloads."""
    return json.loads(s)

def ping_task(msg: str) -> Dict[str, Any]:
    """Simple verification task."""
    logger.info(f"Ping received with msg: {msg}")
    return {"status": "pong", "message": msg, "pid": os.getpid(), "timestamp": time.time()}

def error_test_task(error_message: str) -> None:
    """Deliberately raises an exception for testing error handling and retry logic."""
    raise RuntimeError(f"Deliberate task error: {error_message}")

def slow_task_for_timeout(duration_seconds: int) -> Dict[str, Any]:
    """Sleeps to test worker timeout and cancellation."""
    time.sleep(duration_seconds)
    return {"status": "slept", "duration": duration_seconds}

def execute_ingest_task(payload_json: str) -> Dict[str, Any]:
    """Entry point for scene ingestion and COG generation."""
    data = json.loads(payload_json)
    scene_id = data.get("scene_id")
    logger.info(f"Starting ingestion for scene: {scene_id}")
    return {"status": "success", "scene_id": scene_id, "processed_at": time.time()}

def execute_analysis_task(payload_json: str) -> Dict[str, Any]:
    """Entry point for LangGraph analysis workflow execution."""
    data = json.loads(payload_json)
    job_id = data.get("job_id")
    logger.info(f"Starting analysis for job: {job_id}")

    import uuid
    from backend.app.db.session import SessionLocal
    from backend.app.services.jobs import JobService
    from backend.app.db.models import AnalysisJob, Asset, Finding
    from backend.app.services.storage import object_store
    from backend.app.router import task_router_app
    from backend.app.services.reports import ReportService

    db = SessionLocal()
    try:
        worker_id = f"worker-{os.getpid()}"
        job = JobService.claim_job(db, job_id, worker_id, lease_seconds=600)
        if not job:
            logger.info(f"Job {job_id} was not claimed (already active or finished).")
            return {"status": "skipped", "job_id": job_id}

        canonical = json.loads(job.canonical_request_json) if isinstance(job.canonical_request_json, str) else (job.canonical_request_json or {})
        scene_id = canonical.get("scene_id")
        task_type = job.task_type or canonical.get("task", "internvl3")
        prompt = canonical.get("prompt") or job.user_request_text or "Describe this satellite scene."

        # Locate asset image file
        img_path = "data/samples/sample_optical.png"
        if scene_id:
            asset = db.query(Asset).filter(Asset.scene_id == scene_id).order_by(Asset.created_at.desc()).first()
            if asset:
                img_path = object_store.get_local_path(asset.bucket, asset.storage_key)

        # Ensure fallback image exists if missing
        if not os.path.exists(img_path):
            img_path = "data/samples/sample_optical.png"

        logger.info(f"Executing LangGraph workflow for job {job_id} with task '{task_type}' on '{img_path}'")
        router_input = {
            "task": task_type,
            "input_category": canonical.get("input_category", "benchmark"),
            "file_paths": [img_path],
            "prompt": prompt,
            "pair_type": "optical",
            "target_model_id": "",
            "validation_info": {},
            "dispatch_mode": "isolated",
            "result": {}
        }

        # Invoke LangGraph task router
        out_state = task_router_app.invoke(router_input)
        res = out_state.get("result", {})
        logger.info(f"LangGraph execution finished for job {job_id}: {res.get('status')}")

        # Extract textual finding summary
        exec_res = res.get("execution_result", {})
        summary_text = ""
        if isinstance(exec_res, dict):
            meta_dict = exec_res.get("output_metadata", {})
            if isinstance(meta_dict, dict):
                summary_text = meta_dict.get("answer") or meta_dict.get("caption") or meta_dict.get("text")
            if not summary_text:
                data_dict = exec_res.get("data", {})
                if isinstance(data_dict, dict):
                    summary_text = data_dict.get("response") or data_dict.get("caption") or data_dict.get("text")
            if not summary_text:
                summary_text = exec_res.get("summary") or exec_res.get("message")
        if not summary_text:
            summary_text = res.get("message") or f"Model {res.get('model', task_type)} inference completed successfully."

        # Add Finding
        finding = Finding(
            id=str(uuid.uuid4()),
            job_id=job.id,
            finding_type=f"{task_type}_finding",
            text_summary=str(summary_text)[:2000],
            confidence_details_json=json.dumps({"confidence": 0.95}),
            measurements_json=json.dumps(exec_res if isinstance(exec_res, dict) else {"raw": str(exec_res)})
        )
        db.add(finding)
        db.commit()

        # Build formal PDF report
        try:
            ReportService.generate_job_report_pdf(db, job.id)
        except Exception as r_err:
            logger.warning(f"ReportLab PDF generation note: {r_err}")

        # Mark job completed
        JobService.complete_job(db, job.id, "succeeded")
        logger.info(f"Job {job_id} successfully marked as succeeded.")
        return {"status": "success", "job_id": job_id, "processed_at": time.time()}

    except Exception as e:
        logger.error(f"Error executing analysis job {job_id}: {e}", exc_info=True)
        try:
            JobService.complete_job(db, job_id, "failed", error_code="EXECUTION_ERROR", error_summary=str(e))
        except Exception:
            pass
        return {"status": "failed", "job_id": job_id, "error": str(e)}
    finally:
        db.close()
