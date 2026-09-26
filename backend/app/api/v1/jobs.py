"""
Analysis Jobs Endpoints.
Handles job submission (202 Accepted), status polling, cursor-based event logs,
cancellation, and retries.
"""

from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import AnalysisJob, JobEvent, User
from backend.app.auth import get_current_user, verify_project_access
from backend.app.services.jobs import JobService, ConflictError, CapacityExceededError
from backend.app.services.outbox import outbox_dispatcher

router = APIRouter(prefix="/analysis-jobs")


class SubmitJobRequest(BaseModel):
    project_id: str
    task_type: str  # 'vqa', 'change_detection', 'land_cover', 'optical_sar'
    canonical_request: Dict[str, Any]
    user_request_text: Optional[str] = None
    idempotency_key: Optional[str] = None


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def submit_analysis_job(
    req: SubmitJobRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Submits an analysis job to the asynchronous execution engine.
    Returns HTTP 202 with job tracking URLs and durable event stream pointers.
    Returns HTTP 429 with Retry-After if GPU queue is at capacity.
    """
    verify_project_access(req.project_id, current_user, db)

    try:
        job, created = JobService.create_job(
            db=db,
            project_id=req.project_id,
            task_type=req.task_type,
            canonical_request=req.canonical_request,
            user_id=current_user.id,
            user_request_text=req.user_request_text,
            idempotency_key=req.idempotency_key
        )
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except CapacityExceededError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
            headers={"Retry-After": str(e.retry_after_seconds)}
        )

    # Trigger outbox processor immediately to reduce queue latency
    try:
        outbox_dispatcher.process_pending_events(db, batch_size=5)
    except Exception:
        pass

    return {
        "job_id": job.id,
        "status": job.status,
        "waiting_reason": job.waiting_reason,
        "estimated_queue_position": job.estimated_queue_position,
        "is_idempotent_duplicate": not created,
        "status_url": f"/api/v1/analysis-jobs/{job.id}",
        "events_url": f"/api/v1/analysis-jobs/{job.id}/events",
        "created_at": job.created_at.isoformat()
    }


@router.get("/{job_id}")
def get_job_status(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns durable job status, execution attempt, and error summary."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    verify_project_access(job.project_id, current_user, db)

    return {
        "id": job.id,
        "project_id": job.project_id,
        "task_type": job.task_type,
        "status": job.status,
        "waiting_reason": job.waiting_reason,
        "estimated_queue_position": job.estimated_queue_position,
        "current_attempt": job.current_attempt,
        "error_code": job.error_code,
        "error_summary": job.error_summary,
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "findings_count": len(job.findings),
        "reports_count": len(job.reports)
    }



@router.get("/{job_id}/events")
def get_job_events(
    job_id: str,
    since_event_id: Optional[int] = Query(None, description="Cursor for fetching events after monotonic event ID"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Returns chronological, monotonic event log for reconnectable progress polling."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    verify_project_access(job.project_id, current_user, db)

    query = db.query(JobEvent).filter(JobEvent.job_id == job_id)
    if since_event_id:
        query = query.filter(JobEvent.id > since_event_id)

    events = query.order_by(JobEvent.id.asc()).limit(100).all()

    return [
        {
            "event_id": ev.id,
            "event_type": ev.event_type,
            "payload": ev.payload_json,
            "created_at": ev.created_at.isoformat()
        } for ev in events
    ]


@router.post("/{job_id}/cancel")
def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Requests graceful cancellation of a queued or running job."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    verify_project_access(job.project_id, current_user, db)

    cancelled_job = JobService.cancel_job(db, job.project_id, job_id)
    return {"job_id": job_id, "status": cancelled_job.status}


@router.post("/{job_id}/retry")
def retry_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retries a failed job if allowed by the retry policy."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    verify_project_access(job.project_id, current_user, db)

    if job.status not in ("failed", "cancelled"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot retry job in status '{job.status}'."
        )

    # Deterministic failures cannot be retried blindly
    if job.error_code in ("UNSUPPORTED_SENSOR_PRODUCT", "MISSING_TRAINED_HEAD", "CHECKPOINT_MISMATCH"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Job failed with permanent error '{job.error_code}' which cannot be resolved by retrying."
        )

    job.status = "queued"
    job.error_code = None
    job.error_summary = None
    job.current_attempt += 1
    db.commit()

    return {"job_id": job.id, "status": job.status, "attempt": job.current_attempt}
