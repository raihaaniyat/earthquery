"""
Unit tests for Evidence Recording and ReportLab PDF Report Generation.
"""

import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import Base
from backend.app.db.models import User, Project, AnalysisJob, Asset, Finding
from backend.app.services.evidence import EvidenceService
from backend.app.services.reports import ReportService
from backend.app.services.storage import object_store


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    user = User(id="user-1", email="dev@satquery.local", hashed_password="pw")
    project = Project(id="proj-1", owner_id="user-1", name="Test Project")
    job = AnalysisJob(
        id="job-rep-1",
        project_id="proj-1",
        task_type="bitemporal_change",
        user_request_text="Analyze building changes between Scene A and Scene B.",
        canonical_request_json='{"task": "change_detection"}',
        request_hash="hash123",
        status="succeeded"
    )
    session.add_all([user, project, job])
    session.commit()

    yield session
    session.close()


def test_record_finding_and_evidence_links(db_session):
    # Create output mask asset
    asset = Asset(
        id="asset-mask-1",
        project_id="proj-1",
        role="mask",
        bucket="test-bucket",
        storage_key="results/mask.png",
        sha256_hash="sha_mask_123",
        byte_size=1024,
        media_type="image/png",
        commit_status="committed"
    )
    db_session.add(asset)
    db_session.commit()

    finding = EvidenceService.record_finding(
        db=db_session,
        job_id="job-rep-1",
        finding_type="change_detection_summary",
        finding_text="Detected significant building expansion in the southern quadrant.",
        measurements={"changed_pixels": 4520, "change_percentage": 6.89},
        confidence_details={"model": "ChangeFormerV6", "calibration": "LEVIR-CD verified"},
        supporting_assets=[{"asset_id": asset.id, "evidence_role": "change_mask"}]
    )

    assert finding.id is not None
    assert finding.finding_type == "change_detection_summary"
    assert len(finding.evidence) == 1
    assert finding.evidence[0].asset_id == asset.id


def test_generate_pdf_report(db_session):
    # Record finding first
    EvidenceService.record_finding(
        db=db_session,
        job_id="job-rep-1",
        finding_type="change_detection_summary",
        finding_text="Sample observation for report testing.",
        measurements={"change_percentage": 5.2}
    )

    # Generate PDF report
    report = ReportService.generate_job_report_pdf(db_session, "job-rep-1")

    assert report.id is not None
    assert report.report_format == "pdf"
    assert report.manifest_digest is not None
    assert len(report.manifest_digest) == 64  # Valid SHA-256

    # Verify asset was committed
    report_asset = db_session.query(Asset).filter(Asset.id == report.report_asset_id).first()
    assert report_asset is not None
    assert report_asset.role == "report"
    assert report_asset.media_type == "application/pdf"
    assert report_asset.sha256_hash == report.manifest_digest
