"""
Scene Ingestion and Asset Processing Service.
Handles bounded upload streaming, SHA-256 computation, database persistence,
and launches isolated geospatial worker subprocesses in satquery-core.
"""

import os
import sys
import json
import time
import uuid
import logging
import subprocess
from pathlib import Path
from typing import BinaryIO, Dict, Any, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.db.models import Scene, Asset
from backend.app.services.storage import object_store
from backend.runtime.protocol import SubprocessRequest, SubprocessResponse

logger = logging.getLogger("satquery.services.ingestion")


class IngestionService:
    @staticmethod
    def ingest_upload_stream(
        db: Session,
        project_id: str,
        filename: str,
        stream: BinaryIO,
        media_type: str = "application/octet-stream",
        sensor_platform: Optional[str] = None,
        product_level: Optional[str] = None
    ) -> Tuple[Scene, Asset]:
        """
        Durable upload pipeline:
        1. Generates scene and asset IDs.
        2. Streams file to ObjectStore, computing SHA-256 and byte size.
        3. Commits scene and original asset to PostgreSQL.
        4. Launches metadata extraction subprocess.
        5. Attaches preview and updates scene validation status.
        """
        scene_id = str(uuid.uuid4())
        asset_id = str(uuid.uuid4())
        
        # Safe storage key
        safe_filename = Path(filename).name
        storage_key = f"inputs/{project_id}/{scene_id}/{asset_id}/{safe_filename}"
        bucket = settings.S3_BUCKET_INPUTS

        # Stream to storage and compute SHA-256
        byte_size, sha256_hash = object_store.put_stream(
            bucket=bucket,
            key=storage_key,
            stream=stream,
            content_type=media_type
        )

        # 1. Create Scene record
        scene = Scene(
            id=scene_id,
            project_id=project_id,
            name=safe_filename,
            sensor_platform=sensor_platform or "Unknown",
            product_level=product_level,
            coordinate_space="pixel",
            width=0,
            height=0,
            validation_status="validating"
        )
        db.add(scene)

        # 2. Create Original Asset record
        asset = Asset(
            id=asset_id,
            project_id=project_id,
            scene_id=scene_id,
            role="original",
            bucket=bucket,
            storage_key=storage_key,
            sha256_hash=sha256_hash,
            byte_size=byte_size,
            media_type=media_type,
            commit_status="committed"
        )
        db.add(asset)
        db.commit()
        db.refresh(scene)
        db.refresh(asset)

        # 3. Execute geospatial preprocessing subprocess
        local_input_path = object_store.get_local_path(bucket, storage_key)
        out_dir = Path(settings.SATQUERY_STORAGE_ROOT) / "derived" / project_id / scene_id
        out_dir.mkdir(parents=True, exist_ok=True)

        req = SubprocessRequest(
            job_id=f"ingest-{scene_id}",
            step_key="preprocess",
            attempt_id="1",
            model_version_id="none",
            task_type="metadata_extraction",
            asset_references={"original": local_input_path},
            parameters={},
            output_dir=str(out_dir)
        )

        req_json_path = out_dir / "request.json"
        resp_json_path = out_dir / "response.json"
        with open(req_json_path, "w", encoding="utf-8") as f:
            f.write(req.model_dump_json(indent=2))

        # Launch satquery-core via conda run to ensure proper Windows DLL resolution
        conda_exe = settings.SATQUERY_CONDA_EXE
        cmd = [
            conda_exe,
            "run",
            "-n", settings.CORE_ENV,
            "--no-capture-output",
            "python",
            "-m", "backend.runtime.preprocess",
            "--request-json", str(req_json_path),
            "--response-json", str(resp_json_path)
        ]

        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parent.parent.parent.parent)

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60, env=env)
        
        if res.returncode == 0 and resp_json_path.exists():
            with open(resp_json_path, "r", encoding="utf-8") as f:
                resp_data = json.load(f)
            resp = SubprocessResponse(**resp_data)
            
            if resp.success:
                meta = resp.output_metadata
                scene.width = meta.get("width", 0)
                scene.height = meta.get("height", 0)
                scene.coordinate_space = meta.get("coordinate_space", "pixel")
                scene.native_crs_epsg = meta.get("native_crs_epsg")
                scene.native_crs_wkt = meta.get("native_crs_wkt")
                scene.pixel_size_x = meta.get("pixel_size_x")
                scene.pixel_size_y = meta.get("pixel_size_y")
                scene.pixel_unit = meta.get("pixel_unit")
                scene.validation_status = "ready"
                
                # Check for preview derivative
                if "preview" in resp.output_assets:
                    preview_local = resp.output_assets["preview"]
                    preview_key = f"derived/{project_id}/{scene_id}/preview.png"
                    preview_size, preview_sha = object_store.put_file(
                        bucket=settings.S3_BUCKET_DERIVED,
                        key=preview_key,
                        local_src_path=preview_local,
                        content_type="image/png"
                    )
                    preview_asset = Asset(
                        id=str(uuid.uuid4()),
                        project_id=project_id,
                        scene_id=scene_id,
                        role="preview",
                        bucket=settings.S3_BUCKET_DERIVED,
                        storage_key=preview_key,
                        sha256_hash=preview_sha,
                        byte_size=preview_size,
                        media_type="image/png",
                        commit_status="committed"
                    )
                    db.add(preview_asset)
            else:
                scene.validation_status = "invalid"
                scene.validation_error = resp.error_message
        else:
            scene.validation_status = "failed"
            scene.validation_error = f"Ingestion process error: {res.stderr}"

        db.commit()
        db.refresh(scene)
        return scene, asset
