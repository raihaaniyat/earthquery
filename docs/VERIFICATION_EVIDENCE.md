# SatQuery AI — Verification Evidence & Full-Stack Audit

**Execution Date:** 2026-09-26  
**Host Machine:** Windows 11 Home (Build 10.0.26200), RTX 5060 Laptop (8 GB VRAM, sm_120 Blackwell, CC 12.0)  
**System Memory:** 31.72 GB RAM (18.7 GB Free), 508.4 GB Free Disk on C:  
**Current Git Commit:** `be28fa4` (Branch: `feat/antigravity-backend`)  

---

## 1. System & Dependency Environment Verification

### Conda Environment Isolation Audit
| Environment | Python | Key Packages | Verified Capabilities & Hardware | Status |
| :--- | :--- | :--- | :--- | :--- |
| `satquery-api` | 3.11.16 | FastAPI 0.115, SQLAlchemy 2.0, Alembic, Pydantic 2.10, RQ 2.2.0, Boto3 1.35, ReportLab 4.2 | Zero PyTorch/GDAL dependency leakage. Passed `pip check`. | **READY** |
| `satquery-core` | 3.11.16 | PyTorch 2.10.0 (CUDA 13.0, cu130), GDAL 3.6.2, Rasterio 1.4.3, Shapely 2.0.5, PyProj 3.6.1 | CUDA available: `True`. RTX 5060 acceleration verified. Geospatial subprocess benchmark: 9.2 ms. | **READY** |
| `satquery-changeformer` | 3.9.25 | PyTorch 2.6.0, Torchvision 0.15.2a0 | ChangeFormerV6 CPU inference verified. | **READY** |
| `satquery-geoground` | 3.10.21 | Python 3.10, GeoGround 7B (LLaVA-1.5) | 13.16 GB checkpoint intentionally blocked on 8 GB VRAM to prevent hard OOM. | **BLOCKED (BY DESIGN)** |
| `satquery-tools` | 3.11.16 | pip-tools, huggingface_hub, pytest 9.1.1, Ruff | Offline checksum and model verification utilities. | **READY** |

### Frontend Build Verification
- **Framework:** React 18.3.1 + Vite 6.4.3 + TypeScript 5.7.2 + TailwindCSS
- **Build Command:** `cmd.exe /c "npm run build"`
- **Result:**
  ```text
  vite v6.4.3 building for production...
  transforming...
  ✓ 1918 modules transformed.
  rendering chunks...
  computing gzip size...
  dist/index.html                   1.03 kB │ gzip:   0.63 kB
  dist/assets/index-CV8W0B7M.css   22.72 kB │ gzip:   5.02 kB
  dist/assets/index-BxVsxzFe.js   418.99 kB │ gzip: 124.05 kB
  ✓ built in 1.72s
  ```

---

## 2. Infrastructure & Docker/WSL Gate Status (Phase B & C)

- **WSL Status:**
  ```text
  The Windows Subsystem for Linux is not installed. You can install by running 'wsl.exe --install'.
  ```
- **Shell Elevation Check:** `False` (Non-elevated user execution).
- **Recorded Blocker:** `wsl.exe --install` requires Windows Administrator UAC elevation to enable `VirtualMachinePlatform` and install the Linux kernel.
- **Action Required for Docker Stack:**
  Run in an elevated PowerShell prompt:
  ```powershell
  wsl.exe --install -d Ubuntu
  ```
  Followed by Docker Desktop installation enabling the WSL 2 engine.
- **Current Runtime Fallback:**
  - Database: SQLAlchemy Psycopg with SQLite-compatible test adapter.
  - Object Storage: Integrated local filesystem storage mirror active under `storage/` replicating S3 key structure.
  - Image digests pinned in `docker/images.lock.json` (`postgis/postgis:16-3.4`, `redis:7.2.5-alpine`, `chrislusf/seaweedfs:3.79`).

---

## 3. Test Suite Verification (34 / 34 PASSED — 100%)

Command: `conda run -n satquery-api pytest tests/ -v`

```text
============================= test session starts =============================
platform win32 -- Python 3.11.16, pytest-9.1.1, pluggy-1.6.0 -- C:\Users\HP\miniconda3\envs\satquery-api\python.exe
cachedir: .pytest_cache
rootdir: C:\Users\HP\earthquery
configfile: pytest.ini
plugins: anyio-4.15.1, langsmith-0.14.0
collecting ... collected 34 items

tests/integration/test_api_v1.py::test_health_live_endpoint PASSED       [  2%]
tests/integration/test_api_v1.py::test_capabilities_endpoint PASSED      [  5%]
tests/integration/test_api_v1.py::test_projects_lifecycle PASSED         [  8%]
tests/integration/test_api_v1.py::test_scene_upload_and_search PASSED    [ 11%]
tests/integration/test_api_v1.py::test_job_submission_and_status PASSED  [ 14%]
tests/integration/test_api_v1.py::test_model_versions_endpoint PASSED    [ 17%]
tests/integration/test_api_v1.py::test_auth_session_endpoints PASSED     [ 20%]
tests/integration/test_api_v1.py::test_external_providers_endpoints PASSED [ 23%]
tests/unit/test_catalog_and_pairing.py::test_catalog_search_filters_and_excludes_pixel_benchmarks PASSED [ 26%]
tests/unit/test_catalog_and_pairing.py::test_stac_export_rejects_pixel_scene PASSED [ 29%]
tests/unit/test_catalog_and_pairing.py::test_bitemporal_pairing_temporal_inversion PASSED [ 32%]
tests/unit/test_catalog_and_pairing.py::test_optical_sar_pairing_blocks_unsupported_sensors PASSED [ 35%]
tests/unit/test_database_schema.py::test_metadata_contains_all_entities PASSED [ 38%]
tests/unit/test_database_schema.py::test_scene_foreign_keys_and_indices PASSED [ 41%]
tests/unit/test_database_schema.py::test_job_idempotency_constraint PASSED [ 44%]
tests/unit/test_evidence_and_reports.py::test_record_finding_and_evidence_links PASSED [ 47%]
tests/unit/test_evidence_and_reports.py::test_generate_pdf_report PASSED [ 50%]
tests/unit/test_external_and_admission.py::test_bhoonidhi_collections_listing PASSED [ 52%]
tests/unit/test_external_and_admission.py::test_bhoonidhi_search_normalization_and_online_flag PASSED [ 55%]
tests/unit/test_external_and_admission.py::test_bhoonidhi_import_product_and_metadata PASSED [ 58%]
tests/unit/test_external_and_admission.py::test_bhuvan_layers_and_thematic_statistics PASSED [ 61%]
tests/unit/test_external_and_admission.py::test_gpu_supervisor_vram_reserve_admission PASSED [ 64%]
tests/unit/test_external_and_admission.py::test_job_queue_capacity_backpressure PASSED [ 67%]
tests/unit/test_ingestion_service.py::test_object_store_stream_roundtrip PASSED [ 70%]
tests/unit/test_ingestion_service.py::test_ingest_sample_geotiff PASSED  [ 73%]
tests/unit/test_ingestion_service.py::test_ingest_sample_benchmark_png PASSED [ 76%]
tests/unit/test_jobs_and_outbox.py::test_job_creation_and_idempotency PASSED [ 79%]
tests/unit/test_jobs_and_outbox.py::test_job_claim_and_heartbeat PASSED  [ 82%]
tests/unit/test_jobs_and_outbox.py::test_job_cancellation PASSED         [ 85%]
tests/unit/test_jobs_and_outbox.py::test_reconciliation_recovers_expired_lease PASSED [ 88%]
tests/unit/test_worker_lifecycle.py::test_spawn_worker_class_available PASSED [ 91%]
tests/unit/test_worker_lifecycle.py::test_json_task_serialization PASSED [ 94%]
tests/unit/test_worker_lifecycle.py::test_job_execution_with_worker PASSED [ 97%]
tests/unit/test_worker_lifecycle.py::test_job_exception_handling PASSED  [100%]
================= 34 passed in 127.84s =================
```

---

## 4. Operational Diagnostics Evidence (`doctor.py --scope all`)

Command: `conda run -n satquery-api python scripts/doctor.py --scope all`
Exit Code: `0`

```text
==============================================================================
  INFRASTRUCTURE SCOPE: SERVICES, STORAGE, AND SYSTEM RESOURCES
==============================================================================
OS:               Windows 10 (Build 10.0.26200)
System RAM:       31.72 GB Total (18.74 GB Free)
C: Free Disk:     508.42 GB Free (Budget > 10 GB)
Docker Executable: MISSING FROM PATH (Docker Desktop WSL 2 recommended)
WSL 2 Subsystem:   NOT INSTALLED (Run wsl.exe --install)
PostgreSQL/PostGIS: BLOCKED (psycopg.errors.ConnectionTimeout)
Redis Queue Server: BLOCKED (Connection refused at 127.0.0.1:6379)
Object Storage:     PASS (LOCAL_STORAGE_MIRROR_ACTIVE)

==============================================================================
  PIPELINE SCOPE: ISOLATED CONDA ENVIRONMENTS & SUBPROCESS RUNNERS
==============================================================================
[satquery-api          ] READY (Python 3.11.16) — FastAPI, SQLAlchemy 2, Alembic, Pydantic, Boto3, RQ
[satquery-core         ] READY (Python 3.11.16) — PyTorch 2.10, CUDA 13, GDAL, Rasterio, InternVL, CROMA, UPerNet
[satquery-changeformer ] READY (Python 3.9.25) — PyTorch 2.6, ChangeFormerV6 (CPU inference)
[satquery-geoground    ] READY (Python 3.10.21) — Python 3.10, GeoGround 7B (Isolated weights)
[satquery-tools        ] READY (Python 3.11.16) — pip-tools, huggingface_hub, pytest, ruff

Testing satquery-core geospatial subprocess runner...
Geospatial Subprocess: PASSED (Processed in 9.2 ms)

==============================================================================
  MODELS SCOPE: CHECKPOINT VERIFICATION & CAPABILITY MATRIX
==============================================================================
Model ID           | Task                   | State                | Status    
--------------------------------------------------------------------------------
internvl3          | vqa                    | LOAD_TESTED          | PASS      
croma              | feature_extraction     | LOAD_TESTED          | PASS      
changeformer       | bitemporal_change      | LOAD_TESTED          | PASS      
upernet            | land_cover_segmentation | LOAD_TESTED          | PASS      
geoground          | visual_grounding       | INSTALLED_NOT_RUNNABLE_LOCALLY | BLOCKED   
change_vqa         | change_vqa             | TRAINING_REQUIRED    | BLOCKED   
optical_sar_head   | optical_sar_classification | TRAINING_REQUIRED    | BLOCKED   
==============================================================================
```

---

## 5. Frontend & Full-Stack Journey Checklist

- [x] **Project Management:** Project creation and selection synced across UI and backend catalog.
- [x] **Scene Ingestion:** Upload with progress bar; distinction between GeoTIFF (EPSG:4326/projected) and Pixel Benchmark (PNG/JPG).
- [x] **Model Capability Enforcement:** Dynamic capabilities loaded from `/api/v1/capabilities`. Submissions to blocked/untrained models disabled with explicit reasons.
- [x] **Asynchronous Job Monitor:** Real-time polling with durable event IDs; displays `queued`, `waiting_for_resources`, `running`, `succeeded`, `cancelled`, and `failed`.
- [x] **Cancellation:** Interactive cancel button issues `POST /api/v1/analysis-jobs/{id}/cancel` and awaits durable cancellation acknowledgment.
- [x] **Capacity Backpressure:** Handled `HTTP 429 Too Many Requests` with `Retry-After: 30` header and visible countdown timer.
- [x] **Findings & PDF Reports:** Factual findings displayed with confidence metrics; ReportLab PDF downloadable directly from storage asset URL.
- [x] **ISRO BHOONIDHI STAC:** Search across 8 official collections with `Online=Y` validation and staged streaming import.
- [x] **Bhuvan Contextual Layers:** Toggleable WMS thematic overlays (`lulc_50k`, `flood_hazard`, `water_bodies`) with explicit attribution and visual separation from ML prediction masks.
