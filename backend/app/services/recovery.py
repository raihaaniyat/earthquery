"""
Reconciliation & Recovery Service.
Handles expired worker leases, orphaned staging assets,
and uncommitted storage uploads to maintain durable cluster consistency.
"""

import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_

from backend.app.db.models import AnalysisJob, Asset, JobEvent
from backend.app.services.storage import object_store

logger = logging.getLogger("satquery.services.recovery")


class ReconciliationService:
    @staticmethod
    def reconcile_expired_leases(db: Session, max_retries: int = 3) -> int:
        """
        Reconciles crashed workers by inspecting expired leases on running jobs.
        """
        now = datetime.now(timezone.utc)
        expired_jobs = db.query(AnalysisJob).filter(
            AnalysisJob.status == "running",
            AnalysisJob.lease_expires_at < now
        ).all()

        recovered_count = 0
        for job in expired_jobs:
            if job.current_attempt < max_retries:
                job.status = "retry_wait"
                job.current_attempt += 1
                job.lease_holder = None
                job.lease_expires_at = None
                db.add(JobEvent(
                    job_id=job.id,
                    event_type="LEASE_EXPIRED_RETRY",
                    payload_json=f'{{"attempt": {job.current_attempt}, "max_retries": {max_retries}}}'
                ))
            else:
                job.status = "failed"
                job.error_code = "LEASE_TIMEOUT"
                job.error_summary = f"Job exceeded max lease attempts ({max_retries}). Worker failed to report heartbeat."
                job.completed_at = now
                job.lease_holder = None
                job.lease_expires_at = None
                db.add(JobEvent(
                    job_id=job.id,
                    event_type="LEASE_FAILED",
                    payload_json='{"error": "Exceeded lease timeout retries"}'
                ))
            recovered_count += 1

        db.commit()
        return recovered_count

    @staticmethod
    def reconcile_staging_assets(db: Session, age_hours: int = 24) -> int:
        """
        Identifies staging assets that were never committed within the timeout window.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=age_hours)
        uncommitted = db.query(Asset).filter(
            Asset.commit_status == "staging",
            Asset.created_at < cutoff
        ).all()

        cleaned_count = 0
        for asset in uncommitted:
            asset.commit_status = "orphan"
            cleaned_count += 1

        db.commit()
        return cleaned_count
