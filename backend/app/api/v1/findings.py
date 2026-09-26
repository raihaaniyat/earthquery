"""
Findings and Evidence API Endpoints.
"""

import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import AnalysisJob, Finding, FindingEvidence, User
from backend.app.auth import get_current_user, verify_project_access
from backend.app.services.evidence import EvidenceService

router = APIRouter()


@router.get("/analysis-jobs/{job_id}/findings")
def get_job_findings(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves all factual findings produced by an analysis job."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    verify_project_access(job.project_id, current_user, db)

    findings = EvidenceService.get_job_findings(db, job_id)
    return [
        {
            "id": f.id,
            "job_id": f.job_id,
            "step_id": f.step_id,
            "finding_type": f.finding_type,
            "finding_text": f.finding_text,
            "measurements": json.loads(f.measurements_json) if f.measurements_json else None,
            "confidence_details": json.loads(f.confidence_details_json) if f.confidence_details_json else None,
            "review_status": f.review_status,
            "evidence_count": len(f.evidence)
        } for f in findings
    ]


@router.get("/findings/{finding_id}/evidence")
def get_finding_evidence(
    finding_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieves the full evidence chain for a specific finding."""
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found.")

    job = db.query(AnalysisJob).filter(AnalysisJob.id == finding.job_id).first()
    if job:
        verify_project_access(job.project_id, current_user, db)

    evidence_items = db.query(FindingEvidence).filter(FindingEvidence.finding_id == finding_id).all()
    return [
        {
            "id": ev.id,
            "asset_id": ev.asset_id,
            "evidence_role": ev.evidence_role,
            "step_id": ev.step_id,
            "observation_scope": ev.observation_scope,
            "asset_download_url": f"/api/v1/assets/{ev.asset_id}/download"
        } for ev in evidence_items
    ]
