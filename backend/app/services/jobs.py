"""
Durable Analysis Job Service.
Manages job lifecycle, idempotency key uniqueness, atomic worker leases,
heartbeats, and at-least-once outbox dispatch events.
"""

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple, List
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from backend.app.config import settings
from backend.app.db.models import AnalysisJob, OutboxEvent, JobEvent, ExecutionStep

logger = logging.getLogger("satquery.services.jobs")



class ConflictError(Exception):
    pass


class CapacityExceededError(Exception):
    def __init__(self, message: str, retry_after_seconds: int = 30):
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class JobService:
    @staticmethod
    def create_job(
        db: Session,
        project_id: str,
        task_type: str,
        canonical_request: Dict[str, Any],
        user_id: Optional[str] = None,
        user_request_text: Optional[str] = None,
        idempotency_key: Optional[str] = None
    ) -> Tuple[AnalysisJob, bool]:
        """
        Creates a durable AnalysisJob and OutboxEvent in a single transaction.
        Enforces idempotency and admission backpressure:
        - Same idempotency_key + same request hash -> returns existing job (created=False)
        - Same idempotency_key + different request hash -> raises ConflictError
        - Active jobs >= MAX_QUEUED_GPU_JOBS -> raises CapacityExceededError
        """
        req_json = json.dumps(canonical_request, sort_keys=True)
        req_hash = hashlib.sha256(req_json.encode("utf-8")).hexdigest()

        if idempotency_key:
            existing = db.query(AnalysisJob).filter(
                AnalysisJob.project_id == project_id,
                AnalysisJob.idempotency_key == idempotency_key
            ).first()
            if existing:
                if existing.request_hash == req_hash:
                    logger.info(f"Idempotent request matched existing job {existing.id}")
                    return existing, False
                else:
                    raise ConflictError(
                        f"Idempotency key '{idempotency_key}' already used with different request parameters."
                    )

        # Capacity backpressure check
        active_count = db.query(AnalysisJob).filter(
            AnalysisJob.status.in_(["queued", "waiting_for_resources", "running"])
        ).count()

        if active_count >= settings.MAX_QUEUED_GPU_JOBS:
            raise CapacityExceededError(
                f"GPU task queue has reached its maximum capacity of {settings.MAX_QUEUED_GPU_JOBS} active jobs. "
                "Please retry once active jobs complete.",
                retry_after_seconds=30
            )

        # Newly created jobs start in queued state
        initial_status = "queued"
        waiting_reason = None

        job_id = str(uuid.uuid4())
        job = AnalysisJob(
            id=job_id,
            project_id=project_id,
            user_id=user_id,
            task_type=task_type,
            user_request_text=user_request_text,
            canonical_request_json=req_json,
            request_hash=req_hash,
            idempotency_key=idempotency_key,
            status=initial_status,
            waiting_reason=waiting_reason,
            estimated_queue_position=active_count + 1,
            current_attempt=1
        )
        db.add(job)


        # Create Outbox event for dispatch
        outbox_event = OutboxEvent(
            aggregate_type="job",
            aggregate_id=job_id,
            event_type="JOB_CREATED",
            payload_json=json.dumps({
                "job_id": job_id,
                "project_id": project_id,
                "task_type": task_type,
                "request": canonical_request
            })
        )
        db.add(outbox_event)

        # Record initial event
        job_event = JobEvent(
            job_id=job_id,
            event_type="STATE_CHANGED",
            payload_json=json.dumps({"status": "queued", "message": "Job queued for execution"})
        )
        db.add(job_event)

        db.commit()
        db.refresh(job)
        return job, True

    @staticmethod
    def claim_job(
        db: Session,
        job_id: str,
        worker_id: str,
        lease_seconds: int = 120
    ) -> Optional[AnalysisJob]:
        """
        Atomically claims a job for execution.
        Returns job if claimed successfully, None if already claimed by active worker.
        """
        now = datetime.now(timezone.utc)
        job = db.query(AnalysisJob).filter(
            AnalysisJob.id == job_id,
            or_(
                AnalysisJob.status == "queued",
                AnalysisJob.status == "waiting_for_resources",
                AnalysisJob.status == "retry_wait",
                and_(
                    AnalysisJob.status == "running",
                    AnalysisJob.lease_expires_at < now
                )
            )
        ).with_for_update().first()

        if not job:
            return None

        job.status = "running"
        job.lease_holder = worker_id
        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        job.started_at = job.started_at or now

        # Add event
        job_event = JobEvent(
            job_id=job.id,
            event_type="LEASE_CLAIMED",
            payload_json=json.dumps({"worker_id": worker_id, "attempt": job.current_attempt})
        )
        db.add(job_event)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def heartbeat(db: Session, job_id: str, worker_id: str, lease_seconds: int = 120) -> bool:
        """Extends worker lease duration."""
        now = datetime.now(timezone.utc)
        job = db.query(AnalysisJob).filter(
            AnalysisJob.id == job_id,
            AnalysisJob.status == "running",
            AnalysisJob.lease_holder == worker_id
        ).first()

        if not job:
            return False

        job.lease_expires_at = now + timedelta(seconds=lease_seconds)
        db.commit()
        return True

    @staticmethod
    def cancel_job(db: Session, project_id: str, job_id: str) -> Optional[AnalysisJob]:
        """Requests cancellation of a queued or running job."""
        job = db.query(AnalysisJob).filter(
            AnalysisJob.id == job_id,
            AnalysisJob.project_id == project_id
        ).first()

        if not job:
            return None

        if job.status in ("succeeded", "failed", "cancelled"):
            return job

        if job.status == "queued":
            job.status = "cancelled"
            job.completed_at = datetime.now(timezone.utc)
        else:
            job.status = "cancel_requested"

        db.add(JobEvent(
            job_id=job.id,
            event_type="CANCEL_REQUESTED",
            payload_json=json.dumps({"status": job.status})
        ))
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def complete_job(
        db: Session,
        job_id: str,
        status: str,
        error_code: Optional[str] = None,
        error_summary: Optional[str] = None
    ) -> AnalysisJob:
        """Completes an analysis job, releasing the lease."""
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found.")

        job.status = status
        job.error_code = error_code
        job.error_summary = error_summary
        job.completed_at = datetime.now(timezone.utc)
        job.lease_holder = None
        job.lease_expires_at = None

        db.add(JobEvent(
            job_id=job.id,
            event_type="JOB_COMPLETED",
            payload_json=json.dumps({
                "status": status,
                "error_code": error_code,
                "error_summary": error_summary
            })
        ))
        db.commit()
        db.refresh(job)
        return job
