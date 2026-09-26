"""
Export Database & Storage Snapshot Manifest for Backup.
Handles database connectivity gracefully when container services are offline.
"""

import sys
import json
import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.db.session import SessionLocal
from backend.app.db.models import Scene, Asset, AnalysisJob, Finding, Report
from backend.app.config import settings


def main():
    parser = argparse.ArgumentParser(description="Export backup manifest")
    parser.add_argument("--dest-folder", required=True, help="Destination backup directory")
    args = parser.parse_args()

    manifest = {
        "database_status": "connected",
        "scenes": [],
        "assets": [],
        "jobs": [],
        "findings_count": 0,
        "reports_count": 0
    }

    try:
        db = SessionLocal()
        manifest["scenes"] = [{"id": s.id, "name": s.name} for s in db.query(Scene).all()]
        manifest["assets"] = [
            {
                "id": a.id,
                "role": a.role,
                "storage_key": a.storage_key,
                "sha256": a.sha256_hash,
                "size": a.byte_size
            } for a in db.query(Asset).all()
        ]
        manifest["jobs"] = [{"id": j.id, "status": j.status, "task_type": j.task_type} for j in db.query(AnalysisJob).all()]
        manifest["findings_count"] = db.query(Finding).count()
        manifest["reports_count"] = db.query(Report).count()
        db.close()
    except Exception as e:
        manifest["database_status"] = f"offline ({type(e).__name__}: {str(e)[:100]})"
        print(f"Notice: Database is offline ({type(e).__name__}). Exporting filesystem storage assets.")
        
        # Scan local storage directory for assets
        storage_root = Path(settings.SATQUERY_STORAGE_ROOT)
        if storage_root.exists():
            for f_path in storage_root.glob("**/*"):
                if f_path.is_file():
                    rel_key = str(f_path.relative_to(storage_root)).replace("\\", "/")
                    manifest["assets"].append({
                        "id": f_path.stem,
                        "role": "local_storage_file",
                        "storage_key": rel_key,
                        "sha256": "local",
                        "size": f_path.stat().st_size
                    })

    out_path = Path(args.dest_folder) / "manifest.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    print(f"Saved manifest with {len(manifest['assets'])} assets (Database: {manifest['database_status']}).")


if __name__ == "__main__":
    main()
