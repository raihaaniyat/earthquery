"""
Reports API Endpoints.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import AnalysisJob, Report, User
from backend.app.auth import get_current_user, verify_project_access
from backend.app.services.reports import ReportService

router = APIRouter()


@router.get("/analysis-jobs/{job_id}/reports")
def list_job_reports(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all available reports for an analysis job."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    verify_project_access(job.project_id, current_user, db)

    reports = db.query(Report).filter(Report.job_id == job_id).all()
    return [
        {
            "id": r.id,
            "job_id": r.job_id,
            "format": r.report_format,
            "manifest_digest": r.manifest_digest,
            "created_at": r.created_at.isoformat(),
            "download_url": f"/api/v1/assets/{r.report_asset_id}/download"
        } for r in reports
    ]


@router.post("/analysis-jobs/{job_id}/reports", status_code=status.HTTP_201_CREATED)
def generate_report(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Generates an official PDF report with ReportLab."""
    job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found.")

    verify_project_access(job.project_id, current_user, db)

    try:
        report = ReportService.generate_job_report_pdf(db, job_id)
        return {
            "id": report.id,
            "job_id": report.job_id,
            "format": report.report_format,
            "manifest_digest": report.manifest_digest,
            "download_url": f"/api/v1/assets/{report.report_asset_id}/download",
            "created_at": report.created_at.isoformat()
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {str(e)}"
        )
