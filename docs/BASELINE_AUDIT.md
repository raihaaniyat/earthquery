# SatQuery AI — Baseline System and Environment Audit (Phase 0)
**Date/Time:** 2026-09-25T21:42:56.4063742+05:30
**Host OS:** Windows 10 (Build 10.0.26200)
**Platform Architecture:** AMD64
**C: Disk Free:** 508.94 GB (Total: 1056.38 GB)
**NVIDIA GPU & Driver:** NVIDIA GeForce RTX 5060, 8151 MiB, 591.55
**WSL Installed:** No (wsl error / not installed)
**Docker in PATH:** No

## 1. Existing Conda Environments
```text
# conda environments:
#
# * -> active
# + -> frozen
                         C:\Users\HP\.anaconda-desktop\micromamba\envs\assistant
                         C:\Users\HP\.anaconda-desktop\micromamba\envs\cuda
                         C:\Users\HP\anaconda3
base                     C:\Users\HP\miniconda3
earthdial                C:\Users\HP\miniconda3\envs\earthdial
satquery-changeformer     C:\Users\HP\miniconda3\envs\satquery-changeformer
satquery-core            C:\Users\HP\miniconda3\envs\satquery-core
satquery-geoground       C:\Users\HP\miniconda3\envs\satquery-geoground
```

## 2. Geospatial Stack Audit (`satquery-core`)
```text
GDAL (osgeo): 3.6.2
Rasterio: 1.4.3, GDAL compiled: 3.6.2
PyProj: 3.6.1, PROJ: 9.3.1
Shapely: 2.0.5
GeoPandas: 1.1.3
NumPy: 1.26.4
GTiff Driver available: True
Raster read/write test: PASSED
Transform EPSG:4326 -> EPSG:3857 (Bengaluru): (8637279.29, 1456305.05) - PASSED
```

## 3. GPU PyTorch & Tensor Execution (`satquery-core`)
```text
PyTorch: 2.10.0
CUDA Available: True
Device Name: NVIDIA GeForce RTX 5060
Compute Capability: (12, 0)
CUDA MatMul 1024x1024 Norm: 32741.29 - PASSED
Allocated VRAM: 20.12 MB
```

## 4. Model Checkpoint & State Inventory
- **`ChangeFormer`**: 1879.90 MB
- **`ChangeFormer_repo`**: 24.31 MB
- **`CROMA`**: 741.54 MB
- **`CROMA_repo`**: 0.11 MB
- **`GeoGround`**: 0.00 MB
- **`GeoGround_repo`**: 32.84 MB
- **`InternVL3-2B`**: 3998.07 MB
- **`upernet-convnext-tiny`**: 459.84 MB

## 5. Discrepancy & Finding Table

| Area | Observation | Impact | Required Action in Plan |
|---|---|---|---|
| Docker / WSL | Docker executable not found in PATH; WSL not installed | Containers cannot run natively until Docker Desktop/WSL is installed | Maintain fallback resilience, document setup commands for Windows host, use mock/sqlite in isolated test gates when containers offline |
| cuDNN on Windows | Dynamic symbol mismatch in cuDNN 9 (`cudnnGetVersion`) | PyTorch scripts fail if cuDNN is enabled | Keep `torch.backends.cudnn.enabled = False` in CUDA worker processes |
| NumPy Version | Pinned to `1.26.4` in `satquery-core` | NumPy 2.x breaks GDAL / Shapely C-ABI | Maintain `numpy==1.26.4` across all geospatial worker environments |
| ChangeFormer Environment | Python 3.9 in `satquery-changeformer` | Dedicated worker for legacy dependencies | Use isolated subprocess runner; verify CPU inference execution |
| GeoGround 7B VRAM | 13.16 GB checkpoint on 8 GB GPU | Cannot fit in VRAM concurrently | Keep marked as `INSTALLED BUT NOT RUNNABLE LOCALLY`; require explicit offload / remote host |
| RQ Windows Support | Windows does not support `fork()` | Standard RQ workers fail on Windows | Use `rq.worker.SpawnWorker` (available in RQ >= 2.2; currently installed 2.12.0) |
