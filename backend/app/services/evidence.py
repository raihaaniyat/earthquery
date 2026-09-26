"""
Evidence & Factual Findings Service.
Records traceable findings linked to execution steps and input/output assets.
Stores structured confidence details, observation scopes, and limitations.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from backend.app.db.models import Finding, FindingEvidence, ExecutionStep, Asset

logger = logging.getLogger("satquery.services.evidence")


class EvidenceService:
    @staticmethod
    def record_finding(
        db: Session,
        job_id: str,
        finding_type: str,
        finding_text: str,
        step_id: Optional[str] = None,
        measurements: Optional[Dict[str, Any]] = None,
        confidence_details: Optional[Dict[str, Any]] = None,
        supporting_assets: Optional[List[Dict[str, str]]] = None,
        geometry_geojson: Optional[str] = None
    ) -> Finding:
        """
        Creates an immutable, traceable factual finding.
        Links supporting assets and execution steps as evidence.
        """
        conf_str = json.dumps(confidence_details) if confidence_details else None
        meas_str = json.dumps(measurements) if measurements else None

        finding = Finding(
            job_id=job_id,
            step_id=step_id,
            finding_type=finding_type,
            finding_text=finding_text,
            measurements_json=meas_str,
            confidence_details_json=conf_str,
            review_status="unreviewed"
        )
        db.add(finding)
        db.commit()
        db.refresh(finding)

        # Attach evidence assets
        if supporting_assets:
            for item in supporting_assets:
                asset_id = item.get("asset_id")
                role = item.get("evidence_role", "output")
                if asset_id:
                    evidence = FindingEvidence(
                        finding_id=finding.id,
                        asset_id=asset_id,
                        evidence_role=role,
                        step_id=step_id,
                        observation_scope=item.get("observation_scope", "scene")
                    )
                    db.add(evidence)
            db.commit()

        return finding

    @staticmethod
    def get_job_findings(db: Session, job_id: str) -> List[Finding]:
        """Retrieves all findings for an analysis job with their evidence references."""
        return db.query(Finding).filter(Finding.job_id == job_id).all()
