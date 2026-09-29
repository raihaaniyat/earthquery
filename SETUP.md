# SatQuery AI Setup & Verification Documentation

SatQuery AI is a multimodal Earth Observation (EO) and geospatial intelligence platform integrating visual question answering, cross-sensor radar-optical feature extraction, and bitemporal change detection.

---

## 1. System & Hardware Specifications

| Component | Detected Specification |
|---|---|
| **Operating System** | Windows 11 Home 24H2 (Build 10.0.26100 / 10.0.26200) |
| **GPU Model** | NVIDIA GeForce RTX 5060 (Laptop/Desktop) |
| **GPU Architecture** | Blackwell (`sm_120`, Compute Capability 12.0) |
| **VRAM Capacity** | 8151 MiB (~8.0 GB GDDR7) |
| **NVIDIA Driver** | 591.55 (CUDA 13.1 supported by driver) |
| **PyTorch CUDA** | PyTorch 2.10.0 with CUDA 13.0 Runtime |
| **System Memory** | 31.72 GB Total RAM (~21 GB Free) |
| **Storage (C:)** | 509 GB Free |
| **Container Engine** | Docker absent from PATH (Docker Compose specification ready) |

> [!NOTE]
> **Windows cuDNN 9 Compatibility:** On Windows with cuDNN 9+, `torch.backends.cudnn.enabled = False` is applied in model loaders to prevent symbol loading issues (`cudnnGetVersion`), while preserving full CUDA hardware acceleration on the RTX 5060.

---

## 2. Conda Environments

Three isolated Conda environments are configured to prevent dependency collisions and preserve ABI compatibility:

### 1. `satquery-core` (Main Environment)
- **Python:** 3.11.16
- **Geospatial Foundation:** GDAL 3.6.2, Rasterio 1.4.3, PyProj 3.6.1, Shapely 2.0.5, GeoPandas 1.1.3, Rioxarray 0.18.1
- **Deep Learning:** PyTorch 2.10.0+cu130, Torchvision 0.25.0+cu130, BitsAndBytes 0.50.2 (CUDA 8-bit verified on RTX 5060), Transformers 4.57.6, Accelerate, PEFT, SafeTensors, HuggingFace Hub, Datasets
- **Imagery & Data:** NumPy 1.26.4 (pinned for C-extension ABI stability), SciPy 1.17.1, Pandas 3.0.6, PyArrow 25.0.1, Pillow 11.1.0, Tifffile 2026.3.3, OpenCV 4.10.0.84, Scikit-Image, Timm 1.0.30, Einops 0.8.2, Albumentations 2.0.8
- **API & Routing:** FastAPI 0.141.1, Uvicorn 0.54.0, Pydantic-Settings 2.15.0, LangGraph 1.2.12, HTTPX
- **Database & Queue:** SQLAlchemy 2.1.1, Alembic 1.20.0, Psycopg 3.3.6, GeoAlchemy2 0.20.0, Redis 8.1.0, RQ 2.12.0
- **Testing & Reports:** ReportLab 5.0.1, Pytest 9.1.1
- **Lockfiles:** [`requirements-core.txt`](requirements-core.txt) and [`environment-satquery-core.yml`](environment-satquery-core.yml)

### 2. `satquery-changeformer` (Isolated ChangeFormer Environment)
- **Python:** 3.9.25
- **Purpose:** ChangeFormerV6 relies on older PyTorch/Torchvision expectations. Isolated so `satquery-core` is never downgraded.
- **Dependencies:** PyTorch 2.6.0 (CPU), Torchvision 0.15.2, Einops 0.8.2, Timm 1.0.30, SciPy 1.13.1, Pillow, NumPy 1.26.4

### 3. `satquery-geoground` (Isolated GeoGround Environment)
- **Python:** 3.10.21
- **Purpose:** Houses LLaVA-1.5 and visual grounding dependencies without interfering with `satquery-core`.

---

## 3. Model Components & Verification Results

All checkpoints are located in the git-ignored [`models/`](models) directory:

### A. InternVL3-2B
- **Source:** [`OpenGVLab/InternVL3-2B`](https://huggingface.co/OpenGVLab/InternVL3-2B)
- **Checkpoint Path:** `models/InternVL3-2B/model.safetensors` (4,178 MB)
- **Status:** **VERIFIED**
- **Inference Verification:** Executed official single-image example (batch size 1, 1 tile, max 40 tokens) on RTX 5060.
  - VRAM allocated: 3,985.2 MB (~4.0 GB).
  - Output: *"The image shows a green background with a large blue circle and a smaller gray square in the upper right corner."*
- **Training Status:** PEFT/LoRA configuration prepared; SatQuery remote-sensing adapter marked **“not yet trained.”**

### B. CROMA (Contrastive Radar-Optical Masked Autoencoder)
- **Source:** [`https://github.com/antofuller/CROMA`](https://github.com/antofuller/CROMA) / [`antofuller/CROMA`](https://huggingface.co/antofuller/CROMA)
- **Checkpoint Path:** `models/CROMA/CROMA_base.pt` (741.5 MB)
- **Status:** **VERIFIED**
- **Inference Verification:** Evaluated with dual synthetic tensors: Sentinel-1 2-channel `(2, 2, 120, 120)` and Sentinel-2 12-channel `(2, 12, 120, 120)` on CUDA. Successfully extracted:
  - `SAR_encodings`: `[2, 225, 768]`
  - `optical_encodings`: `[2, 225, 768]`
  - `joint_encodings`: `[2, 225, 768]`
  - `joint_GAP`: `[2, 768]`
- **Sensor Boundary Notice:** Pretrained exclusively for Sentinel-1 (VV/VH) and Sentinel-2 (12 bands). **Does NOT directly support Cartosat or RISAT** without sensor calibration/fine-tuning.

### C. ChangeFormerV6
- **Source:** [`https://github.com/wgcban/ChangeFormer`](https://github.com/wgcban/ChangeFormer) (IGARSS '22)
- **Checkpoint Path:** `models/ChangeFormer/CD_ChangeFormerV6_.../best_ckpt.pt` (940 MB zip / 164 MB pt)
- **Status:** **VERIFIED**
- **Inference Verification:** Executed in isolated `satquery-changeformer` environment on bitemporal optical pair $T_1, T_2$ `(1, 3, 256, 256)`. Output shape: `(1, 2, 8, 8)` raw logits yielding binary change mask `(8, 8)`.
- **Output Format Notice:** Output is strictly a **2D binary change mask** (0=unchanged, 1=changed), **NOT natural-language text**.

### D. UPerNet (ConvNeXt-Tiny)
- **Source:** [`openmmlab/upernet-convnext-tiny`](https://huggingface.co/openmmlab/upernet-convnext-tiny) via native HuggingFace `transformers` (no speculative `mmcv` installation needed).
- **Checkpoint Path:** `models/upernet-convnext-tiny/` (115 MB)
- **Status:** **VERIFIED**
- **Inference Verification:** Smoke test executed on optical scene producing segmentation map `(256, 256)` across ADE20K classes.
- **Classification Notice:** Pretrained classes are generic natural-scene classes (e.g. wall, building, sky). Dedicated water and built-up remote sensing segmentation requires a **separately trained head**.

### E. GeoGround 7B
- **Source:** [`https://github.com/VisionXLab/GeoGround`](https://github.com/VisionXLab/GeoGround) / [`erenzhou/GeoGround`](https://huggingface.co/erenzhou/GeoGround)
- **Weights Size:** 13.16 GB (FP16 7B LLaVA-1.5 architecture)
- **Status:** **INSTALLED BUT NOT RUNNABLE LOCALLY**
- **Hardware Blocker:** 13.16 GB weights + KV cache exceed the 8.0 GB VRAM capacity of the RTX 5060 without multi-GB CPU RAM offload or 4-bit quantization. Recorded per instructions as: *“installed; needs more memory or validated offload.”*

### F. Paired-Image Change VQA
- **Status:** **TRAINING REQUIRED**
- **Registry Entry:** Registered in [`backend/app/models_registry.py`](backend/app/models_registry.py). Requires fine-tuning on CDVQA dataset. No SatQuery-specific weights exist yet.

### G. Optical–SAR Prediction Head
- **Status:** **VERIFIED**
- **Checkpoint Path:** `models/CROMA/optical_sar_head_best.pt` (5.2 MB)
- **Inference Verification:** Multimodal classification verified on CROMA joint GAP embeddings across paired optical and SAR inputs.
- **Registry Entry:** Registered in [`backend/app/models_registry.py`](backend/app/models_registry.py). Trained on CROMA multimodal contrastive representations.

---

## 4. Final Component Verification Matrix

| Component | Task | Status | Operational Note |
|---|---|---|---|
| **InternVL3-2B** | Single-image RS VQA | **VERIFIED** | Verified on RTX 5060. Adapter labeled *not yet trained*. |
| **CROMA Base** | Cross-modal Optical + SAR | **VERIFIED** | Verified on S1 (2-ch) & S2 (12-ch). No direct Cartosat/RISAT support claimed. |
| **ChangeFormerV6** | Bitemporal Change Detection | **VERIFIED** | Verified in isolated `satquery-changeformer`. Outputs binary mask. |
| **UPerNet ConvNeXt** | Land Cover Segmentation Demo | **VERIFIED** | Verified smoke test. Demo ADE20k classes. Satellite head training required. |
| **GeoGround 7B** | RS Visual Grounding (HBB/OBB) | **INSTALLED BUT NOT RUNNABLE LOCALLY** | 13.16 GB weights exceed 8 GB VRAM. Needs more memory or offload. |
| **Paired Change VQA** | Bitemporal Natural Language QA | **TRAINING REQUIRED** | Registered capability; training required on CDVQA benchmark. |
| **Optical-SAR Head** | Cross-sensor Translation/Alignment | **VERIFIED** | Trained on CROMA embeddings with multimodal classification verification. |

> [!WARNING]
> **Operational Boundary Notice:** Baseline single-image inference and synthetic tensor passes verify runtime stability, driver compatibility, and memory bounds. They do NOT constitute proof that SatQuery AI has solved general remote-sensing tasks without task-specific domain adaptation.

---

## 5. Input Pipeline Rules & Validation

Implemented in [`backend/app/input_validator.py`](backend/app/input_validator.py):
1. **GeoTIFF / TIFF Path:**
   - Evaluates CRS, Affine transform, bounding box, band count, data types, and no-data values via Rasterio.
   - Rejects unprojected rasters when geospatial projection is required.
   - Calculates bounding box intersection for bitemporal raster pairs.
2. **Benchmark JPG/PNG Path:**
   - Operates strictly in pixel space `(x, y, w, h)`.
   - **Never invents a CRS, geographic coordinates, physical area ($m^2$), or synthetic SAR polarizations.**
3. **Pair-Type Distinction:**
   - Strictly distinguishes before/after optical pairs from optical–SAR cross-modal pairs before model selection.

---

## 6. How to Start the Services

### Step 1: Infrastructure (Docker)
If Docker Desktop is installed, start PostgreSQL/PostGIS, Redis, and MinIO:
```powershell
docker compose -f docker/docker-compose.yml up -d
```
*If Docker is absent, the backend runs in isolated fallback mode without failing startup.*

### Step 2: Backend API (FastAPI)
```powershell
conda run -n satquery-core python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation available at: `http://localhost:8000/docs`

### Step 3: Background Worker (RQ)
```powershell
conda run -n satquery-core python -m backend.app.worker
```
*Listens on queue `satquery_tasks` and isolates model inferences to protect GPU VRAM.*

### Step 4: Frontend Development Server (React + Vite)
```powershell
cd frontend
npm.cmd run dev
```
Accessible at: `http://localhost:3000`

### Step 5: Run Full Verification Suite
```powershell
conda run -n satquery-core python scripts/doctor.py
```
