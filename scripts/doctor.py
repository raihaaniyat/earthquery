#!/usr/bin/env python3
"""
SatQuery AI Diagnostic Suite & Orchestrator.
Supports scopes: infrastructure, pipeline, models, all.
Executes lightweight checks in satquery-api and delegates isolated model/geospatial checks
to their respective environments without polluting satquery-api with heavy libraries.
"""

import os
import sys
import json
import shutil
import socket
import argparse
import subprocess
from pathlib import Path
from typing import Dict, Any, List

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CONDA_EXE = r"C:\Users\HP\miniconda3\Scripts\conda.exe"



def print_banner(title: str):
    print("\n" + "=" * 78)
    print(f"  {title.upper()}")
    print("=" * 78)


def check_infrastructure() -> Dict[str, Any]:
    print_banner("Infrastructure Scope: Services, Storage, and System Resources")
    import platform
    import psutil

    results = {}

    # 1. System Resources
    os_info = f"{platform.system()} {platform.release()} (Build {platform.version()})"
    total_ram_gb = psutil.virtual_memory().total / (1024 ** 3)
    free_ram_gb = psutil.virtual_memory().available / (1024 ** 3)
    free_disk_gb = shutil.disk_usage("C:\\").free / (1024 ** 3)

    print(f"OS:               {os_info}")
    print(f"System RAM:       {total_ram_gb:.2f} GB Total ({free_ram_gb:.2f} GB Free)")
    print(f"C: Free Disk:     {free_disk_gb:.2f} GB Free (Budget > 10 GB)")

    results["system"] = {
        "status": "PASS" if free_disk_gb > 10 and total_ram_gb >= 16 else "WARN",
        "os": os_info,
        "ram_gb": round(total_ram_gb, 2),
        "free_disk_gb": round(free_disk_gb, 2)
    }

    # 2. Docker & WSL
    docker_found = shutil.which("docker") is not None
    wsl_check = subprocess.run(["wsl", "-l", "-v"], capture_output=True, text=True)
    wsl_found = wsl_check.returncode == 0

    print(f"Docker Executable: {'FOUND' if docker_found else 'MISSING FROM PATH (Docker Desktop WSL 2 recommended)'}")
    print(f"WSL 2 Subsystem:   {'INSTALLED' if wsl_found else 'NOT INSTALLED (Run wsl.exe --install)'}")

    results["docker"] = {"status": "PASS" if docker_found else "BLOCKED", "installed": docker_found}
    results["wsl"] = {"status": "PASS" if wsl_found else "BLOCKED", "installed": wsl_found}

    # 3. PostgreSQL / PostGIS
    try:
        from backend.app.db.session import check_db_connection
        db_info = check_db_connection()
        if db_info["connected"]:
            db_status = "PASS"
            print(f"PostgreSQL/PostGIS: CONNECTED (PostGIS: {db_info.get('postgis_version') or 'Active'})")
        else:
            db_status = "BLOCKED"
            print(f"PostgreSQL/PostGIS: BLOCKED ({db_info.get('error')})")
        results["database"] = {"status": db_status, "details": db_info}
    except Exception as e:
        print(f"PostgreSQL/PostGIS: ERROR ({e})")
        results["database"] = {"status": "FAIL", "error": str(e)}

    # 4. Redis Queue
    try:
        from backend.app.worker import check_redis_connection
        redis_info = check_redis_connection()
        if redis_info["connected"]:
            r_status = "PASS"
            print("Redis Queue Server: CONNECTED (127.0.0.1:6379)")
        else:
            r_status = "BLOCKED"
            print(f"Redis Queue Server: BLOCKED ({redis_info.get('error')})")
        results["redis"] = {"status": r_status, "details": redis_info}
    except Exception as e:
        print(f"Redis Queue Server: ERROR ({e})")
        results["redis"] = {"status": "FAIL", "error": str(e)}

    # 5. Object Storage (S3 / SeaweedFS / Local Fallback)
    try:
        from backend.app.services.storage import object_store
        s3_ok = object_store.is_s3_available()
        storage_status = "PASS" if s3_ok else "PASS (LOCAL_STORAGE_MIRROR_ACTIVE)"
        print(f"Object Storage:     {storage_status}")
        results["storage"] = {
            "status": "PASS",
            "s3_available": s3_ok,
            "local_root": str(object_store.local_storage_root)
        }
    except Exception as e:
        print(f"Object Storage:     ERROR ({e})")
        results["storage"] = {"status": "FAIL", "error": str(e)}

    return results


def check_pipeline() -> Dict[str, Any]:
    print_banner("Pipeline Scope: Isolated Conda Environments & Subprocess Runners")
    results = {}

    envs_to_check = [
        ("satquery-api", "FastAPI, SQLAlchemy 2, Alembic, Pydantic, Boto3, RQ"),
        ("satquery-core", "PyTorch 2.10, CUDA 13, GDAL, Rasterio, InternVL, CROMA, UPerNet"),
        ("satquery-changeformer", "PyTorch 2.6, ChangeFormerV6 (CPU inference)"),
        ("satquery-geoground", "Python 3.10, GeoGround 7B (Isolated weights)"),
        ("satquery-tools", "pip-tools, huggingface_hub, pytest, ruff")
    ]

    for env_name, desc in envs_to_check:
        cmd = [CONDA_EXE, "run", "-n", env_name, "python", "-c", "import sys; print(sys.version.split()[0])"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            py_ver = res.stdout.strip()
            print(f"[{env_name:<22}] READY (Python {py_ver}) — {desc}")
            results[env_name] = {"status": "PASS", "python": py_ver}
        else:
            print(f"[{env_name:<22}] NOT FOUND or ERROR ({res.stderr.strip()[:60]})")
            results[env_name] = {"status": "FAIL", "error": res.stderr.strip()}

    # Check Geospatial Subprocess
    print("\nTesting satquery-core geospatial subprocess runner...")
    req_json = json.dumps({
        "job_id": "doctor-pipeline-test",
        "step_key": "health_check",
        "attempt_id": "1",
        "model_version_id": "none",
        "task_type": "metadata_extraction",
        "asset_references": {"original": str(REPO_ROOT / "data" / "samples" / "sample_optical.png")},
        "output_dir": str(REPO_ROOT / "cache" / "doctor_test")
    })
    resp_path = REPO_ROOT / "cache" / "doctor_test" / "resp.json"
    os.makedirs(resp_path.parent, exist_ok=True)

    cmd = [
        CONDA_EXE, "run", "-n", "satquery-core", "--no-capture-output",
        "python", "-m", "backend.runtime.preprocess",
        "--request-json", req_json,
        "--response-json", str(resp_path)
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT)
    sub_res = subprocess.run(cmd, capture_output=True, text=True, env=env)

    if sub_res.returncode == 0 and resp_path.exists():
        with open(resp_path, "r", encoding="utf-8") as f:
            sub_data = json.load(f)
        print(f"Geospatial Subprocess: PASSED (Processed in {sub_data.get('metrics', {}).get('duration_ms', 0):.1f} ms)")
        results["geospatial_subprocess"] = {"status": "PASS"}
    else:
        print(f"Geospatial Subprocess: FAILED ({sub_res.stderr.strip()[:100]})")
        results["geospatial_subprocess"] = {"status": "FAIL", "error": sub_res.stderr.strip()}

    return results


def check_models() -> Dict[str, Any]:
    print_banner("Models Scope: Checkpoint Verification & Capability Matrix")
    from scripts.verify_models import verify_models
    return verify_models("config/models.yaml")


def main():
    parser = argparse.ArgumentParser(description="SatQuery Diagnostic Suite")
    parser.add_argument("--scope", choices=["infrastructure", "pipeline", "models", "all"], default="all")
    parser.add_argument("--json", action="store_true", help="Output summary in JSON")
    args = parser.parse_args()

    overall = {}
    if args.scope in ("infrastructure", "all"):
        overall["infrastructure"] = check_infrastructure()
    if args.scope in ("pipeline", "all"):
        overall["pipeline"] = check_pipeline()
    if args.scope in ("models", "all"):
        overall["models"] = check_models()

    if args.json:
        print("\n" + json.dumps(overall, indent=2))


if __name__ == "__main__":
    main()
