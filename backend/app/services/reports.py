"""
Automated PDF Report Generation Service via ReportLab.
Generates comprehensive intelligence summaries including query provenance,
model versions, factual findings, evidence references, and limitations.
"""

import io
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable

from backend.app.config import settings
from backend.app.db.models import AnalysisJob, Report, Asset
from backend.app.services.storage import object_store

logger = logging.getLogger("satquery.services.reports")


class ReportService:
    @staticmethod
    def generate_job_report_pdf(db: Session, job_id: str) -> Report:
        """
        Builds a formal PDF analysis report using ReportLab and commits it to storage.
        """
        job = db.query(AnalysisJob).filter(AnalysisJob.id == job_id).first()
        if not job:
            raise ValueError(f"Job {job_id} not found.")

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "ReportTitle",
            parent=styles["Title"],
            fontSize=20,
            leading=24,
            textColor=colors.HexColor("#0f172a"),
            alignment=0
        )
        heading_style = ParagraphStyle(
            "ReportHeading",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#1e293b"),
            spaceBefore=12,
            spaceAfter=6
        )
        body_style = ParagraphStyle(
            "ReportBody",
            parent=styles["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#334155")
        )
        callout_style = ParagraphStyle(
            "ReportCallout",
            parent=styles["Normal"],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#475569")
        )

        story = []

        # 1. Title Banner
        story.append(Paragraph("<b>SatQuery AI — Geospatial Analysis Report</b>", title_style))
        story.append(Spacer(1, 4))
        story.append(Paragraph("Remote Sensing Intelligence & Multimodal Evidence Verification", callout_style))
        story.append(Spacer(1, 10))
        story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#3b82f6"), spaceAfter=14))

        # 2. Executive Metadata Table
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        meta_data = [
            [Paragraph("<b>Job ID:</b>", body_style), Paragraph(job.id, body_style)],
            [Paragraph("<b>Project ID:</b>", body_style), Paragraph(job.project_id, body_style)],
            [Paragraph("<b>Task Type:</b>", body_style), Paragraph(job.task_type.upper(), body_style)],
            [Paragraph("<b>Status:</b>", body_style), Paragraph(f"<b>{job.status.upper()}</b>", body_style)],
            [Paragraph("<b>Generated:</b>", body_style), Paragraph(now_str, body_style)],
        ]
        meta_table = Table(meta_data, colWidths=[120, 384])
        meta_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(meta_table)
        story.append(Spacer(1, 14))

        # 3. User Query & Task Intent
        story.append(Paragraph("<b>1. Request Specification</b>", heading_style))
        query_text = job.user_request_text or "Direct task execution"
        story.append(Paragraph(f"<b>Query / Prompt:</b> \"{query_text}\"", body_style))
        story.append(Spacer(1, 10))

        # 4. Factual Findings & Measurements
        story.append(Paragraph("<b>2. Factual Findings & Observations</b>", heading_style))
        findings = job.findings
        if findings:
            for idx, f in enumerate(findings, 1):
                story.append(Paragraph(f"<b>Finding {idx} ({f.finding_type}):</b> {f.finding_text}", body_style))
                if f.measurements_json:
                    meas = json.loads(f.measurements_json)
                    meas_lines = ", ".join([f"{k}: {v}" for k, v in meas.items()])
                    story.append(Paragraph(f"<i>Measurements:</i> {meas_lines}", callout_style))
                story.append(Spacer(1, 6))
        else:
            story.append(Paragraph("No structured findings recorded for this analysis.", body_style))
        story.append(Spacer(1, 10))

        # 5. Scientific Limitations & Review Notes
        story.append(Paragraph("<b>3. Operational Boundaries & Limitations</b>", heading_style))
        limits_text = (
            "• Observations are generated based on local hardware inference (RTX 5060 Laptop GPU).<br/>"
            "• ChangeFormer outputs represent 2D building change masks trained on LEVIR-CD.<br/>"
            "• UPerNet semantic segmentation reflects generic ADE20K demo proxy classes unless domain-trained.<br/>"
            "• Satellite pixel coordinates are not mapped to geographic bounds unless explicit CRS metadata is verified.<br/>"
            "• Analyst confirmation is recommended prior to operational deployment."
        )
        story.append(Paragraph(limits_text, callout_style))

        # Build document
        doc.build(story)
        pdf_bytes = buffer.getvalue()

        # Upload PDF to ObjectStore
        storage_key = f"reports/{job.project_id}/{job.id}/report.pdf"
        byte_size, sha256_hash = object_store.put_stream(
            bucket=settings.S3_BUCKET_DERIVED,
            key=storage_key,
            stream=io.BytesIO(pdf_bytes),
            content_type="application/pdf"
        )

        # Create Asset record
        asset = Asset(
            project_id=job.project_id,
            role="report",
            bucket=settings.S3_BUCKET_DERIVED,
            storage_key=storage_key,
            sha256_hash=sha256_hash,
            byte_size=byte_size,
            media_type="application/pdf",
            commit_status="committed"
        )
        db.add(asset)
        db.commit()
        db.refresh(asset)

        # Create Report record
        report = Report(
            job_id=job.id,
            report_asset_id=asset.id,
            report_format="pdf",
            manifest_digest=sha256_hash
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        return report
