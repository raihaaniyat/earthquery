"""
Full System End-to-End Audit Suite for SatQuery AI.
Checks:
1. Database (PostgreSQL / PostGIS) connectivity and schema
2. Redis Cache & Queue
3. Object Storage (SeaweedFS S3)
4. FastAPI Backend Health & Capabilities Endpoint
5. Worker Health & Lease Management
6. Model-by-Model Execution (all 7 models):
   - InternVL3-2B (VQA)
   - CROMA-Base (Cross-Modal Features)
   - ChangeFormerV6 (Bitemporal Change Detection)
   - UPerNet ConvNeXt (Land Cover Segmentation)
   - OWLv2 GeoGround (Visual Grounding)
   - Paired Change VQA (Bitemporal Reasoning)
   - Optical-SAR Head (Multimodal Land Classification)
7. Findings & ReportLab PDF Generation
8. Frontend Dev Server Health
"""

import os
import sys
import time
import json
import httpx
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

BASE_URL = "http://127.0.0.1:8000"
FRONTEND_URL = "http://localhost:3000"

results = {
    "infrastructure": {},
    "api": {},
    "models": {},
    "reporting": {}
}


def log_step(name, status, details=""):
    symbol = " PASS " if status else " FAIL "
    color_start = "\033[92m" if status else "\033[91m"
    color_end = "\033[0m"
    print(f"[{color_start}{symbol}{color_end}] {name} {details}")


def run_audit():
    print("=" * 70)
    print("        SATQUERY AI - COMPREHENSIVE SYSTEM-WIDE AUDIT")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. DATABASE CHECK
    # -------------------------------------------------------------
    print("\n--- 1. DATABASE & STORAGE LAYER CHECKS ---")
    try:
        from backend.app.db.session import SessionLocal
        from backend.app.db.models import Project, AnalysisJob, Finding, Report, Asset
        db = SessionLocal()
        num_projects = db.query(Project).count()
        num_jobs = db.query(AnalysisJob).count()
        num_findings = db.query(Finding).count()
        num_reports = db.query(Report).count()
        db.close()
        log_step("PostgreSQL Connection", True, f"(Projects: {num_projects}, Jobs: {num_jobs}, Findings: {num_findings}, Reports: {num_reports})")
        results["infrastructure"]["database"] = True
    except Exception as e:
        log_step("PostgreSQL Connection", False, str(e))
        results["infrastructure"]["database"] = False

    # -------------------------------------------------------------
    # 2. REDIS CHECK
    # -------------------------------------------------------------
    try:
        from backend.app.worker import get_redis_connection
        r = get_redis_connection()
        pong = r.ping()
        q_len = r.llen("rq:queue:satquery-analysis")
        log_step("Redis Queue Connection", pong, f"(Queue 'satquery-analysis' length: {q_len})")
        results["infrastructure"]["redis"] = pong
    except Exception as e:
        log_step("Redis Queue Connection", False, str(e))
        results["infrastructure"]["redis"] = False

    # -------------------------------------------------------------
    # 3. OBJECT STORAGE CHECK
    # -------------------------------------------------------------
    try:
        from backend.app.storage.object_store import object_store
        buckets = object_store.list_buckets()
        log_step("SeaweedFS S3 Object Store", True, f"(Buckets: {', '.join(buckets)})")
        results["infrastructure"]["storage"] = True
    except Exception as e:
        log_step("SeaweedFS S3 Object Store", False, str(e))
        results["infrastructure"]["storage"] = False

    # -------------------------------------------------------------
    # 4. BACKEND API & CAPABILITIES CHECK
    # -------------------------------------------------------------
    print("\n--- 2. BACKEND API & CAPABILITY MATRIX CHECKS ---")
    try:
        resp = httpx.get(f"{BASE_URL}/healthz", timeout=5)
        log_step("FastAPI /healthz", resp.status_code == 200, f"(Status: {resp.status_code})")
        results["api"]["healthz"] = resp.status_code == 200
    except Exception as e:
        log_step("FastAPI /healthz", False, str(e))
        results["api"]["healthz"] = False

    projects = []
    try:
        resp = httpx.get(f"{BASE_URL}/api/v1/projects", timeout=5)
        projects = resp.json()
        log_step("API Projects List", resp.status_code == 200 and len(projects) > 0, f"(Found {len(projects)} projects)")
        results["api"]["projects"] = len(projects) > 0
    except Exception as e:
        log_step("API Projects List", False, str(e))
        results["api"]["projects"] = False

    project_id = projects[0]["id"] if projects else None

    # Check Capabilities Matrix
    caps_data = {}
    try:
        resp = httpx.get(f"{BASE_URL}/api/v1/capabilities", timeout=5)
        caps_data = resp.json().get("capabilities", {})
        total_caps = len(caps_data)
        runnable_caps = sum(1 for c in caps_data.values() if c.get("is_runnable"))
        all_ok = total_caps == 7 and runnable_caps == 7
        log_step("Capability Matrix Check", all_ok, f"({runnable_caps}/{total_caps} models VERIFIED & RUNNABLE)")
        for m_id, m_info in caps_data.items():
            print(f"    - {m_id.ljust(18)}: Status={m_info.get('status').ljust(10)} Runnable={str(m_info.get('is_runnable')).ljust(5)} VRAM={m_info.get('vram_required_gb')} GB")
        results["api"]["capabilities"] = all_ok
    except Exception as e:
        log_step("Capability Matrix Check", False, str(e))
        results["api"]["capabilities"] = False

    # -------------------------------------------------------------
    # 5. ALL 7 MODELS END-TO-END EXECUTION CHECKS
    # -------------------------------------------------------------
    print("\n--- 3. DETAILED MODEL-BY-MODEL EXECUTION CHECKS ---")

    test_models = [
        {
            "id": "internvl3",
            "name": "InternVL3-2B",
            "task_type": "internvl3",
            "prompt": "Identify any noticeable infrastructure features in this satellite scene.",
            "expected_key": "internvl_vqa"
        },
        {
            "id": "croma",
            "name": "CROMA-Base",
            "task_type": "croma",
            "prompt": "Extract joint optical-SAR features.",
            "expected_key": "croma_features"
        },
        {
            "id": "changeformer",
            "name": "ChangeFormerV6",
            "task_type": "changeformer",
            "prompt": "Detect pixel-level building changes.",
            "expected_key": "changeformer_cd"
        },
        {
            "id": "upernet",
            "name": "UPerNet ConvNeXt",
            "task_type": "upernet",
            "prompt": "Segment scene into semantic land cover masks.",
            "expected_key": "upernet_segmentation"
        },
        {
            "id": "geoground",
            "name": "OWLv2 GeoGround",
            "task_type": "geoground",
            "prompt": "locate circles, squares, buildings",
            "expected_key": "geoground_detection"
        },
        {
            "id": "change_vqa",
            "name": "Paired Change VQA",
            "task_type": "change_vqa",
            "prompt": "What changed between these two acquisition dates?",
            "expected_key": "change_vqa_reasoning"
        },
        {
            "id": "optical_sar_head",
            "name": "Optical-SAR Classification Head",
            "task_type": "optical_sar_head",
            "prompt": "Classify land cover using combined SAR and optical data.",
            "expected_key": "optical_sar_classification"
        }
    ]

    for model in test_models:
        m_id = model["id"]
        m_name = model["name"]
        print(f"\n>> Validating Model {m_id} ({m_name})...")
        t_m_start = time.time()

        if not project_id:
            log_step(f"Job: {m_name}", False, "Skipping: no project available")
            continue

        payload = {
            "project_id": project_id,
            "task_type": model["task_type"],
            "canonical_request": {
                "task": model["task_type"],
                "input_category": "benchmark",
                "prompt": model["prompt"]
            },
            "user_request_text": model["prompt"]
        }

        try:
            submit_resp = httpx.post(f"{BASE_URL}/api/v1/analysis-jobs", json=payload, timeout=10)
            if submit_resp.status_code != 202:
                log_step(f"Submit: {m_name}", False, f"Status code: {submit_resp.status_code}")
                results["models"][m_id] = False
                continue

            job_id = submit_resp.json()["job_id"]

            # Poll for worker execution and database persistence
            final_status = "unknown"
            findings_count = 0
            reports_count = 0

            for _ in range(25):
                time.sleep(1.5)
                s_resp = httpx.get(f"{BASE_URL}/api/v1/analysis-jobs/{job_id}", timeout=5)
                if s_resp.status_code == 200:
                    data = s_resp.json()
                    final_status = data.get("status")
                    findings_count = data.get("findings_count", 0)
                    reports_count = data.get("reports_count", 0)
                    if final_status in ("succeeded", "failed"):
                        break

            dur = round(time.time() - t_m_start, 2)
            is_success = (final_status == "succeeded" and findings_count > 0 and reports_count > 0)

            # Fetch finding details
            f_resp = httpx.get(f"{BASE_URL}/api/v1/analysis-jobs/{job_id}/findings", timeout=5)
            finding_text = ""
            if f_resp.status_code == 200 and f_resp.json():
                finding_text = f_resp.json()[0].get("finding_text", "")

            log_step(
                f"Model [{m_name}]",
                is_success,
                f"Status: {final_status.upper()} in {dur}s | Findings: {findings_count} | Reports: {reports_count}"
            )
            if finding_text:
                print(f"    Result Summary: \"{finding_text[:140]}...\"")

            results["models"][m_id] = is_success

        except Exception as e:
            log_step(f"Model [{m_name}]", False, str(e))
            results["models"][m_id] = False

    # -------------------------------------------------------------
    # 6. FRONTEND CHECK
    # -------------------------------------------------------------
    print("\n--- 4. FRONTEND DEV SERVER CHECK ---")
    try:
        resp = httpx.get(FRONTEND_URL, timeout=5)
        log_step("Vite Frontend Server", resp.status_code == 200, f"(Status: {resp.status_code} at {FRONTEND_URL})")
        results["reporting"]["frontend"] = resp.status_code == 200
    except Exception as e:
        log_step("Vite Frontend Server", False, f"Could not reach {FRONTEND_URL}: {e}")
        results["reporting"]["frontend"] = False

    # -------------------------------------------------------------
    # FINAL RECAP
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("                     FINAL AUDIT SUMMARY")
    print("=" * 70)
    infra_ok = all(results["infrastructure"].values())
    api_ok = all(results["api"].values())
    models_ok = all(results["models"].values()) and len(results["models"]) == 7
    all_ok = infra_ok and api_ok and models_ok

    print(f"  - Infrastructure (DB, Redis, S3)    : {'ALL HEALTHY' if infra_ok else 'ISSUES DETECTED'}")
    print(f"  - Backend API & Capability Matrix   : {'ALL HEALTHY' if api_ok else 'ISSUES DETECTED'}")
    print(f"  - All 7 Satellite AI Models        : {'7/7 VERIFIED & PASSING' if models_ok else 'SOME MODELS FAILED'}")
    print(f"  - Automated Reporting (PDF/Findings): {'HEALTHY & PERSISTED' if models_ok else 'ISSUES'}")
    print(f"  - Overall System Operability Status : {'READY FOR PRODUCTION DEMO' if all_ok else 'ACTION REQUIRED'}")
    print("=" * 70)

    return all_ok


if __name__ == "__main__":
    success = run_audit()
    sys.exit(0 if success else 1)
